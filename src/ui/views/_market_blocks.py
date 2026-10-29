"""src/ui/views/_market_blocks.py — 📊 市場頁（UI-M，2026-10-29）頁內自有區塊（L5 UI）。

單一職責：把 `page_market.render_page_market()` 的**新首屏與圖表區**（Hero 4 卡、⚡ 需要處理、圖 A～D、
「查看依據」六欄元件）拆成「純函式（可單測）＋薄渲染」。`page_market.py` 只負責編排與保留區塊。

規格出處：`docs/vnext/NEWUI_D25_A_FOUR_PAGE_SPEC_2026-10-27.md` §4.1／§6／§7／§8.1（DEC-092 Q2／Q3／Q6）＋
已核准線框 `docs/vnext/d25_wireframes/market.html`。與線框的偏離逐項列在 PR 描述。

═══ 這個檔**不是**什麼 ═══════════════════════════════════════════════
- **不是新的計算**：風險項取自 L2 `compute_five_bucket_summary`（每桶 `main_key`＝既有主因燈）與
  `page_today._load_lamp_directions`（L2 `lamp_direction`）；本檔只做「挑出哪幾桶、排成表」，
  ⛔ 不重算燈號規則、⛔ 不做重要性排序、⛔ 不把方向翻成「惡化」（A 規格 §7.1：方向語意是否＝惡化未驗證）。
- **不新增資料源／schema／公式／投資語意／Risk Cap 定義**：圖 A 走 L3 `market_twii_view_service`（原樣帶 attrs），
  圖 B 只讀 session 既有 `cl_data['intl']`，圖 C 是空框（區塊內零數字）。
- **不碰 Risk Cap 數字**：水位卡首屏固定「⬜ 尚未核准／無法判定」；原有出手區間（含 risk_cap.v2）整段只放在
  該卡的「🔍 查看依據」內，且由 `page_today._render_one` 渲染同一張卡（本檔⛔ 不讀任何上限欄位）。
- ⛔ 不 import `src.data.*`（L1）、不 import `shared.ia_nav4`（legacy 路徑零依賴新模組，沿用 `page_market` 作法）。

§1／v3 §02：missing 一律 ⬜ 顯式，⛔ 不當 0／中性／續抱；未載入＝灰、真出錯＝紅；狀態不只靠顏色（每個狀態都有文字）。
"""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from shared.lamp_direction_thresholds import (
    LAMP_DIRECTION_ERROR_TEMPLATE,
    LAMP_DIRECTION_LABELS,
    LAMP_DIRECTION_MISSING_REASON,
)
from shared.macro_buckets import (
    BUCKET_DANGER_SPECS,
    BUCKET_META,
    BUCKET_ORDER,
    CL_INTL_KEY_DXY,
    CL_INTL_KEY_US10Y,
    LEVEL_EMOJI,
)
from shared.market_conclusion import CONCEPT_RISK_CAP, RISK_CAP_PENDING_TEXT
from shared.secret_scrub import scrub_secrets
from shared.signal_thresholds import TRADING_DAYS_PER_YEAR
from src.services import market_twii_view_service as twii_svc
from src.ui.views import page_today as today

# ══════════════════════════════════════════════════════════════════
# session key（沿用 page_market 的 `p00m_` 前綴；與既有 gate key 不相撞）
# ══════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════
# 字樣（客戶白話說明一律逐字取自 A 規格 §4.1.2，⛔ 不改寫）
# ══════════════════════════════════════════════════════════════════
#: 頁內標題。⚠️ 與 `shared/ia_nav4.PAGE4_LABELS[P4_MARKET]` 同字，但本檔不得 import ia_nav4
#: （旗標字面值各一份＋測試對帳，同 `page_market._NAV4_LEGACY_SESSION_KEY` 作法）。
PAGE_TITLE: str = "📊 市場"
PAGE_SUBTITLE: str = "現在適不適合投資？未來風險正在增加還是下降？"

NOT_LOADED: str = "⬜ 尚未載入，請按更新"
UNDETERMINED: str = "⬜ 無法判定"
#: 「更新時間」≠「資料日」的提醒由 `page_market.status_line` 負責；這裡只管「資料日」那一格。
DATA_DATE_NOT_PROVIDED: str = "⬜ 資料日未提供"
ASOF_CONTRACT_MISSING: str = "⬜ 此判斷的資料日：契約未提供"
NOT_DEFINED: str = "⬜ 尚未定義"

#: 市場狀態卡（沿用 `_regime_tile`）下方的範圍說明。
REGIME_SCOPE_CAPTION: str = "市場位階，不是台股趨勢"

#: 建議總持股水位卡（A 規格 §7.2 選項 A／I-10；C11 沿用 DEC-081 Q2-2）。
WATER_TITLE: str = "建議總持股水位"
WATER_VALUE: str = "⬜ 尚未核准／無法判定"
WATER_WHY: str = "正式 Risk Cap 尚未核准。核准前，此卡不顯示任何百分比（頁首更新報告展開後的步驟說明除外）。"
WATER_BASIS_NOTE: str = "原有出手區間（含 risk_cap.v2 硬否決天花板；未經 C2b 核准）如下："

HERO_RISK_TITLE: str = "今日主要風險"
HERO_RISK_NO_RANKING_NOTE: str = "依五桶固定順序列出非綠桶，不做重要性排序"
#: 超過 3 項時的尾註（N＝多出來的項數）。
HERO_RISK_MORE_FMT: str = "另 {n} 項見圖 D"
HERO_RISK_MAX_ITEMS: int = 3   # P2 登記：宜移 L0（目前沒有合適的 UI 顯示上限 SSOT 檔）
HERO_AI_PLACEHOLDER: str = "🤖 AI 投資總結：⬜ 尚未提供"

