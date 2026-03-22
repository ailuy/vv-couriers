import requests
import json
import time
import re
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

# Только те страницы, которые реально отдают контент без блокировок.
# Яндекс Лавка, Яндекс Еда, Wildberries, Ozon Fresh — покрываем через Claude web_search.

CAREER_PAGES = {
    "ВкусВилл":  "https://vkusvill.ru/job/courier/samozanyatye/",
    "Достависта": "https://dostavista.ru/couriers",
    "Самокат":   "https://samokat-clever.ru/",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Connection": "keep-alive",
}

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

SNAPSHOTS_DIR = DATA_DIR / "career_snapshots"
SNAPSHOTS_DIR.mkdir(exist_ok=True)


def safe_filename(name: str) -> str:
    return re.sub(r'[^\w\-]', '_', name)


def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "head",
                     "iframe", "noscript"]):
        tag.decompose()
    # Явно указываем кодировку
    text = soup.get_text(separator="\n", strip=True)
    lines = [l for l in text.splitlines() if l.strip()]
    return "\n".join(lines)


def load_previous_snapshot(employer_name: str) -> dict | None:
    path = SNAPSHOTS_DIR / f"{safe_filename(employer_name)}.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def save_snapshot(employer_name: str, data: dict):
    path = SNAPSHOTS_DIR / f"{safe_filename(employer_name)}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def scrape_page(employer_name: str, url: str) -> dict:
    result = {
        "employer": employer_name,
        "url": url,
        "scraped_at": datetime.now().strftime("%Y-%m-%d"),
        "status": "ok",
        "text": "",
        "previous_text": "",
    }

    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.encoding = r.apparent_encoding  # автодетект кодировки
        result["http_status"] = r.status_code

        if r.status_code == 403:
            result["status"] = "blocked_403"
            return result

        if r.status_code != 200:
            result["status"] = f"http_error_{r.status_code}"
            return result

        result["text"] = extract_text(r.text)

        previous = load_previous_snapshot(employer_name)
        if previous:
            result["previous_text"] = previous.get("text", "")
            result["previous_scraped_at"] = previous.get("scraped_at", "")

        save_snapshot(employer_name, result)

    except requests.exceptions.Timeout:
        result["status"] = "timeout"
        print(f"  ⚠️  Таймаут: {employer_name}")
    except requests.exceptions.ConnectionError as e:
        result["status"] = "connection_error"
        print(f"  ⚠️  Ошибка соединения {employer_name}: {e}")
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        print(f"  ⚠️  Ошибка {employer_name}: {e}")

    return result


def run_collection():
    today = datetime.now().strftime("%Y-%m-%d")
    all_results = {}
    errors = []

    print(f"🚀 Сбор карьерных страниц | {today}\n")

    for name, url in CAREER_PAGES.items():
        print(f"📄 {name}...")
        result = scrape_page(name, url)
        all_results[name] = result

        if result["status"] == "ok":
            has_prev = bool(result.get("previous_text"))
            print(f"  ✅ Готово — "
                  f"{'есть предыдущий снимок' if has_prev else 'первый снимок'}")
        else:
            errors.append(f"{name}: {result['status']}")
            print(f"  ❌ Ошибка: {result['status']}")

        time.sleep(3)

    output_file = DATA_DIR / f"career_pages_{today}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({"collected_at": today, "pages": all_results},
                  f, ensure_ascii=False, indent=2)

    latest_file = DATA_DIR / "career_pages_latest.json"
    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump({"collected_at": today, "pages": all_results},
                  f, ensure_ascii=False, indent=2)

    print(f"\n✅ Готово. Сохранено в {output_file}")
    if errors:
        print(f"\n❌ Ошибки: {', '.join(errors)}")

    return all_results


if __name__ == "__main__":
    run_collection()
