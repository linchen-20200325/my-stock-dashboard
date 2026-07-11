"""src/ui/pages/data_registry_panel.py — 資料源完整清單診斷 panel(v18.394 Path C)。

把 `session_state['data_registry']`(由 data_registry_scanner + macro_registry_patch
寫入)的 50+ entries 渲染成可瀏覽 panel:

- 按 SSOT category 分組(11 個 emoji label,對齊 src.data.core.data_registry)
- 每筆顯示:emoji 燈號 / 名稱 / 最後更新 / rows / frequency / missing 旗標
- 燈號 freshness rule:
  - 🟢 7 日內 / 月頻 90 日內 — 新鮮
  - 🟡 7~30 日 / 月頻 90~180 日 — 過期
  - 🔴 30 日以上 / missing — 缺失
  - ⬜ N/A(未觸發 fetch)

§8.2 L5 UI:純讀 session_state,無副作用;無 fetch / 無 service 呼叫。

對外 API:
- compute_registry_groups() -> dict[category, list[entry_meta]]  純函式,易測
- render_data_registry_panel() -> None  Streamlit 渲染
"""
from __future__ import annotations

import datetime as _dt
from typing import Any

import streamlit as st

from shared.data_categories import (
    ALL_CATEGORIES, CAT_FALLBACK, FRESHNESS_THRESHOLDS_DAYS, coverage_emoji_for,
)

_C_GREEN  = "#3fb950"
_C_YELLOW = "#d29922"
_C_RED    = "#f85149"
_C_IDLE   = "#666"


