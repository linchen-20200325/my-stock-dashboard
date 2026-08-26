"""src/ui/render/station_cards.py — L4 戰情室燈格 / 燈條 / 明細面板渲染。

只負責「把 L2 已經判好的燈畫出來」。**不取數、不判燈、不碰 session_state。**
資料由 L5 `src/ui/etf/etf_tab_dividend_station.py` 備妥後傳進來。

本檔是總經 v2 `src/ui/render/macro_v2_cards.py` 的姊妹檔,刻意採同一套結構
(常數表 → 純函式 → 渲染),差別只在戰情室的燈**不共用同一把尺**(見下)。

## 兩個視覺頻道(這是本檔的核心設計)

| 頻道 | 編碼什麼 | 怎麼畫 |
|---|---|---|
| **填色** | 這盞燈**自己印的那個判定符號** | 見 `LEVEL_STYLES` |
| **外框 / 紋理** | 四態(這盞燈可不可信) | 實心=運作中 / 橙環=門檻已失準 / 斜紋=無資料 / 對角槓=未接線 |

⚠️ **狀態頻道刻意不出 emoji。** L0 `station_specs.STATE_META` 的第二欄是
   `("運作中", "🟢")` —— 而「判定通過」在本專案也是 🟢。兩個 🟢 並排印出去,
   等於自己製造混淆再花一段文案去解釋。故本檔**只用 `STATE_META[state][0]`
   那個中文標籤**(維持文案 SSOT),第二欄的 emoji 一律不取。

§3.3 反捏造 —— 本檔不寫死任何色碼或門檻:
  · 色碼   ← `shared.colors`(L0 SSOT)
  · 門檻文字 / 燈名 / 來源 ← `shared.station_specs.StationSpec`(L0 SSOT)
  · 235 各級意義 ← `shared.dividend_station_thresholds.LIGHT_META`(L0 SSOT)
  · 四態文字 ← `shared.station_specs.STATE_META`(L0 SSOT)
  · 缺值原因文字 ← `shared.station_specs.MISS_TEXT`(L0 SSOT)

§8.2 分層 —— L4。**不 import 任何 L1 模組**;向下 import L0 `shared/*` 與
  L2 `src.compute.etf.dividend_station`(只取 `LEVEL_UNJUDGED` 這個 sentinel,
  同 `render/risk_contribution_render.py` 取 L2 dataclass 的既有慣例)。
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape as _esc

import streamlit as st

from shared import dividend_station_thresholds as T
from shared import station_specs as SS
from shared.colors import (
    TRAFFIC_GREEN,
    TRAFFIC_NEUTRAL,
    TRAFFIC_ORANGE,
    TRAFFIC_RED,
    TRAFFIC_YELLOW,
)
from src.compute.etf.dividend_station import LEVEL_UNJUDGED

# ══════════════════════════════════════════════════════════════════════
# 一、`level` → 視覺的對應表
# ══════════════════════════════════════════════════════════════════════
#
# ## 為什麼這張表放在 L4,不放 L0
#
# B1 那組的原話:「如果第 3 層要統一色階,那個對應表是**呈現決定**,該明文放
# L0 規格表或 L5,不該由轉換層默默決定。」—— 兩個位置都被點名,選 L4 的理由:
#
#   1. 它**只有畫面在用**。L0 `station_specs.py` 開頭自己寫明「不判燈,只描述
#      規格」,而且它已經示範過拒絕碰色碼(`STATE_META` 只放 emoji,沒有 hex)。
#      把「哪個符號填哪個顏色」塞進 L0,等於讓規格表開始承載某一頁的美術設定。
#   2. **既有前例就在 L4**:總經 v2 的 `macro_v2_cards.BAND_META`(band → 色)
#      也住在 L4,而那一頁 user 已經核准上線。同類東西放同一層。
#   3. 色碼本身**不是在這裡發明的** —— 全部 import 自 L0 `shared/colors.py`。
#      本表決定的只有「哪個 SSOT 顏色配哪個符號」,這正是呈現決定。
#   4. L5 要用直接 `from ...station_cards import` 即可(L5 → L4 是合法方向),
#      不必為此新增任何 §8.2.A 例外。
#
# ## 為什麼是「符號 → 顏色」而不是「通過/注意/不通過 → 顏色」
#
# 因為戰情室的 12 盞燈**不共用同一把尺**,硬要三分會講錯話:
#
#   · 健檢 A/B/C/D、汰換建議 → 🔴/🟡/🟢/⚪ 是「體質好不好」,🔴 = 不通過。
#   · **235 加碼燈** → 🔴/🟡/🟢 是「市場跌多深、該加多少碼」。
#     `LIGHT_META[LIGHT_3]` 的 label 就是「崩盤/深水加碼」——
#     **它的 🔴 是買進訊號,不是「不通過」。**
#   · 3-3-3 三子項 → ✅/❌/❔ 是「挑選條件符不符合」,不是健康告警。
#
# 所以本表只做一件事:**把主表已經在印的那個符號,忠實地畫成同色的格子**。
# 顏色照著符號走 = 搬運;顏色照著「我覺得它算好算壞」走 = 新判斷(§1 禁止)。
# 「這個 🔴 是什麼意思」交給 `level_meaning(group, level)` 按**該盞燈自己那把尺**
# 回答,並且明細面板一定會把那句話印出來。


@dataclass(frozen=True)
class LevelStyle:
    """一個判定符號的畫法。

    `fill=""` 代表**不填色**(hollow)—— 保留給「沒有判定可以填」與
    「有判定但刻意不上告警色」兩種情形,兩者再用 `dashed` 區分。
    """

    fill: str          #: 格子填色;"" = 不填色
    glyph: str         #: 不填色時格子裡的小記號("" = 空格子)
    dashed: bool       #: 外框虛線(= 這盞燈根本沒有判定)


#: 判定符號 → 格子畫法。**鍵就是 L2 `LightCell.level` 原樣搬運的那個字串。**
#:
#: | 符號 | 出現在哪盞燈 | 填色 | 為什麼 |
#: |---|---|---|---|
#: | 🔴 | 健檢 / 235 / 汰換 | 紅 | 主表就印這個符號,格子跟著符號同色 = 忠實搬運 |
#: | 🟡 | 同上 | 黃 | 同上 |
#: | 🟢 | 同上 | 綠 | 同上 |
#: | ⚪ | 同上 | 灰 | 中性:不是好也不是壞(235 的 ⚪ 是巡航,健檢的 ⚪ 是沒判) |
#: | 💰 | 只有 235 | 橙 | 停利警示既不是「通過」也不是「不通過」,是**第四種東西**。
#:        刻意不與 🟡 共用色 —— 在 235 這把尺上 🟡 是「急跌加碼」,方向正好相反 |
#: | ✅ | 只有 3-3-3 | 綠 | 挑選條件符合 |
#: | ❌ | 只有 3-3-3 | **不填色**(灰實線框 + ✗) | ⚠️ **刻意不給紅**。3-3-3 從不
#:        參與 `_worst_level` / `worst_health`,主表**沒有**這盞紅燈;給它紅色
#:        等於在格子牆上憑空多出一盞主表沒有的紅燈,那是新判斷不是轉換(§1) |
#: | ❔ | 只有 3-3-3 | 灰 | 無法判定 |
#: | `""` | 個股 3 盞 + 整檔抓取失敗 | **不填色**(虛線框 + 空格) | ⚠️ `LEVEL_UNJUDGED`。
#:        L2 **從來沒有**為這盞燈判過等級,填任何顏色都是假裝它有判定。
#:        虛線 = 「這格是空的」,與 ❌ 的實線框(有判定,只是不上告警色)分開 |
LEVEL_STYLES: dict[str, LevelStyle] = {
    "🔴": LevelStyle(fill=TRAFFIC_RED, glyph="", dashed=False),
    "🟡": LevelStyle(fill=TRAFFIC_YELLOW, glyph="", dashed=False),
    "🟢": LevelStyle(fill=TRAFFIC_GREEN, glyph="", dashed=False),
    "⚪": LevelStyle(fill=TRAFFIC_NEUTRAL, glyph="", dashed=False),
    "💰": LevelStyle(fill=TRAFFIC_ORANGE, glyph="", dashed=False),
    "✅": LevelStyle(fill=TRAFFIC_GREEN, glyph="", dashed=False),
    "❌": LevelStyle(fill="", glyph="✗", dashed=False),
    "❔": LevelStyle(fill=TRAFFIC_NEUTRAL, glyph="", dashed=False),
    LEVEL_UNJUDGED: LevelStyle(fill="", glyph="", dashed=True),
}

#: 235 的 icon → 該級的意思。**從 L0 `LIGHT_META` 反查,不在本檔重打一次文案**
#: (§3.3:上游改 label,本頁自動跟著改)。
_L235_MEANING: dict[str, str] = {
    str(_m["icon"]): str(_m["label"]) for _m in T.LIGHT_META.values()
}

#: 健檢 A/B/C/D 那把尺(`Flag.level`)。這一組才是真正的「通過 / 注意 / 不通過」。
_HEALTH_MEANING: dict[str, str] = {
    "🔴": "不通過 —— 這一項踩到紅線",
    "🟡": "注意 —— 還沒踩線,但要盯著",
    "🟢": "通過",
    "⚪": "沒有判定(看下面的缺值原因)",
}

#: 個股汰換建議那把尺(`StockAssessment.swap_level`)。與健檢同符號但語意是「動作」。
_SWAP_MEANING: dict[str, str] = {
    "🔴": "建議換出",
    "🟡": "留意 / 減碼觀察",
    "🟢": "續抱",
    "⚪": "沒有判定(看下面的缺值原因)",
}

#: 3-3-3 三子項那把尺(L2 `_SCREEN_SYMBOL` 的三個值)。
#: ⚠️ 「不符合」刻意不寫成「未過(紅燈)」—— 它不是告警,只是這個挑選條件沒中。
_SCREEN_MEANING: dict[str, str] = {
    "✅": "符合這個挑選條件",
    "❌": "不符合這個挑選條件(**不是**體質紅燈 —— 3-3-3 不計入健檢)",
    "❔": "無法判定(看下面的缺值原因)",
}

#: `StationSpec.group` → 該組用哪一把尺。group 是 L0 規格表既有欄位,
#: 不在本檔另建一份「哪盞燈屬於哪組」的名單(那會與規格表漂移)。
_MEANING_BY_GROUP: dict[str, dict[str, str]] = {
    "health": _HEALTH_MEANING,     # 健檢 A/B/C/D
    "timing": _L235_MEANING,       # 235 加碼燈
    "screen": _SCREEN_MEANING,     # 3-3-3 ①②③
    "stock": _SWAP_MEANING,        # 個股組的預設尺(汰換建議);另兩盞見 _MEANING_BY_KEY
}

#: 個股「財報體檢」那把尺(`StockAssessment.health_level`)。
#:
#: ⚠️ 與汰換建議**同符號、不同意思**,故不可共用 `_SWAP_MEANING`:
#: 汰換建議還吃 KD 與趨勢,「財報 C + KD 轉強」→ 汰換是 🟡「留意 / 減碼觀察」,
#: 而體檢仍是 🔴「體質不合格」。兩盞燈在同一列**本來就可能不同色**,
#: 那正是把它們拆成兩盞的理由。
_STOCK_HEALTH_MEANING: dict[str, str] = {
    "🔴": "體質不合格 —— 列入汰換候選(評等 C / F)",
    "🟡": "體質尚可,但要盯著(評等 B)",
    "🟢": "體質合格(評等 A+ / A / B+)",
    "⚪": "沒有判定(看下面的缺值原因)",
    # ⚠️ 這盞燈**有**自己的等級,只是這一輪算不出來 → 不可套通用的
    # `UNJUDGED_TEXT`(那句話說「從來沒有各自的等級」,對這盞燈已經是假的)。
    LEVEL_UNJUDGED: "這一輪沒有評等可判(看下面的缺值原因)",
}

#: 個股「財報趨勢」那把尺(`StockAssessment.trend_level`,來自 `diff_fin_health`)。
#:
#: ⚠️ **這裡的 🔴 不是「建議換出」。** 它說的是「上一季到這一季,評等變差的項目多於
#: 變好」—— 一檔 A+ 的公司也可能是 🔴(從很好變成沒那麼好)。套 `_SWAP_MEANING`
#: 會讓明細面板對著一檔體質良好的股票印「建議換出」,那是假敘述(§1)。
#: ⚠️ ⚪ 也不能共用:在汰換那把尺上 ⚪ 是「沒有判定」,在這裡是**有判定** ——
#: 兩期比過了,每一項評等都沒變。
_STOCK_TREND_MEANING: dict[str, str] = {
    "🔴": "變差的項目多於變好(**不等於建議換出** —— 這只是上一季到這一季的方向)",
    "🟡": "有好有壞,方向分歧",
    "🟢": "變好的項目多於變差",
    "⚪": "兩期比過了,每一項評等都沒變(**不是**沒資料)",
    # 同上:有等級,只是這一輪比不出來(最常見的原因是缺上一季財報,沒得比)。
    LEVEL_UNJUDGED: "這一輪比不出方向 —— 多半是缺上一季財報,沒有東西可以比",
}

#: 少數幾盞燈有**自己**的尺,不跟著 group 走。key 是 L0 規格表的 canonical key。
#:
#: 為什麼不乾脆給它們各自的 `group`:`group` 是規格表用來分區塊的欄位(畫面把
#: 個股 4 盞排在一起),改 group 會連帶影響任何依 group 分組的消費端。
#: 「用哪一把尺」是**呈現決定**,和分區塊是兩件事 —— 故在 L4 這裡另立一張表。
_MEANING_BY_KEY: dict[str, dict[str, str]] = {
    SS.KEY_STOCK_HEALTH: _STOCK_HEALTH_MEANING,
    SS.KEY_STOCK_TREND: _STOCK_TREND_MEANING,
}

#: `LEVEL_UNJUDGED` 的說明。**與四態的「無資料」是兩件事**,故獨立成句:
#: 「無資料」= 這輪沒取到值(等 / 重跑就會有);
#: 「未判定」= L2 從來沒有為這盞燈判過等級(重跑一百次也不會有等級)。
UNJUDGED_TEXT = "未判定 —— 這盞燈只當上游輸入用,從來沒有各自的等級(不是這次沒抓到)"


def level_meaning(group: str, level: str, *, key: str = "") -> str:
    """`(規格表 group, 判定符號)` → 這個符號在**這把尺**上的意思。

    為什麼要帶 `group` 而不能只查符號:同一個 🔴 在健檢是「踩到紅線」、
    在 235 是「崩盤/深水加碼」(買進訊號)。只查符號必然講錯其中一邊。

    `key`(選填):同一個 group 裡有自己一把尺的燈(見 `_MEANING_BY_KEY`)——
    個股組的「財報體檢」「財報趨勢」與「汰換建議」同符號但意思不同,
    不帶 key 會拿到汰換那把尺(在趨勢那盞燈上會講成「建議換出」= 假敘述)。
    參數是**選填**,舊呼叫端行為不變。

    未登錄的符號回 `""`(呼叫端顯示原符號即可)—— 這裡**不猜**它是什麼意思。

    ⚠️ `LEVEL_UNJUDGED` 的文案也走同一把尺。通用的 `UNJUDGED_TEXT` 說的是
    「這盞燈**從來沒有**各自的等級」—— 那句話只對「根本沒有判燈邏輯」的燈
    (現在只剩 KD)成立。對「有等級、只是這一輪算不出來」的燈(財報體檢 /
    財報趨勢)照印,就是假敘述(§1),故那兩盞在自己的尺裡覆寫這句。
    """
    _scale = _MEANING_BY_KEY.get(key) or _MEANING_BY_GROUP.get(group, {})
    if level == LEVEL_UNJUDGED:
        return _scale.get(LEVEL_UNJUDGED) or UNJUDGED_TEXT
    return _scale.get(level, "")


# ══════════════════════════════════════════════════════════════════════
# 二、CSS
# ══════════════════════════════════════════════════════════════════════
#
# 半透明底 + `color:inherit` —— 讓格子在 Streamlit 亮/暗兩種佈景都成立
# (寫死背景色必有一邊不能看)。`__ORANGE__` 佔位符在下面用 `.replace` 代入
# L0 色碼,不在 CSS 字面值裡寫死 hex(§3.3)。
_CSS_TEMPLATE = """
<style>
.dsl-cell{display:inline-block; width:13px; height:13px; border-radius:3px;
          box-sizing:border-box; vertical-align:middle; margin-right:3px;
          border:1px solid rgba(128,128,128,.55);
          font-size:9px; line-height:11px; text-align:center; overflow:hidden;}
