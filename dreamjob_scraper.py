import requests
import json
import time
import re
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

# ─── Конфигурация ───────────────────────────────────────────────────────────

EMPLOYERS = {
    "ВкусВилл":        "56859",
    "Самокат":         "91312",
    "Купер":           "93692",
    "Ozon":            "26029",
    "Ozon Fresh":      "5740005",
    "Wildberries":     "6690",
    "Магнит":          "26161",
    "Яндекс Еда":      "2246796",
    "Достависта":      "297569",
    "Сбер":            "25583",
    "Т-Банк":          "25607",
    "Альфа-Банк":      "26069",
    "СДЭК":            "45131",
}

# Ключевые слова для фильтрации отзывов — берём только курьеров
COURIER_ROLES = [
    "курьер", "доставщик", "водитель", "представитель",
    "самозанятый", "партнёр", "партнер",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

MAX_PAGES = 5  # Не более 5 страниц на работодателя (~50 отзывов)


# ─── Парсинг ────────────────────────────────────────────────────────────────

def is_courier_role(role: str) -> bool:
    role_lower = role.lower()
    return any(kw in role_lower for kw in COURIER_ROLES)


def parse_rating(review_div) -> float:
    """Извлекаем числовой рейтинг из dj-rating."""
    rating_div = review_div.find("div", class_="dj-rating")
    if not rating_div:
        return 0.0
    text = rating_div.get_text(strip=True).replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def parse_review(review_div, employer_name: str) -> dict | None:
    """Парсим один блок отзыва."""
    # Должность
    title_tag = review_div.find("h2", class_="review__header-title")
    role = title_tag.get_text(strip=True) if title_tag else ""

    # Фильтруем — берём только курьерские роли
    if not is_courier_role(role):
        return None

    # Дата и город — второй тег tags__item_grey
    tags = review_div.find_all("div", class_="tags__item_grey")
    duration = tags[0].get_text(strip=True) if len(tags) > 0 else ""
    date_city = tags[1].get_text(strip=True) if len(tags) > 1 else ""

    # Рейтинг
    rating = parse_rating(review_div)

    # Плюсы и минусы
    titles = review_div.find_all("div", class_="review__title")
    plus_text = ""
    minus_text = ""

    for i, t in enumerate(titles):
        label = t.get_text(strip=True)
        # Берём текстовый узел после заголовка
        next_sib = t.next_sibling
        content = ""
        while next_sib and getattr(next_sib, "name", None) != "div":
            if hasattr(next_sib, "get_text"):
                content += next_sib.get_text(separator=" ", strip=True)
            elif isinstance(next_sib, str):
                content += next_sib.strip()
            next_sib = next_sib.next_sibling

        if "нравится" in label.lower() or "плюс" in label.lower():
            plus_text = content
        elif "улучш" in label.lower() or "минус" in label.lower():
            minus_text = content

    # ID отзыва из атрибута id="reviewXXXXXX"
    review_id = review_div.get("id", "").replace("review", "")

    return {
        "id": review_id,
        "employer": employer_name,
        "role": role,
        "duration": duration,
        "date_city": date_city,
        "rating": rating,
        "plus": plus_text,
        "minus": minus_text,
        "url": f"https://dreamjob.ru/reviews/{review_id}" if review_id else "",
    }


def scrape_employer(employer_name: str, employer_id: str) -> list:
    """Скрейпим все страницы работодателя."""
    results = []
    base_url = f"https://dreamjob.ru/employers/{employer_id}"

    for page in range(1, MAX_PAGES + 1):
        url = base_url if page == 1 else f"{base_url}?page={page}"

        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
        except Exception as e:
            print(f"  ⚠️  Ошибка запроса {employer_name} стр.{page}: {e}")
            break

        if r.status_code != 200:
            print(f"  ⚠️  HTTP {r.status_code} для {employer_name} стр.{page}")
            break

        soup = BeautifulSoup(r.text, "html.parser")
        reviews = soup.find_all("div", class_="review")

        if not reviews:
            break  # Страниц больше нет

        for rev in reviews:
            parsed = parse_review(rev, employer_name)
            if parsed:
                results.append(parsed)

        print(f"  стр.{page}: {len(reviews)} отзывов найдено, "
              f"{len([r for r in results])} курьерских всего")

        # Проверяем, есть ли следующая страница
        next_btn = soup.find("a", class_=re.compile(r"pagination.*next|next.*page"))
        if not next_btn:
            # Простая проверка — есть ли ссылка на следующую страницу
            next_link = soup.find("a", href=re.compile(rf"employers/{employer_id}\?page={page+1}"))
            if not next_link:
                break

        time.sleep(2)  # Вежливая пауза между страницами

    return results


# ─── Запуск ─────────────────────────────────────────────────────────────────

def run_collection():
    today = datetime.now().strftime("%Y-%m-%d")
    all_results = {}
    summary = []

    print(f"🚀 Сбор отзывов DreamJob | {today}\n")

    for name, emp_id in EMPLOYERS.items():
        print(f"\n📦 {name} (id={emp_id})...")
        reviews = scrape_employer(name, emp_id)
        all_results[name] = reviews
        summary.append(f"  {name}: {len(reviews)} курьерских отзывов")
        print(f"  ✅ Итого курьерских: {len(reviews)}")
        time.sleep(3)  # Пауза между работодателями

    output_file = DATA_DIR / f"dreamjob_reviews_{today}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({"collected_at": today, "employers": all_results},
                  f, ensure_ascii=False, indent=2)

    latest_file = DATA_DIR / "dreamjob_reviews_latest.json"
    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump({"collected_at": today, "employers": all_results},
                  f, ensure_ascii=False, indent=2)

    print(f"\n✅ Готово. Сохранено в {output_file}")
    print("\n📊 Итого:")
    for line in summary:
        print(line)

    return all_results


if __name__ == "__main__":
    run_collection()
