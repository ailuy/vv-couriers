import requests
import json

# Конкуренты для поиска
competitors = [
    "Самокат",
    "Яндекс Еда",
    "Купер",
    "Ozon Fresh",
    "Wildberries",
    "Магнит доставка",
    "Впрок",
    "Достависта",
    "Яндекс Доставка",
    "Т-Банк",
    "Сбербанк",
    "Альфа-Банк",
    "СДЭК",
    "Boxberry"
]

headers = {"User-Agent": "courier-monitor/1.0"}

results = {}

for name in competitors:
    params = {"text": name, "per_page": 5}
    r = requests.get("https://api.hh.ru/employers", params=params, headers=headers)
    data = r.json()
    
    print(f"\n=== {name} ===")
    candidates = []
    for emp in data.get("items", []):
        print(f"  id={emp['id']} | {emp['name']} | {emp.get('alternate_url', '')}")
        candidates.append({
            "id": emp["id"],
            "name": emp["name"],
            "url": emp.get("alternate_url", "")
        })
    results[name] = candidates

# Сохраняем для следующего шага
with open("employer_candidates.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\n\nРезультаты сохранены в employer_candidates.json")
print("Проверь список и принеси сюда — выберем правильные id для каждого конкурента")