.dsl-dash{border-style:dashed;}
/* 無資料:斜紋。與「未判定」的虛線框是兩個獨立頻道,可同時出現。 */
.dsl-hatch{background-image:repeating-linear-gradient(45deg,
           rgba(138,142,150,.85) 0 1.5px, transparent 1.5px 4.5px);}
/* 未接線:一條對角槓(= 這盞燈被劃掉了,永遠不會亮)。 */
.dsl-bar{background-image:linear-gradient(45deg, transparent 42%,
         rgba(138,142,150,.95) 42% 58%, transparent 58%);}
/* 門檻已失準:橙環。用 outline 不用 border —— border 會改變格子尺寸,
   一列裡有一格 degraded 就會讓整條燈條錯位。 */
.dsl-ring{outline:2px solid __ORANGE__; outline-offset:1px;}
.dsl-strip{display:inline-block; white-space:nowrap; line-height:1;}
.dsl-row{display:flex; align-items:center; gap:8px; padding:5px 0;
         border-bottom:1px solid rgba(128,128,128,.18); font-size:12.5px;}
.dsl-tk{font-weight:700; white-space:nowrap;}
.dsl-nm{opacity:.66; flex:1 1 auto; min-width:0; overflow:hidden;
        text-overflow:ellipsis; white-space:nowrap;}
