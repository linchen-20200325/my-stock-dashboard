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

═══ Phase 4 P4-1（2026-10-30，客戶 DEC-117 已核准線框；有意識的修改，⛔ 不是漏刪）═══════════
第一屏改為「頁首 → 更新 CTA → 今日結論 → 3 個核心狀態 → ⚡ 需要處理 → AI／資料狀態 →（圖區，P4-2）」：
  · Q1=B：~~Hero 4 卡 `render_hero`（`st.columns(4)`）~~ → `render_core_tiles`（桌機 3 欄：市場位階｜建議總持股水位｜
    今日主要風險；手機 2＋1 走 `P4M_LAYOUT_CSS` 的窄螢幕規則，CSS 失效時退化為單欄堆疊，⛔ 不藏任何內容）。
    「🚀 更新今日戰情」改由 `render_update_cta` 畫在頁首（同一支 `single_submit_form`、同一組 session key）。
  · Q8b：更新模式 radio＋長說明收進「更新選項」摺疊（`single_submit_form(options_label=, options_note=)`）。
  · Q6=A：風險項外露縮短行（`risk_item_short_text`）；整句版 `risk_item_text`、`HERO_RISK_NO_RANKING_NOTE` 進 tile 的
    「🔍 查看依據」；退化／護欄句（未載入、算不出來、資料不足、全綠不代表安全）逐字外露（`hero_risk_face_lines`）。
  · Q2=A′：`DANGER_POINTER` 縮短（三要素「指標危險度」「指標明細（16 項）」「最上方」）；舊句原文保留為
    `DANGER_POINTER_UIM`，放風險 tile 的摺疊（資訊只下沉）。
  · Q3=A／U6：tile／⚡ 各**只有一個**「🔍 查看依據」；位階卡原 hover-only 的「位階的出處」與「生效分支」、
    原卡標題（含「總經契約」）併入位階 tile 的六欄（`basis_regime`），原卡整張畫在同一摺疊內。
  · Q8c：⚡ 需要處理＝一行 bar（`alerts_bar_line`）＋同一個「🔍 查看依據」摺疊內的完整清單（原卡、衝突提示）。
  · 圖 A～D 本批不動（P4-2）。

═══ Phase 4 P4-2（2026-10-30，客戶 DEC-117 Q4=P-B／Q3=A／Q8a；有意識的修改，⛔ 不是漏刪）═══════════
圖區改為「Primary（圖 A）→ Secondary（國際小倍數 → 圖 D → 圖 C）」，每張圖＝header（標題→chip→1 句，`compact.chart_header_html`）
→ 圖或誠實 placeholder → **恰一個**「▸ 為什麼／來源／限制／去哪補」摺疊（`render_chart_fold`；六欄依據依線框 §3.5 分四段，逐字）：
  · 圖 A：正式原生 `st.line_chart`（指數＋MA 水平參考線＋圖例＋y 軸），高 `PRIMARY_CHART_HEIGHT_PX`；冷啟動／讀不到同高槽（D6=B）；
    兩條護欄（均線聲明逐字、`⬜ 尚未定義`）各自獨立成 chip（D10(a)），來源 caption 下沉「來源」。
  · 圖 B：5 格 small multiples（`compact.small_multiples_html`＋`sparkline_svg`，⛔ 數字、⛔ 切換列）；缺系列格＝既有字樣；
    超過 8 字的兩個系列名用顯示名對映（`INTL_DISPLAY_NAMES`），正式全名在摺疊與 L2。
  · 圖 D：「是否惡化：⬜ 尚未定義」改成 header 護欄 chip（寫一次），表格兩欄；「N 項未評估（…未評估不等於安全）」外露。
  · 圖 C：一行（標題＋「研究框架，未啟用」chip＋`CHART_C_EMPTY`）；`CHART_C_SAY`→「為什麼」、`CHART_C_BASIS`→「來源」（Q8a）。