ALERTS_TITLE: str = "⚡ 需要處理"
ALERTS_NO_SOURCE: str = "⬜ 目前沒有可列的警示來源"
ALERTS_CONFLICTS_NUMBER_NOTE: str = ("上列提示若提到「數字」，指建議總持股水位卡「🔍 查看依據」裡的原有出手區間；"
                                     "該區間未經 C2b 核准，首屏不顯示。")
ALERTS_CONFLICTS_HEADING: str = "建議持股附帶的衝突／警示提示（原樣轉述，不新增行動語彙）"

HEALTH_CHIP: str = "⬜ 資料狀態：尚未彙總"
HEALTH_CHIP_POINTER: str = "（逐來源結果見頁首更新鈕下方的更新報告）"

CHART_A_TITLE: str = "圖A 🇹🇼 台股趨勢"
CHART_A_SAY: str = "看台股目前是在長期上升、整理還是轉弱；趨勢與短期波動分開判斷。"
CHART_A_MA_DISCLAIMER: str = "均線為參考，不等於正式台股趨勢判斷。"
CHART_A_CONCLUSION: str = f"台股趨勢結論：{NOT_DEFINED}"
CHART_A_MA_NOTE: str = "均線為『市場評估』輸入的最新值，畫成水平參考線（不是歷史均線曲線，本頁不自行算均線）"

CHART_B_TITLE: str = "圖B 🌍 國際趨勢"
CHART_B_SAY: str = "看海外市場、利率與美元是否正在幫助或壓抑台股風險偏好。"
CHART_B_CONCLUSION: str = f"國際趨勢結論：{NOT_DEFINED}"
CHART_B_NOTE: str = "每個系列單獨一張小圖，不疊同一座標軸、不正規化；窗口很短，不代表長期趨勢。"
TREND_DEFINITION_NOTE: str = "正式趨勢定義另列 High Gate，定義前不由均線／單一指標補成多空結論。"
#: 趨勢「還在等客戶定義」的一句說明（原在 `page_market`；移到這裡後由 `page_market` re-export 以保 `M.TREND_PENDING_WHY`）。
TREND_PENDING_WHY: str = "怎麼判斷還在等您定義；定義之前本頁不給這一項結論。"

CHART_C_TITLE: str = "圖C 💰 大盤合理區間"
CHART_C_TAG: str = "研究框架，未啟用"
CHART_C_SAY: str = "用企業獲利 EPS 搭配不同合理本益比情境，觀察目前指數位在便宜、合理或偏貴區域。"
CHART_C_EMPTY: str = "需先核准：EPS 資料來源、PE 情境、計算公式、更新頻率。核准前這個區塊不畫任何圖形、區間或指數位置。"
CHART_C_BASIS: str = "查看依據：此區塊未啟用，沒有使用任何資料。"

CHART_D_TITLE: str = "圖D ⚠️ 主要風險"
CHART_D_NOTE: str = "只顯示最需要注意的 3–5 項、方向、是否惡化。"
CHART_D_WORSENING: str = f"是否惡化：{NOT_DEFINED}"
CHART_D_ALL_LAMPS_POINTER: str = "查看全部指標 › 請展開下方「指標明細（16 項）」"
INSUFFICIENT_TEXT: str = "⬜ 資料不足／無法判定"

BASIS_EXPANDER_LABEL: str = "🔍 查看依據"
AI_NOT_INVOLVED: str = "不參與（本區由規則／資料顯示產生，本頁沒有 AI 呼叫）"

# ══════════════════════════════════════════════════════════════════
# 圖 A 窗口、均線規格
# ══════════════════════════════════════════════════════════════════
#: 圖 A 畫幾個交易日 ＝ 一個交易年（L0 `TRADING_DAYS_PER_YEAR`）。⛔ 不另寫數字；實際筆數以資料為準（不足不補）。
TWII_CHART_TRADING_DAYS: int = TRADING_DAYS_PER_YEAR

#: (mkt_info 鍵, 顯示名)。均線值是 `market_strategy.get_market_assessment` 已算好的純量，本頁⛔ 不自行算滾動曲線。
MA_REFERENCE_SPECS: tuple[tuple[str, str], ...] = (
    ("ma5", "MA5"), ("ma60", "MA60"), ("ma120", "MA120"), ("ma200", "MA200"),
)
TWII_COLUMN: str = "加權指數收盤"

# ══════════════════════════════════════════════════════════════════
# 圖 B 分組（鍵＝`cl_data['intl']` 的中文名；SSOT 在 L3 `daily_checklist.INTL_MAP`，
# 由 `tests/test_market_blocks.py` 對帳：INTL_MAP 每個鍵都恰好落在一組，漂移就紅）
# ══════════════════════════════════════════════════════════════════
INTL_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("海外市場", ("道瓊工業 DJI", "納斯達克 IXIC", "費城半導體 SOX")),
    ("利率", (CL_INTL_KEY_US10Y,)),
    ("美元", (CL_INTL_KEY_DXY,)),
)
INTL_OTHER_GROUP: str = "其他（未分組）"

KIND_RISK: str = "risk"
KIND_GREEN: str = "green"
KIND_INSUFFICIENT: str = "insufficient"

# 五桶摘要 dict 的鍵（L2 `compute_five_bucket_summary` 輸出）。
# ⚠️ 這是「五桶燈號」自己的欄位，不是舊 UI 的紅綠燈結論欄（`page_market` 的 R12 守衛禁的是後者）。
_K_LEVEL = "level"
_K_LABEL = "label"
_K_HEADLINE = "headline"
_K_DETAILS = "details"
_K_MAIN = "main_key"