.dsl-cnt{font-variant-numeric:tabular-nums; opacity:.72; white-space:nowrap;}
.dsl-lg{font-size:11.5px; opacity:.8; line-height:2.0;}
.dsl-lg b{opacity:.9;}
.dsl-miss{font-size:12px; opacity:.88; background:rgba(128,128,128,.11);
          border-radius:7px; padding:7px 10px; margin:5px 0 2px;}
.dsl-lbl{font-size:13px; font-weight:600;}
.dsl-sub{font-size:11.5px; opacity:.62; margin:1px 0 0;}
/* ── 第 1 層結論卡 ────────────────────────────────────────────
   手機優先:卡片本身不設固定寬,由呼叫端的 st.columns 決定;卡內數字用
   flex-wrap,窄螢幕自動換行而不是被截斷。 */
.dsl-card{border:1px solid rgba(128,128,128,.28); border-radius:10px;
          padding:11px 13px; height:100%;}
.dsl-card h4{font-size:12px; font-weight:700; opacity:.66; margin:0 0 7px;
             letter-spacing:.04em;}
.dsl-head{font-size:15px; font-weight:700; line-height:1.45; margin:0 0 6px;}
.dsl-figs{display:flex; flex-wrap:wrap; gap:4px 16px; margin-top:8px;}
.dsl-fig{min-width:0;}
.dsl-fig b{display:block; font-size:17px; font-weight:700; line-height:1.25;
           font-variant-numeric:tabular-nums; white-space:nowrap;}
.dsl-fig span{font-size:11px; opacity:.62;}
/* 四態分佈條:**只用紋理區分狀態,不用顏色** —— 顏色在本檔一律代表「判定」,
   拿來編狀態就會出現「綠色格子＝運作中」與「綠色格子＝判定通過」兩種讀法
   (同檔頭「兩個 🟢」那段的理由)。故四段共用同一個中性底,靠紋理分辨。 */
