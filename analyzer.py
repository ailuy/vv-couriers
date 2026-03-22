import anthropic
import json
import os
from datetime import datetime
from pathlib import Path

DATA_DIR = Path("data")
MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """Ты старший аналитик рынка труда курьеров в Москве.
Твоя задача — синтезировать данные из нескольких источников в еженедельный дайджест.

Ты хорошо понимаешь контекст: ВкусВилл конкурирует за самозанятых курьеров с Самокатом, 
Яндекс Едой, Купером и другими. Курьеры работают на нескольких платформах одновременно 
и каждый день выбирают где брать заказы. Удержание — это не HR-задача, а продуктовая.

Будь конкретным и прямым. Избегай общих фраз. Если данных недостаточно — скажи об этом.
Отвечай на русском языке."""


def load_latest_data() -> dict:
    """Загружаем все последние данные."""
    data = {}

    # Claude signals
    signals_file = DATA_DIR / "claude_signals_latest.json"
    if signals_file.exists():
        with open(signals_file, encoding="utf-8") as f:
            data["signals"] = json.load(f)

    # HH вакансии
    hh_file = DATA_DIR / "hh_vacancies_latest.json"
    if hh_file.exists():
        with open(hh_file, encoding="utf-8") as f:
            data["hh"] = json.load(f)

    # Карьерные страницы
    career_file = DATA_DIR / "career_pages_latest.json"
    if career_file.exists():
        with open(career_file, encoding="utf-8") as f:
            data["career"] = json.load(f)

    return data


def prepare_context(data: dict) -> str:
    """Готовим контекст для Claude — сжато и структурированно."""
    parts = []
    today = datetime.now().strftime("%Y-%m-%d")

    # 1. Сигналы по конкурентам
    if "signals" in data:
        parts.append("## СИГНАЛЫ ПО КОНКУРЕНТАМ (Claude web_search)\n")
        for competitor, info in data["signals"]["competitors"].items():
            high_signals = [s for s in info.get("signals", [])
                           if s.get("importance") == "высокая"]
            all_signals = info.get("signals", [])
            retention = info.get("retention_score_change", "нет данных")
            reasoning = info.get("retention_score_reasoning", "")

            parts.append(f"### {competitor}")
            parts.append(f"Retention: {retention} — {reasoning}")

            if high_signals:
                parts.append("Высокоприоритетные сигналы:")
                for s in high_signals:
                    parts.append(f"- [{s['type']}] {s['summary']}")
            elif all_signals:
                parts.append(f"Сигналов высокой важности нет. "
                            f"Всего сигналов: {len(all_signals)}")
            else:
                parts.append("Данных нет.")
            parts.append("")

    # 2. Стратегические вакансии с HH
    if "hh" in data:
        strategic = []
        for employer, vacancies in data["hh"]["employers"].items():
            for v in vacancies:
                if v.get("signal_type") == "стратегический":
                    strategic.append(
                        f"- {employer}: «{v['title']}» ({v['published']})"
                    )
        if strategic:
            parts.append("## СТРАТЕГИЧЕСКИЕ ВАКАНСИИ (HH.ru)\n")
            parts.extend(strategic)
            parts.append("")

    # 3. Изменения карьерных страниц
    if "career" in data:
        changed = []
        for employer, page in data["career"]["pages"].items():
            if page.get("status") == "ok" and page.get("previous_text"):
                changed.append(f"- {employer}: есть предыдущий снимок для сравнения")
                # Даём Claude первые 500 символов текущей и предыдущей версии
                changed.append(f"  Текущий текст (начало): "
                              f"{page['text'][:300].replace(chr(10), ' ')}")
                changed.append(f"  Предыдущий текст (начало): "
                              f"{page['previous_text'][:300].replace(chr(10), ' ')}")
        if changed:
            parts.append("## КАРЬЕРНЫЕ СТРАНИЦЫ\n")
            parts.extend(changed)
            parts.append("")

    return "\n".join(parts)


