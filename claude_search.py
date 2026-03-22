import anthropic
import json
import time
import os
from datetime import datetime
from pathlib import Path

# ─── Конфигурация ───────────────────────────────────────────────────────────

# Конкуренты для поиска — все из нашего списка
COMPETITORS = [
    "Самокат",
    "Купер",
    "Wildberries",
    "Магнит",
    "Яндекс Еда",
    "Яндекс Лавка",
    "Достависта",
    "Ozon Fresh",
    "Т-Банк",
    "Альфа-Банк",
    "Сбер",
    "СДЭК",
    "Впрок",
    "Пятёрочка",
    "Перекрёсток",
    "Чижик",
]

# Для этих конкурентов добавляем дополнительный запрос про условия работы
# (их карьерные страницы нельзя скрейпить)
BLOCKED_CAREER_PAGES = [
    "Яндекс Еда", "Яндекс Лавка", "Wildberries", "Ozon Fresh"
]

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

MODEL = "claude-sonnet-4-6"


# ─── Системный промпт ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Ты аналитик рынка труда курьеров в Москве. 
Твоя задача — найти актуальные сигналы о том, как компании работают с курьерами: 
условия работы, удержание, изменения в оффере, новые программы, жалобы курьеров.

При анализе результатов поиска:
- Фокусируйся только на информации за последние 3-6 месяцев
- Отличай факты от слухов
- Указывай источник каждого сигнала
- Будь краток — одно предложение на сигнал

Классифицируй сигналы по типам:
- экономический: ставки, бонусы, выплаты, компенсации
- операционный: слоты, штрафы, приложение, поддержка, retention-программы  
- стратегический: как компания думает об удержании курьеров, новые роли, заявления руководства
- позиционирование: как компания себя подаёт курьерам в рекламе и рекрутинге

Отвечай ТОЛЬКО валидным JSON без markdown-обёртки и пояснений."""


# ─── Основной запрос ────────────────────────────────────────────────────────

def build_prompt(competitor: str) -> str:
    year = datetime.now().year
    extra = ""
    if competitor in BLOCKED_CAREER_PAGES:
        extra = f"""
4. Условия работы курьером в {competitor} прямо сейчас:
   Запрос: "{competitor} стать курьером условия ставка бонусы {year}"
"""

    return f"""Найди актуальные сигналы о работе с курьерами в компании "{competitor}".

Выполни следующие поисковые запросы:

1. Свежие отзывы курьеров о работе в {competitor}:
   Запрос: "{competitor} отзывы курьеров {year}"

2. Новости и PR про курьеров {competitor}:
   Запрос: "{competitor} курьеры условия работы новости {year}"

3. Стратегия удержания курьеров в {competitor}:
   Запрос: "{competitor} удержание курьеров программа лояльность {year}"{extra}

4. Продуктовый слой — приложение и инструменты для курьеров {competitor}:
   Запрос: "{competitor} приложение курьер обновление отзывы {year}"
   Ищи: обновления курьерского приложения, отзывы в магазинах приложений (RuStore, Google Play),
   вакансии продактов/UX в курьерское направление, новые фичи или баги приложения.

После всех поисков верни JSON строго в этом формате:
{{
  "employer": "{competitor}",
  "week": "{datetime.now().strftime('%Y-%m-%d')}",
  "signals": [
    {{
      "type": "экономический|операционный|стратегический|позиционирование|продуктовый",
      "summary": "краткое описание сигнала",
      "source": "url источника или 'нет источника'",
      "importance": "высокая|средняя|низкая"
    }}
  ],
  "retention_score_change": "улучшилось|ухудшилось|без изменений|нет данных",
  "retention_score_reasoning": "одно предложение — почему такой вывод"
}}

Типы сигналов:
- экономический: ставки, бонусы, выплаты, компенсации
- операционный: слоты, штрафы, поддержка, retention-программы
- стратегический: как компания думает об удержании, новые роли, заявления руководства
- позиционирование: как компания себя подаёт курьерам в рекрутинге
- продуктовый: приложение для курьеров, UX, технические изменения, вакансии продактов

ВАЖНО про retention_score_change: это оценка ДИНАМИКИ за последние 2-4 недели, не общего состояния.
- "ухудшилось" — только если есть явные свежие сигналы об ухудшении
- "улучшилось" — только если есть явные свежие сигналы об улучшении
- "без изменений" — стабильная ситуация, жалобы хронические, ничего нового
- "нет данных" — нет свежих источников за последние 1-2 месяца