# ══════════════════════════════════════════════════════════════════
# 純函式 1：風險項（hero 與圖 D 的單一來源）
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class BucketRiskRow:
    """一個風險桶的一列（hero「今日主要風險」與圖 D 共用同一個物件）。

    Attributes:
        kind: `risk`（黃／紅，有主因燈）／`green`（有評估且全綠）／`insufficient`（資料不足，不硬選）。
        level_text: 桶燈號短語（L2 `bucket_level_label`，例「循環惡化」）—— 狀態的文字載體（不只靠顏色）。
        lamp_key / lamp_label / lamp_value: 主因燈（L2 `main_key`）；非 risk 列為 None／""。
        direction_word: 方向原詞（例「↗ 上升」「無資料」「計算失敗（未回傳）」）。
        direction_full: 方向完整句（含窗口與資料日；缺值同上）。
        tied_labels: 桶內與桶等級同級的全部燈名（≥1；超過 1 項＝並列）。
        covered: (桶內有資料的燈數, 桶內燈總數)。
    """

    bucket: str
    title: str
    kind: str
    level: str
    level_text: str
    headline: str
    lamp_key: str | None = None
    lamp_label: str = ""
    lamp_value: str = ""
    direction_word: str = ""
    direction_full: str = ""
    tied_labels: tuple[str, ...] = ()
    covered: tuple[int, int] = (0, 0)

    @property
    def tied_n(self) -> int:
        return len(self.tied_labels)


@dataclass(frozen=True)
class MarketRisks:
    """五桶風險列＋覆蓋事實。`cold`＝上游還沒寫過任何總經 key；`failed`＝五桶摘要算不出來（真出錯，紅）。"""

    rows: tuple[BucketRiskRow, ...] = ()
    cold: bool = False
    failed: bool = False
    error: str = ""
    n_lamps: int = 0
    n_unevaluated: int = 0

    @property
    def risk_rows(self) -> tuple[BucketRiskRow, ...]:
        return tuple(_r for _r in self.rows if _r.kind == KIND_RISK)

    @property
    def n_insufficient(self) -> int:
        return sum(1 for _r in self.rows if _r.kind == KIND_INSUFFICIENT)


def lamp_direction_texts(directions: Mapping[str, Any] | None, key: str | None) -> tuple[str, str]:
    """主因燈的方向 → `(短詞, 完整句)`。**只轉述 L2 `LampDirection` 的原詞**。

    - 上升／持平／下降＝L2 算出來的方向原詞（箭頭＋字，⛔ 不翻成「惡化」「好轉」）；
    - 無資料／計算失敗＝L2 原文字（⛔ 絕不畫成「持平」）；
    - `directions` 沒給（None）→ 「⬜ 方向未提供」；給了 mapping 卻缺這盞 → 「計算失敗（未回傳）」（同燈卡列的處置）。
    """
    if key is None:
        return "—", "—"
    if directions is None:
        return "⬜ 方向未提供", "⬜ 方向未提供"
    _d = directions.get(key)
    if _d is None:
        _t = LAMP_DIRECTION_ERROR_TEMPLATE.format(reason=LAMP_DIRECTION_MISSING_REASON)
        return _t, _t
    from src.compute.macro.lamp_direction import format_direction_text
    _full = format_direction_text(_d)
    if getattr(_d, "direction", None) in LAMP_DIRECTION_LABELS:
        _arrow, _zh = LAMP_DIRECTION_LABELS[_d.direction]
        return f"{_arrow} {_zh}", _full
    return _full, _full


def _bucket_title(bucket: str) -> str:
    _m = BUCKET_META[bucket]
    return f"{_m['emoji']} {_m['title']}"


def build_market_risks(readout: Any, directions: Mapping[str, Any] | None) -> MarketRisks:
    """`page_today.MacroReadout` ＋ 方向 → 五桶風險列。hero 與圖 D **共用這一個回傳值**（單一來源）。

    規則（A §7.1 R-A／DEC-092 Q3，⛔ 不新增跨指標排序）：
    - 冷啟動（`readout.requested` 為 False）→ `cold=True`，不產生任何列（⛔ 不顯示過期值）。
    - `readout.error` 非空 → `failed=True`（五桶摘要算不出來，真出錯）。
    - 桶全灰／缺 → `insufficient`（⛔ 不硬選最差）；全綠 → `green`；黃／紅 → `risk`，主因燈＝L2 `main_key`。
    """
    if not getattr(readout, "requested", False):
        return MarketRisks(cold=True, n_lamps=len(BUCKET_DANGER_SPECS), n_unevaluated=len(BUCKET_DANGER_SPECS))
    if getattr(readout, "error", ""):
        return MarketRisks(failed=True, error=str(readout.error), n_lamps=len(BUCKET_DANGER_SPECS))
    _summary = readout.summary or {}
    _rows: list[BucketRiskRow] = []
    _evaluated = 0
    for _b in BUCKET_ORDER:
        _s = _summary.get(_b) or {}
        _details = list(_s.get(_K_DETAILS) or [])
        _n_ok = sum(1 for _d in _details if _d.get("danger") in ("green", "yellow", "red"))
        _evaluated += _n_ok
        _level = str(_s.get(_K_LEVEL) or "gray")
        _title = _bucket_title(_b)
        _cov = (_n_ok, len(_details))
        if _level in ("yellow", "red"):
            _mk = _s.get(_K_MAIN)
            _hit = next((_d for _d in _details if _d.get("key") == _mk), None) if _mk else None
            _tied = tuple(str(_d.get("label", _d.get("key", ""))) for _d in _details if _d.get("danger") == _level)
            _word, _full = lamp_direction_texts(directions, _mk)
            _rows.append(BucketRiskRow(
                bucket=_b, title=_title, kind=KIND_RISK, level=_level,
                level_text=str(_s.get(_K_LABEL) or ""), headline=str(_s.get(_K_HEADLINE) or ""),
                lamp_key=_mk,
                lamp_label=(str(_hit.get("label")) if _hit else "（主因燈未回傳）"),
                lamp_value=(str(_hit.get("value_str", "")) if _hit else ""),
                direction_word=_word, direction_full=_full, tied_labels=_tied, covered=_cov))
        elif _level == "green":
            _rows.append(BucketRiskRow(
                bucket=_b, title=_title, kind=KIND_GREEN, level=_level,
                level_text=str(_s.get(_K_LABEL) or ""), headline=str(_s.get(_K_HEADLINE) or ""),
                covered=_cov))
        else:
            _rows.append(BucketRiskRow(
                bucket=_b, title=_title, kind=KIND_INSUFFICIENT, level="gray",
                level_text="", headline=INSUFFICIENT_TEXT, covered=_cov))
    _total = len(BUCKET_DANGER_SPECS)
    return MarketRisks(rows=tuple(_rows), n_lamps=_total, n_unevaluated=max(_total - _evaluated, 0))


