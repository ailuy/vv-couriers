import requests
import json
import time
from datetime import datetime
from pathlib import Path

EMPLOYERS = {
    "Самокат":         "2460946",
    "Купер":           "1272486",
    "Wildberries":     "87021",
    "Магнит":          "49357",
    "Яндекс Еда":      "9694561",
    "Яндекс Доставка": "10177029",
    "Достависта":      "1316038",
    "Ozon":            "2180",
    "Т-Банк":          "78638",
    "Альфа-Банк":      "80",
    "Сбер":            "3529",
    "СДЭК":            "3530",
    "Впрок":           "4759512",
    # X5 Group
    "Перекрёсток":     "1942336",
    "Пятёрочка":       "1942330",
    "Чижик":           "5879729",
}

COURIER_KEYWORDS = [
    "курьер", "доставк", "водитель-курьер",
    "курьерск", "last mile", "последняя миля",
    "представитель",
]

STRATEGIC_KEYWORDS = [
    "удержани", "retention",
    "продукт", "product manager", "ux", "приложени",
]

HEADERS = {"User-Agent": "courier-monitor/1.0"}
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)


def is_relevant(vacancy: dict) -> bool:
    title = vacancy.get("name", "").lower()
    return any(kw in title for kw in COURIER_KEYWORDS) or \
           any(kw in title for kw in STRATEGIC_KEYWORDS)


def get_signal_type(title: str) -> str:
    title_lower = title.lower()
    if any(kw in title_lower for kw in STRATEGIC_KEYWORDS):
        return "стратегический"
    return "операционный"


def get_vacancy_details(vacancy_id: str) -> dict:
    url = f"https://api.hh.ru/vacancies/{vacancy_id}"
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 200:
        return r.json()
    return {}


def extract_salary(vacancy: dict) -> dict:
    salary = vacancy.get("salary") or {}
    return {
        "from": salary.get("from"),
        "to": salary.get("to"),
        "currency": salary.get("currency", "RUR"),
        "gross": salary.get("gross", False),
    }


def extract_employment(vacancy: dict) -> str:
    emp = vacancy.get("employment") or {}
    return emp.get("name", "")


def collect_employer_vacancies(employer_name: str, employer_id: str) -> list:
    results = []
    page = 0

    while True:
        params = {
            "employer_id": employer_id,
            "area": 1,
            "per_page": 50,
            "page": page,
            "order_by": "publication_time",
        }
        r = requests.get("https://api.hh.ru/vacancies", params=params, headers=HEADERS)

        if r.status_code != 200:
            print(f"  ⚠️  Ошибка {r.status_code} для {employer_name}")
            break

        data = r.json()
        items = data.get("items", [])

        if not items:
            break

        for v in items:
            if is_relevant(v):
                details = get_vacancy_details(v["id"])
                time.sleep(0.3)

                results.append({
                    "id": v["id"],
                    "title": v["name"],
                    "signal_type": get_signal_type(v["name"]),
                    "employer": employer_name,
                    "employer_id": employer_id,
                    "published": v["published_at"][:10],
                    "url": v["alternate_url"],
                    "salary": extract_salary(v),
                    "employment_type": extract_employment(v),
                    "schedule": (v.get("schedule") or {}).get("name", ""),
                    "experience": (v.get("experience") or {}).get("name", ""),
                    "snippet_requirement": (v.get("snippet") or {}).get("requirement", ""),
                    "snippet_responsibility": (v.get("snippet") or {}).get("responsibility", ""),
                    "key_skills": [s["name"] for s in details.get("key_skills", [])],
                    "description_preview": details.get("description", "")[:1000] if details else "",
                })

        if page >= data.get("pages", 1) - 1:
            break
        page += 1
        time.sleep(0.5)

    return results


def run_collection():
    today = datetime.now().strftime("%Y-%m-%d")
    all_results = {}
    summary = []

    print(f"🚀 Запуск сбора вакансий | {today}\n")

    for name, emp_id in EMPLOYERS.items():
        print(f"📦 {name} (id={emp_id})...")
        vacancies = collect_employer_vacancies(name, emp_id)
        all_results[name] = vacancies
        strategic = [v for v in vacancies if v["signal_type"] == "стратегический"]
        summary.append(f"  {name}: {len(vacancies)} вакансий" +
                      (f" (⚡ {len(strategic)} стратегических)" if strategic else ""))
        print(f"  ✅ Найдено: {len(vacancies)}" +
              (f" | ⚡ стратегических: {len(strategic)}" if strategic else ""))
        time.sleep(1)

    output_file = DATA_DIR / f"hh_vacancies_{today}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({"collected_at": today, "employers": all_results},
                  f, ensure_ascii=False, indent=2)

    latest_file = DATA_DIR / "hh_vacancies_latest.json"
    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump({"collected_at": today, "employers": all_results},
                  f, ensure_ascii=False, indent=2)

    print(f"\n✅ Готово. Сохранено в {output_file}")
    print("\n📊 Итого:")
    for line in summary:
        print(line)
    print(f"\n  Всего вакансий: {sum(len(v) for v in all_results.values())}")

    return all_results


if __name__ == "__main__":
    run_collection()