Если не можешь уверенно определить динамику — ставь "нет данных", не "ухудшилось".
Если по конкуренту ничего свежего не найдено — верни пустой список signals и retention_score_change = "нет данных"."""


def search_competitor(competitor: str, client: anthropic.Anthropic) -> dict:
    """Один вызов Claude API = один конкурент: поиск + синтез."""
    for attempt in range(1, 4):  # До 3 попыток при rate limit
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                tools=[{
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 5,
                }],
                messages=[{
                    "role": "user",
                    "content": build_prompt(competitor)
                }]
            )

            # Извлекаем текстовый ответ
            text = ""
            for block in response.content:
                if block.type == "text":
                    text += block.text

            # Парсим JSON
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

            result = json.loads(text)
            print(f"  ✅ Найдено сигналов: {len(result.get('signals', []))} | "
                  f"retention: {result.get('retention_score_change', '?')}")
            return result

        except json.JSONDecodeError as e:
            print(f"  ⚠️  Ошибка парсинга JSON для {competitor}: {e}")
            return {
                "employer": competitor,
                "week": datetime.now().strftime("%Y-%m-%d"),
                "signals": [],
                "retention_score_change": "ошибка",
                "retention_score_reasoning": f"Ошибка парсинга: {e}",
                "raw_response": text[:500]
            }
        except anthropic.RateLimitError:
            wait = 30 * attempt  # 30, 60, 90 секунд
            print(f"  ⚠️  Rate limit, жду {wait}с (попытка {attempt}/3)...")
            time.sleep(wait)
        except Exception as e:
            print(f"  ❌ Ошибка для {competitor}: {e}")
            return {
                "employer": competitor,
                "week": datetime.now().strftime("%Y-%m-%d"),
                "signals": [],
                "retention_score_change": "ошибка",
                "retention_score_reasoning": str(e)
            }

    return {
        "employer": competitor,
        "week": datetime.now().strftime("%Y-%m-%d"),
        "signals": [],
        "retention_score_change": "ошибка",
        "retention_score_reasoning": "Превышен rate limit после 3 попыток"
    }


# ─── Запуск ─────────────────────────────────────────────────────────────────

def run_collection(competitors: list = None):
    """Запускаем поиск по всем конкурентам."""
    if competitors is None:
        competitors = COMPETITORS

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Не найден ANTHROPIC_API_KEY в переменных окружения")

    client = anthropic.Anthropic(api_key=api_key)
    today = datetime.now().strftime("%Y-%m-%d")
    all_results = {}

    output_file = DATA_DIR / f"claude_signals_{today}.json"
    latest_file = DATA_DIR / "claude_signals_latest.json"

    # Загружаем существующие данные за сегодня — для дозаписи
    for f in [output_file, latest_file]:
        if f.exists():
            with open(f, encoding="utf-8") as fp:
                existing = json.load(fp)
                if existing.get("collected_at") == today:
                    all_results = existing.get("competitors", {})
                    print(f"📂 Найдены данные за сегодня: "
                          f"{len(all_results)} конкурентов, дозаписываем\n")
                    break

    print(f"🚀 Claude web_search | {today}\n")

    for competitor in competitors:
        # Пропускаем если уже собрано сегодня
        if competitor in all_results and all_results[competitor].get("signals"):
            print(f"⏭️  {competitor} — уже собран, пропускаем")
            continue

        print(f"🔍 {competitor}...")
        result = search_competitor(competitor, client)
        all_results[competitor] = result

        # Сохраняем после каждого — не теряем данные при падении
        payload = {"collected_at": today, "competitors": all_results}
        for f in [output_file, latest_file]:
            with open(f, "w", encoding="utf-8") as fp:
                json.dump(payload, fp, ensure_ascii=False, indent=2)

        time.sleep(10)

    print(f"\n✅ Готово. Сохранено в {output_file}")

    print("\n📊 Сводка retention_score_change:")
    for name, data in all_results.items():
        score = data.get("retention_score_change", "?")
        n_signals = len(data.get("signals", []))
        emoji = {"улучшилось": "📈", "ухудшилось": "📉",
                 "без изменений": "➡️", "нет данных": "❓"}.get(score, "❓")
        print(f"  {emoji} {name}: {score} ({n_signals} сигналов)")

    return all_results


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        run_collection([sys.argv[1]])
    else:
        run_collection()