_CIRCLED = "①②③④⑤"


def hero_risk_items(risks: MarketRisks) -> tuple[tuple[BucketRiskRow, ...], int]:
    """hero 要列的風險項：`risks.rows` 裡的 `risk` 列，依桶順序取前 3；回 `(items, 多出來的項數)`。

    ⛔ 直接取自 `risks.rows`（與圖 D 同一份），不另算、不重排。
    """
    _all = risks.risk_rows
    _items = _all[:HERO_RISK_MAX_ITEMS]
    return _items, len(_all) - len(_items)


def risk_item_text(row: BucketRiskRow, *, index: int | None = None) -> str:
    """一個風險項的一行文字（含方向原詞；並列時註明項數）。"""
    _head = (_CIRCLED[index] + " ") if index is not None and index < len(_CIRCLED) else ""
    _tie = f"｜同級並列 {row.tied_n} 項" if row.tied_n > 1 else ""
    _lvl = f"（{row.level_text}）" if row.level_text else ""
    return (f"{_head}{LEVEL_EMOJI[row.level]} {row.title}：{row.lamp_label}{_lvl}"
            f"｜方向：{row.direction_word}{_tie}")


def hero_risk_lines(risks: MarketRisks) -> list[tuple[str, str]]:
    """hero「今日主要風險」要畫的行：`(tone, text)`；tone ∈ item／note／grey／error。

    ⛔ 不寫「無風險」「沒有需要處理」：未載入＝灰、算不出來＝紅、選不出＝⬜ 無法判定。
    """
    if risks.cold:
        return [("grey", NOT_LOADED)]
    if risks.failed:
        return [("error", f"五桶風險摘要算不出來：{scrub_secrets(risks.error)}")]
    _items, _more = hero_risk_items(risks)
    if _items:
        _out = [("item", risk_item_text(_r, index=_i)) for _i, _r in enumerate(_items)]
        if _more:
            _out.append(("note", HERO_RISK_MORE_FMT.format(n=_more)))
        if risks.n_insufficient:
            _out.append(("note", f"另有 {risks.n_insufficient} 桶資料不足、無法判定（見圖 D）"))
        _out.append(("note", HERO_RISK_NO_RANKING_NOTE))
        return _out
    if risks.n_insufficient >= len(risks.rows):
        return [("grey", f"{UNDETERMINED}（五桶資料皆不足）")]
    if risks.n_insufficient:
        return [("grey", f"本輪沒有非綠桶可列；另有 {risks.n_insufficient} 桶資料不足、無法判定（不代表安全）")]
    _ev = risks.n_lamps - risks.n_unevaluated
    return [("grey", f"本輪五桶皆為綠燈，沒有非綠桶可列（已評估 {_ev}／{risks.n_lamps} 項燈，"
                     f"{risks.n_unevaluated} 項未評估；只根據已取得的資料，不代表安全）")]


def risk_panel_rows(risks: MarketRisks) -> list[tuple[str, str, str]]:
    """圖 D 的表格列：`(風險桶, 方向, 是否惡化)`。五桶固定順序，每桶一列；與 hero 同一份 `risks.rows`。"""
    _out: list[tuple[str, str, str]] = []
    for _r in risks.rows:
        if _r.kind == KIND_RISK:
            _tie = f"（同級並列 {_r.tied_n} 項）" if _r.tied_n > 1 else ""
            _val = f" {_r.lamp_value}" if _r.lamp_value else ""
            _out.append((f"{LEVEL_EMOJI[_r.level]} {_r.title}：{_r.lamp_label}{_val}"
                         f"（{_r.level_text}）{_tie}", _r.direction_word, CHART_D_WORSENING))
        elif _r.kind == KIND_GREEN:
            _out.append((f"{LEVEL_EMOJI['green']} {_r.title}：已評估 {_r.covered[0]}／{_r.covered[1]} 項皆綠"
                         f"（{_r.level_text}）", "—（沒有非綠燈可挑）", CHART_D_WORSENING))
        else:
            _out.append((f"{LEVEL_EMOJI['gray']} {_r.title}", INSUFFICIENT_TEXT, INSUFFICIENT_TEXT))
    return _out


# ══════════════════════════════════════════════════════════════════
# 「查看依據」六欄元件
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Basis:
    """六欄皆必填（空字串＝呼叫端忘了填 ⇒ `ValueError`；沒有資料就明寫 ⬜ 原因）。"""

    data_used: str
    as_of: str
    rule: str
    missing: str
    confidence: str
    ai: str


BASIS_FIELDS: tuple[tuple[str, str], ...] = (
    ("使用的資料", "data_used"),
    ("資料日期", "as_of"),
    ("規則／計算結果", "rule"),
    ("missing", "missing"),
    ("confidence／availability", "confidence"),
    ("AI 是否參與", "ai"),
)


