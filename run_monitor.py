import subprocess
import sys
import os
import json
import time
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

LOG_FILE = DATA_DIR / "run_log.json"


def log(message: str, level: str = "info"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    emoji = {"info": "ℹ️", "ok": "✅", "error": "❌", "warn": "⚠️"}.get(level, "")
    print(f"[{timestamp}] {emoji}  {message}")


def run_script(script_name: str) -> dict:
    """Запускаем один скрипт и возвращаем результат."""
    start = time.time()
    log(f"Запуск {script_name}...")

    try:
        result = subprocess.run(
            [sys.executable, script_name],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=1800,  # 30 минут максимум на скрипт
        )
        elapsed = round(time.time() - start, 1)

        if result.returncode == 0:
            log(f"{script_name} завершён за {elapsed}с", "ok")
            return {"script": script_name, "status": "ok",
                    "elapsed": elapsed, "output": result.stdout[-500:]}
        else:
            log(f"{script_name} завершился с ошибкой", "error")
            print(result.stderr[-500:])
            return {"script": script_name, "status": "error",
                    "elapsed": elapsed, "error": result.stderr[-500:]}

    except subprocess.TimeoutExpired:
        log(f"{script_name} превысил лимит времени (30 мин)", "error")
        return {"script": script_name, "status": "timeout", "elapsed": 1800}
    except Exception as e:
        log(f"{script_name} упал с исключением: {e}", "error")
        return {"script": script_name, "status": "exception", "error": str(e)}


def check_api_key():
    """Проверяем наличие API ключа."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log("ANTHROPIC_API_KEY не найден в переменных окружения", "error")
        log("Установи ключ командой:", "warn")
        log('  $env:ANTHROPIC_API_KEY="sk-ant-..."', "warn")
        return False
    return True


def save_run_log(results: list, total_elapsed: float):
    """Сохраняем лог запуска."""
    run_record = {
        "run_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_elapsed": total_elapsed,
        "results": results,
        "status": "ok" if all(r["status"] == "ok" for r in results) else "partial"
    }

    # Загружаем историю запусков
    history = []
    if LOG_FILE.exists():
        with open(LOG_FILE, encoding="utf-8") as f:
            history = json.load(f)

    history.append(run_record)
    # Храним последние 12 запусков (3 месяца)
    history = history[-12:]

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def run_all():
    """Главная функция — запускаем все скрипты в правильном порядке."""
    start_time = time.time()
    today = datetime.now().strftime("%Y-%m-%d")
    results = []

    print(f"\n{'='*60}")
    print(f"  🚀 COURIER MONITOR | {today}")
    print(f"{'='*60}\n")

    # Проверка API ключа
    if not check_api_key():
        sys.exit(1)

    # ── Шаг 1: HH + карьерные страницы параллельно ──────────────────
    log("ШАГ 1: Сбор данных (HH + карьерные страницы параллельно)")

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(run_script, "hh_collector.py"): "hh",
            executor.submit(run_script, "career_scraper.py"): "career",
        }
        for future in as_completed(futures):
            results.append(future.result())

    # ── Шаг 2: Claude web_search ─────────────────────────────────────
    log("\nШАГ 2: Claude web_search (займёт ~20 минут)")
    result = run_script("claude_search.py")
    results.append(result)

    if result["status"] != "ok":
        log("claude_search.py завершился с ошибкой — дайджест может быть неполным",
            "warn")

    # ── Шаг 3: Анализ и дайджест ─────────────────────────────────────
    log("\nШАГ 3: Генерация дайджеста")
    result = run_script("analyzer.py")
    results.append(result)

    # ── Итог ─────────────────────────────────────────────────────────
    total_elapsed = round(time.time() - start_time, 1)
    save_run_log(results, total_elapsed)

    print(f"\n{'='*60}")
    ok_count = sum(1 for r in results if r["status"] == "ok")
    print(f"  Завершено: {ok_count}/{len(results)} скриптов успешно")
    print(f"  Общее время: {total_elapsed // 60:.0f} мин {total_elapsed % 60:.0f} сек")

    # Показываем где лежит дайджест
    digest_file = DATA_DIR / f"digest_{today}.md"
    if digest_file.exists():
        print(f"\n  📄 Дайджест: {digest_file.absolute()}")

    print(f"{'='*60}\n")

    return results


if __name__ == "__main__":
    run_all()
