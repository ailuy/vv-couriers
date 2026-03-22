import streamlit as st
import json
import os
from pathlib import Path
from datetime import datetime

# ─── Конфигурация ───────────────────────────────────────────────────────────

DATA_DIR = Path("data")

COLORS = {
    "улучшилось":     "#2DB551",
    "ухудшилось":     "#E8504A",
    "без изменений":  "#29B6F6",
    "нет данных":     "#B0BEC5",
    "ошибка":         "#FF9800",
}

SIGNAL_TYPE_LABELS = {
    "экономический":   "💰 Экономический",
    "операционный":    "⚙️ Операционный",
    "стратегический":  "🎯 Стратегический",
    "позиционирование":"📢 Позиционирование",
    "продуктовый":     "📱 Продуктовый",
}

RETENTION_EMOJI = {
    "улучшилось":    "📈",
    "ухудшилось":    "📉",
    "без изменений": "➡️",
    "нет данных":    "❓",
    "ошибка":        "⚠️",
}

# ─── Стили ──────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Courier Monitor | ВкусВилл",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Onest:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'Onest', sans-serif; }

.section-header {
    font-size: 18px; font-weight: 700; color: #e8e8e8;
    margin: 24px 0 12px 0; padding-bottom: 6px;
    border-bottom: 2px solid #2DB551;
}
.retention-cell {
    display: inline-block; padding: 4px 12px; border-radius: 20px;
    font-size: 13px; font-weight: 600; color: white;
}
.run-status {
    font-family: 'JetBrains Mono', monospace; font-size: 12px;
    background: #0d1117; color: #2DB551;
    padding: 12px 16px; border-radius: 8px; white-space: pre-wrap;
}
.vv-header {
    background: linear-gradient(135deg, #2DB551 0%, #1a8c35 100%);
    color: white; padding: 20px 28px; border-radius: 14px; margin-bottom: 24px;
}
</style>
""", unsafe_allow_html=True)


# ─── Утилиты ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_signals() -> dict:
    f = DATA_DIR / "claude_signals_latest.json"
    if f.exists():
        with open(f, encoding="utf-8") as fp:
            return json.load(fp)
    return {}


@st.cache_data(ttl=60)
def load_digest() -> dict:
    f = DATA_DIR / "digest_latest.json"
    if f.exists():
        with open(f, encoding="utf-8") as fp:
            return json.load(fp)
    return {}


@st.cache_data(ttl=60)
def load_hh() -> dict:
    f = DATA_DIR / "hh_vacancies_latest.json"
    if f.exists():
        with open(f, encoding="utf-8") as fp:
            return json.load(fp)
    return {}


@st.cache_data(ttl=60)
def load_run_log() -> list:
    f = DATA_DIR / "run_log.json"
    if f.exists():
        with open(f, encoding="utf-8") as fp:
            return json.load(fp)
    return []


def retention_badge(status: str) -> str:
    color = COLORS.get(status, "#B0BEC5")
    emoji = RETENTION_EMOJI.get(status, "❓")
    return (f'<span class="retention-cell" style="background:{color}">'
            f'{emoji} {status}</span>')


# Приоритет типов сигналов для топа
SIGNAL_TYPE_PRIORITY = {
    "стратегический":  0,
    "продуктовый":     1,
    "операционный":    2,
    "экономический":   3,
    "позиционирование":4,
}

# Приоритет retention статуса
RETENTION_PRIORITY = {
    "ухудшилось":    0,
    "улучшилось":    1,
    "без изменений": 2,
    "нет данных":    3,
    "ошибка":        4,
}

def get_all_high_signals(signals_data: dict) -> list:
    """Возвращает высокоприоритетные сигналы, отсортированные по варианту В:
    1. Сначала сигналы конкурентов с динамикой (ухудшилось/улучшилось)
    2. Внутри — по приоритету типа (стратегический > продуктовый > ...)
    """
    competitors = signals_data.get("competitors", {})
    result = []
    for employer, data in competitors.items():
        retention = data.get("retention_score_change", "нет данных")
        retention_rank = RETENTION_PRIORITY.get(retention, 3)
        for s in data.get("signals", []):
            if s.get("importance") == "высокая":
                type_rank = SIGNAL_TYPE_PRIORITY.get(s.get("type", ""), 5)
                result.append({
                    **s,
                    "employer": employer,
                    "_retention_rank": retention_rank,
                    "_type_rank": type_rank,
                })
    # Сортируем: сначала по retention конкурента, потом по типу сигнала
    return sorted(result, key=lambda x: (x["_retention_rank"], x["_type_rank"]))


# ─── Боковая панель ─────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 🚚 Courier Monitor")
    st.markdown("**ВкусВилл** · Удержание курьеров")
    st.divider()

    page = st.radio(
        "Раздел",
        ["📊 Главная", "🏢 По конкурентам", "📄 Дайджест"],
        label_visibility="collapsed"
    )

    st.divider()

    st.markdown("""
    <div style="font-size:12px;color:#aaa;line-height:1.6">
    Еженедельный мониторинг рынка труда курьеров в Москве. Отслеживает условия работы,
    удержание и стратегии конкурентов — от ставок и бонусов до продуктовых решений.
    Обновляется автоматически каждое воскресенье.
    </div>
    <div style="font-size:11px;color:#666;line-height:1.5;margin-top:10px">
    <b style="color:#888">Почему эти компании:</b><br>
    Прямые конкуренты за курьеров — дарксторы и экспресс-доставка (Самокат, Яндекс Лавка,
    Купер, Магнит, Ozon Fresh, Пятёрочка, Перекрёсток, Чижик, Впрок, Достависта).
    Косвенные конкуренты — банки и финтех (Сбер, Т-Банк, Альфа), которые переманивают
    самозанятых с авто в роль «полевого представителя». Wildberries и СДЭК —
    крупнейшие работодатели курьеров в Москве с пересекающейся аудиторией.
    </div>
    """, unsafe_allow_html=True)


# ─── Запуск скриптов — только локально ──────────────────────────────────────
# Кнопки управления убраны из облачной версии.
# Сбор данных запускается автоматически через GitHub Actions каждое воскресенье.


# ════════════════════════════════════════════════════════════════════════════
# СТРАНИЦА 1 — ГЛАВНАЯ
# ════════════════════════════════════════════════════════════════════════════

if page == "📊 Главная":
    signals_data = load_signals()
    digest_data = load_digest()

    # Шапка
    collected_at = signals_data.get("collected_at", "—")
    n_competitors = len(signals_data.get("competitors", {}))

    st.markdown(f"""
    <div class="vv-header">
        <div style="font-size:24px;font-weight:700;margin-bottom:4px">
            Рынок труда курьеров · Москва
        </div>
        <div style="opacity:0.85;font-size:14px">
            Данные за {collected_at} · {n_competitors} конкурентов
        </div>
    </div>
    """, unsafe_allow_html=True)

    if not signals_data:
        st.info("Данных пока нет. Запусти сбор через кнопку в боковой панели.")
        st.stop()

    # ── Радар удержания ──────────────────────────────────────────────────
    st.markdown('<div class="section-header">Радар удержания</div>',
                unsafe_allow_html=True)

    competitors = signals_data.get("competitors", {})

    # Легенда
    st.markdown("""
    <div style="display:flex;gap:20px;margin-bottom:12px;font-size:12px;flex-wrap:wrap">
        <span style="color:#2DB551">📈 улучшилось</span>
        <span style="color:#E8504A">📉 ухудшилось</span>
        <span style="color:#29B6F6">➡️ без изменений</span>
        <span style="color:#B0BEC5">❓ нет данных</span>
        <span style="color:#666;margin-left:10px">· цифра справа — кол-во сигналов</span>
    </div>
    """, unsafe_allow_html=True)

    # Компактная таблица — две колонки, строки по алфавиту
    sorted_competitors = sorted(competitors.items(), key=lambda x: x[0])
    mid = (len(sorted_competitors) + 1) // 2
    col1, col2 = st.columns(2)

    def radar_row(employer, data):
        status = data.get("retention_score_change", "нет данных")
        color = COLORS.get(status, "#B0BEC5")
        emoji = RETENTION_EMOJI.get(status, "❓")
        n = len(data.get("signals", []))
        return f"""<div style="display:flex;align-items:center;gap:10px;
                    padding:6px 10px;border-radius:6px;margin-bottom:4px;
                    background:#1e2130;border-left:3px solid {color}">
            <span style="font-size:14px">{emoji}</span>
            <span style="font-size:13px;color:#e0e0e0;flex:1">{employer}</span>
            <span style="font-size:11px;color:#666">{n}</span>
        </div>"""

    with col1:
        html = "".join(radar_row(e, d) for e, d in sorted_competitors[:mid])
        st.markdown(html, unsafe_allow_html=True)
    with col2:
        html = "".join(radar_row(e, d) for e, d in sorted_competitors[mid:])
        st.markdown(html, unsafe_allow_html=True)

    # ── Аналитика ────────────────────────────────────────────────────────
    if digest_data.get("digest_text"):
        st.markdown('<div class="section-header">Аналитика</div>',
                    unsafe_allow_html=True)
        digest_text = digest_data["digest_text"]
        if "## Аналитика" in digest_text:
            analytics = digest_text.split("## Аналитика")[1].strip()
            # Разбиваем по блокам **Заголовок:** и рендерим с отступами
            import re
            blocks = re.split(r'(\*\*[^*]+\*\*)', analytics)
            rendered = ""
            for block in blocks:
                if re.match(r'\*\*[^*]+\*\*', block):
                    rendered += f'<div style="font-size:15px;font-weight:700;color:#2DB551;margin-top:20px;margin-bottom:6px">{block[2:-2]}</div>'
                else:
                    text = block.strip()
                    if text:
                        rendered += f'<div style="font-size:14px;color:#ccc;line-height:1.7;margin-bottom:4px">{text}</div>'
            st.markdown(rendered, unsafe_allow_html=True)

    # ── Топ-5 сигналов недели ────────────────────────────────────────────
    st.markdown('<div class="section-header">Топ-5 сигналов недели</div>',
                unsafe_allow_html=True)

    high_signals = get_all_high_signals(signals_data)

    # Фильтры — чекбоксы
    with st.expander("🔍 Фильтры", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Тип сигнала**")
            type_filter = []
            for key, label in SIGNAL_TYPE_LABELS.items():
                if st.checkbox(label, value=True, key=f"type_{key}"):
                    type_filter.append(key)
        with col2:
            st.markdown("**Конкурент**")
            sorted_employers = sorted(competitors.keys())
            employer_filter = []
            for emp in sorted_employers:
                if st.checkbox(emp, value=True, key=f"emp_{emp}"):
                    employer_filter.append(emp)

    filtered = [s for s in high_signals
                if s.get("type") in type_filter
                and s.get("employer") in employer_filter]

    def render_signal(s):
        type_label = SIGNAL_TYPE_LABELS.get(s.get("type", ""), s.get("type", ""))
        source = s.get("source", "")
        source_html = (f'<a href="{source}" target="_blank" '
                      f'style="color:#29B6F6;font-size:11px">'
                      f'↗ источник</a>' if source != "нет источника" else "")
        st.markdown(f"""
        <div style="background:#1e2130;border-radius:10px;padding:14px 16px;
                    margin-bottom:8px;border-left:3px solid #E8504A;
                    border:1px solid #2a2d3e">
            <div style="display:flex;justify-content:space-between;
                        align-items:flex-start;margin-bottom:6px">
                <span style="font-size:12px;color:#888">{type_label}</span>
                <span style="font-size:12px;font-weight:600;
                             color:#2DB551">{s.get('employer')}</span>
            </div>
            <div style="font-size:14px;line-height:1.5;color:#e0e0e0">
                {s.get('summary', '')}
            </div>
            <div style="margin-top:6px">{source_html}</div>
        </div>
        """, unsafe_allow_html=True)

    if filtered:
        # Топ-5
        for s in filtered[:5]:
            render_signal(s)

        # Полный список — скрыт по умолчанию
        if len(filtered) > 5:
            with st.expander(f"Показать все сигналы ({len(filtered)} всего)"):
                for s in filtered[5:]:
                    render_signal(s)
    else:
        st.info("Нет сигналов по выбранным фильтрам")


# ════════════════════════════════════════════════════════════════════════════
# СТРАНИЦА 2 — ПО КОНКУРЕНТАМ
# ════════════════════════════════════════════════════════════════════════════

elif page == "🏢 По конкурентам":
    signals_data = load_signals()
    competitors = signals_data.get("competitors", {})

    if not competitors:
        st.info("Данных пока нет.")
        st.stop()

    st.markdown("## По конкурентам")

    # Алфавитный список
    selected = st.selectbox(
        "Выберите конкурента",
        options=sorted(competitors.keys()),
        label_visibility="collapsed"
    )

    data = competitors[selected]
    status = data.get("retention_score_change", "нет данных")
    reasoning = data.get("retention_score_reasoning", "")
    signals = data.get("signals", [])
    color = COLORS.get(status, "#B0BEC5")
    emoji = RETENTION_EMOJI.get(status, "❓")

    # Карточка конкурента — единый стиль с главной
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(f"""
        <div style="background:#1e2130;border-radius:12px;padding:20px;
                    border-left:5px solid {color};border:1px solid #2a2d3e">
            <div style="font-size:22px;font-weight:700;margin-bottom:8px;color:#e0e0e0">
                {selected}
            </div>
            <div style="font-size:14px;color:{color};font-weight:600;
                        margin-bottom:8px">{emoji} {status}</div>
            <div style="font-size:13px;color:#aaa;line-height:1.6">
                {reasoning}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        by_type = {}
        for s in signals:
            t = s.get("type", "—")
            by_type[t] = by_type.get(t, 0) + 1
        st.markdown("**Сигналы по типам**")
        for t, count in sorted(by_type.items(),
                                key=lambda x: SIGNAL_TYPE_PRIORITY.get(x[0], 5)):
            label = SIGNAL_TYPE_LABELS.get(t, t)
            st.markdown(f"{label}: **{count}**")

    # Сравнение с прошлой неделей
    st.markdown("---")
    st.markdown("**Эта неделя vs прошлая**")
    digest_data = load_digest()
    retention_map = digest_data.get("retention_map", {})
    current_status = retention_map.get(selected, {}).get("status", "нет данных")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"Текущая неделя: {retention_badge(current_status)}",
                   unsafe_allow_html=True)
    with col2:
        st.markdown("Прошлая неделя: ❓ нет данных *(первый запуск)*")

    # Все сигналы
    st.markdown("---")
    st.markdown("**Все сигналы**")

    # Легенда важности
    st.markdown("""
    <div style="display:flex;gap:16px;margin-bottom:12px;font-size:12px">
        <span style="color:#E8504A">🔴 высокая важность</span>
        <span style="color:#29B6F6">🔵 средняя важность</span>
        <span style="color:#B0BEC5">⚪ низкая важность</span>
    </div>
    """, unsafe_allow_html=True)

    importance_order = {"высокая": 0, "средняя": 1, "низкая": 2}
    sorted_signals = sorted(signals,
                            key=lambda x: (
                                importance_order.get(x.get("importance", "низкая"), 2),
                                SIGNAL_TYPE_PRIORITY.get(x.get("type", ""), 5)
                            ))

    for s in sorted_signals:
        imp = s.get("importance", "низкая")
        type_label = SIGNAL_TYPE_LABELS.get(s.get("type", ""), s.get("type", ""))
        source = s.get("source", "")
        source_html = (f'<a href="{source}" target="_blank" '
                      f'style="color:#29B6F6;font-size:11px">↗ источник</a>'
                      if source != "нет источника" else "")
        imp_colors = {"высокая": "#E8504A", "средняя": "#29B6F6", "низкая": "#B0BEC5"}
        border_color = imp_colors.get(imp, "#B0BEC5")

        st.markdown(f"""
        <div style="background:#1e2130;border-radius:10px;padding:14px 16px;
                    margin-bottom:8px;border-left:3px solid {border_color};
                    border:1px solid #2a2d3e">
            <div style="display:flex;justify-content:space-between;margin-bottom:6px">
                <span style="font-size:12px;color:#888">{type_label}</span>
            </div>
            <div style="font-size:14px;line-height:1.5;color:#e0e0e0">
                {s.get('summary', '')}
            </div>
            <div style="margin-top:6px">{source_html}</div>
        </div>
        """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# СТРАНИЦА 3 — ДАЙДЖЕСТ
# ════════════════════════════════════════════════════════════════════════════

elif page == "📄 Дайджест":
    digest_data = load_digest()
    signals_data = load_signals()

    st.markdown("## Еженедельный дайджест")

    if not digest_data:
        st.info("Дайджест ещё не сгенерирован. Запусти анализ через боковую панель.")
        st.stop()

    generated_at = digest_data.get("generated_at", "—")
    n_covered = digest_data.get("competitors_covered", 0)
    digest_text = digest_data.get("digest_text", "")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Дата", generated_at)
    with col2:
        st.metric("Конкурентов", n_covered)
    with col3:
        if digest_text:
            st.download_button(
                "⬇️ Скачать Markdown",
                data=digest_text.encode("utf-8"),
                file_name=f"digest_{generated_at}.md",
                mime="text/markdown",
                use_container_width=True
            )

    st.divider()

    if not digest_text:
        st.stop()

    import re

    def render_digest_block(text):
        """Рендерим текст в стиле блока Аналитика — зелёные заголовки, серый текст."""
        blocks = re.split(r'(\*\*[^*]+\*\*)', text)
        rendered = ""
        for block in blocks:
            if re.match(r'\*\*[^*]+\*\*', block):
                rendered += (f'<div style="font-size:15px;font-weight:700;'
                            f'color:#2DB551;margin-top:18px;margin-bottom:6px">'
                            f'{block[2:-2]}</div>')
            else:
                t = block.strip()
                if t:
                    rendered += (f'<div style="font-size:14px;color:#ccc;'
                                f'line-height:1.7;margin-bottom:4px">{t}</div>')
        return rendered

    # ── Главное за неделю ────────────────────────────────────────────────
    if "## Главное за неделю" in digest_text:
        st.markdown('<div class="section-header">Главное за неделю</div>',
                    unsafe_allow_html=True)
        main_block = digest_text.split("## Главное за неделю")[1]
        main_block = main_block.split("##")[0].strip()
        st.markdown(main_block)

    # ── Аналитика ────────────────────────────────────────────────────────
    if "## Аналитика" in digest_text:
        st.markdown('<div class="section-header">Аналитика</div>',
                    unsafe_allow_html=True)
        analytics = digest_text.split("## Аналитика")[1]
        analytics = analytics.split("##")[0].strip()
        st.markdown(render_digest_block(analytics), unsafe_allow_html=True)

    # ── Радар удержания ──────────────────────────────────────────────────
    st.markdown('<div class="section-header">Радар удержания</div>',
                unsafe_allow_html=True)

    # Таблица по алфавиту из живых данных (не из дайджеста)
    competitors_live = signals_data.get("competitors", {})
    if competitors_live:
        # Легенда статусов
        st.markdown("""
        <div style="display:flex;gap:16px;margin-bottom:12px;font-size:11px;flex-wrap:wrap">
            <span style="color:#2DB551">📈 улучшилось — свежие позитивные изменения</span>
            <span style="color:#E8504A">📉 ухудшилось — свежие негативные изменения</span>
            <span style="color:#29B6F6">➡️ без изменений — хронические проблемы, ничего нового</span>
            <span style="color:#B0BEC5">❓ нет данных — нет свежих источников за 1-2 месяца</span>
        </div>
        """, unsafe_allow_html=True)

        rows = ""
        for employer in sorted(competitors_live.keys()):
            data = competitors_live[employer]
            status = data.get("retention_score_change", "нет данных")
            reasoning = data.get("retention_score_reasoning", "")
            short = reasoning
            color = COLORS.get(status, "#B0BEC5")
            emoji = RETENTION_EMOJI.get(status, "❓")
            rows += f"""<tr style="border-bottom:1px solid #2a2d3e">
                <td style="padding:8px 12px;color:#e0e0e0;font-weight:600;
                           white-space:nowrap;width:140px">{employer}</td>
                <td style="padding:8px 12px;color:{color};font-weight:600;
                           white-space:nowrap;width:160px">{emoji} {status}</td>
                <td style="padding:8px 12px;color:#aaa;font-size:13px;
                           line-height:1.5">{short}</td>
            </tr>"""

        st.markdown(f"""
        <table style="width:100%;border-collapse:collapse;font-size:14px">
            <thead>
                <tr style="border-bottom:2px solid #2DB551">
                    <th style="padding:8px 12px;text-align:left;color:#2DB551;
                               font-size:12px;font-weight:600;width:140px">Конкурент</th>
                    <th style="padding:8px 12px;text-align:left;color:#2DB551;
                               font-size:12px;font-weight:600;width:160px">Статус</th>
                    <th style="padding:8px 12px;text-align:left;color:#2DB551;
                               font-size:12px;font-weight:600">Причина</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
        """, unsafe_allow_html=True)

    # ── По конкурентам — из живых данных ────────────────────────────────
    st.markdown('<div class="section-header">По конкурентам · высокоприоритетные сигналы</div>',
                unsafe_allow_html=True)

    if competitors_live:
        for employer in sorted(competitors_live.keys()):
            data = competitors_live[employer]
            high = [s for s in data.get("signals", [])
                    if s.get("importance") == "высокая"]
            if not high:
                continue
            status = data.get("retention_score_change", "нет данных")
            color = COLORS.get(status, "#B0BEC5")
            emoji = RETENTION_EMOJI.get(status, "❓")

            st.markdown(f"""
            <div style="margin-top:16px;margin-bottom:6px">
                <span style="font-size:15px;font-weight:700;color:#e0e0e0">{employer}</span>
                <span style="font-size:12px;color:{color};font-weight:600;
                             margin-left:10px">{emoji} {status}</span>
            </div>
            """, unsafe_allow_html=True)

            for s in high[:4]:
                type_label = SIGNAL_TYPE_LABELS.get(s.get("type", ""), s.get("type", ""))
                source = s.get("source", "")
                source_html = (f'<a href="{source}" target="_blank" '
                              f'style="color:#29B6F6;font-size:11px">↗ источник</a>'
                              if source != "нет источника" else "")
                imp_colors = {"высокая": "#E8504A", "средняя": "#29B6F6",
                              "низкая": "#B0BEC5"}
                border_color = imp_colors.get(s.get("importance", "низкая"), "#B0BEC5")
                st.markdown(f"""
                <div style="background:#1e2130;border-radius:8px;padding:10px 14px;
                            margin-bottom:6px;border-left:3px solid {border_color};
                            border:1px solid #2a2d3e">
                    <div style="font-size:11px;color:#888;margin-bottom:4px">{type_label}</div>
                    <div style="font-size:13px;line-height:1.5;color:#e0e0e0">
                        {s.get('summary', '')}
                    </div>
                    <div style="margin-top:4px">{source_html}</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Нет данных для отображения.")
