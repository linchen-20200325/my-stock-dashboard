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
</style>
"""

CSS = _CSS_TEMPLATE.replace("__ORANGE__", TRAFFIC_ORANGE)


# ══════════════════════════════════════════════════════════════════════
# 三、純函式(無 st.*、無 I/O,可單測)
# ══════════════════════════════════════════════════════════════════════

def watch_count(cells) -> tuple[int, int]:
    """一列的「N/M 在看」—— N = 四態為 `live` 的燈數,M = 這一列的總燈數。

    ⚠️ 分母是**整列的燈**,不是「算得出來的燈」。抓取失敗的列同樣有 M 盞
    (L2 `missing_light_cells` 就是為此存在),否則分母會悄悄變小、畫面反而
    顯示可信度更高(§1)。
    """
    _cs = tuple(cells or ())
    return sum(1 for c in _cs if c.state == SS.STATE_LIVE), len(_cs)


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
    """燈格牆 —— 一列一行:代號 / 名稱 / 燈條 / N-M 在看。

    `items`: `[(代號, 名稱, cells), ...]`,由 L5 從 row 的 `_lights` 備妥。

    ⚠️ 這裡**不用 `st.expander` 也不用巢狀 `st.tabs`**:兩者的 body 在
    Streamlit 每次 app run 都會執行(收合只是前端),把 N 檔 × 12 盞燈塞進
    每列一個 expander,就是 STATE.md v19.132 產業熱力圖那個坑的另一個入口。
    整面牆是一次 `st.markdown` 的純 HTML,零 widget、零額外執行成本。
    """
    if not items:
        return
    _rows = []
    for _tk, _nm, _cells in items:
        _n, _m = watch_count(_cells)
        # 代號 / 名稱來自使用者的 Google Sheet → 一律 escape。名稱含 `<` 或 `&`
        # 時不 escape 會直接把整面牆的版面弄壞(不是安全問題,是會壞掉)。
        _rows.append(
            f'<div class="dsl-row"><span class="dsl-tk">{_esc(_tk)}</span>'
            f'<span class="dsl-nm">{_esc(_nm or "")}</span>'
            f'{strip_html(_cells)}'
            f'<span class="dsl-cnt">{_n}/{_m} 在看</span></div>')
    st.markdown("".join(_rows), unsafe_allow_html=True)


def render_holding_detail(ticker: str, name: str, cells,
                          *, value_texts: dict[str, str] | None = None,
                          error: str = "") -> None:
    """單一持股的逐盞燈明細(右欄常駐面板,點左表任一列就地更新)。

    Streamlit 沒有原生 Drawer,且 `st.expander` 的 body 每次 rerun 都會執行 ——
    故採「常駐右欄 + 只渲染被選中那一列」,與總經 v2 第 3 層同一套做法。

    `value_texts`: `{規格表 key: 這盞燈實際算出什麼}`。由 L5 從 row 的 `_detail`
      對應過來;沒有對應文字的燈顯示「—」,**不由本層編一句**(§1)。
    """
    _vt = value_texts or {}
    _n, _m = watch_count(cells)

    st.markdown(f"### {ticker}　{name or ''}".rstrip())   # st.markdown 預設不吃 raw HTML
    st.markdown(f'{strip_html(cells)}　<span class="dsl-cnt">{_n}/{_m} 盞在看</span>',
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