def basis_rows(basis: Basis) -> list[tuple[str, str]]:
    """六欄 → `(標籤, 內容)`。任一欄空白 → `ValueError`（§1：不留白，⛔ 不用空字串蒙混）。"""
    _out: list[tuple[str, str]] = []
    for _label, _attr in BASIS_FIELDS:
        _v = str(getattr(basis, _attr) or "").strip()
        if not _v:
            raise ValueError(f"查看依據「{_label}」不得留白（沒有就寫 ⬜ 與原因）")
        _out.append((_label, _v))
    return _out


def render_basis(basis: Basis, *, extra: Callable[[], None] | None = None) -> None:
    """預設收合的「🔍 查看依據」。`extra`＝展開後在六欄下面多畫的內容（例：水位卡的原有出手區間）。"""
    with st.expander(BASIS_EXPANDER_LABEL, expanded=False):
        st.markdown("\n".join(f"- **{_k}**：{scrub_secrets(_v)}" for _k, _v in basis_rows(basis)))
        if extra is not None:
            extra()


def _cell(text: Any) -> str:
    return scrub_secrets(str(text)).replace("|", "／").replace("\n", " ")


def _md_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    _head = "| " + " | ".join(headers) + " |"
    _sep = "|" + "---|" * len(headers)
    return "\n".join([_head, _sep, *("| " + " | ".join(_cell(_c) for _c in _r) + " |" for _r in rows)])


# ── 各區塊的依據內容（純函式，可單測）──────────────────────────────
def basis_water(alloc: Any, alloc_error: str) -> Basis:
    if alloc is None:
        _missing = (f"建議持股讀取失敗：{scrub_secrets(alloc_error)}" if alloc_error
                    else "建議持股尚未載入（見下方原卡說明）")
    else:
        _missing = "本頁未另做缺漏檢查，沿用下方原卡的說明"
    return Basis(
        data_used="建議持股服務（L3 allocation_service，姿態油門與各 Cap 取小；含 risk_cap.v2）",
        as_of=ASOF_CONTRACT_MISSING,
        rule="首屏固定顯示「尚未核准／無法判定」；原有出手區間只放在本展開區，且未經 C2b 核准",
        missing=_missing,
        confidence="⬜ 契約未提供",
        ai=AI_NOT_INVOLVED)


def basis_risks(risks: MarketRisks) -> Basis:
    """hero「今日主要風險」與圖 D 共用的依據（同一份 `risks`）。"""
    if risks.cold:
        return Basis(
            data_used="五桶摘要（L2 compute_five_bucket_summary，16 盞燈）＋燈卡變化方向（L2 lamp_direction）",
            as_of=ASOF_CONTRACT_MISSING, rule="尚未載入，沒有可列的風險項",
            missing=NOT_LOADED, confidence="⬜ 契約未提供", ai=AI_NOT_INVOLVED)
    if risks.failed:
        return Basis(
            data_used="五桶摘要（L2 compute_five_bucket_summary）",
            as_of=ASOF_CONTRACT_MISSING, rule="五桶摘要算不出來，沒有可列的風險項",
            missing=f"計算失敗：{scrub_secrets(risks.error)}", confidence="⬜ 契約未提供", ai=AI_NOT_INVOLVED)
    _insuff = [_r.title for _r in risks.rows if _r.kind == KIND_INSUFFICIENT]
    _per = "；".join(
        f"{_r.title} {_r.covered[0]}／{_r.covered[1]} 項有資料"
        + (f"（並列：{'、'.join(_r.tied_labels)}）" if _r.tied_n > 1 else "")
        for _r in risks.rows)
    _dirs = "；".join(f"{_r.title}「{_r.lamp_label}」{_r.direction_full}"
                      for _r in risks.rows if _r.kind == KIND_RISK) or "（本輪沒有非綠桶）"
    return Basis(
        data_used="五桶摘要（L2 compute_five_bucket_summary，16 盞燈）＋燈卡變化方向（L2 lamp_direction）",
        as_of=f"{ASOF_CONTRACT_MISSING}；方向列各自的資料日：{_dirs}",
        rule=("每桶取桶內既有的主因燈（五桶摘要的 worst-of 規則）；只列非綠桶、依五桶固定順序、最多 3 項、"
              "不做重要性排序；方向為原詞，不翻成「惡化」。逐桶：" + _per),
        missing=(f"{risks.n_unevaluated}／{risks.n_lamps} 項燈未評估；資料不足的桶：" + ("、".join(_insuff) or "無")),
        confidence=f"⬜ 契約未提供（覆蓋率：{risks.n_lamps - risks.n_unevaluated}／{risks.n_lamps} 項燈有資料）",
        ai=AI_NOT_INVOLVED)


def basis_alerts(alerts: Any, scanned: bool, error: str, alloc: Any) -> Basis:
    _items = list((alerts or {}).get("items") or []) if isinstance(alerts, Mapping) else []
    _conf = list(getattr(alloc, "conflicts", ()) or ()) if alloc is not None else []
    if error:
        _missing = f"今日關鍵警示產生失敗：{scrub_secrets(error)}"
    elif not scanned:
        _missing = "門檻層本輪未掃描（未評估，不等於沒有異常）"
    else:
        _missing = "—（門檻層已掃描；沒有列出的事項只代表這兩個來源沒有，不代表沒有其他需要處理的事）"
    return Basis(
        data_used="今日關鍵警示（L2 daily_key_alerts）＋建議持股的衝突提示（AllocationDecision.conflicts）",
        as_of=ASOF_CONTRACT_MISSING,
        rule=f"只轉述既有輸出：警示 {len(_items)} 則、被壓制的相反訊號 {len(_conf)} 則；不新增行動語彙",
        missing=_missing, confidence="⬜ 契約未提供", ai=AI_NOT_INVOLVED)