.dsl-bar-wrap{display:flex; height:15px; border-radius:8px; overflow:hidden;
              margin:3px 0 5px; background:rgba(128,128,128,.16);}
.dsl-seg{height:100%; background:rgba(128,128,128,.34);}
.dsl-seg-live{background:rgba(128,128,128,.78);}
.dsl-seg-ring{box-shadow:inset 0 0 0 2px __ORANGE__;}
/* ── 兩套刻度對照表 ──────────────────────────────────────── */
.dsl-tbl{width:100%; border-collapse:collapse; font-size:12px;}
.dsl-tbl th,.dsl-tbl td{border:1px solid rgba(128,128,128,.28);
                        padding:6px 8px; text-align:left; vertical-align:top;}
.dsl-tbl th{opacity:.72; font-weight:700; white-space:nowrap;}
.dsl-tbl td:first-child{font-weight:600; white-space:nowrap;}
.dsl-scroll{overflow-x:auto;}
</style>
"""

CSS = _CSS_TEMPLATE.replace("__ORANGE__", TRAFFIC_ORANGE)


# ══════════════════════════════════════════════════════════════════════
# 三、純函式(無 st.*、無 I/O,可單測)
# ══════════════════════════════════════════════════════════════════════

def _in_judged_denominator(cell) -> bool:
    """這一格算不算進「給得出判定」的分母。**分子分母共用同一個判準。**

    兩種格子不進分母,理由不同,兩種都**不是**「今天沒抓到」:

      1. `miss_reason == MISS_NOT_APPLICABLE` —— 這類持股結構上沒有這盞燈
         (個股沒有折溢價)。它永遠不會有值。
      2. 規格表宣告 `emits_level=False` —— 這盞燈**依規格就不出等級**
         (現況只有個股 KD:K、D 都在,但沒有判燈規則)。它會亮、會被看,
         只是不會給等級。留在分母裡的後果不是「分數低一點」,而是
         **每一列個股永遠差一盞** → 巡航那句話永遠印不出來(user 2026-08-26
         裁示移出分母,理由見規格表該盞燈的 `no_level_reason`)。

    ⚠️ 「今天沒抓到」**照樣留在分母裡**把分數拉低 —— 那正是這個指標存在的理由。
    ⚠️ 規格表查不到的 key(上下游漂移)**算進分母**:寧可分數偏低,也不要因為
    一個沒人發現的 key 漂移而讓畫面顯示可信度更高(§1)。
    """
    if cell.miss_reason == SS.MISS_NOT_APPLICABLE:
        return False
    _spec = SS.SPECS_BY_KEY.get(cell.key)
    return _spec is None or _spec.emits_level


def watch_count(cells) -> tuple[int, int]:
    """一列的「N/M 在看」—— N = 四態為 `live` 的燈數,M = 這一列的總燈數。

    ⚠️ 分母是**整列的燈**,不是「算得出來的燈」。抓取失敗的列同樣有 M 盞
    (L2 `missing_light_cells` 就是為此存在),否則分母會悄悄變小、畫面反而
    顯示可信度更高(§1)。

    ⚠️ **2026-08-26 起 production 沒有呼叫端了**(改動後 grep 只剩測試引用):
    第 3 層燈格牆 / 選列表 / 明細面板三處原本用這把寬鬆的尺,與第 1 層的
    `judged_count` 在同一頁印出差 1 的兩個數字(實測 2330:第 1 層 2/4、
    第 3 層 3/4)。user 2026-08-26 裁示三處一律改用嚴格計數,矛盾消除。
    本函式**刻意保留不刪**(要不要刪由 user 決定);四態分佈條的「運作中」
    那一格仍然表達同一件事,走 `tally_states`。
    ⚠️ 原文這裡寫著「與 `judged_count` 是兩把不同的尺,**刻意的**」——
    那句話在畫面上已經不成立,故刪除;留著會讓下一個人以為同頁兩個數字
    本來就該不一樣。
    """
    _cs = tuple(cells or ())
    return sum(1 for c in _cs if c.state == SS.STATE_LIVE), len(_cs)


def judged_count(cells) -> tuple[int, int]:
    """一列的「N/M **給得出判定**」。**第 1 層與第 3 層一律用這一把尺。**

    ```
    分母 = 全部燈數 − 結構上不進分母的(見 `_in_judged_denominator`)
    分子 = 分母內  且  state == live  且  level 非空(!= LEVEL_UNJUDGED)
    ```

    ## 為什麼分子要多一個「level 非空」的條件

    `state == live` 的語意是「**這盞燈的資料管道通**」—— 它不保證那盞燈
    **產出過等級**。「在看」≠「有判定」(user 2026-08-26 裁示)。
    這個條件同時是**反向守衛**:規格表宣告 `emits_level=True` 的燈若真的沒出
    等級,它會如實把分數拉低,而不是被當成「有判定」蒙混過去
    (`tests/test_station_layer1.py` 另有一條測試直接釘住這件事)。

    ## 個股 KD 為什麼不在分母裡(2026-08-26 改)

    KD 資料通(live)、但**依規格就不出等級**(規格表 `emits_level=False`)。
    原本把它留在分母、只是不進分子 —— 後果是**只要組合裡有任何一檔個股,
    那一列就永遠不可能「每盞都給得出判定」**,`is_fully_judged` 恆為 False,
    巡航那句話變成永遠印不出來的死碼。user 裁示:結構上永遠不出等級的燈
    視同不適用,移出分母(個股分母 4 → 3)。
    ⚠️ 它**只離開分母,沒離開畫面** —— 燈格牆照畫、明細照開,而且明細面板會
    印出「這盞燈還沒有判定規則」把理由講清楚(**不借用**「不適用」的文案,
    那對 KD 是假話)。

    ## 為什麼分母**不**扣掉「今天沒抓到」的燈

    「這輪沒抓到」必須**留在分母裡把分數拉低** —— 那正是這個指標存在的理由。
    把算不出來的從分母移走,畫面會在資料最爛的時候顯示可信度最高(§1)。

    ⚠️ 分母是**動態**的:ETF 8 盞、個股 3 盞(4 盞扣掉 KD)。呼叫端**不得**
    寫死任何總數 —— 混合持股的總格數會隨組合成分改變。
    """
    _cs = tuple(c for c in (cells or ()) if _in_judged_denominator(c))
    _num = sum(1 for c in _cs
               if c.state == SS.STATE_LIVE and c.level != LEVEL_UNJUDGED)
    return _num, len(_cs)


def is_fully_judged(cells) -> bool:
    """這一列**每一盞適用的燈**都給得出判定嗎(= 巡航 gate 的准印條件)。

    空列回 `False`:一盞燈都沒有的列不是「全部都好」,是「什麼都沒有」——
    回 True 會讓 `all(...)` 在最糟的情況下反而放行(§1)。
    """
    _n, _m = judged_count(cells)
    return _m > 0 and _n == _m


def aggregate_judged(cells_per_row) -> tuple[int, int]:
    """多列 → 整個組合的 (給得出判定, 分母)。逐列走 `judged_count` 再相加。"""
    _n = _m = 0
    for _cells in (cells_per_row or ()):
        _a, _b = judged_count(_cells)
        _n += _a
        _m += _b
    return _n, _m


def tally_states(cells_per_row) -> dict[str, int]:
    """多列 → 四態各有幾格。鍵一律是 `SS.STATE_*` 四個,**沒出現的填 0**
    (缺鍵讓呼叫端 `.get(k, 0)` 也能動,但那會讓「0 格未接線」跟「忘了統計」
    長得一樣 —— 明確填 0 才分得出來)。

    ⚠️ 分母口徑與 `judged_count` **共用同一個判準**(`_in_judged_denominator`),
    否則「四態加總」會對不上卡片上那個 N/M(同一張卡兩個分母 = 自己打自己)。
    2026-08-26 起這表示同時排除「結構上不適用」與「依規格不出等級」(KD)兩種格子。
    """
    _out = {_s: 0 for _s in (SS.STATE_LIVE, SS.STATE_DEGRADED,
                             SS.STATE_MISSING, SS.STATE_UNWIRED)}
    for _cells in (cells_per_row or ()):
        for _c in (_cells or ()):
            if not _in_judged_denominator(_c):
                continue
            if _c.state in _out:
                _out[_c.state] += 1
    return _out


#: 巡航這句話**只有在 gate 放行時**才准出現。與 L2 `suggest_action` 的
#: 「⚪ 巡航：維持定期定額」**刻意不同字** —— 那一句講的是**單一持股**的建議動作
#: (而且是 LINE 每日推播在用的字串,改它等於改推播內容);這一句講的是
#: **整個組合今天沒有需要動作的部位**,是另一個層級的結論。
CRUISE_TEXT = "⚪ 巡航：今天沒有需要動作的部位"


def cruise_or_gap(judged: int, total: int, *, all_rows_judged: bool) -> str:
    """巡航 gate(**顯示層**,不碰 L2 判燈)。

    准印巡航的條件:**每一列的每一盞適用燈都 live 且有 level**。
    只要有一列不滿足,就不准說「沒事」—— 改說清楚「有幾個依據可用」,
    因為那兩件事在畫面上原本長得一模一樣,而它們的處置完全相反(§1)。

    ⚠️ 這裡**刻意不呼叫也不修改** `dividend_station.suggest_action`。那支函式
    同時餵著主表的「建議動作」欄與 `scripts/push_holdings_daily.py` 的 LINE 推播;
    在那裡加 gate 會變成行為變更,需另外核准。gate 只做在畫面這一層。
    """
    if all_rows_judged and total > 0 and judged == total:
        return CRUISE_TEXT
    return (f"{judged}/{total} 個依據可用 —— "
            f"**不是都沒事,是沒東西可以判**")


def cell_html(cell) -> str:
    """一格燈。填色=判定、外框/紋理=四態(兩個頻道互不干擾)。

    §1:未登錄的判定符號**當場炸**,不畫成灰格子。理由與 L2 `light_cells`
    對「規格表有這盞燈但沒接上」的處理一致 —— 悄悄畫成灰色的話,新增一種
    判定符號時畫面只會多一格看起來很正常的灰格,沒有人會發現它沒被上色。
    """
    if cell.level not in LEVEL_STYLES:
        raise KeyError(
            f"station_cards: 判定符號 {cell.level!r}(燈 {cell.key!r})沒有登錄在 "
            f"LEVEL_STYLES —— 新增判定符號時必須同時決定它怎麼畫"
            f"(§1 寧可炸掉,不可畫一格沒人知道是什麼的格子)")
    _sty = LEVEL_STYLES[cell.level]
    _cls = ["dsl-cell"]
    _style = f"background:{_sty.fill};" if _sty.fill else ""
    if _sty.dashed:
        _cls.append("dsl-dash")
    if cell.state == SS.STATE_MISSING:
        _cls.append("dsl-hatch")
    elif cell.state == SS.STATE_UNWIRED:
        _cls.append("dsl-bar")
    elif cell.state == SS.STATE_DEGRADED:
        _cls.append("dsl-ring")
    # title= 讓桌機滑鼠停留看得到燈名;手機沒有 hover,故明細面板必須把同樣的話再講一次。
    _spec = SS.SPECS_BY_KEY.get(cell.key)
    _tip = _esc(f"{_spec.label if _spec else cell.key}｜{SS.STATE_META[cell.state][0]}")
    return (f'<span class="{" ".join(_cls)}" style="{_style}" title="{_tip}">'
            f'{_sty.glyph}</span>')


def strip_html(cells) -> str:
    """一列的燈條(N 格連在一起)。"""
    return ('<span class="dsl-strip">'
            + "".join(cell_html(c) for c in (cells or ()))
            + "</span>")


# ══════════════════════════════════════════════════════════════════════
# 四、渲染
# ══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class _DemoCell:
    """圖例用的假格子。**只給 `render_legend` 用**,不外流。

    刻意不 import L2 的 `LightCell` 來造 —— 圖例畫的是視覺語彙,不是任何一檔
    的真實判定,用真型別會讓人以為它是資料。
    """

    level: str
    state: str
    key: str = ""


def render_legend() -> None:
    """圖例 —— 沒有這段,兩個頻道的視覺語彙沒有人看得懂。

    ⚠️ 狀態那一排**不印 emoji**,只印格子本身 + 中文標籤(見檔頭「兩個 🟢」)。
    """
    def _demo(level: str, state: str) -> str:
        return cell_html(_DemoCell(level=level, state=state))

    _lv = "　".join(
        f'{_demo(_l, SS.STATE_LIVE)}{_t}'
        for _l, _t in (("🔴", "紅"), ("🟡", "黃"), ("🟢", "綠"), ("⚪", "灰"),
                       ("💰", "停利"), ("❌", "不符合"), (LEVEL_UNJUDGED, "未判定"))
    )
    _stt = "　".join(
        f'{_demo("⚪", _s)}{SS.STATE_META[_s][0]}'
        for _s in (SS.STATE_LIVE, SS.STATE_DEGRADED, SS.STATE_MISSING, SS.STATE_UNWIRED)
    )
    st.markdown(
        f'<div class="dsl-lg"><b>填色＝判定</b>　{_lv}<br>'
        f'<b>外框／紋理＝這盞燈可不可信</b>　{_stt}</div>',
        unsafe_allow_html=True)


def render_light_wall(items: list[tuple[str, str, tuple]]) -> None:
    """燈格牆 —— 一列一行:代號 / 名稱 / 燈條 / N-M 有判定。

    `items`: `[(代號, 名稱, cells), ...]`,由 L5 從 row 的 `_lights` 備妥。

    ⚠️ **數字走 `judged_count`,與第 1 層結論卡同一把尺**(user 2026-08-26 裁示)。
    原本這裡用寬鬆的 `watch_count`,同一頁上第 1 層印 2/4、這裡印 3/4 ——
    兩個都不算錯,但使用者只會讀成「有一邊算錯了」。文字也跟著從「在看」改為
    「有判定」:數字的意思變了,標籤不跟著改就是掛著舊名賣新東西(§1)。

    ⚠️ 這裡**不用 `st.expander` 也不用巢狀 `st.tabs`**:兩者的 body 在
    Streamlit 每次 app run 都會執行(收合只是前端),把 N 檔 × 12 盞燈塞進
    每列一個 expander,就是 STATE.md v19.132 產業熱力圖那個坑的另一個入口。
    整面牆是一次 `st.markdown` 的純 HTML,零 widget、零額外執行成本。
    """
    if not items:
        return
    _rows = []
    for _tk, _nm, _cells in items:
        _n, _m = judged_count(_cells)
        # 代號 / 名稱來自使用者的 Google Sheet → 一律 escape。名稱含 `<` 或 `&`
        # 時不 escape 會直接把整面牆的版面弄壞(不是安全問題,是會壞掉)。
        _rows.append(
            f'<div class="dsl-row"><span class="dsl-tk">{_esc(_tk)}</span>'
            f'<span class="dsl-nm">{_esc(_nm or "")}</span>'
            f'{strip_html(_cells)}'
            f'<span class="dsl-cnt">{_n}/{_m} 有判定</span></div>')
    st.markdown("".join(_rows), unsafe_allow_html=True)


def render_holding_detail(ticker: str, name: str, cells,
                          *, value_texts: dict[str, str] | None = None,
                          error: str = "") -> None:
    """單一持股的逐盞燈明細(右欄常駐面板,點左表任一列就地更新)。

    Streamlit 沒有原生 Drawer,且 `st.expander` 的 body 每次 rerun 都會執行 ——
    故採「常駐右欄 + 只渲染被選中那一列」,與總經 v2 第 3 層同一套做法。

    `value_texts`: `{規格表 key: 這盞燈實際算出什麼}`。由 L5 從 row 的 `_detail`
      對應過來;沒有對應文字的燈顯示「—」,**不由本層編一句**(§1)。

    ⚠️ 標題那個 N/M 與燈格牆、與第 1 層結論卡**同一把尺**(`judged_count`)——
    同一頁三個地方印同一件事,不准有三個數字。
    """
    _vt = value_texts or {}
    _n, _m = judged_count(cells)

    st.markdown(f"### {ticker}　{name or ''}".rstrip())   # st.markdown 預設不吃 raw HTML
    st.markdown(f'{strip_html(cells)}　<span class="dsl-cnt">{_n}/{_m} 盞有判定</span>',
                unsafe_allow_html=True)
    if error:
        st.error(f"這一檔整批抓取失敗:{error}", icon="🚨")

    for _c in cells:
        _spec = SS.SPECS_BY_KEY.get(_c.key)
        if _spec is None:
            # 規格表查不到 = 上下游 key 漂移。不靜默略過(那就等於少畫一盞燈)。
            st.markdown(f'{cell_html(_c)} `{_c.key}` —— 規格表查無此燈(程式要修)')
            continue
        st.markdown(
            f'<div style="margin:10px 0 0">{cell_html(_c)}'
            f'<span class="dsl-lbl">{_spec.label}</span>'
            f'<span class="dsl-sub">狀態　{SS.STATE_META[_c.state][0]}'
            f'　·　判定　{_c.level or "—"}　{level_meaning(_spec.group, _c.level, key=_c.key)}</span>'
            f'</div>',
            unsafe_allow_html=True)
        st.markdown(
            f'<div class="dsl-sub">值　{_vt.get(_c.key) or "—"}<br>'
            f'門檻　{_spec.threshold_text}<br>'
            f'來源　{_spec.source}</div>',
            unsafe_allow_html=True)

        if _c.key == SS.KEY_LIGHT235:
            # 235 是三取一:少一軸燈照樣會亮,只是根據變薄 —— 那件事只有這裡講得出來。
            _used = SS.axes_text(_c.axes_used) or "（一個依據都沒有）"
            st.markdown(
                f'<div class="dsl-sub">依據　{_used}'
                f'　（{len(_c.axes_used)}/{len(SS.LIGHT235_AXES)} 個可用）</div>',
                unsafe_allow_html=True)
        if not _spec.emits_level and _spec.no_level_reason:
            # 「這盞燈依規格就不出等級」與四態、與缺值原因都是**不同的一件事**,
            # 故獨立成塊、**不共用**任何既有文案:借用「不適用」會對 KD 講假話
            # (它對個股完全適用),借用「無資料」會讓人以為重跑就會有(不會)。
            # 這一塊同時是那個 N/M 分母的交代 —— 少一盞不是算錯。
            st.markdown(f'<div class="dsl-miss"><b>這盞燈還沒有判定規則</b><br>'
                        f'{_spec.no_level_reason}</div>', unsafe_allow_html=True)
        if _c.state == SS.STATE_UNWIRED and _spec.unwired_reason:
            st.markdown(f'<div class="dsl-miss"><b>這盞燈沒有在運作</b><br>'
                        f'{_spec.unwired_reason}</div>', unsafe_allow_html=True)
        elif _c.state == SS.STATE_DEGRADED and _spec.degraded_reason:
            st.markdown(f'<div class="dsl-miss"><b>門檻已失準</b><br>'
                        f'{_spec.degraded_reason}</div>', unsafe_allow_html=True)
        if _c.miss_reason:
            # 文字走 L0 `MISS_TEXT`;上游沒登記原因就什麼都不印 —— **不猜**
            # (挑錯 MISS_* 會給出「重跑一次就好」這種錯誤指引)。
            _txt = SS.MISS_TEXT.get(_c.miss_reason)
            if _txt:
                st.markdown(f'<div class="dsl-miss">{_txt}</div>',
                            unsafe_allow_html=True)
        st.markdown(f'<div class="dsl-sub" style="margin-top:6px">{_spec.why}</div>',
                    unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# 五、第 1 層 —— 結論卡（階段 C）
# ══════════════════════════════════════════════════════════════════════
#
# ⚠️ **本節不做任何新判斷（防呆 4）。** 三張卡印的每一個結論都是上游**已經算好**
#    的東西:紅燈檔數 / 加碼檔數走 L3 `build_station_digest`（與 LINE 推播吃的是
#    同一支函式、同一組定義）,可信度走本檔 `judged_count`（純計數,不看市場）,
#    金額走 L3 `compute_portfolio_totals`（純乘加）。
#    這裡唯一「決定」的事情是**排版**,以及巡航那句話准不准印（`cruise_or_gap`）。


def _fig(value: str, label: str) -> str:
    """一個數字 + 一行標籤。`value` 已由呼叫端格式化(含單位)。"""
    return (f'<div class="dsl-fig"><b>{_esc(value)}</b>'
            f'<span>{_esc(label)}</span></div>')


def render_conclusion_card(*, headline: str, figures: list[tuple[str, str]],
                           note: str = "") -> None:
    """卡①「這個組合現在該做什麼」—— 一句話 + 幾個數字。

    `headline` 由呼叫端備妥（含巡航 gate 的結果）;本函式**不決定**它說什麼。
    `figures`: `[(顯示值, 標籤), ...]`,顯示值已格式化;**缺資料的項目由呼叫端
      直接不放進來或放「—」,本層不代填 0**(§1)。
    """
    _figs = "".join(_fig(_v, _l) for _v, _l in (figures or ()))
    st.markdown(
        f'<div class="dsl-card"><h4>這個組合現在該做什麼</h4>'
        f'<div class="dsl-head">{headline}</div>'
        f'<div class="dsl-figs">{_figs}</div>'
        + (f'<div class="dsl-sub" style="margin-top:8px">{note}</div>' if note else "")
        + '</div>',
        unsafe_allow_html=True)


#: 四態在分佈條上各自的 CSS class。**順序即畫面由左到右的順序**,固定為
#: 「能用 → 半信 → 沒有 → 不會有」,讓長度變化一眼看得出往哪邊倒。
_STATE_SEG_CLASS: tuple[tuple[str, str], ...] = (
    (SS.STATE_LIVE, "dsl-seg dsl-seg-live"),
    (SS.STATE_DEGRADED, "dsl-seg dsl-seg-ring"),
    (SS.STATE_MISSING, "dsl-seg dsl-hatch"),
    (SS.STATE_UNWIRED, "dsl-seg dsl-bar"),
)


def render_credibility_card(judged: int, total: int, tally: dict) -> None:
    """卡②「訊號可信度」—— N/M 盞 + 四態分佈條 + 圖例。

    `judged` / `total` 由 `aggregate_judged` 算出(防呆 1 的定義),`tally` 由
    `tally_states` 算出。**兩者分母口徑一致**（都排除結構上不適用的格子）——
    否則同一張卡會出現兩個對不起來的總數。

    ⚠️ 分佈條**不用顏色編狀態**(見 CSS 註解):本檔的顏色一律代表「判定」,
    再拿來代表狀態就會有兩種讀法。四段靠紋理分辨,與燈格牆同一套語彙。
    """
    _sum = sum(tally.values()) or 0
    _segs = ""
    for _state, _cls in _STATE_SEG_CLASS:
        _n = tally.get(_state, 0)
        if _n <= 0:
            continue
        _segs += f'<div class="{_cls}" style="width:{_n / _sum * 100:.4f}%"></div>'
    _pct = f"{judged / total * 100:.0f}%" if total > 0 else "—"
    st.markdown(
        f'<div class="dsl-card"><h4>訊號可信度</h4>'
        f'<div class="dsl-head">{judged}/{total} 盞給得出判定'
        f'<span style="font-size:12px;opacity:.6;font-weight:400">　{_pct}</span></div>'
        f'<div class="dsl-bar-wrap">{_segs}</div>',
        unsafe_allow_html=True)
    # 圖例:重用 `render_legend` 的同一組示範格 + `STATE_META` 的中文標籤(文案 SSOT)。
    _lg = "　".join(
        f'{cell_html(_DemoCell(level="⚪", state=_s))}{SS.STATE_META[_s][0]} {tally.get(_s, 0)}'
        for _s, _ in _STATE_SEG_CLASS
    )
    st.markdown(
        f'<div class="dsl-lg">{_lg}</div>'
        f'<div class="dsl-sub" style="margin-top:6px">'
        f'分母扣掉兩種燈:一是「這類持股結構上沒有的」(個股沒有折溢價);'
        f'二是「依規格就不出等級的」—— 目前只有個股 KD,'
        f'K、D 都抓得到、也照樣畫在下面的燈格牆上,但它還沒有判燈規則,'
        f'留在分母只會讓每一檔個股永遠差一盞。'
        f'**沒有**扣掉「今天沒抓到的燈」—— 抓不到就是要把分數拉低。<br>'
        f'⚠️ 分子**至多**等於這一排的「運作中」,可能更少:'
        f'「運作中」只問**資料管道通不通**,分子還多要求那盞燈**真的產出了等級**。<br>'
        f'✅ 這個數字與下方燈格牆的「有判定」是**同一把尺**'
        f'(2026-08-26 起;在那之前燈格牆用的是比較寬鬆的「在看」,同一頁兩個數字差 1)。'
        f'</div></div>',
        unsafe_allow_html=True)


def render_todo_card(*, add_n: int, cut_n: int, unjudged_n: int) -> None:
    """卡③「需要處理的檔數」。

    三個數字**全部來自上游既有結論**:`add_n` / `cut_n` 是 L3
    `build_station_digest` 的 `adds` / `reds` 長度(與 LINE 推播同定義),
    `unjudged_n` 是「這一列不是每盞燈都給得出判定」的列數(含整檔抓取失敗)。

    ⚠️ 三者**可以重疊**（一檔可以同時亮加碼燈又有燈缺資料）,故刻意**不加總**、
    也不寫「共 N 檔要處理」—— 那個總數會比實際檔數大,是憑空生出來的數字(§1)。
    """
    st.markdown(
        f'<div class="dsl-card"><h4>需要處理的檔數</h4>'
        f'<div class="dsl-figs" style="margin-top:2px">'
        f'{_fig(str(add_n), "該加碼")}{_fig(str(cut_n), "該換掉")}'
        f'{_fig(str(unjudged_n), "今天判斷不了")}</div>'
        f'<div class="dsl-sub" style="margin-top:8px">'
        f'三個數字**可能重疊**(同一檔可以既亮加碼燈、又有燈缺資料),故不相加。'
        f'「該加碼」= 235 有加碼金;「該換掉」= 健檢紅燈;'
        f'「今天判斷不了」= 這一列有燈給不出判定(含整檔抓取失敗)。</div></div>',
        unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# 六、第 2 層 —— 兩套刻度對照表
# ══════════════════════════════════════════════════════════════════════
#
# ## 這張表在解什麼
#
# 同一個名詞在這個 app 的不同區塊被**兩套不同的尺**量。使用者對照兩個畫面時
# 會看到兩個數字,而它們都不是錯的 —— 錯的是沒有人告訴他這是兩把尺。
#
# ## 這張表**不**做什麼
#
# **只揭露,不改判定。** 第 1 列以外的三列都維持現行行為;統一它們是策略決定,
# 要 user 拍板,不在本次範圍。第 1 列之所以不同,是因為它已經被當成 bug 修掉了
# (commit `1a0992b` / `1030c28`),舊文案再寫「可能相反」就是在教使用者用一把
# 已經不存在的尺。
#
# §3.3:本表引用的門檻一律從 `T`(L0 SSOT)組出,不在這裡重打數字。
# 沒有 SSOT 常數的那幾個(日線月均線的週期、σ 取樣視窗)**刻意不寫數字** ——
# 為了讓一張說明表變綠而新造常數,只會製造第二份真相(station_specs.py 檔頭
# 已就同一件事寫過同樣的警告)。改用「哪一層、哪個模組」定位,讀者查得到。

#: 兩套刻度四列。`(名詞, 這邊怎麼量, 那邊怎麼量, 現況)`。
#: 內容含刻意的 `<b>` 標記 → 本表**不經 `_esc`**,故**禁止**把任何使用者輸入
#: (代號 / 名稱 / Sheet 欄位)接進這裡;這是一張純靜態文案表。
def _two_scale_rows() -> tuple[tuple[str, str, str, str], ...]:
    return (
        (
            "有沒有吃到本金",
            "戰情室 健檢 A：近一年總報酬 vs 年化配息率",
            "第 5 區 🏛️ 核心資產戰情室：總報酬 vs 殖利率",
            (
                "<b>✅ 已修正，只剩一套。</b>兩邊現在都用還原價的價差當「含息總報酬」"
                "（<code>etf_calc.calc_total_return_1y</code> / "
                "<code>dividend_station.total_return_pct</code>）。"
                "舊版曾在還原價之外<b>再加一次現金配息</b>，殖利率被代數消掉、"
                "那盞紅燈實際只在問「總報酬是不是負的」—— 已當 bug 修掉。<br>"
                "殘留差異（<b>不是</b>兩把尺，是兩個窗口守衛）：上市未滿一年時"
                "兩邊的「資料夠不夠」判準不同（一個看今天往回 365 天有沒有資料、"
                "一個看實際跨度有沒有到 365 天的九成），"
                "所以剛上市的標的可能一邊出數字、一邊出「—」。"
                "<b>兩邊都不會給你灌水的數字</b>，只是誰先閉嘴的門檻不一樣。"
            ),
        ),
        (
            "跌多深該加碼",
            (
                f"235 加碼燈：<b>週線</b> {T.BOLL_PERIOD_WEEKS} 週布林 z"
                f"（σ 取這 {T.BOLL_PERIOD_WEEKS} 週），加碼金比例走 "
                f"<code>LIGHT_META</code>"
            ),
            (
                "第 5 區 🚀 衛星資產戰情室：<b>日線</b>月均線 ± n×σ"
                "（σ 取近一年日線），加碼比例是另一組字面值"
            ),
            (
                "⚠️ <b>兩把尺，只揭露不改。</b>同樣叫「σ」，但中心線（週均 vs 日均）、"
                "σ 的取樣視窗、以及對應的加碼比例三者全都不同 —— "
                "<b>同一檔在兩個畫面拿到不同的加碼建議是正常的</b>，不是哪邊算錯。"
                "要不要統一是策略決定，等你拍板。"
            ),
        ),
        (
            "核心 / 衛星目標比",
            (
                f"戰情室 📊 80/20：<b>固定</b>目標 "
                f"{T.CORE_TARGET_PCT:.0f}/{T.SATELLITE_TARGET_PCT:.0f}，"
                f"分類用「ETF＝核心、個股＝衛星」"
            ),
            (
                "第 5 區 🎯 vs regime 目標：目標<b>隨總經位階浮動</b>"
                "（<code>CoreSatelliteManager</code>），分類走 "
                "<code>assess_role_split</code>（債券／台股分類表／海外寬基／未知）"
            ),
            (
                "⚠️ <b>兩把尺，只揭露不改。</b>固定 80/20 是存股法的原始設定；"
                "浮動目標是依總經位階調整。一檔債券 ETF 在上面算「核心」、"
                "在下面會被歸「債券」而<b>不進股票腿的分母</b> —— "
                "兩個百分比本來就不會相等。"
            ),
        ),
        (
            "同一個比例出現三次",
            "本頁 📊 80/20（分母＝有張數均價的持股市值）",
            (
                "第 5 區 🧱 核心/衛星拆解（分母＝總市值，含債券）<br>"
                "第 5 區 🎯 vs regime 目標（分母＝<b>只算股票腿</b>）"
            ),
            (
                "⚠️ <b>三處，三個分母，只揭露不改。</b>同一頁上「核心佔比」會出現三個"
                "不同的百分比，因為三處的分母與分類規則都不一樣。"
                "看的時候請認明它旁邊寫的是哪一種分母，<b>不要跨區相減</b>。"
            ),
        ),
    )


def render_two_scales() -> None:
    """第 2 層 · 兩套刻度對照表。純靜態文案 + L0 門檻,不吃任何 row 資料。"""
    st.markdown("##### 📏 同一個名詞，兩套刻度")
    st.caption(
        "這個 app 有幾個地方用**兩把不同的尺**量同一件事。兩邊都不是壞掉 —— "
        "但如果沒有人講，你對照兩個畫面時會以為其中一邊算錯。以下四列一次講完；"
        "除了第一列已經當 bug 修掉之外，其餘**只揭露、不改判定**（要不要統一是策略決定）。"
    )
    _head = ("<tr><th>名詞</th><th>這邊怎麼量</th><th>那邊怎麼量</th>"
             "<th>現況</th></tr>")
    _body = "".join(
        f"<tr><td>{_n}</td><td>{_a}</td><td>{_b}</td><td>{_s}</td></tr>"
        for _n, _a, _b, _s in _two_scale_rows())
    st.markdown(
        f'<div class="dsl-scroll"><table class="dsl-tbl">{_head}{_body}</table></div>',
        unsafe_allow_html=True)