def _freshness_emoji(last_updated: str, frequency: str, missing: bool) -> tuple[str, str]:
    """從 last_updated + frequency + missing 判 freshness。

    Returns (emoji, hex_color).
    Rules:
      - missing=True → 🔴
      - last_updated='N/A' → ⬜
      - daily / weekly:7 日內 🟢 / 7~30 🟡 / >30 🔴
      - monthly:90 日內 🟢 / 90~180 🟡 / >180 🔴
      - quarterly / yearly:180 日內 🟢 / 180~365 🟡 / >365 🔴
      - event:always 🟢(觸發型)
    """
    if missing:
        return ('🔴', _C_RED)
    if not last_updated or last_updated == 'N/A':
        return ('⬜', _C_IDLE)
    try:
        d = _dt.datetime.strptime(last_updated[:10], '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return ('⬜', _C_IDLE)
    today = _dt.date.today()
    days_old = (today - d).days
    # v18.401 SSOT:frequency-aware thresholds 從 shared.data_categories 引入。
    if frequency == 'event':
        return ('🟢', _C_GREEN)
    warn, crit = FRESHNESS_THRESHOLDS_DAYS.get(
        frequency, FRESHNESS_THRESHOLDS_DAYS['daily'])
    if days_old <= warn:
        return ('🟢', _C_GREEN)
    if days_old <= crit:
        return ('🟡', _C_YELLOW)
    return ('🔴', _C_RED)


def compute_registry_groups(
    state: dict | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """從 session_state['data_registry'] 分組成 {category → [entry, ...]}。

    state: 測試可注入 dict;None → 讀 st.session_state。
    entry 補 emoji / color 兩個 UI 欄位後 list 化。
    """
    if state is not None:
        _reg = state.get('data_registry') or {}
    else:
        try:
            _reg = st.session_state.get('data_registry') or {}
        except Exception:  # noqa: BLE001
            _reg = {}

    groups: dict[str, list[dict[str, Any]]] = {c: [] for c in ALL_CATEGORIES}
    groups[CAT_FALLBACK] = groups.get(CAT_FALLBACK) or []

    for _name, _meta in (_reg or {}).items():
        if not isinstance(_meta, dict):
            continue
        _cat = _meta.get('category') or CAT_FALLBACK
        _last = str(_meta.get('last_updated') or '')
        _freq = str(_meta.get('frequency') or 'daily')
        _missing = bool(_meta.get('missing'))
        _emo, _col = _freshness_emoji(_last, _freq, _missing)
        _entry = {
            'name':         _name,
            'last_updated': _last,
            'rows':         _meta.get('rows', 0),
            'frequency':    _freq,
            'missing':      _missing,
            'emoji':        _emo,
            'color':        _col,
            'category':     _cat,
        }
        groups.setdefault(_cat, []).append(_entry)

    # drop empty categories for UI;keep order from ALL_CATEGORIES
    return {c: groups[c] for c in groups if groups.get(c)}


def render_data_registry_panel() -> None:
    """渲染「📋 資料源完整清單」panel(在 data_coverage 之後)。"""
    st.markdown("### 📋 資料源完整清單(by SSOT 分類)")
    st.caption("細粒度資料源 metadata — 對齊 CLAUDE.md §2.1 SSOT。"
               "🟢 新鮮 / 🟡 過期 / 🔴 缺失 / ⬜ 未觸發。")

    groups = compute_registry_groups()
    if not groups:
        st.info("尚未觸發 data_registry 載入。請至 🌐 總經 Tab 按 🚀 一鍵更新。")
        return

    _th = ("font-size:10px;color:#888;font-weight:700;padding:6px 10px;"
           "border-bottom:1px solid #30363d")
    _td = "font-size:11px;padding:6px 10px;line-height:1.4"

    for _cat, _entries in groups.items():
        _emo_cnt = {'🟢': 0, '🟡': 0, '🔴': 0, '⬜': 0}
        for _e in _entries:
            _emo_cnt[_e['emoji']] = _emo_cnt.get(_e['emoji'], 0) + 1
        _summary = (
            f"🟢 {_emo_cnt['🟢']}  "
            f"🟡 {_emo_cnt['🟡']}  "
            f"🔴 {_emo_cnt['🔴']}  "
            f"⬜ {_emo_cnt['⬜']}"
        )
        with st.expander(f"{coverage_emoji_for(_cat)}（{len(_entries)} 筆 ｜ {_summary}）",
                          expanded=(_cat in _entries[0].get('category', _cat))):
            _html = (
                f"<div style='display:grid;grid-template-columns:0.4fr 2.4fr 1.1fr 0.7fr 0.8fr;"
                f"background:#0d1117;border-radius:6px 6px 0 0'>"
                f"<span style='{_th};text-align:center'>狀態</span>"
                f"<span style='{_th}'>名稱</span>"
                f"<span style='{_th}'>最後更新</span>"
                f"<span style='{_th};text-align:right'>列數</span>"
                f"<span style='{_th}'>頻率</span>"
                f"</div>"
            )
            for _e in _entries:
                _bg = ("#0a1a0a" if _e['emoji'] == "🟢" else
                       ("#1a1200" if _e['emoji'] == "🟡" else
                        ("#1a0606" if _e['emoji'] == "🔴" else "#0d1117")))
                _missing_tag = ("<span style='color:#f85149;font-size:9px;"
                                "padding:0 4px;border:1px solid #f85149;border-radius:3px;"
                                "margin-left:6px'>缺</span>" if _e['missing'] else "")
                _html += (
                    f"<div style='display:grid;grid-template-columns:0.4fr 2.4fr 1.1fr 0.7fr 0.8fr;"
                    f"background:{_bg};border-bottom:1px solid #21262d'>"
                    f"<span style='{_td};text-align:center;color:{_e['color']};font-size:14px'>{_e['emoji']}</span>"
                    f"<span style='{_td};color:#e6edf3'>{_e['name']}{_missing_tag}</span>"
                    f"<span style='{_td};color:{_e['color']};font-family:monospace'>{_e['last_updated']}</span>"
                    f"<span style='{_td};color:#bbb;text-align:right'>{_e['rows']}</span>"
                    f"<span style='{_td};color:#888'>{_e['frequency']}</span>"
                    f"</div>"
                )
            st.markdown(
                f"<div style='border:1px solid #30363d;border-radius:6px;overflow:hidden'>"
                f"{_html}</div>", unsafe_allow_html=True,
            )

    _total = sum(len(v) for v in groups.values())
    st.caption(
        f"全 {_total} 筆資料源,分 {len(groups)} 個 SSOT category。"
        "細項缺失 → 🌐 總經 Tab 按更新觸發,或檢查下方 API Key / Proxy 診斷。"
    )


# ═══════════════════════════════════════════════════════════════
# v19.96 批次4 Item1+2:@monitored fetcher 監控面板 + 孤兒 set-diff
# ═══════════════════════════════════════════════════════════════
def render_fetch_monitor_panel() -> None:
    """渲染 @monitored fetcher 自我登錄清單(shared/fetch_monitor)。

    - 每列:狀態燈 / fetcher 名 / 最後真實抓取時間 / rows / 耗時 / 錯誤。
      「未執行」= import 過但本 session 尚無真實外抓(cache hit 不計)。
    - Item2 孤兒檢查:已監控且宣告 registry_key 但 session_state['data_registry']
      沒有該 key → 警示(= 有在抓但診斷清單沒它的列,B5/S13 那類 bug 自動亮)。
    §8.2 L5:純讀 accessor(EX-PASSTHRU-1 精神),無副作用。
    """
    from shared.fetch_monitor import find_orphans, get_monitor_registry

    reg = get_monitor_registry()
    st.markdown("#### 🛰️ Fetcher 監控（@monitored 自我登錄）")
    if not reg:
        st.caption("尚無 fetcher 掛 @monitored（shared/fetch_monitor）。")
        return

    _icon = {'ok': '🟢', 'failed': '🔴', '未執行': '⬜'}
    rows = []
    for name, ent in sorted(reg.items()):
        rows.append({
            '狀態': _icon.get(ent.get('last_status'), '⬜'),
            'fetcher': name,
            '分類': ent.get('category') or '—',
            '最後真實抓取': ent.get('last_called_at') or '—',
            'rows': ent.get('last_rows') if ent.get('last_rows') is not None else '—',
            '耗時(ms)': ent.get('last_ms') if ent.get('last_ms') is not None else '—',
            '錯誤': ent.get('last_error') or '',
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption("「未執行」= 本 session 尚無真實外抓（cache 命中不計,狀態代表最後一次真實請求）。")

    # Item2:孤兒 set-diff(對照 session_state['data_registry'])
    _present = list((st.session_state.get('data_registry') or {}).keys())
    orphans = find_orphans(_present)
    if _present and orphans:
        st.warning(
            "🧩 孤兒 fetcher（有被監控、但診斷清單缺對應資料列 → 抓壞不會亮紅）:\n\n"
            + "\n".join(f"- `{n}` → 預期 registry key `{reg[n]['registry_key']}` 不存在"
                        for n in orphans)
        )
    elif _present:
        st.caption("✅ 孤兒檢查:所有已監控 fetcher 的 registry_key 均存在於診斷清單。")
    else:
        st.caption("⬜ 孤兒檢查待資料:session_state['data_registry'] 尚未建立（先按 🚀 更新）。")