def ma_reference_values(mkt_info: Any) -> tuple[list[tuple[str, float]], list[tuple[str, str]]]:
    """`mkt_info` 的 MA 純量 → `(可畫的 [(顯示名, 值)], 缺的 [(顯示名, 原因)])`。非有限／≤0／缺 → 缺（⛔ 不補值）。"""
    _ok: list[tuple[str, float]] = []
    _bad: list[tuple[str, str]] = []
    _src = mkt_info if isinstance(mkt_info, Mapping) else {}
    for _key, _name in MA_REFERENCE_SPECS:
        _v = _src.get(_key)
        _f: float | None
        try:
            _f = float(_v) if _v is not None and not isinstance(_v, bool) else None
        except (TypeError, ValueError):
            _f = None
        if _f is not None and math.isfinite(_f) and _f > 0:
            _ok.append((_name, _f))
            continue
        _why = "無資料"
        if _key == "ma200" and _src.get("ma200_status"):
            _why = f"無資料（{_src.get('ma200_status')}）"
        _bad.append((_name, _why))
    return _ok, _bad


def twii_chart_frame(view: twii_svc.TwiiTrendView,
                     refs: Sequence[tuple[str, float]]) -> pd.DataFrame:
    """指數收盤 ＋ 每條均線一條**水平**參考線（各欄恆為同一個值）。⛔ 不做任何滾動運算。"""
    _idx = pd.to_datetime(list(view.xs))
    _df = pd.DataFrame({TWII_COLUMN: list(view.close)}, index=_idx)
    for _name, _val in refs:
        _df[f"{_name}（最新值，參考）"] = _val
    return _df


def basis_chart_a(view: twii_svc.TwiiTrendView | None, mkt_info: Any) -> Basis:
    _refs, _bad = ma_reference_values(mkt_info)
    _ma_date = (str(mkt_info.get("index_as_of"))[:10]
                if isinstance(mkt_info, Mapping) and mkt_info.get("index_as_of") else DATA_DATE_NOT_PROVIDED)
    if view is None:
        _line = "指數線：尚未讀取（勾選上方核取方塊才讀本地快取）"
        _avail = "⬜ 契約未提供（指數線尚未讀取）"
    elif not view.ok:
        _line = f"指數線：⬜ 讀不到（{scrub_secrets(view.error)}）"
        _avail = "⬜ 指數線讀不到"
    else:
        _stale = {True: "已過期", False: "未過期", None: "⬜ 新鮮度未判定"}[view.is_stale]
        _age = f"，距今 {view.age_days} 天" if view.age_days is not None else ""
        _line = f"指數線資料日 {view.as_of}（{_stale}{_age}）"
        _avail = f"指數線共 {view.n_available:,} 筆可用，本圖取最近 {len(view.close)} 筆；{_stale}"
    _miss = [f"{_n}：{_w}" for _n, _w in _bad]
    if view is not None and not view.ok:
        _miss.insert(0, f"指數線：{scrub_secrets(view.error)}")
    if view is not None and view.ok and view.upstream_error:
        _miss.append(f"上游最後一次錯誤：{scrub_secrets(view.upstream_error)}")
    return Basis(
        data_used=f"{twii_svc.TWII_SOURCE_TEXT}；均線取自『市場評估』輸入 session mkt_info",
        as_of=f"{_line}；均線資料日 {_ma_date}（兩者來源不同）",
        rule=f"{CHART_A_MA_NOTE}。{CHART_A_MA_DISCLAIMER}{CHART_A_CONCLUSION}",
        missing="；".join(_miss) or "—（可畫的均線皆有值）",
        confidence=_avail, ai=AI_NOT_INVOLVED)


@dataclass(frozen=True)
class IntlSeries:
    """圖 B 的一個系列。`status`：ok／empty（有框架但沒收盤）／absent（本輪沒有這個系列）。"""

    group: str
    name: str
    status: str
    close: pd.Series | None = None

    @property
    def n(self) -> int:
        return 0 if self.close is None else int(len(self.close))

    @property
    def last_date(self) -> str | None:
        return None if self.close is None or self.close.empty else str(self.close.index[-1])[:10]

    @property
    def window_text(self) -> str:
        """圖上標示：近 N 日，資料至 YYYY-MM-DD（兩者都由資料算出，⛔ 不寫死）。"""
        return f"近 {self.n} 日，資料至 {self.last_date}" if self.status == "ok" else "⬜ 無資料"


def intl_series(session: Mapping[str, Any]) -> list[IntlSeries] | None:
    """`session['cl_data']['intl']` → 分組後的系列清單；`cl_data`／`intl` 不存在 → None（＝尚未載入）。"""
    _cl = session.get("cl_data") if isinstance(session, Mapping) else None
    _intl = _cl.get("intl") if isinstance(_cl, Mapping) else None
    if not isinstance(_intl, Mapping):
        return None
    _out: list[IntlSeries] = []
    _seen: set[str] = set()
    _groups = list(INTL_GROUPS)
    _extra = [str(_n) for _n in _intl if str(_n) not in {_n2 for _g in INTL_GROUPS for _n2 in _g[1]}]
    if _extra:
        _groups.append((INTL_OTHER_GROUP, tuple(_extra)))
    for _g, _names in _groups:
        for _name in _names:
            _seen.add(_name)
            _df = _intl.get(_name)
            _cols = getattr(_df, "columns", None)
            _col = next((_c for _c in ("close", "Close") if _cols is not None and _c in _cols), None)
            if _df is None:
                _out.append(IntlSeries(_g, _name, "absent"))
            elif _col is None or getattr(_df, "empty", True):
                _out.append(IntlSeries(_g, _name, "empty"))
            else:
                _s = _df[_col].dropna()
                _out.append(IntlSeries(_g, _name, "ok" if not _s.empty else "empty", _s if not _s.empty else None))
    return _out