"""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
from shared import ia_nav
from shared.market_conclusion import CONCEPT_REGIME, CONCEPT_RISK_CAP, RISK_CAP_PENDING_TEXT
from shared.secret_scrub import scrub_secrets
from shared.signal_thresholds import TRADING_DAYS_PER_YEAR
from shared.ui_state import UI_DEGRADED, UI_EMPTY, UI_FAILED, UI_LIVE
from src.services import market_twii_view_service as twii_svc
from src.ui.views import page_today as today
from src.ui.views._ui_kit import single_submit_form
from src.ui_v2 import compact as cp

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
WATER_WHY: str = "正式 Risk Cap 尚未核准，此卡不顯示任何百分比。"
#: 事實（放「查看依據」而非首屏）：更新報告展開後的步驟說明可能列出本次寫檔的上限數值（現行行為，本批不改）。
#: 📌 QA 第二輪（2026-10-30；有意識的更新，不是漏刪；決策者 AI 總管）：~~「頁首「上一次更新的結果」展開後…」~~ 位置詞改用
#:   X3／X10 既有片段「頁首更新鈕下方的「上一次更新的結果」」—— DEC-118 D1 之後報告有真錯誤時在今日結論正下方，
#:   「頁首」字面不再成立，「頁首更新鈕下方」仍成立。其餘字逐字未改（本句非客戶原句：只出現在 UI-M 程式與 P4 文件）。
WATER_REPORT_DISCLOSURE: str = "頁首更新鈕下方的「上一次更新的結果」展開後，系統風險上限那一步的說明可能列出本次寫檔的數值（現行行為，不屬本卡）"
#: 圖 B「使用的資料」白話說明（內部對照：session cl_data['intl']；畫面不寫工程符號）。
CHART_B_SOURCE_PLAIN: str = ("Yahoo Finance 的國際指數、10 年債殖利率（^TNX）與美元指數"
                             "（本次更新抓到的資料；10 年債與總經區的 FRED 10 年債不同源）")
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
#: P4-4（A8）：圖 C 外露一行只畫 `CHART_C_EMPTY` 的第一句（逐字取自原句前半，不新造字；≤32 字）；整句 `CHART_C_EMPTY` 逐字進「為什麼」。
CHART_C_EMPTY_FACE: str = "需先核准：EPS 資料來源、PE 情境、計算公式、更新頻率。"
CHART_C_BASIS: str = "查看依據：此區塊未啟用，沒有使用任何資料。"

CHART_D_TITLE: str = "圖D ⚠️ 主要風險"
CHART_D_NOTE: str = "只顯示最需要注意的 3–5 項、方向、是否惡化。"
CHART_D_WORSENING: str = f"是否惡化：{NOT_DEFINED}"
#: 客戶裁示 3A（DEC-105）：「指標危險度」卡降階到下方展開區最上方 ⇒ 首屏必須清楚指路（字樣含「指標危險度」四字）。
#: 展開區標題字面與 `page_market` 的 expander 標題相同（由測試對帳）。
LAMP_DETAIL_EXPANDER_LABEL: str = "指標明細（16 項）"
#: 📌 P4-1（客戶 DEC-117 Q2=A′；有意識的修改，⛔ 不是漏刪）：~~UI-M 原句（38 字）~~ 縮到 ≤32 字，仍是說明句（⛔ chip），
#:   必須同時含「指標危險度」「指標明細（16 項）」「最上方」三要素（`tests/test_p4_1_market_first_screen.py` 釘字面）。
#:   UI-M 原句保留為 `DANGER_POINTER_UIM`，放在風險 tile 的「🔍 查看依據」內（只下沉，⛔ 刪）。
DANGER_POINTER_UIM: str = f"指標危險度（整體危險度與五桶摘要）請展開下方「{LAMP_DETAIL_EXPANDER_LABEL}」最上方。"
DANGER_POINTER: str = f"指標危險度：見下方「{LAMP_DETAIL_EXPANDER_LABEL}」最上方"
#: 指路句長度上限（契約 Gate A8：外露的非客戶原句 ≤32 字）。
DANGER_POINTER_MAX_CHARS: int = 32
CHART_D_ALL_LAMPS_POINTER: str = f"查看全部指標 › 請展開下方「{LAMP_DETAIL_EXPANDER_LABEL}」"
INSUFFICIENT_TEXT: str = "⬜ 資料不足／無法判定"

BASIS_EXPANDER_LABEL: str = "🔍 查看依據"

# ══════════════════════════════════════════════════════════════════
# P4-1（DEC-117）第一屏字樣
# ══════════════════════════════════════════════════════════════════
#: Q8b：更新模式 radio＋長說明收進的摺疊（客戶原文「移到『更新選項』」）。
UPDATE_OPTIONS_LABEL: str = "更新選項"
#: Q1：位階 tile 的標題＝結論句的概念名（L0 SSOT；原卡標題「市場位階（總經契約）」移入摺疊）。
REGIME_TILE_LABEL: str = CONCEPT_REGIME
#: Q8c：⚡ bar 上的衝突提示計數（清單本身原樣轉述在「🔍 查看依據」內）。
ALERTS_CONFLICTS_COUNT_FMT: str = "建議持股另附 {n} 則衝突／警示提示（見查看依據）"
#: Q6：tile 摺疊內整句版的小標（整句、燈說明、同級並列、不排序說明都在這一段）。
HERO_RISK_FULL_HEADING: str = "完整風險項（原句）"
#: Q1：手機 2＋1 用的容器 key（CSS class `.st-key-<key>`；Streamlit 非公開保證 ⇒ 失效時退化為單欄堆疊）。
P4M_CORE_TILES_KEY: str = "p4m_core_tiles"
#: C1-10／U4：L1 決策區（頁首～AI／資料狀態）的容器 key；窄螢幕只在這個容器內壓縮間距、內距與結論小標字級。
P4M_L1_KEY: str = "p4m_l1"
#: L1 內各個有框容器（3 tile、⚡）的 key 前綴：窄螢幕只縮它們的內距（`[class*="st-key-<前綴>"]`）。
P4M_BOX_KEY_PREFIX: str = "p4m_box_"
#: ⚠️ 只排版、⛔ 不藏任何東西：規則全部失效時＝Streamlit 預設（窄螢幕單欄堆疊、預設間距），
#:   沒有任何「靠 CSS 才顯示」的內容；⛔ display:none／visibility／height:0／overflow 截斷。
P4M_LAYOUT_CSS: str = (
    # QA 修正輪：L1 內所有摺疊內容（六欄依據裡的長 inline code）一律可在任意處換行，不溢出蓋到隔壁 tile（只換行、⛔ 截斷）。
    f".st-key-{P4M_L1_KEY} [data-testid=\"stExpander\"] details,"
    f".st-key-{P4M_L1_KEY} [data-testid=\"stExpander\"] details *{{overflow-wrap:anywhere !important;"
    "word-break:break-word !important;min-width:0 !important;}"
    # 📌 P4-2（線框 §10 C1-8「桌機 Primary header＋圖上緣在第一屏」；有意識的修改，⛔ 不是漏刪；決策者 AI 總管〔內部自決〕）：
    #   ~~以下四條 L1 間距／內距／摺疊標題列／結論小標規則只在窄螢幕（@media 內）~~ → 桌機也套用（只排版、⛔ 藏內容）。
    #   P4-1 時只為手機第一屏壓縮；桌機實量 Primary 標題 y941（第一屏外）⇒ 同一組規則擴到全寬。
    f".st-key-{P4M_L1_KEY},.st-key-{P4M_L1_KEY} [data-testid=\"stVerticalBlock\"]{{gap:0.5rem !important;}}"
    f".st-key-{P4M_L1_KEY} [class*=\"st-key-{P4M_BOX_KEY_PREFIX}\"],"
    f".st-key-{P4M_L1_KEY} [data-testid=\"stForm\"]{{padding:0.5rem 0.625rem !important;}}"
    f".st-key-{P4M_L1_KEY} [data-testid=\"stExpander\"] summary{{padding-top:0.3rem !important;"
    "padding-bottom:0.3rem !important;}"
    f".st-key-{P4M_L1_KEY} h4{{font-size:1rem !important;padding-top:0.25rem !important;"
    "padding-bottom:0.25rem !important;}"
    "@media (max-width: 640px){"
    f".st-key-{P4M_CORE_TILES_KEY} [data-testid=\"stHorizontalBlock\"]{{flex-wrap:wrap !important;gap:0.5rem !important;}}"
    f".st-key-{P4M_CORE_TILES_KEY} [data-testid=\"stHorizontalBlock\"] > [data-testid=\"stColumn\"]:nth-child(-n+2)"
    "{flex:1 1 calc(50% - 0.25rem) !important;min-width:calc(50% - 0.25rem) !important;"
    "width:calc(50% - 0.25rem) !important;}"
    f".st-key-{P4M_CORE_TILES_KEY} [data-testid=\"stHorizontalBlock\"] > [data-testid=\"stColumn\"]:nth-child(3)"
    "{flex:1 1 100% !important;min-width:100% !important;width:100% !important;}"
    "}")
#: 內部對照：L2 compute_five_bucket_summary（16 盞燈）＋ L2 lamp_direction；畫面只寫白話。
RISK_DATA_PLAIN: str = "五桶風險摘要（16 項指標燈）＋各燈的變化方向"
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


def risk_item_short_text(row: BucketRiskRow) -> str:
    """P4-1（客戶 DEC-117 Q6=A）外露縮短行：**燈色＋桶名＋燈名＋方向**（方向＝L2 原詞，⛔ 翻成惡化／好轉）。

    整句版（燈說明、「｜方向：」、「｜同級並列 N 項」）照舊由 `risk_item_text` 產生，放 tile 的「🔍 查看依據」。
    """
    return f"{LEVEL_EMOJI[row.level]} {row.title}：{row.lamp_label}　{row.direction_word}"


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


def hero_risk_face_lines(risks: MarketRisks) -> list[tuple[str, str]]:
    """P4-1 風險 tile **外露層**要畫的行（Q6=A）。

    - 有風險項：項目行換成縮短行；「另 K 項見圖 D」「另有 N 桶資料不足、無法判定（見圖 D）」照舊外露；
      只有 `HERO_RISK_NO_RANKING_NOTE`（排列說明）下沉到摺疊。
    - 沒有風險項（未載入／算不出來／全部不足／部分不足／全綠）：**與 `hero_risk_lines` 逐字相同**——
      這些退化／護欄句（含「不代表安全」）客戶明示必須外露逐字保留，⛔ 縮、⛔ 移進摺疊。
    """
    _full = hero_risk_lines(risks)
    _items, _ = hero_risk_items(risks)
    if not _items:
        return _full
    return ([("item", risk_item_short_text(_r)) for _r in _items]
            + [(_t, _x) for _t, _x in _full if _t != "item" and _x != HERO_RISK_NO_RANKING_NOTE])


def hero_risk_fold_lines(risks: MarketRisks) -> list[tuple[str, str]]:
    """P4-1 風險 tile 摺疊內的整句版（＝UI-M 外露的那一份，逐字）；沒有風險項時外露層已是全文 ⇒ 空。"""
    _items, _ = hero_risk_items(risks)
    return hero_risk_lines(risks) if _items else []


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


def render_basis(basis: Basis, *, extra: Callable[[], None] | None = None,
                 lead: Callable[[], None] | None = None) -> None:
    """預設收合的「🔍 查看依據」。`extra`＝展開後在六欄下面多畫的內容（例：水位卡的原有出手區間）；
    `lead`（P4-1 加性）＝畫在六欄**上面**的內容（例：⚡ 的完整清單 —— 展開後先看到清單，再看依據）。"""
    with st.expander(BASIS_EXPANDER_LABEL, expanded=False):
        if lead is not None:
            lead()
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
def basis_regime(regime_tile: Any) -> Basis:
    """P4-1 位階 tile 的六欄（Q3=A／U6）：原卡標題、原 hover-only 的「位階的出處」與「生效分支」等**全部 facts 逐字**
    寫進「規則／計算結果」—— 從此不再只活在 `title=`（手機無 hover）。非 live 態把卡上的 now／why 寫進 missing。"""
    _card = regime_tile.card
    _facts = "；".join(f"{_k}：{_v}" for _k, _v in tuple(getattr(regime_tile, "facts", ()) or ()))
    _rule = f"卡片原標題「{_card.label}」" + (f"；{_facts}" if _facts else "")
    if _card.state == UI_LIVE:
        _missing = "—（本卡本輪有值）"
    else:
        _note = getattr(_card, "note", None)
        _bits = [str(getattr(_note, _a, "") or "").replace("**", "").strip() for _a in ("now", "why")]
        _missing = "；".join(_b for _b in _bits if _b) or "⬜ 卡片沒有提供原因"
    return Basis(
        data_used="市場位階契約（總經狀態；仲裁後的位階與生效分支）",
        as_of=ASOF_CONTRACT_MISSING,
        rule=_rule,
        missing=_missing,
        confidence="⬜ 契約未提供（紅綠燈資料來源齊備程度見下方「市場位階：為什麼？」的信心度）",
        ai=AI_NOT_INVOLVED)


def basis_water(alloc: Any, alloc_error: str) -> Basis:
    if alloc is None:
        _missing = (f"建議持股讀取失敗：{scrub_secrets(alloc_error)}" if alloc_error
                    else "建議持股尚未載入（見下方原卡說明）")
    else:
        _missing = "本頁未另做缺漏檢查，沿用下方原卡的說明"
    return Basis(
        data_used="建議持股結果（姿態油門與各項上限取小；含 risk_cap.v2 規則）",
        as_of=ASOF_CONTRACT_MISSING,
        rule=("首屏固定顯示「尚未核准／無法判定」；原有出手區間只放在本展開區，且未經 C2b 核准。" + WATER_REPORT_DISCLOSURE),
        missing=_missing + "；" + WATER_REPORT_DISCLOSURE,
        confidence="⬜ 契約未提供",
        ai=AI_NOT_INVOLVED)


def basis_risks(risks: MarketRisks) -> Basis:
    """hero「今日主要風險」與圖 D 共用的依據（同一份 `risks`）。"""
    if risks.cold:
        return Basis(
            data_used=RISK_DATA_PLAIN,
            as_of=ASOF_CONTRACT_MISSING, rule="尚未載入，沒有可列的風險項",
            missing=NOT_LOADED, confidence="⬜ 契約未提供", ai=AI_NOT_INVOLVED)
    if risks.failed:
        return Basis(
            data_used="五桶風險摘要",
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
        data_used=RISK_DATA_PLAIN,
        as_of=f"{ASOF_CONTRACT_MISSING}；方向列各自的資料日：{_dirs}",
        rule=("每桶取桶內既有的主因燈（沿用五桶摘要既有的挑法：桶內最差、超標最多者）；只列非綠桶、依五桶固定順序、最多 3 項、"
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
        data_used="今日關鍵警示＋建議持股附帶的衝突提示",
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
        _line = f"指數線：{NOT_LOADED}"
        _avail = f"⬜ 契約未提供（指數線{NOT_LOADED}）"
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
        data_used=f"{twii_svc.TWII_SOURCE_TEXT}；均線取自『市場評估』結果",
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


def basis_chart_b(series: list[IntlSeries] | None) -> Basis:
    source_note = CHART_B_SOURCE_PLAIN
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
#: 資料日的來源說明（原與日期同一句外露；P4-4 A8 只下沉：外露層只留「資料日：YYYY-MM-DD」，本句逐字進「資料來源與完整度」）。
DATA_DATE_SOURCE_NOTE: str = "（加權指數，來源：市場評估輸入）"


def data_date_text(mkt_info: Any, *, full: bool = True) -> str:
    """更新卡的「資料日」＝`mkt_info['index_as_of']`（市場評估用的加權指數最後一根）；取不到 → ⬜。

    📌 P4-4（A8，有意識的修改，⛔ 不是漏刪；決策者 AI 總管〔v3 §03-1 內部自決〕）：`full=True`（預設）＝原整句不變
    （`資料日：{日期}（加權指數，來源：市場評估輸入）`）；`full=False`＝外露層短版（只到日期，取自原句前半，不新造字）。
    被拿掉的後半句＝`DATA_DATE_SOURCE_NOTE`，由 `page_market` 以 `full=True` 逐字放進「資料來源與完整度」展開區。"""
    _v = mkt_info.get("index_as_of") if isinstance(mkt_info, Mapping) else None
    _s = str(_v).strip()[:10] if _v is not None else ""
    if not _s:
        return DATA_DATE_NOT_PROVIDED
    return f"資料日：{_s}" + (DATA_DATE_SOURCE_NOTE if full else "")


def _render_lines(lines: Sequence[tuple[str, str]]) -> None:
    for _tone, _text in lines:
        if _tone == "error":
            st.error(_text, icon="❌")
        elif _tone == "item":
            st.markdown(_text)
        else:
            st.caption(_text)


def render_layout_css() -> None:
    """P4-1 版面規則（手機 2＋1、L1 決策區窄螢幕間距壓縮）。由 `page_market` 在 L1 決策區之前呼叫一次。
    ⚠️ 只排版：全部失效時＝Streamlit 預設單欄堆疊與預設間距，⛔ 沒有任何內容靠 CSS 才看得到。

    📌 P4-2（有意識的修改，⛔ 不是漏刪）：同一個 `<style>` 另帶 `compact.compact_css()`（圖區 chip／header／小倍數元件樣式；
    顏色引用 `page_today._inject_v2_css` 已注入的 `page_css` token）—— ⛔ 多一個 `<style>` 元素（不在圖區前多出一個元素，
    C1-7「AI 行之後緊接 Primary」）。`compact_css()` 本身不改（Phase 3 golden）。"""
    st.markdown(f"<style>{P4M_LAYOUT_CSS}\n{cp.compact_css()}</style>", unsafe_allow_html=True)


def update_options_note(session: Mapping[str, Any]) -> str:
    """「更新選項」摺疊內那一句：與 `page_today._render_update_form` 鍵下 caption **同一組常數、同一格式**（逐字）。"""
    _mode = today.applied_update_mode(session)
    return (f"已套用的更新模式：**{today.MODE_LABELS[_mode] if _mode else '（尚未送出過）'}**"
            f"　·　⚠️ {today.PAGE_REFRESH_SCOPE_WHY}。{today.REFRESH_SPEED_HINT}")


def render_update_cta(session: Mapping[str, Any]) -> None:
    """P4-1 頁首主 CTA（DEC-117 Q1／Q8b）：「🚀 更新今日戰情」＋預設收合的「更新選項」（radio＋已套用模式＋長說明）。

    ⛔ 不是第二套更新流程：form key、radio 的 widget／已套用 key、選項與顯示名、模式對映、重抓函式、報告 key
    **全部是 `page_today` 的同一組 SSOT**（經模組屬性取用）；與今天頁唯一的差別是 radio 與說明收進摺疊
    （`single_submit_form(options_label=, options_note=)`）。form 語意不變：只有按鈕送出才重抓、radio 不即時 rerun、
    單次 submit；送出後報告落 session → `st.rerun()`，下一輪由頁首的更新報告畫出（同今天頁）。
    """
    _submitted = single_submit_form(
        today.FORM_KEY,
        submit_label=ia_nav.action_label(ia_nav.ACTION_UPDATE_TODAY),
        radio_label="更新模式",
        options=tuple(today.MODE_LABELS),
        option_labels=today.MODE_LABELS,
        widget_key=today.SS_MODE_WIDGET,
        applied_key=today.SS_APPLIED_MODE,
        options_label=UPDATE_OPTIONS_LABEL,
        options_note=update_options_note(session),
    )
    if not _submitted:
        return
    _mode = today.applied_update_mode(session)
    if _mode not in today.UPDATE_MODE_TO_REFRESH_MODE:
        # §1：對不上就出聲（同今天頁），⛔ 拿一個預設模式假裝使用者選了它。
        st.error(f"未知的更新模式 `{_mode!r}` —— 本頁不替你挑一個模式跑。", icon="❌")
        return
    st.session_state[today.SS_REFRESH_REPORT] = today._run_refresh_now(
        today.UPDATE_MODE_TO_REFRESH_MODE[_mode])
    st.rerun()


def regime_failed_reason(regime_tile: Any, regime_error_line: str) -> str:
    """位階 tile 真錯誤的外露原因（QA 修正輪，客戶 Q6「真錯誤必須外露逐字」）：讀契約拋例外 ⇒ `page_market` 傳入的
    X1 既有紅字（「市場位階契約讀不出來：…」逐字）；其餘 failed（例：上一次更新的紅綠燈步驟失敗）⇒ 卡上既有 `why`。
    ⛔ 新造文案；兩者都沒有 ⇒ 空字串（不補一句）。"""
    if regime_error_line:
        return regime_error_line
    return str(getattr(getattr(regime_tile.card, "note", None), "why", "") or "").strip()


def _render_regime_face(regime_tile: Any, face: str, badge: str, error_line: str = "") -> None:
    """位階 tile 外露值：有值（live／degraded）＝粗體＋徽章字；真錯誤＝紅（外露值＋原因同一個紅框）；其餘＝灰。"""
    _state = regime_tile.card.state
    if _state == UI_FAILED:
        _why = regime_failed_reason(regime_tile, error_line)
        st.error(f"{face}\n\n{_why}" if _why else face, icon="❌")
    elif _state in (UI_LIVE, UI_DEGRADED):
        st.markdown(f"**{face}**" + (f"　{badge}" if badge else ""))
    else:
        st.caption(face)


def render_core_tiles(*, regime_tile: Any, regime_face: str, regime_badge: str, exposure_tile: Any,
                      alloc: Any, alloc_error: str, risks: MarketRisks, coverage_text: str,
                      regime_error_line: str = "") -> None:
    """P4-1 三個核心狀態 tile（DEC-117 Q1=B）：市場位階｜建議總持股水位｜今日主要風險。

    桌機 3 欄；手機 2＋1（`P4M_LAYOUT_CSS`）。每張 tile **只有一個**「🔍 查看依據」（Q3=A／U6）。
    `regime_face`／`regime_badge` 由 `page_market` 以結論句同一支 `regime_clause`／`card_badge_text` 算好傳入
    （tile 與結論句同字，⛔ 另寫一套說法）。`coverage_text` ＝ `page_market.status_line` 的覆蓋率那一半（逐字）。
    """
    with st.container(key=P4M_CORE_TILES_KEY):
        _cols = st.columns(3)
        with _cols[0]:
            with st.container(border=True, key=f"{P4M_BOX_KEY_PREFIX}regime"):
                st.markdown(f"**{REGIME_TILE_LABEL}**")
                _render_regime_face(regime_tile, regime_face, regime_badge, regime_error_line)
                st.caption(REGIME_SCOPE_CAPTION)
                render_basis(basis_regime(regime_tile), extra=lambda: today._render_one(regime_tile))
        with _cols[1]:
            with st.container(border=True, key=f"{P4M_BOX_KEY_PREFIX}water"):
                st.markdown(f"**{WATER_TITLE}**")
                st.markdown(f"**{WATER_VALUE}**")
                st.caption(f"{CONCEPT_RISK_CAP}：{RISK_CAP_PENDING_TEXT}")

                def _original_range() -> None:
                    st.caption(WATER_WHY)
                    st.caption(WATER_BASIS_NOTE)
                    today._render_one(exposure_tile)
                render_basis(basis_water(alloc, alloc_error), extra=_original_range)
        with _cols[2]:
            with st.container(border=True, key=f"{P4M_BOX_KEY_PREFIX}risk"):
                st.markdown(f"**{HERO_RISK_TITLE}**")
                _render_lines(hero_risk_face_lines(risks))
                st.caption(DANGER_POINTER)
                st.caption(coverage_text)

                def _full_risk_lines() -> None:
                    _fold = hero_risk_fold_lines(risks)
                    if _fold:
                        st.markdown(f"**{HERO_RISK_FULL_HEADING}**")
                        _render_lines(_fold)
                    st.caption(DANGER_POINTER_UIM)
                render_basis(basis_risks(risks), extra=_full_risk_lines)


def ai_status_line_face() -> str:
    """AI／資料狀態一行的外露短版＝`HERO_AI_PLACEHOLDER`＋`HEALTH_CHIP`（原句前兩段，不新造字；P4-4 A8，≤32 字）。"""
    return f"{HERO_AI_PLACEHOLDER}　{HEALTH_CHIP}"


def ai_status_line_full() -> str:
    """AI／資料狀態一行的**原整句**（DEC-105 第 5 點合併一行的原字樣）。P4-4 起不外露，逐字放進「資料來源與完整度」展開區。"""
    return f"{ai_status_line_face()}{HEALTH_CHIP_POINTER}"


def render_ai_status_line() -> None:
    """AI／資料狀態一行（DEC-105 第 5 點合併一行；位置由 DEC-117 Q5 定在 ⚡ 之後、圖區之前）。

    📌 P4-4（A8，有意識的修改，⛔ 不是漏刪；決策者 AI 總管〔v3 §03-1 內部自決〕）：外露層只畫 `ai_status_line_face()`（前兩段，
    原整句 44 字 → 外露 ≤32 字）；後半的 `HEALTH_CHIP_POINTER`（指路句）連同原整句 `ai_status_line_full()` 逐字下沉到
    「資料來源與完整度」展開區（資訊只下沉、不刪）。"""
    st.caption(ai_status_line_face())


def alerts_has_listable_source(alerts: Any, alloc: Any) -> bool:
    _items = (alerts or {}).get("items") if isinstance(alerts, Mapping) else None
    return bool(_items) or bool(getattr(alloc, "conflicts", ()) if alloc is not None else ())


def alerts_bar_line(alerts_tile: Any, alerts: Any, alloc: Any) -> tuple[str, str]:
    """P4-1（DEC-117 Q8c）⚡ 一行 bar：`(tone, text)`；tone ∈ item／grey／error（同 `_render_lines`）。

    字一律取自既有卡：有值＝卡的 label＋value（例「今日關鍵：1 紅 · 1 黃」）；其餘態＝卡上 `now` 那一句（例「今日關鍵
    尚未載入 —— 未評估 ≠ 無異常」）。三態判別仍由 `build_key_alert_tile` 負責（⛔ 本函式不另判）。
    沒有可列來源 ⇒ 同一行明寫 `ALERTS_NO_SOURCE`（⛔ 不寫沒事）；真錯誤（卡 failed）＝紅；未載入／未評估＝灰。
    """
    _card = alerts_tile.card
    _state = _card.state
    if _state == UI_LIVE:
        _summary = f"{_card.label}：{_card.value}"
    else:
        _summary = str(getattr(_card.note, "now", "") or "").replace("**", "").strip() or _card.label
    _bits = [f"**{ALERTS_TITLE}**　{_summary}"]
    if _state == UI_DEGRADED and isinstance(alerts, Mapping):
        # QA 修正輪：degraded（有值、只含急變層）照樣帶紅／黃計數 —— 格式同 `build_key_alert_tile` live 態的 value。
        _bits.append(f"{int(alerts.get('n_red') or 0)} 紅 · {int(alerts.get('n_yellow') or 0)} 黃")
    if _state == UI_FAILED:
        # QA 修正輪（客戶 Q6「真錯誤必須外露逐字」）：卡上既有的原因句（`why`）逐字外露在紅 bar 上。
        _why = str(getattr(_card.note, "why", "") or "").strip()
        if _why:
            _bits.append(_why)
    _conf = list(getattr(alloc, "conflicts", ()) or ()) if alloc is not None else []
    if _conf:
        _bits.append(ALERTS_CONFLICTS_COUNT_FMT.format(n=len(_conf)))
    if not alerts_has_listable_source(alerts, alloc):
        _bits.append(ALERTS_NO_SOURCE)
    _tone = "error" if _state == UI_FAILED else ("item" if _state in (UI_LIVE, UI_DEGRADED) else "grey")
    return _tone, "　".join(_bits)


def render_alerts_block(*, alerts_tile: Any, alerts: Any, scanned: bool, alerts_error: str, alloc: Any) -> None:
    """⚡ 需要處理（P4-1：一行 bar＋同一個「🔍 查看依據」內的完整清單）。只轉述既有警示＋建議持股的衝突提示。

    摺疊內先畫完整清單（原「今日關鍵」卡整張、衝突提示原文與數字說明），再畫六欄依據 —— 資訊只下沉，⛔ 刪。
    """
    _conf = list(getattr(alloc, "conflicts", ()) or ()) if alloc is not None else []

    def _full_list() -> None:
        today._render_one(alerts_tile)
        if _conf:
            st.markdown(f"**{ALERTS_CONFLICTS_HEADING}**")
            st.markdown("\n".join(f"- {_cell(_c)}" for _c in _conf))
            st.caption(ALERTS_CONFLICTS_NUMBER_NOTE)
    with st.container(border=True, key=f"{P4M_BOX_KEY_PREFIX}alerts"):
        _render_lines([alerts_bar_line(alerts_tile, alerts, alloc)])
        render_basis(basis_alerts(alerts, scanned, alerts_error, alloc), lead=_full_list)


# ══════════════════════════════════════════════════════════════════
# P4-2（客戶 DEC-117 Q4=P-B／Q3=A／Q8a；線框 §10 C3-1／C4-1～C4-6／C8-a／C8-0）圖區
# ══════════════════════════════════════════════════════════════════
#: 圖表摺疊入口（客戶 DEC-109 五原文字樣；DEC-117 Q3=A：圖用四段、tile／⚡ 維持「🔍 查看依據」）。每張圖恰一個。
FOLD_LABEL: str = "▸ 為什麼／來源／限制／去哪補"
#: 四段（契約 §4：固定四段，不適用寫「—」並說明）。
FOLD_SECTIONS: tuple[str, ...] = ("為什麼", "來源", "限制", "去哪補")
#: 六欄 Basis → 四段（線框 §3.5；「去哪補」六欄沒有對應欄，由各圖另給）。
BASIS_TO_FOLD: Mapping[str, tuple[str, ...]] = {
    "為什麼": ("rule", "ai"), "來源": ("data_used", "as_of"), "限制": ("missing", "confidence"), "去哪補": ()}
#: 「去哪補」指向 L2 展開區的句型 —— **既有片段**（`CHART_D_ALL_LAMPS_POINTER`／`DANGER_POINTER_UIM` 的「請展開下方「…」」），
#: 只換成該圖詳細數值所在的既有展開區標題（由 `page_market` 傳入同一個字串，⛔ 另抄一份）。
FOLD_WHERE_FMT: str = "請展開下方「{label}」"
#: 「不適用寫『—』並說明」（契約 §4）的句型 —— 沿用本檔既有「—（…）」寫法（例 `—（本卡本輪有值）`）；說明一律取既有常數。
FOLD_NOT_APPLICABLE_FMT: str = "—（{why}）"
#: Primary 圖高（契約 §19 Q3 桌機上限＝`compact.SLOT_HEIGHT_MAX_PX`；冷啟動／讀不到時的槽同高，D6=B）。
PRIMARY_CHART_HEIGHT_PX: int = cp.SLOT_HEIGHT_MAX_PX
#: 小倍數 SVG 的 viewBox（寬 300 × 高 64；高＝`compact.SPARK_HEIGHT_MAX_PX`，格寬縮放時等比）。
SM_SPARK_W: int = 300
SM_SPARK_H: int = cp.SPARK_HEIGHT_MAX_PX
#: 缺系列格（既有字樣，線框 Phase 3 §3.7／Phase 4 §10 C4-2 指定逐字沿用）。
SM_MISSING_ABSENT: str = "⬜ 本輪沒有這個系列"
SM_MISSING_EMPTY: str = "⬜ 沒有可用收盤"
#: 線框 F-3：小倍數格名 ≤`compact.SM_NAME_MAX_CHARS`（8）字。**只對映超過上限的兩個系列**（顯示名，⛔ 改 `INTL_GROUPS`／
#: `INTL_MAP` 的正式名）；簡稱取自已核准線框（Phase 3 §3.7／Phase 4 §4.1）。正式全名在摺疊「來源」與 L2「國際市場」表格。
INTL_DISPLAY_NAMES: Mapping[str, str] = {"納斯達克 IXIC": "那指 IXIC", "費城半導體 SOX": "費半 SOX"}
#: 圖區容器 key（DOM 量測與窄螢幕排版用；`.st-key-<key>`）。
P4M_PRIMARY_KEY: str = "p4m_primary"
P4M_SECONDARY_KEY_PREFIX: str = "p4m_secondary_"
_TW_TZ = timezone(timedelta(hours=8))

FoldLine = tuple[str, str]   # (tone, text)；tone ∈ md／caption／warning


@dataclass(frozen=True)
class ChartFold:
    """圖表摺疊的四段內容（每段 ≥1 行；空段 ⇒ `ValueError`：不適用必須寫「—」並說明，⛔ 留白）。"""

    why: tuple[FoldLine, ...]
    source: tuple[FoldLine, ...]
    limit: tuple[FoldLine, ...]
    where: tuple[FoldLine, ...]

    def sections(self) -> tuple[tuple[str, tuple[FoldLine, ...]], ...]:
        _out = tuple(zip(FOLD_SECTIONS, (self.why, self.source, self.limit, self.where)))
        for _name, _lines in _out:
            if not _lines or not all(str(_t).strip() for _, _t in _lines):
                raise ValueError(f"圖表摺疊「{_name}」不得留白（不適用寫「—」並說明）")
            for _tone, _ in _lines:
                if _tone not in ("md", "caption", "warning"):
                    raise ValueError(f"圖表摺疊行的 tone 不合法：{_tone!r}")
        return _out


def chart_fold(basis: Basis | None, *, why: Sequence[FoldLine] = (), source: Sequence[FoldLine] = (),
               limit: Sequence[FoldLine] = (), where: Sequence[FoldLine] = ()) -> ChartFold:
    """六欄 Basis（有的話）依 `BASIS_TO_FOLD` 分到四段（同一格式「- **欄名**：內容」、逐字），再接各段額外行。
    六欄內容一字不改（資訊守恆：原「🔍 查看依據」的每一欄都在某一段）。"""
    _extra = {"為什麼": tuple(why), "來源": tuple(source), "限制": tuple(limit), "去哪補": tuple(where)}
    _rows = dict(zip((_a for _, _a in BASIS_FIELDS), basis_rows(basis))) if basis is not None else {}
    _sec: dict[str, tuple[FoldLine, ...]] = {}
    for _name in FOLD_SECTIONS:
        _attrs = [_a for _a in BASIS_TO_FOLD[_name] if _a in _rows]
        _md = "\n".join(f"- **{_rows[_a][0]}**：{scrub_secrets(_rows[_a][1])}" for _a in _attrs)
        _sec[_name] = ((("md", _md),) if _md else ()) + _extra[_name]
    return ChartFold(why=_sec["為什麼"], source=_sec["來源"], limit=_sec["限制"], where=_sec["去哪補"])


def render_chart_fold(fold: ChartFold) -> None:
    """每張圖**恰一個**摺疊（預設收合）：四段依序「**段名**」＋內容。"""
    _sections = fold.sections()          # 先驗（留白就紅），再畫
    with st.expander(FOLD_LABEL, expanded=False):
        for _name, _lines in _sections:
            st.markdown(f"**{_name}**")
            for _tone, _text in _lines:
                if _tone == "warning":
                    st.warning(_text, icon="⚠️")
                elif _tone == "caption":
                    st.caption(_text)
                else:
                    st.markdown(_text)


def render_chart_header(*, title: str, chips: Sequence[Any], say: str | None,
                        say_verbatim: bool = True) -> tuple[Any, ...]:
    """圖 header（契約 §4：標題 → chip 列 → 1 句；`compact.chart_header_html`）。回傳溢出 chip（交摺疊「來源」）。
    ⚠️ 走 `st.markdown(unsafe_allow_html=True)`（線框 F-4：`st.html` 會剝行內 svg；header 本身沒有 svg，同一路徑保持一致）。"""
    _html, _overflow = cp.chart_header_html(title=title, chips=list(chips), say=say,
                                            say_verbatim=say_verbatim, title_verbatim=True)
    st.markdown(_html, unsafe_allow_html=True)
    return _overflow


def _overflow_lines(overflow: Sequence[Any]) -> tuple[FoldLine, ...]:
    return tuple(("caption", str(_c.text)) for _c in overflow)


def asof_chip_value(as_of: Any, *, today_date: Any = None) -> str | None:
    """資料日 → chip 值（契約 §6：`MM/DD`，跨年 `YYYY/MM/DD`）；不是 `YYYY-MM-DD` ⇒ None（不出 chip，⛔ 猜一個日期）。
    `today_date`（`date`；預設＝台北今天）只用來判斷是否跨年。"""
    _s = str(as_of or "").strip()[:10]
    try:
        _d = datetime.strptime(_s, "%Y-%m-%d").date()
    except ValueError:
        return None
    _today = today_date if today_date is not None else datetime.now(_TW_TZ).date()
    return f"{_d:%m/%d}" if _d.year == _today.year else f"{_d:%Y/%m/%d}"


# ── 圖 A（Primary）─────────────────────────────────────────────
def chart_a_chips(view: twii_svc.TwiiTrendView | None, *, today_date: Any = None) -> list[Any]:
    """圖 A header chip（DEC-115 D10(a)：兩條護欄各自獨立、來源下沉）：均線聲明（逐字）＋`⬜ 尚未定義`＋（有圖時）資料日、
    窗口、可讀性（✅ 可讀＝未過期；⚠ 過期；新鮮度未判定＝不給 ✅，原句在摺疊「限制」）。"""
    _chips: list[Any] = [cp.guard_chip(CHART_A_MA_DISCLAIMER), cp.meta_chip("not_defined")]
    if view is None or not view.ok:
        return _chips
    _asof = asof_chip_value(view.as_of, today_date=today_date)
    if _asof:
        _chips.append(cp.meta_chip("asof", _asof))
    _chips.append(cp.meta_chip("window", f"近 {len(view.close)} 日"))
    if view.is_stale is True:
        _chips.append(cp.meta_chip("stale", f"{view.age_days} 天") if view.age_days is not None
                      else cp.meta_chip("stale"))
    elif view.is_stale is False:
        _chips.append(cp.meta_chip("readable"))
    return _chips


def chart_a_fold(view: twii_svc.TwiiTrendView | None, mkt_info: Any, *, requested: bool, where_label: str,
                 overflow: Sequence[Any] = ()) -> ChartFold:
    """圖 A 摺疊：原外露的趨勢結論句、來源 caption、均線說明、缺均線清單、過期／新鮮度、趨勢定義說明**全部下沉到這裡**（逐字）。"""
    _, _bad = ma_reference_values(mkt_info)
    _source: list[FoldLine] = []
    _limit: list[FoldLine] = []
    if view is not None and view.ok:
        _source.append(("caption", f"近 {len(view.close)} 日，資料至 {view.as_of}　·　{twii_svc.TWII_SOURCE_TEXT}"))
        if view.is_stale:
            _limit.append(("warning", f"台股指數歷史快取已過期：{scrub_secrets(view.stale_reason or '原因未提供')}"))
        elif view.is_stale is None:
            _limit.append(("caption", "⬜ 台股指數歷史快取的新鮮度未判定"))
    if not isinstance(mkt_info, Mapping) or not mkt_info:
        _limit.append(("caption", f"⬜ 均線：{NOT_LOADED}"))
    elif _bad:
        _limit.append(("caption", "⬜ 缺少的均線：" + "、".join(f"{_n}：{_w}" for _n, _w in _bad)))
    _limit += [("caption", CHART_A_MA_NOTE), ("caption", TREND_DEFINITION_NOTE)]
    _where: list[FoldLine] = [] if requested else [("caption", NOT_LOADED)]
    _where.append(("caption", FOLD_WHERE_FMT.format(label=where_label)))
    # 趨勢結論句 `CHART_A_CONCLUSION` 已在六欄「規則／計算結果」內逐字（`basis_chart_a`）⇒ 不再另列一行（同段重複）。
    return chart_fold(basis_chart_a(view, mkt_info),
                      source=(*_source, *_overflow_lines(overflow)), limit=_limit, where=_where)


def render_chart_a(session: Mapping[str, Any], *, where_label: str) -> None:
    """圖 A 台股趨勢＝**Primary Visual**（DEC-117 Q4=P-B）：header（標題→chip→客戶原句）→ 正式原生圖（指數＋MA 水平參考線
    ＋圖例＋y 軸，高 `PRIMARY_CHART_HEIGHT_PX`）→ 恰一個四段摺疊。預設直接畫（讀本地 parquet，毫秒級、非外部抓取，故無 gate）。

    未載入（上游一個總經 key 都沒寫過）→ 同高槽內灰字「⬜ 尚未載入，請按更新」，**不讀快取、不畫（不顯示過期值）**；
    讀不到＝灰、真例外＝紅（字串逐字沿用，外露在槽內）。趨勢結論固定 `⬜ 尚未定義`（header chip；原句在摺疊「為什麼」）。
    """
    with st.container(border=True, key=P4M_PRIMARY_KEY):
        _mkt = session.get("mkt_info")
        _refs, _ = ma_reference_values(_mkt)
        _view = None
        _slot: list[tuple[str, str]] = []
        _requested = True
        if not today.upstream_requested(session):
            _requested = False
            _slot = [("grey", NOT_LOADED)]
        else:
            try:
                _view = twii_svc.get_twii_trend_view(TWII_CHART_TRADING_DAYS)
            except Exception as _e:  # noqa: BLE001 — 真例外：紅，且講出來（§1）
                print(f"[views/_market_blocks] 圖 A 讀取失敗：{_e!r}")
                _slot = [("error", f"台股指數歷史讀取失敗：`{scrub_secrets(repr(_e))}`")]
            else:
                if _view.failed:
                    _slot = [("error", f"台股指數歷史讀取失敗：`{scrub_secrets(_view.error)}`")]
                elif not _view.ok:
                    _slot = [("grey", f"⬜ 台股指數歷史暫時讀不到：{scrub_secrets(_view.error)}")]
        _overflow = render_chart_header(title=CHART_A_TITLE, chips=chart_a_chips(_view), say=CHART_A_SAY)
        if _slot:
            # D6=B：Primary 冷啟動／讀不到保持正式高度（⛔ 縮掉造成載入前後跳動）；槽內只有誠實的一句。
            with st.container(height=PRIMARY_CHART_HEIGHT_PX, border=True):
                _render_lines(_slot)
        else:
            # 正式原生圖（Q4：MA 參考線、y 軸、圖例保留 —— 多序列 DataFrame 欄名＝圖例；⛔ 以參數或 CSS 隱藏軸）。
            st.line_chart(twii_chart_frame(_view, _refs), height=PRIMARY_CHART_HEIGHT_PX)
        render_chart_fold(chart_a_fold(_view, _mkt, requested=_requested, where_label=where_label,
                                       overflow=_overflow))


# ── 圖 B（Secondary：國際 small multiples）──────────────────────
def intl_core_series(series: Sequence[IntlSeries]) -> list[IntlSeries]:
    """小倍數的 5 格＝`INTL_GROUPS` 的 5 個系列（固定順序；`intl_series` 對缺的系列也會給一列 `absent`）。
    其他（未分組）系列不進格（格數固定 5，C4-2），在摺疊「來源」逐列列出（只下沉，⛔ 丟）。"""
    _by = {_s.name: _s for _s in series}
    return [_by.get(_n, IntlSeries(_g, _n, "absent")) for _g, _ns in INTL_GROUPS for _n in _ns]


def intl_display_name(name: str) -> str:
    return INTL_DISPLAY_NAMES.get(name, name)


def chart_b_parts(series: Sequence[IntlSeries] | None, *, today_date: Any = None) -> tuple[list[Any], list[Any]]:
    """圖 B → `(組級 chip, 小倍數格)`。chip：`⬜ 尚未定義`（一律）＋資料日（各系列相同時才寫一次）＋窗口（相同時寫一次；
    不同時改寫在各格）。格：5 格固定順序；有 ≥2 點畫 sparkline（⛔ 數字）；缺系列／沒有收盤／點數不足＝既有字樣 placeholder。"""
    _chips: list[Any] = [cp.meta_chip("not_defined")]
    if series is None:
        return _chips, []
    _core = intl_core_series(series)
    _ok = [_s for _s in _core if _s.status == "ok"]
    _dates = {_s.last_date for _s in _ok}
    if len(_dates) == 1:
        _asof = asof_chip_value(next(iter(_dates)), today_date=today_date)
        if _asof:
            _chips.append(cp.meta_chip("asof", _asof))
    _uniform = len({_s.n for _s in _ok}) == 1
    if _ok and _uniform:
        _chips.append(cp.meta_chip("window", f"近 {_ok[0].n} 日"))
    _cells: list[Any] = []
    for _s in _core:
        _name = intl_display_name(_s.name)
        if _s.status == "ok" and _s.n >= 2:
            try:
                _svg = cp.sparkline_svg([float(_v) for _v in _s.close.tolist()], w=SM_SPARK_W, h=SM_SPARK_H,
                                        title=_s.name, missing_state=UI_EMPTY,
                                        missing_text=INSUFFICIENT_TEXT.removeprefix("⬜ "))
            except ValueError as _e:   # 非有限值等：講出來（log），格內寫既有「資料不足／無法判定」，⛔ 畫一條假線
                print(f"[views/_market_blocks] 圖 B {_s.name} 畫不出小圖：{_e!r}")
                _cells.append(cp.SmCell(_name, missing_verbatim=INSUFFICIENT_TEXT))
                continue
            _win = None if _uniform else cp.meta_chip("window", f"近 {_s.n} 日")
            _cells.append(cp.SmCell(_name, svg=_svg, window_chip=_win))
        elif _s.status == "ok":
            _cells.append(cp.SmCell(_name, missing_verbatim=INSUFFICIENT_TEXT))
        else:
            _cells.append(cp.SmCell(_name, missing_verbatim=(SM_MISSING_ABSENT if _s.status == "absent"
                                                              else SM_MISSING_EMPTY)))
    return _chips, _cells


def chart_b_fold(series: Sequence[IntlSeries] | None, *, source_note: str, where_label: str,
                 overflow: Sequence[Any] = ()) -> ChartFold:
    """圖 B 摺疊：原外露的分組小標、每系列「名稱　·　近 N 日，資料至…」、來源 caption、窗口說明、趨勢結論句、
    趨勢定義說明**全部下沉到這裡**（逐字；系列名用正式全名）。"""
    _source: list[FoldLine] = []
    if series is not None:
        _source.append(("caption", source_note))
        _last = None
        for _s in series:
            if _s.group != _last:
                _source.append(("md", f"**{_s.group}**"))
                _last = _s.group
            _source.append(("md", f"{_s.name}　·　{_s.window_text}"))
    _where: list[FoldLine] = [("caption", NOT_LOADED)] if series is None else []
    _where.append(("caption", FOLD_WHERE_FMT.format(label=where_label)))
    # 趨勢結論句 `CHART_B_CONCLUSION`：有資料時已在六欄「規則／計算結果」內逐字（`basis_chart_b`）⇒ 不再另列一行（同段重複）；
    # 未載入時 `basis_chart_b` 的規則欄沒有它 ⇒ 另列一行（資訊守恆：外露的「⬜ 尚未定義」句只下沉、不能因去重而掉）。
    _basis = basis_chart_b(None if series is None else list(series))
    return chart_fold(_basis, why=() if CHART_B_CONCLUSION in _basis.rule else (("md", CHART_B_CONCLUSION),),
                      source=(*_source, *_overflow_lines(overflow)),
                      limit=(("caption", CHART_B_NOTE), ("caption", TREND_DEFINITION_NOTE)), where=_where)


def render_chart_b(session: Mapping[str, Any], *, source_note: str, where_label: str) -> None:
    """圖 B 國際趨勢＝**Secondary small multiples 一組**（DEC-117 Q4=P-B）：5 格、各自座標、⛔ 疊軸／正規化／數字（D5=A）、
    ⛔ 切換列。未載入 ⇒ 縮成一行灰字（D6=B）。詳細數值（最後收盤、資料日、筆數）與完整走勢圖仍在 L2「國際市場」展開區。"""
    with st.container(border=True, key=f"{P4M_SECONDARY_KEY_PREFIX}intl"):
        _series = intl_series(session)
        _chips, _cells = chart_b_parts(_series)
        _overflow = render_chart_header(title=CHART_B_TITLE, chips=_chips, say=CHART_B_SAY)
        if _series is None:
            st.caption(NOT_LOADED)
        else:
            # ⚠️ 行內 svg 一律走 `st.markdown(unsafe_allow_html=True)`（線框 F-4：`st.html` 在 1.56.0 會整段剝掉 svg）。
            st.markdown(cp.small_multiples_html(_cells, cols_desktop=3, cols_mobile=2), unsafe_allow_html=True)
        render_chart_fold(chart_b_fold(_series, source_note=source_note, where_label=where_label,
                                       overflow=_overflow))


# ── 圖 C（Secondary：研究框架，一行）────────────────────────────
#: 圖 C 摺疊「限制」：不適用（本區塊未啟用），說明取既有 `CHART_C_TAG`。
CHART_C_LIMIT: str = FOLD_NOT_APPLICABLE_FMT.format(why=CHART_C_TAG)


def chart_c_texts() -> tuple[str, ...]:
    """圖 C 區塊內的**全部**靜態文字（含摺疊；供「零數字」測試；「去哪補」的展開區標題由頁面測試另驗）。"""
    return (CHART_C_TITLE, CHART_C_TAG, CHART_C_SAY, CHART_C_EMPTY, CHART_C_EMPTY_FACE, CHART_C_BASIS, CHART_C_LIMIT)


def chart_c_fold(*, where_label: str) -> ChartFold:
    """Q8a／C3-1：`CHART_C_SAY`（客戶原句）→「為什麼」逐字；`CHART_C_BASIS` →「來源」逐字。"""
    return chart_fold(None, why=(("md", CHART_C_SAY), ("caption", CHART_C_EMPTY)), source=(("caption", CHART_C_BASIS),),
                      limit=(("caption", CHART_C_LIMIT),),
                      where=(("caption", FOLD_WHERE_FMT.format(label=where_label)),))


def render_chart_c(*, where_label: str) -> None:
    """圖 C 大盤合理區間：一行（D6=B）＝標題＋「研究框架，未啟用」護欄 chip＋`CHART_C_EMPTY`；客戶原句下沉到「為什麼」（Q8a）。
    ⛔ 區塊內零數值、零圖形、不畫區間標籤。"""
    with st.container(border=True, key=f"{P4M_SECONDARY_KEY_PREFIX}c"):
        render_chart_header(title=CHART_C_TITLE, chips=[cp.guard_chip(CHART_C_TAG)], say=None)
        st.caption(CHART_C_EMPTY_FACE)       # P4-4（A8）：外露只畫第一句；整句 `CHART_C_EMPTY` 在摺疊「為什麼」
        render_chart_fold(chart_c_fold(where_label=where_label))


# ── 圖 D（Secondary：主要風險 compact）──────────────────────────
#: 圖 D 表格欄（線框 P-16：三欄→兩欄；「是否惡化」改成 header 護欄 chip 寫一次）。
CHART_D_HEADERS: tuple[str, str] = ("風險桶（每桶一項）", "方向")


def chart_d_table_rows(risks: MarketRisks) -> list[tuple[str, str]]:
    """圖 D 兩欄＝`risk_panel_rows` 的前兩欄（同一份 `risks.rows`、同字）；第三欄恆為 `CHART_D_WORSENING`（風險／綠桶）或
    與方向欄同字的 `INSUFFICIENT_TEXT`（資料不足桶）—— 前者改由 header 護欄 chip 寫一次，後者方向欄已有 ⇒ 不丟資訊。"""
    _out: list[tuple[str, str]] = []
    for _bucket, _dir, _worse in risk_panel_rows(risks):
        if _worse not in (CHART_D_WORSENING, _dir):
            raise ValueError(f"圖 D 第三欄出現未預期的內容（不能直接併掉）：{_worse!r}")
        _out.append((_bucket, _dir))
    return _out


def chart_d_fold(risks: MarketRisks, *, overflow: Sequence[Any] = ()) -> ChartFold:
    """圖 D 摺疊：原「🔍 查看依據」六欄分四段；原外露的「查看全部指標 › …」指路移到「去哪補」（只下沉）。"""
    return chart_fold(basis_risks(risks), source=_overflow_lines(overflow),
                      where=(("md", CHART_D_ALL_LAMPS_POINTER),))


def render_chart_d(risks: MarketRisks) -> None:
    """圖 D 主要風險（Secondary compact）：五桶各一列（兩欄；與 hero 同一份 `risks`）；「N 項未評估（…未評估不等於安全）」
    **外露**（C6-5）；指標危險度指路句外露（C2）；未載入一行灰、算不出來紅（外露）。"""
    with st.container(border=True, key=f"{P4M_SECONDARY_KEY_PREFIX}d"):
        _overflow = render_chart_header(title=CHART_D_TITLE, chips=[cp.guard_chip(CHART_D_WORSENING)],
                                        say=CHART_D_NOTE, say_verbatim=False)
        if risks.cold:
            st.caption(NOT_LOADED)
        elif risks.failed:
            st.error(f"五桶風險摘要算不出來：{scrub_secrets(risks.error)}", icon="❌")
        else:
            st.markdown(f"**{risks.n_unevaluated} 項未評估**（共 {risks.n_lamps} 項燈；未評估不等於安全）")
            st.markdown(_md_table(CHART_D_HEADERS, chart_d_table_rows(risks)))
        st.caption(DANGER_POINTER)
        render_chart_fold(chart_d_fold(risks, overflow=_overflow))


#: 供測試掃描「不得出現的詞」用：頁面各區塊字樣的聚合入口（不含動態資料）。
STATIC_TEXTS: tuple[str, ...] = (
    PAGE_TITLE, PAGE_SUBTITLE, NOT_LOADED, REGIME_SCOPE_CAPTION, WATER_TITLE, WATER_VALUE, WATER_WHY,
    HERO_RISK_TITLE, HERO_RISK_NO_RANKING_NOTE, HERO_AI_PLACEHOLDER, ALERTS_TITLE, ALERTS_NO_SOURCE,
    HEALTH_CHIP, CHART_A_TITLE, CHART_A_SAY, CHART_A_MA_DISCLAIMER, CHART_A_CONCLUSION, CHART_B_TITLE,
    CHART_B_SAY, CHART_B_CONCLUSION, CHART_C_TITLE, CHART_C_TAG, CHART_C_SAY, CHART_C_EMPTY, CHART_D_TITLE,
    CHART_D_NOTE, CHART_D_WORSENING, INSUFFICIENT_TEXT,
    # P4-1（DEC-117）新增的第一屏字樣
    UPDATE_OPTIONS_LABEL, REGIME_TILE_LABEL, DANGER_POINTER, ALERTS_CONFLICTS_COUNT_FMT, HERO_RISK_FULL_HEADING,
    # P4-2（DEC-117）圖區字樣
    FOLD_LABEL, *FOLD_SECTIONS, FOLD_WHERE_FMT, CHART_C_LIMIT, SM_MISSING_ABSENT, SM_MISSING_EMPTY,
    *INTL_DISPLAY_NAMES.values(),
)