def generate_digest(context: str, client: anthropic.Anthropic) -> str:
    """Генерируем дайджест через Claude."""
    today = datetime.now().strftime("%Y-%m-%d")

    prompt = f"""На основе данных ниже составь еженедельный дайджест по рынку труда курьеров в Москве.

ДАННЫЕ:
{context}

---

Структура дайджеста (строго в этом порядке, в формате Markdown):

# Дайджест: рынок труда курьеров | {today}

## Главное за неделю
Три самых важных сигнала — конкретно, одним предложением каждый.

## Retention радар
Таблица в формате Markdown:
| Конкурент | Статус | Причина (одна фраза) |
Включи всех конкурентов из данных. ВкусВилл — добавь отдельной строкой как точку отсчёта 
(на основе своих знаний о позиции ВВ на рынке).

## По конкурентам
Только те у кого есть сигналы высокой важности. Для каждого:
**[Название]** — [retention статус]
- Перечень высокоприоритетных сигналов

## Аналитика
**Что рынок делает с удержанием:** (2-3 предложения — общий тренд)

**Где ВВ выигрывает прямо сейчас:** (конкретно)

**Где ВВ проигрывает прямо сейчас:** (конкретно)

**Что стоит проверить или сделать:** (одна конкретная рекомендация)"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=6000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text


def generate_json_summary(data: dict, digest_text: str,
                           client: anthropic.Anthropic) -> dict:
    """Генерируем машиночитаемый JSON для дашборда."""
    today = datetime.now().strftime("%Y-%m-%d")

    # Собираем retention данные напрямую из signals
    retention_map = {}
    if "signals" in data:
        for competitor, info in data["signals"]["competitors"].items():
            retention_map[competitor] = {
                "status": info.get("retention_score_change", "нет данных"),
                "reasoning": info.get("retention_score_reasoning", ""),
                "high_signals_count": len([
                    s for s in info.get("signals", [])
                    if s.get("importance") == "высокая"
                ]),
                "total_signals": len(info.get("signals", []))
            }

    # Считаем сигналы по типам
    signal_types = {"экономический": 0, "операционный": 0,
                    "стратегический": 0, "позиционирование": 0}
    if "signals" in data:
        for competitor, info in data["signals"]["competitors"].items():
            for s in info.get("signals", []):
                t = s.get("type", "")
                if t in signal_types:
                    signal_types[t] += 1

    # Стратегические вакансии HH
    strategic_vacancies = []
    if "hh" in data:
        for employer, vacancies in data["hh"]["employers"].items():
            for v in vacancies:
                if v.get("signal_type") == "стратегический":
                    strategic_vacancies.append({
                        "employer": employer,
                        "title": v["title"],
                        "published": v["published"],
                        "url": v["url"]
                    })

    return {
        "generated_at": today,
        "retention_map": retention_map,
        "signal_type_counts": signal_types,
        "strategic_vacancies": strategic_vacancies,
        "competitors_covered": len(retention_map),
        "digest_text": digest_text
    }


def run_analysis():
    """Запускаем полный анализ."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Не найден ANTHROPIC_API_KEY")

    client = anthropic.Anthropic(api_key=api_key)
    today = datetime.now().strftime("%Y-%m-%d")

    print(f"🧠 Генерация дайджеста | {today}\n")

    # Загружаем данные
    print("📂 Загружаем данные...")
    data = load_latest_data()
    print(f"  Сигналы: {'✅' if 'signals' in data else '❌'}")
    print(f"  HH вакансии: {'✅' if 'hh' in data else '❌'}")
    print(f"  Карьерные страницы: {'✅' if 'career' in data else '❌'}")

    # Готовим контекст
    print("\n📋 Подготовка контекста...")
    context = prepare_context(data)
    print(f"  Размер контекста: {len(context)} символов")

    # Генерируем Markdown-дайджест
    print("\n✍️  Генерация Markdown-дайджеста...")
    digest_text = generate_digest(context, client)

    # Генерируем JSON для дашборда
    print("📊 Генерация JSON для дашборда...")
    summary_json = generate_json_summary(data, digest_text, client)

    # Сохраняем
    md_file = DATA_DIR / f"digest_{today}.md"
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(digest_text)

    json_file = DATA_DIR / f"digest_{today}.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(summary_json, f, ensure_ascii=False, indent=2)

    latest_json = DATA_DIR / "digest_latest.json"
    with open(latest_json, "w", encoding="utf-8") as f:
        json.dump(summary_json, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Готово!")
    print(f"  Markdown: {md_file}")
    print(f"  JSON: {json_file}")
    print(f"\n--- ДАЙДЖЕСТ ---\n")
    print(digest_text)

    return summary_json, digest_text


if __name__ == "__main__":
    run_analysis()