def basis_chart_b(series: list[IntlSeries] | None, source_note: str) -> Basis:
    if series is None:
        return Basis(data_used=source_note, as_of=NOT_LOADED, rule=CHART_B_NOTE,
                     missing=NOT_LOADED, confidence="⬜ 契約未提供", ai=AI_NOT_INVOLVED)
    _dates = "；".join(f"{_s.name}：{_s.last_date or '⬜'}（{_s.n} 筆）" for _s in series) or "⬜ 沒有任何系列"
    _bad = [f"{_s.name}（{'本輪沒有這個系列' if _s.status == 'absent' else '沒有可用收盤'}）"
            for _s in series if _s.status != "ok"]
    return Basis(
        data_used=source_note, as_of=_dates,
        rule=f"{CHART_B_NOTE}{CHART_B_CONCLUSION}。{TREND_DEFINITION_NOTE}",
        missing="；".join(_bad) or "—（五個系列本輪都有資料）",
        confidence="⬜ 契約未提供（窗口很短，只標示近 N 日與資料日）", ai=AI_NOT_INVOLVED)


# ══════════════════════════════════════════════════════════════════
# 渲染（薄）
# ══════════════════════════════════════════════════════════════════
def data_date_text(mkt_info: Any) -> str:
    """更新卡的「資料日」＝`mkt_info['index_as_of']`（市場評估用的加權指數最後一根）；取不到 → ⬜。"""
    _v = mkt_info.get("index_as_of") if isinstance(mkt_info, Mapping) else None
    _s = str(_v).strip()[:10] if _v is not None else ""
    return f"資料日：{_s}（加權指數，來源：市場評估輸入）" if _s else DATA_DATE_NOT_PROVIDED


def _render_lines(lines: Sequence[tuple[str, str]]) -> None:
    for _tone, _text in lines:
        if _tone == "error":
            st.error(_text, icon="❌")
        elif _tone == "item":
            st.markdown(_text)
        else:
            st.caption(_text)


def render_hero(session: Mapping[str, Any], *, regime_tile: Any, exposure_tile: Any,
                alloc: Any, alloc_error: str, risks: MarketRisks) -> None:
    """Hero 4 卡：市場狀態｜建議總持股水位｜今日主要風險｜更新（A §4.1.1；窄螢幕由 Streamlit 自動疊成一欄）。"""
    _cols = st.columns(4)
    with _cols[0]:
        today._render_one(regime_tile)
        st.caption(REGIME_SCOPE_CAPTION)
    with _cols[1]:
        with st.container(border=True):
            st.markdown(f"**{WATER_TITLE}**")
            st.markdown(f"**{WATER_VALUE}**")
            st.caption(WATER_WHY)
            st.caption(f"{CONCEPT_RISK_CAP}：{RISK_CAP_PENDING_TEXT}")

            def _original_range() -> None:
                st.caption(WATER_BASIS_NOTE)
                today._render_one(exposure_tile)
            render_basis(basis_water(alloc, alloc_error), extra=_original_range)
    with _cols[2]:
        with st.container(border=True):
            st.markdown(f"**{HERO_RISK_TITLE}**")
            _render_lines(hero_risk_lines(risks))
            render_basis(basis_risks(risks))
    with _cols[3]:
        with st.container(border=True):
            st.markdown("**更新**")
            today._render_update_form(session)
            st.caption(data_date_text(session.get("mkt_info")))
    st.caption(f"{HERO_AI_PLACEHOLDER}　{HEALTH_CHIP}{HEALTH_CHIP_POINTER}")


def alerts_has_listable_source(alerts: Any, alloc: Any) -> bool:
    _items = (alerts or {}).get("items") if isinstance(alerts, Mapping) else None
    return bool(_items) or bool(getattr(alloc, "conflicts", ()) if alloc is not None else ())


def render_alerts_block(*, alerts_tile: Any, alerts: Any, scanned: bool, alerts_error: str, alloc: Any) -> None:
    """⚡ 需要處理：只轉述既有警示（`_load_key_alerts`）＋建議持股的衝突提示。三態判別由既有 tile 負責。"""
    with st.container(border=True):
        st.markdown(f"**{ALERTS_TITLE}**")
        today._render_one(alerts_tile)
        _conf = list(getattr(alloc, "conflicts", ()) or ()) if alloc is not None else []
        if _conf:
            st.markdown(f"**{ALERTS_CONFLICTS_HEADING}**")
            st.markdown("\n".join(f"- {_cell(_c)}" for _c in _conf))
            st.caption(ALERTS_CONFLICTS_NUMBER_NOTE)
        if not alerts_has_listable_source(alerts, alloc):
            st.caption(ALERTS_NO_SOURCE)
        render_basis(basis_alerts(alerts, scanned, alerts_error, alloc))


def render_chart_a(session: Mapping[str, Any]) -> None:
    """圖 A 台股趨勢：指數線＋均線水平參考線。預設直接畫（讀本地 parquet，毫秒級、非外部抓取，故無 gate）。

    未載入（上游一個總經 key 都沒寫過）→ 灰字「⬜ 尚未載入，請按更新」，**不讀快取、不畫（不顯示過期值）**。
    趨勢結論固定 ⬜ 尚未定義。
    """
    with st.container(border=True):
        st.markdown(f"**{CHART_A_TITLE}**")
        st.markdown(CHART_A_SAY)
        _mkt = session.get("mkt_info")
        _refs, _bad = ma_reference_values(_mkt)
        _view = None
        if not today.upstream_requested(session):
            st.caption(NOT_LOADED)
        else:
            try:
                _view = twii_svc.get_twii_trend_view(TWII_CHART_TRADING_DAYS)
            except Exception as _e:  # noqa: BLE001 — 真例外：紅，且講出來（§1）
                print(f"[views/_market_blocks] 圖 A 讀取失敗：{_e!r}")
                st.error(f"台股指數歷史讀取失敗：`{scrub_secrets(repr(_e))}`", icon="❌")
            else:
                if _view.failed:
                    st.error(f"台股指數歷史讀取失敗：`{scrub_secrets(_view.error)}`", icon="❌")
                elif not _view.ok:
                    st.caption(f"⬜ 台股指數歷史暫時讀不到：{_view.error}")
                else:
                    if _view.is_stale:
                        st.warning(f"台股指數歷史快取已過期：{scrub_secrets(_view.stale_reason or '原因未提供')}", icon="⚠️")
                    elif _view.is_stale is None:
                        st.caption("⬜ 台股指數歷史快取的新鮮度未判定")
                    st.line_chart(twii_chart_frame(_view, _refs))
                    st.caption(f"近 {len(_view.close)} 日，資料至 {_view.as_of}　·　{twii_svc.TWII_SOURCE_TEXT}")
        if not isinstance(_mkt, Mapping) or not _mkt:
            st.caption(f"⬜ 均線：{NOT_LOADED}")
        elif _bad:
            st.caption("⬜ 缺少的均線：" + "、".join(f"{_n}：{_w}" for _n, _w in _bad))
        st.caption(CHART_A_MA_NOTE)
        st.markdown(f"**{CHART_A_MA_DISCLAIMER}**")
        st.markdown(f"{CHART_A_CONCLUSION}")
        st.caption(TREND_DEFINITION_NOTE)
        render_basis(basis_chart_a(_view, _mkt))


def render_chart_b(session: Mapping[str, Any], *, source_note: str) -> None:
    """圖 B 國際趨勢：按海外／利率／美元分組，每系列一張小圖。`cl_data['intl']` 在 session 就直接畫（記憶體內資料，無 gate）；未載入灰字。"""
    with st.container(border=True):
        st.markdown(f"**{CHART_B_TITLE}**")
        st.markdown(CHART_B_SAY)
        _series = intl_series(session)
        if _series is None:
            st.caption(NOT_LOADED)
        else:
            st.caption(source_note)
            _last_group = None
            for _s in _series:
                if _s.group != _last_group:
                    st.markdown(f"**{_s.group}**")
                    _last_group = _s.group
                st.markdown(f"{_s.name}　·　{_s.window_text}")
                if _s.status == "ok":
                    st.line_chart(_s.close)
                else:
                    st.caption("⬜ 本輪沒有這個系列" if _s.status == "absent" else "⬜ 沒有可用收盤")
            st.caption(CHART_B_NOTE)
        st.markdown(CHART_B_CONCLUSION)
        st.caption(TREND_DEFINITION_NOTE)
        render_basis(basis_chart_b(_series, source_note))


def chart_c_texts() -> tuple[str, ...]:
    """圖 C 區塊內的**全部**文字（供「零數字」測試）。"""
    return (CHART_C_TITLE, CHART_C_TAG, CHART_C_SAY, CHART_C_EMPTY, CHART_C_BASIS)


def render_chart_c() -> None:
    """圖 C 大盤合理區間：空框＋「研究框架，未啟用」。⛔ 區塊內零數值、零圖形、不畫區間標籤。"""
    with st.container(border=True):
        st.markdown(f"**{CHART_C_TITLE}**　`{CHART_C_TAG}`")
        st.markdown(CHART_C_SAY)
        st.caption(CHART_C_EMPTY)
        st.caption(CHART_C_BASIS)


def render_chart_d(risks: MarketRisks) -> None:
    """圖 D 主要風險：五桶各一列（與 hero 同一份 `risks`）；頂端「N 項未評估」。"""
    with st.container(border=True):
        st.markdown(f"**{CHART_D_TITLE}**")
        st.caption(CHART_D_NOTE)
        if risks.cold:
            st.caption(NOT_LOADED)
        elif risks.failed:
            st.error(f"五桶風險摘要算不出來：{scrub_secrets(risks.error)}", icon="❌")
        else:
            st.markdown(f"**{risks.n_unevaluated} 項未評估**（共 {risks.n_lamps} 項燈；未評估不等於安全）")
            st.markdown(_md_table(("風險桶（每桶一項）", "方向", "是否惡化"), risk_panel_rows(risks)))
        st.markdown(CHART_D_ALL_LAMPS_POINTER)
        render_basis(basis_risks(risks))


#: 供測試掃描「不得出現的詞」用：頁面各區塊字樣的聚合入口（不含動態資料）。
STATIC_TEXTS: tuple[str, ...] = (
    PAGE_TITLE, PAGE_SUBTITLE, NOT_LOADED, REGIME_SCOPE_CAPTION, WATER_TITLE, WATER_VALUE, WATER_WHY,
    HERO_RISK_TITLE, HERO_RISK_NO_RANKING_NOTE, HERO_AI_PLACEHOLDER, ALERTS_TITLE, ALERTS_NO_SOURCE,
    HEALTH_CHIP, CHART_A_TITLE, CHART_A_SAY, CHART_A_MA_DISCLAIMER, CHART_A_CONCLUSION, CHART_B_TITLE,
    CHART_B_SAY, CHART_B_CONCLUSION, CHART_C_TITLE, CHART_C_TAG, CHART_C_SAY, CHART_C_EMPTY, CHART_D_TITLE,
    CHART_D_NOTE, CHART_D_WORSENING, INSUFFICIENT_TEXT,
)
