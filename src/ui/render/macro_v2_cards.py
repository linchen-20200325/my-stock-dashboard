"""src/ui/render/macro_v2_cards.py — L4 總經 v2 卡片 / 燈號 / 走勢圖渲染。

只負責「把已經算好的資料畫出來」。**不取數、不判斷業務邏輯、不碰 session_state。**
資料由 L5 `src/ui/tabs/tab_macro_v2.py` 備妥後傳進來。

§3.3 反捏造 —— 本檔**不寫死任何門檻數字或指標名單**:
  · 門檻帶文字 / 門檻虛線 ← `shared.macro_buckets.DangerSpec`(L0 SSOT)
  · 判燈            ← `shared.macro_buckets.classify_danger`(**用上游函式,不自己重寫**)
  · 教學文案        ← 由 caller 從 L3 `services.macro_v2_service.get_edu` 取好傳入
    (本層**不 import L1** —— §8.2「L4 Render 不得直呼 L1 Data」)
  上游改門檻,本頁自動跟著改。

§1 Fail Loud —— 沒有值就顯示「無資料」並說明原因,**絕不編數字填空**;
  沒有歷史序列的指標**不畫圖**(見 `tab_macro_v2._CHART_SPECS` 的挑選理由)。
"""
from __future__ import annotations

import html as _html
from dataclasses import dataclass

import plotly.graph_objects as go
import streamlit as st

from shared.colors import (
    COLORS_7,
    TRAFFIC_GREEN,
    TRAFFIC_RED,
    TRAFFIC_YELLOW,
)
from shared.macro_buckets import DangerSpec, has_thresholds

# ══════════════════════════════════════════════════════════════════════
# 視覺常數
# ══════════════════════════════════════════════════════════════════════

#: 四態 → (中文標籤, 色碼, emoji 雙重編碼)。good/warn/serious 取本專案既有
#: 語意色慣例;「未接線」刻意**不給顏色**(斜線紋)—— 它不是一種燈號等級,
#: 是「沒有消息」。
#:
#: ## 第三欄(emoji)為什麼在這裡,不在畫面層
#:
#: 中文標籤已經住在這張表,emoji 是**同一件事的另一種編碼**。拆兩個地方
#: 放,就是兩把尺:上游哪天多一個狀態、或改一個標籤,必然有一邊沒跟上,
#: 而畫面看起來完全正常(§3.3)。故兩者同列同表,物理上無法分岔。
#: 消費端請走 `state_cell()`,不要自己拼字串。
#:
#: ## 為什麼「門檻已失準」是 🟠 ⚠️ 而不是 🔴 ❌
#:
#: 它的語意是「**有值、燈照亮,只是別照門檻讀**」—— 不是壞掉。紅色叉會
#: 讓人以為那盞燈故障,但它正在正常回報數字(user 2026-08-26 裁示)。
#:
#: ## 為什麼「無資料」⚪ 與「未接線」⚫ 一定要不同
#:
#: 兩者的色碼本來就**同一個灰**(`#8a8e96`,見下),肉眼分不出來 —— 而這
#: 四態存在的整個理由,就是要把「上游這次沒給值」與「決策端根本沒接這條
#: 線」分開。色碼不區分是既有問題,emoji 這一欄把它補上。
#:
#: ## ⚠️ 姊妹檔 `src/ui/render/station_cards.py` 的狀態頻道**刻意不出 emoji**
#:
#: 那不是漏改,也不是本檔漏看 —— 兩邊的前提不同,結論才不同:
#:   · **配息車站**的判定頻道印的就是 emoji 本身(`LEVEL_STYLES` 的
#:     🔴/🟡/🟢/⚪)。狀態再出一個 🟢,同一格旁邊會出現**兩個 🟢**,
#:     等於自己製造混淆再花一段文案解釋。故該檔只取 `STATE_META[...][0]`。
#:   · **總經 v2 第 3 層**的「燈」欄印的是中文「綠 / 黃 / 紅 / 無資料」
#:     (`BAND_META[...][0]`),**不是 emoji**。同列不存在同形符號,碰撞的
#:     前提不成立,所以這裡出 emoji 是安全的。
#: ⚠️ **這個豁免是有條件的**:哪天有人把「燈」欄也改成 emoji(🟢/🟡/🔴),
#:    上面那個前提就當場失效,🟢 會與本表的 live 撞在同一列 —— 屆時請回頭
#:    讀 `station_cards.py` 檔頭那段,不要只改一欄就上線。
#:    (user 2026-08-26 裁示:「燈」欄維持純文字,理由是視覺重心要留給核心結論。)
STATE_META: dict[str, tuple[str, str, str]] = {
    "live": ("運作中", "#0ca30c", "🟢 ✅"),
    "degraded": ("門檻已失準", "#ec835a", "🟠 ⚠️"),
    "missing": ("無資料", "#8a8e96", "⚪ ➖"),
    "unwired": ("未接線", "#8a8e96", "⚫ 🔌"),
}

#: 未定義狀態的 fallback。**不是第五個狀態** —— 走到這裡代表上游冒出了
#: 四態以外的東西,是 bug 的徵兆,不是一種正常結果。故 `state_cell()` 會
#: 同時 `print` 一行警告(§1:不靜默),畫面則誠實顯示「未知狀態」而不是
#: 猜一個最接近的態塞給使用者。
STATE_UNKNOWN_META: tuple[str, str, str] = ("未知狀態", "#8a8e96", "⚪ ❓")


def state_cell(state: str) -> str:
    """狀態欄的顯示字串 = `emoji 雙重編碼 + 中文標籤`(如 `🟢 ✅ 運作中`)。

    **狀態的文字與 emoji 都只在 `STATE_META` 定義一次**,消費端呼叫本函式
    取字串,不要自己 `f"{emoji} {label}"` 拼 —— 拼了就是第二把尺(§3.3)。

    為什麼要 emoji + 中文兩種一起出而不是只出 emoji:emoji 是**冗餘**編碼,
    是加在文字旁邊的第二個線索,不是文字的替代品。只出 emoji 等於把資訊
    綁死在「看得懂這個符號」上,對讀螢幕的人反而更糟。

    §1 —— 未定義的 `state` 不靜默:走到 fallback 代表上游出現了沒人預期的
    狀態(四態以外),那是要有人去看的事。畫面顯示「⚪ ❓ 未知狀態」讓使用
    者知道這格不可信,同時 `print` 一行留下痕跡(比照 `macro_helpers._rec`
    / `_unwired` 對 SSOT 缺欄位的既有做法)。**不回退成「無資料」** ——
    那會把一個 bug 偽裝成一種正常結果。
    """
    meta = STATE_META.get(state)
    if meta is None:
        print(f"[macro_v2_cards/state_cell] ⚠️ 未定義的狀態 {state!r}"
              f"(已知四態:{list(STATE_META)}),畫面以「"
              f"{STATE_UNKNOWN_META[0]}」顯示 —— 請查上游 readiness 側車")
        meta = STATE_UNKNOWN_META
    return f"{meta[2]} {meta[0]}"


#: 「這條線不判燈」的 band key。**與 `"gray"` 是兩件事**:
#:   · `"gray"` = 有門檻、只是這次**沒有值**(上游沒給)。
#:   · `BAND_REFERENCE` = **本來就沒有門檻**,不存在「該亮哪盞燈」這個問題;
#:     值可能好端端地在那裡(加權指數 24,500 點就是)。
#: 兩者混用的後果實測過:K 線卡右上角印「無資料」,而卡片正在畫 60 根真實
#: K 棒 —— **畫面說沒有、內容有**,正是 §1 最忌的那種矛盾。
BAND_REFERENCE: str = "reference"

#: band → (中文標籤, 色碼)。**五個 band,不是四個。**
#:
#: ## 為什麼「無資料」與「不判燈」共用同一個灰
#:
#: 兩者都不該搶視覺重心(它們都不是一盞亮著的燈),所以**色碼刻意相同**,
#: 區分完全由中文標籤承擔。這與 `STATE_META` 的 missing/unwired 是同一個
#: 已知取捨,差別在那邊多一欄 emoji 來補、這邊沒有 emoji 欄 ——「燈」欄
#: 維持純文字是 user 2026-08-26 的裁示(理由見上方 `STATE_META` 那段)。
#: ⚠️ 要改色請兩邊一起想:給「不判燈」單獨挑一個新灰,等於在畫面上**新增
#: 一種顏色語意**,那是視覺規格,不是 L4 自己能拍板的事。
BAND_META: dict[str, tuple[str, str]] = {
    "green": ("綠", "#0ca30c"),
    "yellow": ("黃", "#fab219"),
    "red": ("紅", "#d03b3b"),
    "gray": ("無資料", "#8a8e96"),
    BAND_REFERENCE: ("不判燈", "#8a8e96"),
}


#: band → 燈號 emoji。**只為了回答「危險度那顆燈與位階那顆燈是不是同色」**
#: 這一個問題(D1 並列揭露,2026-08-27),不代表 band 與 regime 語意相等 ——
#: 它們根本不是同一個量(見 `render_regime_parallel` 的 docstring)。
#:
#: 為什麼住在 L4 而不是用它的 L5：本檔是這一頁**所有** emoji 與中文標籤的家
#: (`STATE_META` / `BAND_META` 都在這裡),`tests/test_macro_v2_tab.py::
#: TestStateColumnDualCoding` 也明文守著「L5 不得自己寫一份 emoji」。
#: 比較邏輯留在 L5 `parallel_verdict()`，本層只提供字面。
BAND_LIGHT: dict[str, str] = {
    "green": "🟢",
    "yellow": "🟡",
    "red": "🔴",
    "gray": "⬜",
}


def band_meta(band: str, spec: DangerSpec) -> tuple[str, str]:
    """band + spec → 畫面上該顯示的 (中文標籤, 色碼)。**消費端請走這裡。**

    直接 `BAND_META[row.band]` 會漏掉一件事:**沒有門檻的 spec 送進來的
    `"gray"`,語意不是「無資料」**。上游(L5)對無門檻 spec 一律填 `"gray"`
    —— 那不是它填錯,是 `classify_danger` 對無門檻 spec 會 TypeError
    (L0 刻意的 fail loud),它只能填一個中性值。真正知道「這條線根本沒有
    門檻」的資訊在 `spec` 裡,而 `spec` 本來就傳到這一層了。

    判定完全走 L0 SSOT `has_thresholds(spec)`,**本層不列任何指標名單** ——
    列了就是第二把尺:上游哪天多一條參考走勢,名單不會自己長(§3.3)。

    收斂條件刻意寫得很窄(`band == "gray"` **且** 無門檻):
      · 有門檻 → 一律原樣,`"gray"` 仍讀成「無資料」(零行為變更)。
      · 無門檻卻送來 green/yellow/red → **不動它**。那是上游出了事
        (沒有門檻怎麼判出綠燈?),把它改寫成「不判燈」會把 bug 蓋掉。
      · 上游若哪天直接送 `BAND_REFERENCE` 進來,這裡照樣認得。
    """
    if band == "gray" and not has_thresholds(spec):
        band = BAND_REFERENCE
    return BAND_META[band]

CSS = """
<style>
/* 半透明底 + color:inherit —— 讓卡片在 Streamlit 亮/暗兩種佈景都成立,
   不寫死任何背景色(寫死必有一邊不能看)。 */
.v2-t{font-size:11px; font-weight:700; letter-spacing:.09em;
      text-transform:uppercase; opacity:.62; margin:0 0 10px;}
.v2-hero{font-size:46px; font-weight:700; line-height:1; letter-spacing:-.02em;}
.v2-hero small{font-size:19px; font-weight:500; opacity:.6; margin-left:3px;}
/* 並列揭露（D1）：同一張卡的下半，印「市場位階」那一條。刻意比 .v2-hero 小 ——
   兩者是**並列**不是主從，但危險度是本頁自己算的、位階是外部唯讀帶進來的，
   字級相同會讓人以為本頁也在算位階。 */
.v2-reg{font-size:24px; font-weight:700; line-height:1.25;}
.v2-pill{display:inline-flex; align-items:center; gap:5px; font-size:11.5px;
         font-weight:500; padding:2px 9px; border-radius:99px; line-height:1.6;
         background:rgba(128,128,128,.16); white-space:nowrap;}
.v2-dot{width:8px; height:8px; border-radius:50%; flex:none;}
.v2-hatch{width:8px; height:8px; flex:none; border:1px solid #8a8e96;
          background:repeating-linear-gradient(45deg,#8a8e96 0 1.5px,transparent 1.5px 4px);}
.v2-sig{display:flex; gap:2px; height:24px; margin:10px 0 12px;}
.v2-sig span{flex:1; border-radius:2px; min-width:4px;}
.v2-bk{border:1px solid rgba(128,128,128,.28); border-radius:11px; overflow:hidden;}
.v2-bk-bar{height:5px;}
.v2-bk-in{padding:11px 13px 13px;}
.v2-bk-n{font-size:13px; font-weight:700; margin:0 0 3px;}
.v2-bk-l{font-size:12.5px; opacity:.75; margin:0 0 8px; min-height:2.6em;}
.v2-bk-m{font-size:11.5px; opacity:.55; margin:0;}
.v2-src{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
        font-size:11px; opacity:.6; word-break:break-all;}
.v2-note{font-size:12.5px; opacity:.8; background:rgba(128,128,128,.10);
         border-radius:8px; padding:10px 12px; margin:8px 0 0;}
.v2-dead{border:1px dashed rgba(138,142,150,.7); background:rgba(138,142,150,.10);}

/* ── 第 3 層的列印雙軌 ────────────────────────────────────────────────
   螢幕看互動表(`st.dataframe`,點一列右側就地展開);列印看純 HTML 表。

   為什麼非得兩份:`st.dataframe` 走 glide-data-grid,整張表畫在 <canvas>
   上而且是**虛擬捲動** —— 捲出視窗的那幾列**根本不在 DOM 裡**。這件事
   CSS 救不了(沒有東西可以被印),所以列印時必須另外給一份真的 HTML 表。

   `.st-key-v2_detail_table` 是 Streamlit 把 widget 的 `key=` 轉成的 class
   (`st.dataframe(key="v2_detail_table")` → 該元素容器帶 `st-key-` 前綴的
   class)。用它**只收掉這一張表**,而不是 `[data-testid="stDataFrame"]`
   全域收 —— 全域收會連別的分頁(個股組合批次表等)的主表一起印不出來。
   若部署端 Streamlit 舊到不產生這個 class:列印會同時出現「截斷的互動表」
   與「完整的 HTML 表」—— 醜,但資料仍然完整,不會少印東西。 */
.v2-print-only{display:none;}
@media print{
  .v2-print-only{display:block!important;}
  .st-key-v2_detail_table{display:none!important;}
  .v2-print-cap{font-size:12px; margin:0 0 6px;}
  .v2-print-tbl{border-collapse:collapse; width:100%; font-size:11.5px;}
  .v2-print-tbl th,.v2-print-tbl td{border:1px solid #999; padding:3px 6px;
                                    text-align:left; vertical-align:top;}
  .v2-print-tbl th{font-weight:700;}
  .v2-print-tbl tr{break-inside:avoid;}
}
</style>
"""


# ══════════════════════════════════════════════════════════════════════
# 純函式(無 st.*、無 I/O,可單測)
# ══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Row:
    """一盞燈在畫面上的完整樣貌。由 L5 從 readiness 側車組出。"""
    key: str
    label: str
    bucket: str           # 桶 key(long/mid/short/chips/news)
    unit: str
    value: float | None
    band: str             # green / yellow / red / gray / reference
                          # ⚠️ 顯示請走 `band_meta(band, spec)`,別直讀
                          #    BAND_META —— 無門檻 spec 的 "gray" 不是
                          #    「無資料」,是「不判燈」(見該函式)。
    state: str            # live / degraded / missing / unwired
    reason: str | None    # state=missing 時的 MISSING_* 原因
    hit_source: str | None
    thr_text: str
    source: str
    note: str
    decimals: int


def fmt_value(value: float | None, unit: str, decimals: int) -> str:
    """格式化顯示值。None → 「無資料」,**不代任何預設數字**(§1)。"""
    if value is None:
        return "無資料"
    txt = f"{value:,.{decimals}f}".replace("-", "−")   # U+2212 真減號
    if not unit:
        return txt
    # % 緊貼數字;中文單位(口/億/分/則)空一格才不會黏在一起
    return f"{txt}{unit}" if unit == "%" else f"{txt} {unit}"


def threshold_text(spec: DangerSpec) -> str:
    """門檻帶文字 —— 由 DangerSpec 即時組出,本檔不寫死任何數字。"""
    d, dec = spec.direction, spec.decimals

    def n(v: float) -> str:
        return f"{v:,.{dec}f}".replace("-", "−")

    if d == "band":
        parts = []
        if spec.yellow_lo is not None and spec.red_lo is not None:
            parts.append(f"紅 ≤{n(spec.red_lo)} / 黃 ≤{n(spec.yellow_lo)}")
        if spec.yellow is not None and spec.red is not None:
            parts.append(f"黃 ≥{n(spec.yellow)} / 紅 ≥{n(spec.red)}")
        return "　".join(parts) or "—"
    arrow = "≥" if d == "high_bad" else "≤"
    bits = []
    if spec.yellow is not None:
        bits.append(f"黃 {arrow}{n(spec.yellow)}")
    if spec.red is not None:
        bits.append(f"紅 {arrow}{n(spec.red)}")
    return " / ".join(bits) or "—"


def print_table_html(table: dict[str, list], caption: str) -> str:
    """把 `st.dataframe` 那份欄位 dict 原樣轉成一張**純 HTML** 表(列印用)。

    ⚠️ **本函式不做任何篩選、排序、格式化或補值。** 它吃什麼就畫什麼 ——
    參數 `table` 必須就是 `tab_macro_v2.visible_table()` 回傳、同一刻餵給
    `st.dataframe` 的**那一個 dict**。

    為什麼要寫得這麼死:同一頁上兩張表如果各自組資料,遲早會分岔,而分岔
    的樣子是「畫面說 A、印出來是 B」,兩邊都看起來很正常(§1)。把「組表」
    這件事留在 `visible_table()` 一處、這裡只做 dict → HTML 的機械轉換,
    分岔就在呼叫端寫不出來。

    `caption` 由 caller 傳入(要把**目前的篩選條件**講出來)—— 一張印出來
    只有 3 列的表,若沒說「16 盞裡篩了 3 盞」,讀的人會以為只有 3 盞燈。

    值一律 `html.escape`:內容目前全部來自 SSOT(BAND_META / STATE_META /
    DangerSpec),沒有使用者輸入,但把轉義做在唯一的出口比較不會出事。
    """
    cols = list(table)
    n = len(table[cols[0]]) if cols else 0
    head = "".join(f"<th>{_html.escape(str(c))}</th>" for c in cols)
    body = "".join(
        "<tr>" + "".join(
            f"<td>{_html.escape(str(table[c][i]))}</td>" for c in cols
        ) + "</tr>"
        for i in range(n)
    )
    return (
        '<div class="v2-print-only">'
        f'<p class="v2-print-cap">{_html.escape(caption)}</p>'
        f'<table class="v2-print-tbl"><thead><tr>{head}</tr></thead>'
        f'<tbody>{body}</tbody></table></div>'
    )


def pill(text: str, color: str, hatch: bool = False) -> str:
    mark = '<span class="v2-hatch"></span>' if hatch \
        else f'<span class="v2-dot" style="background:{color}"></span>'
    return f'<span class="v2-pill">{mark}{text}</span>'


# ══════════════════════════════════════════════════════════════════════
# 渲染
# ══════════════════════════════════════════════════════════════════════

def render_regime_parallel(*, light: str, zh: str, source: str,
                           loaded: bool, note: str) -> None:
    """第 1 層標題卡的**下半**：並列印出「市場位階」（D1，2026-08-27 客戶核准）。

    為什麼要並列而不是合併(驗證結論見 `scratchpad/verify_regime_paths.md`)：
    「指標危險度」與「市場位階」**不是同一個量** —— 前者是 16 盞燈的
    worst-of 危險度(不含多空方向)，後者是多空位階(看不到 VIX / PMI / CPI /
    融資)。實跑 400 組格點燈色不一致 39.5%、方向相反 18 組，其中最容易對打的
    不是極端值而是**健康的多頭**(多頭走久 BIAS240 必然放大、融資恆紅)。
    合併等於宣稱「沒有指標踩線 = 多頭」，會把 `regime_arbiter` 剛收掉的
    多來源問題重新製造一個。

    ⚠️ **本函式只印，不判斷、不比較、不調和。** 要印什麼(含 `note` 那句話)
    全部由 L5 `tab_macro_v2.parallel_verdict()` 決定 —— 只有那裡同時看得到
    兩個判斷。這一層若自己再比一次，畫面上就會有第二把尺。

    Args:
        light:  位階燈號 emoji(🟢/🟡/🔴/⬜)，來自 `get_macro_regime()['light']`。
        zh:     位階中文(`shared.allocation_decision.REGIME_LABEL`)。
        source: 生效分支識別碼(`regime_arbiter.SOURCE_*`)，讓使用者看得到
                「為什麼是這個燈」。
        loaded: 位階是否已評估。False → 誠實印「尚未評估」，**不留白、
                也不拿危險度的燈頂替**(§1)。
        note:   兩者關係的說明(L5 依 loaded / 是否同色挑好的那一句)。
    """
    st.divider()
    st.markdown('<p class="v2-t">市場位階 · 全站唯一出處</p>', unsafe_allow_html=True)
    if loaded:
        st.markdown(
            f'<div class="v2-reg">{_html.escape(light)}'
            f'<span style="margin-left:8px">{_html.escape(zh)}</span></div>'
            f'<div class="v2-src" style="margin-top:4px">{_html.escape(source)}</div>',
            unsafe_allow_html=True)
    else:
        # §1：未評估就寫未評估。這裡**不得**印綠燈、不得沿用上半的危險度燈。
        st.markdown(
            '<div class="v2-reg" style="opacity:.62">⬜'
            '<span style="margin-left:8px">尚未評估</span></div>',
            unsafe_allow_html=True)
    # `st.caption` 走 markdown（note 是本檔外的模組常數，含 `**` 強調），
    # 刻意不塞進 `<p class="v2-note">` —— 那條路要 raw HTML，會逼得常數改寫成
    # 標籤，而那些字串是要給人讀的。
    st.caption(note)


def render_signal_health(rows: list[Row]) -> None:
    """訊號可信度卡 —— 16 盞燈裡有幾盞真的在運作。

    這張卡是 v2 存在的主要理由之一:現行畫面上「從沒亮過的燈」與
    「正常的綠燈」長得一模一樣,使用者沒有任何方式分辨。
    """
    n_live = sum(1 for r in rows if r.state == "live")
    st.markdown('<p class="v2-t">訊號可信度</p>', unsafe_allow_html=True)
    st.markdown(
        f'<div><span style="font-size:32px;font-weight:700">{n_live}</span>'
        f'<span style="font-size:13px;opacity:.6">　／{len(rows)} 個指標正常運作中</span></div>',
        unsafe_allow_html=True)

    seg = []
    for r in rows:
        if r.state in ("unwired", "missing"):
            seg.append('<span style="border:1px solid #8a8e96;background:'
                       'repeating-linear-gradient(45deg,#8a8e96 0 2px,transparent 2px 5px)"></span>')
        else:
            seg.append(f'<span style="background:{STATE_META[r.state][1]}"></span>')
    st.markdown(f'<div class="v2-sig">{"".join(seg)}</div>', unsafe_allow_html=True)

    for skey, (label, color, _emoji) in STATE_META.items():
        cnt = sum(1 for r in rows if r.state == skey)
        if not cnt:
            continue
        st.markdown(
            f'<div style="display:flex;font-size:12.5px;padding:2px 0">'
            f'{pill(label, color, hatch=(skey in ("unwired", "missing")))}'
            f'<b style="margin-left:auto;font-variant-numeric:tabular-nums">{cnt}</b></div>',
            unsafe_allow_html=True)


def render_bucket_cards(summary: list[dict]) -> None:
    """五桶卡 —— 每桶最差燈 + 指標數 + 不可信數(worst-of rollup)。"""
    if not summary:
        return
    cols = st.columns(len(summary), gap="small")
    for col, b in zip(cols, summary):
        zh, color = BAND_META[b["band"]]
        with col:
            bad = f'　·　{b["n_bad"]} 個不可信' if b["n_bad"] else ""
            st.markdown(
                f'<div class="v2-bk"><div class="v2-bk-bar" style="background:{color}"></div>'
                f'<div class="v2-bk-in">'
                f'<p class="v2-bk-n">{b["name"]}　{pill(zh, color)}</p>'
                f'<p class="v2-bk-l">最差項:{b["worst_label"]} {b["worst_value"]}</p>'
                f'<p class="v2-bk-m">{b["n"]} 個指標{bad}</p>'
                f'</div></div>',
                unsafe_allow_html=True)


#: 走勢卡腳註裡「門檻線」那一段的兩種說法。**只在這裡定義一次** —— 分兩處寫,
#: 哪天改了一句沒改另一句,畫面上完全看不出來(§3.3)。
_CAP_HAS_THR: str = "門檻線由 SSOT 畫出"
_CAP_NO_THR: str = "本卡沒有門檻線（這個指標未設門檻）"


def threshold_caption(spec: DangerSpec) -> str:
    """腳註該說「門檻線由 SSOT 畫出」還是「沒有門檻線」。

    為什麼需要分支:這句話原本是**無條件**印的,而加權指數的 spec 四個門檻欄
    全是 None,`_threshold_lines_ssot` 一條線都畫不出來(實測
    `fig.layout.shapes == 0`)—— 腳註說有、圖上沒有,兩邊都看起來很正常。

    判定走 L0 SSOT `has_thresholds(spec)`,本層不列名單、不寫死任何指標名。
    ⚠️ 這句話講的是 **L4 自己畫了什麼**(有沒有畫門檻線),不是業務原因 ——
    業務原因(為什麼這條序列不可用之類)屬 L5,見 `render_chart_card` 的
    `notice` 參數。
    """
    return _CAP_HAS_THR if has_thresholds(spec) else _CAP_NO_THR


def _threshold_lines(fig: go.Figure, spec: DangerSpec, *, yref: str = "y") -> None:
    """把 DangerSpec 的門檻畫成虛線 —— 數字來自 SSOT,不在此寫死。

    Parameters
    ----------
    yref : str
        門檻線要綁哪一條 y 軸(`"y"` 主軸 / `"y2"` 副軸)。**預設 `"y"`**
        —— plotly 省略 `yref` 時本來就綁主軸(實測 6.9.0:shape 與其
        annotation 序列化出來都是 `yref="y"`),所以不傳 = 零行為變更。

        【為什麼要有這個參數】現在唯一的 caller `render_chart_card` 畫的是
        **單軸圖**,所以目前不傳也不會錯 —— 這不是在修一個現存 bug,是
        **一改雙軸就會中**的前置準備。若之後在同一張圖疊第二條軸
        (例:左軸 DXY ~105、右軸台幣 ~32),沿用「不傳 yref」的寫法會把
        台幣的 32/33 門檻線畫在**左軸的 32/33 位置**(圖底某處,離資料很遠),
        而畫面上它就是一條標著「黃線 32.0」的正常虛線 —— §1 最忌的那種錯:
        **畫面說 A、內容是 B,而且兩邊都看起來正常。**

        `add_hline` 會把 `yref` 同時套到虛線本身與它的標註(實測確認),
        所以線與標籤不會各綁一條軸。
    """
    for val, color, name in (
        (spec.yellow, "#b8860b", "黃線"),
        (spec.red, "#d03b3b", "紅線"),
        (spec.yellow_lo, "#b8860b", "黃線(下)"),
        (spec.red_lo, "#d03b3b", "紅線(下)"),
    ):
        if val is None:
            continue
        fig.add_hline(
            y=val, line_dash="dash", line_color=color, line_width=1.2,
            yref=yref,
            annotation_text=f"{name} {val:,.{spec.decimals}f}".replace("-", "−"),
            annotation_position="right",
            annotation_font=dict(size=11, color=color),
        )


def render_value_card(row: Row, spec: DangerSpec) -> None:
    """純數值卡 —— 給**沒有歷史序列**的指標用(如 VIX)。

    §1:不畫沒有資料的圖。與其用合成序列讓版面「看起來完整」,
    不如誠實顯示「這個指標目前沒有歷史序列可畫」。
    """
    zh, color = band_meta(row.band, spec)
    with st.container(border=True):
        head, meta = st.columns([7, 3])
        with head:
            st.markdown(f'<p class="v2-t">{row.label}</p>', unsafe_allow_html=True)
            st.markdown(
                f'<div style="font-size:26px;font-weight:700;'
                f'font-variant-numeric:tabular-nums">'
                f'{fmt_value(row.value, row.unit, row.decimals)}</div>',
                unsafe_allow_html=True)
        with meta:
            st.markdown(f'<div style="text-align:right">{pill(zh, color)}</div>',
                        unsafe_allow_html=True)
        st.caption(f"門檻帶　{row.thr_text}")
        st.caption("此指標尚無落地歷史序列,故只顯示當前值 —— 不以合成資料充當走勢。")


def render_chart_card(row: Row, spec: DangerSpec, xs: list, ys: list[float],
                      *, kind: str = "line", series_note: str = "",
                      notice: str = "") -> None:
    """走勢卡 —— 只給**有真實歷史序列**的指標用。

    `xs` / `ys` 由 L5 從真實資料備妥;本函式不生成任何序列。

    Parameters
    ----------
    notice : str
        `ys` 為空時要印的那一句話。**留空 = 沿用預設「歷史序列取得失敗」,
        既有 caller 一個字都不會變。**

        【為什麼要有這個參數】預設那句話把「空序列」一律說成**取得失敗**,
        但空序列不只一種成因。融資餘額卡的實情是「**取到了,但資料不可用
        所以不畫**」—— 印「取得失敗」等於告訴使用者去查一個不存在的連線
        問題(§1:錯的說明比沒有說明更危險)。

        【為什麼原因字串由 caller 給,不在這裡分支】L4 不知道、也不該知道
        「融資餘額為什麼不可用」—— 那是 L5 的業務判斷。本層只負責**有一個
        管道能把它印出來**;真在這裡寫一張「哪個指標配哪句話」的表,就是把
        業務原因硬編進渲染層,而且必然與 L5 那份分岔(§3.3)。
    """
    zh, color = band_meta(row.band, spec)
    with st.container(border=True):
        head, meta = st.columns([7, 3])
        with head:
            st.markdown(f'<p class="v2-t">{row.label}</p>', unsafe_allow_html=True)
            st.markdown(
                f'<div style="font-size:26px;font-weight:700;'
                f'font-variant-numeric:tabular-nums">'
                f'{fmt_value(row.value, row.unit, row.decimals)}</div>',
                unsafe_allow_html=True)
        with meta:
            st.markdown(f'<div style="text-align:right">{pill(zh, color)}</div>',
                        unsafe_allow_html=True)

        if not ys:
            # ↓ 修正點:預設仍是「取得失敗」(零行為變更),但 caller 給了
            #   `notice` 就講實話 —— 空序列不等於取得失敗。
            st.caption(notice or "歷史序列取得失敗 —— 不以合成資料替代。")
            st.caption(f"門檻帶　{row.thr_text}")
            return

        n = len(ys)
        fig = go.Figure()
        if kind == "bar":
            fig.add_bar(x=xs, y=ys, marker_color="#2a78d6",
                        marker_opacity=[0.42] * (n - 1) + [1.0],
                        hovertemplate="%{y:,.0f}<extra></extra>", name=row.label)
        else:
            fig.add_scatter(x=xs, y=ys, mode="lines",
                            line=dict(color="#2a78d6", width=2),
                            fill="tozeroy", fillcolor="rgba(42,120,214,.13)",
                            hovertemplate="%{y:,.2f}<extra></extra>", name=row.label)
            fig.add_scatter(x=[xs[-1]], y=[ys[-1]], mode="markers",
                            marker=dict(color="#2a78d6", size=9),
                            showlegend=False, hoverinfo="skip")
        _threshold_lines(fig, spec)
        fig.update_layout(
            height=210, margin=dict(l=8, r=78, t=8, b=24), showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            hovermode="x unified",
            xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(size=10)),
            yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,.16)",
                       zeroline=False),
        )
        st.plotly_chart(fig, width='stretch',
                        config={"displayModeBar": False}, key=f"v2chart_{row.key}")
        st.caption(f"{threshold_caption(spec)}　·　{series_note}")


def render_detail(row: Row, spec: DangerSpec, edu: dict | None = None,
                  reason_text: str = "") -> None:
    """右側明細面板 —— Streamlit 沒有原生 Drawer,以常駐右欄取代:
    點左表任一列即就地更新,不跳頁。"""
    zh, color = band_meta(row.band, spec)
    slabel, scolor, _semoji = STATE_META[row.state]
    hatch = row.state in ("unwired", "missing")

    st.markdown(f"### {row.label}")
    st.markdown(f'{pill(slabel, scolor, hatch=hatch)}　{pill(zh, color)}',
                unsafe_allow_html=True)
    st.markdown(
        f'<div style="font-size:34px;font-weight:700;margin:8px 0 2px;color:{color}">'
        f'{fmt_value(row.value, row.unit, row.decimals)}</div>',
        unsafe_allow_html=True)
    st.caption(f"門檻帶　{row.thr_text}")
    if row.hit_source:
        st.caption(f"命中來源　{row.hit_source}")

    if edu:
        if edu["meaning"]:
            st.markdown("**這是什麼**")
            st.markdown(edu["meaning"])
        if edu["how_to_read"]:
            st.markdown("**怎麼看**")
            st.dataframe(
                {"條件": [a for a, _ in edu["how_to_read"]],
                 "判讀": [b for _, b in edu["how_to_read"]]},
                hide_index=True, width='stretch',
            )
        if edu["historical_anchor"]:
            st.markdown("**歷史錨點**")
            st.markdown(edu["historical_anchor"])
    else:
        st.info(f"`EDU_GUIDE` 沒有「{row.label}」的教學條目 —— 這裡不會幫它編一段。",
                icon="📭")

    if row.state == "unwired":
        st.markdown(
            f'<div class="v2-note v2-dead"><b>這盞燈沒有在運作</b><br>'
            f'{spec.unwired_reason or "（SSOT 未說明原因）"}</div>',
            unsafe_allow_html=True)
    elif row.state == "degraded":
        # 標題不另寫 —— degraded_reason 第一句本身就是結論,再加一句會重複。
        st.warning(spec.degraded_reason or "（SSOT 未填寫原因）", icon="⚠️")
    elif row.state == "missing" and reason_text:
        st.info(reason_text, icon="📭")

    if row.note:
        st.markdown(f'<div class="v2-note">{row.note}</div>', unsafe_allow_html=True)

    st.markdown("**門檻來源**")
    st.markdown(f'<span class="v2-src">{row.source}</span>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# 卡 A：雙軸走勢卡
# ══════════════════════════════════════════════════════════════════════
#
# 為什麼需要「第二種走勢卡」而不是把 `render_chart_card` 撐大:
# 卡 A「美元指數 / 台幣」左邊 DXY ~105、右邊 USDTWD ~32,**量級差 3.3 倍**。
# 兩條擠在同一條 y 軸上,台幣那條會被壓成一條貼底的水平線 —— 圖還在、線也在,
# 但它已經不傳達任何訊息。這不是美觀問題,是「畫面說有走勢、其實看不出走勢」。
#
# ⚠️ 本區塊最容易出錯、而且**錯了看起來完全正常**的地方是門檻線綁軸:
# plotly 省略 `yref` 時一律綁主軸,右軸台幣的 32 / 33 門檻會被畫在**左軸的
# 32 / 33 位置**(圖底某處),畫面上它就是一條標著「黃線 32.0」的正常虛線。
# 故本區塊的門檻線 helper 把 `yref` 設成**必填的具名參數**(見
# `_threshold_lines_ssot`)—— 讓「忘了傳」在語法層就寫不出來。

#: 門檻線色 —— **走 L0 `shared.colors` SSOT**,本區塊不寫 inline hex。
#:
#: ⚠️ 既有的 `_threshold_lines()` 用的是 inline `#b8860b` / `#d03b3b`。那是既有
#: 瑕疵,姊妹檔 `station_charts.py` 的測試已明文記載「刻意不抄過來」。本區塊
#: 是新寫的,沒有理由把瑕疵複製一份 —— 故走 SSOT。
#: **兩支函式的門檻「數字」仍然同源**(都只讀 `DangerSpec`,誰都沒有自己的一份),
#: 分岔只在色票,而且新的這一邊是對的。把舊函式一併收乾淨屬既有函式的行為變更,
#: 不在本次範圍內(避免夾帶),留待有人動 `render_chart_card` 時一起處理。
_THR_YELLOW: str = TRAFFIC_YELLOW
_THR_RED: str = TRAFFIC_RED

#: 序列本身的線色(「這是資料」,不是「這是門檻」)。取 L0 `COLORS_7`:
#: 第 1 色藍為本站多序列圖的第一條線慣例;右軸取第 5 色紫 —— 刻意**避開**
#: 黃 / 紅 / 橘,那幾個色在本頁已經被門檻與燈號佔用,撞色會讓人以為線在示警。
_SERIES_COLOR_LEFT: str = COLORS_7[0]
_SERIES_COLOR_RIGHT: str = COLORS_7[4]

#: 門檻標註要放在哪一側。**標註跟著自己的軸走** —— 左軸的門檻標在左邊、
#: 右軸的標在右邊。標在同一側的話,兩組數字會疊在一起而且看不出誰是誰的。
_THR_SIDE_LEFT: str = "left"
_THR_SIDE_RIGHT: str = "right"

#: 缺 `miss_reason` 時的文案。§1:**不猜**上游為什麼沒給,直接說這是程式要修的事。
#: (比照 `station_charts.miss_text_for` 對未登記 `MISS_*` 的處置。)
NO_REASON_TEXT: str = "上游沒有交代原因（程式要修）"


# ── 序列取用的兩個小工具 ────────────────────────────────────────────────
# 本區塊兩張新卡的契約是「**已攤平的 list**」(L4 不碰 pandas,見檔頭 §8.2)。
# 但 L5 手上的資料多半來自 DataFrame,`df["close"]` 這種寫法很自然就會傳進來。
# 下面兩個 helper 不是「支援 pandas」,是**讓契約被違反時炸在對的地方、
# 講對的話** —— 直接寫 `bool(seq)` / `seq[-1]` 的話,傳進 Series 會得到
# `ValueError: truth value ... ambiguous` 與 pandas 的**標籤**查找 KeyError,
# 兩個訊息都不會告訴讀的人「這一層要的是 list」。


def _has_points(seq) -> bool:
    """序列裡有沒有東西。`None` / 空 → False。

    刻意**不用** `bool(seq)`:pandas Series 的真值判斷會直接丟
    `ValueError: The truth value of a Series is ambiguous`,而那個訊息與
    「這條線沒有資料」是兩件完全不同的事,混在一起會讓人查錯方向。
    """
    return seq is not None and len(seq) > 0


def _last(seq):
    """序列末項(末點圓點用)。

    ⚠️ 不能直接寫 `seq[-1]`:對 pandas Series 那是**標籤**查找(找一個叫 -1 的
    索引),不是取最後一筆 —— 沒有這個標籤就 KeyError,有的話拿到的還是錯的那筆。
    """
    _iloc = getattr(seq, "iloc", None)
    return seq[-1] if _iloc is None else _iloc[-1]


def _threshold_lines_ssot(fig: go.Figure, spec: DangerSpec, *,
                          yref: str, side: str = _THR_SIDE_RIGHT) -> None:
    """把 `DangerSpec` 的門檻畫成虛線。數字來自 SSOT,色票來自 `shared.colors`。

    Parameters
    ----------
    yref : str
        **必填、且是具名參數**(沒有預設值)。`"y"` = 主軸,`"y2"` = 副軸。

        為什麼不給預設值 —— 這是本檔既有 `_threshold_lines(yref="y")` 的教訓
        反過來用:那支函式給了預設值,是為了讓既有 caller 零行為變更;但**新**
        的 caller 全都在畫雙軸圖,「忘了傳」在那裡不是零變更,是把右軸的門檻
        畫到左軸的座標上,而且畫面完全看不出來。必填 = 這個錯誤寫不出來。
    side : str
        標註放哪一側(`"left"` / `"right"`)。與 `yref` 分開兩個參數,是因為
        降級成單軸時軸會從 `y2` 變回 `y`,但標註仍該留在原本那一側。

    Notes
    -----
    **刻意不用 `fig.add_hline()`,改用顯式 `add_shape` + `add_annotation`。**
    `add_hline` 會不會把 `yref` 一併套到它產生的標註上,是它的內部行為:
    沙箱 plotly 6.9.0 實測**會**,但 `requirements.txt` 宣告的 floor 是
    **5.18.0**,那一版我在此無法實測。線綁對軸、標籤卻綁錯軸 = 一個「浮在
    別處的數字」,同樣是畫面說 A 內容是 B。顯式綁定讓這件事與 plotly 版本無關。
    """
    _x_anchor = "right" if side == _THR_SIDE_LEFT else "left"
    _x_paper = 0.0 if side == _THR_SIDE_LEFT else 1.0
    for val, color, name in (
        (spec.yellow, _THR_YELLOW, "黃線"),
        (spec.red, _THR_RED, "紅線"),
        (spec.yellow_lo, _THR_YELLOW, "黃線(下)"),
        (spec.red_lo, _THR_RED, "紅線(下)"),
    ):
        if val is None:
            continue
        fig.add_shape(
            type="line", xref="paper", x0=0, x1=1, yref=yref, y0=val, y1=val,
            line=dict(color=color, width=1.2, dash="dash"),
        )
        fig.add_annotation(
            xref="paper", x=_x_paper, xanchor=_x_anchor,
            yref=yref, y=val, yanchor="middle", showarrow=False,
            text=f"{name} {val:,.{spec.decimals}f}".replace("-", "−"),
            font=dict(size=11, color=color),
        )


def _v2_base_layout(fig: go.Figure, *, left_margin: int, right_margin: int) -> None:
    """本區塊兩張新卡共用的版面 —— 與既有 `render_chart_card` 同一組透明底設定。

    透明底 + 中性灰格線,**不硬碼任何背景色**:寫死背景塞進
    `st.container(border=True)` 會出現色塊接縫,而且亮 / 暗兩種佈景必有一邊不能看。
    (同 `station_charts._base_layout` 的理由;那邊檔頭寫得更完整。)

    ⚠️ 這是既有 `render_chart_card` 那份 layout 的第二份複本 —— 複本會漂移。
    故 `tests/test_macro_v2_dual_kline.py::TestLayoutMatchesExistingCard` 逐鍵
    比對兩者,任一邊改了視覺基調而另一邊沒跟上就轉紅。
    """
    fig.update_layout(
        height=210, margin=dict(l=left_margin, r=right_margin, t=8, b=24),
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(size=10)),
        yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,.16)",
                   zeroline=False),
    )


@dataclass(frozen=True)
class AxisSeries:
    """雙軸圖的**一條**序列。左右兩邊是同一個型別,結構完全對稱。

    ## 為什麼是「一個型別 × 兩個具名參數」而不是「一個可有可無的 spec」

    最直覺的寫法是讓 `render_dual_axis_card(row, spec, ..., spec2=None)` ——
    右邊沒有就不傳。那等於讓同一個參數位置**有時代表一條線的門檻、有時代表
    兩條線的門檻**,呼叫端要靠記憶判斷現在是哪一種,而判斷錯了畫面照樣畫得
    出來(§3.3 的第二把尺)。這裡把「一條序列該有什麼」封成一個型別,左右各
    給一份 —— 少給一邊在語法層就是錯的,不需要任何人記得。

    Attributes
    ----------
    row : Row
        這條序列對應的那盞燈。label / value / unit / decimals / band 全部沿用
        既有 `Row`,**本型別不另外開一份平行欄位**(開了就是第二把尺)。
    spec : DangerSpec
        **這條序列自己的**門檻。左右各一份,不共用。
    xs, ys : list
        由 L5 從真實資料備妥。本層不生成、不補值、不對齊 —— `ys` 是空的就是
        真的沒有(§1)。
    miss_reason : str
        `ys` 為空時,上游要交代**為什麼**沒有(給使用者看的一句話)。
        沒交代 → 畫面顯示 `NO_REASON_TEXT`,不編一個理由。
    """
    row: Row
    spec: DangerSpec
    xs: list
    ys: list[float]
    miss_reason: str = ""


#: `build_dual_axis_figure` 的四種結果。**「兩條都有」以外的三種都是降級**,
#: 而降級一定要在畫面上講清楚 —— 一張只剩一條線的圖若不說明,使用者會以為
#: 另一條「就是沒有變化」。
MODE_DUAL: str = "dual"
MODE_LEFT_ONLY: str = "left_only"
MODE_RIGHT_ONLY: str = "right_only"
MODE_NONE: str = "none"


@dataclass(frozen=True)
class DualAxisPlot:
    """`build_dual_axis_figure` 的產物 —— 圖 + 走了哪條路 + 要交代什麼。

    把「建 figure」與「渲染」分開,是為了讓 `fig` 能在測試裡直接斷言
    (比照姊妹檔 `station_charts.build_*_figure`)。既有 `render_chart_card`
    把 fig 建在函式體內、外面拿不到 —— 那個瑕疵不在這裡沿用。
    """
    fig: go.Figure | None
    mode: str
    notes: list[str]


def _miss_note(series: AxisSeries) -> str:
    """「某條線為什麼不在」的一句話。§1:上游沒說就說「程式要修」,不編理由。"""
    return f"{series.row.label}：{series.miss_reason or NO_REASON_TEXT}"


def _add_axis_trace(fig: go.Figure, series: AxisSeries, *,
                    color: str, yaxis: str) -> None:
    """畫一條線 + 末點圓點(與既有 `render_chart_card` 的線型一致)。

    雙軸圖**刻意不用 `fill="tozeroy"`**:既有單序列卡有填色,但兩條半透明
    填色疊在一起,交疊處會混出第三個顏色,看起來像第三條序列。
    """
    _dec = series.row.decimals
    fig.add_scatter(
        x=series.xs, y=series.ys, mode="lines", name=series.row.label,
        line=dict(color=color, width=2), yaxis=yaxis,
        hovertemplate=f"{series.row.label} %{{y:,.{_dec}f}}<extra></extra>")
    # ↓ 修正點:`xs[-1]` 對 pandas Series 是標籤查找,不是取最後一筆(見 `_last`)
    fig.add_scatter(
        x=[_last(series.xs)], y=[_last(series.ys)], mode="markers",
        marker=dict(color=color, size=9), yaxis=yaxis,
        showlegend=False, hoverinfo="skip")


def _build_single_axis(series: AxisSeries, *, color: str, side: str,
                       notes: list[str]) -> DualAxisPlot:
    """降級路徑:只有一條線有資料 → **單軸單線,完全不建立 y2**。

    ⚠️ 兩個一起做才算對,少做任何一個都會留下一個「看起來正常」的錯誤畫面:

    1. **不留空的右軸。** 留著一條沒有資料的 y2,畫面上會出現一排從 32 到 33
       的刻度而沒有任何線 —— 讀的人會以為那條線的值是 0(貼在軸底),而不是
       「這條線根本沒抓到」。
    2. **門檻線的 `yref` 要跟著改回 `"y"`。** 這條線現在住在主軸上,它的門檻
       若還綁 `"y2"`,plotly 會**憑空生出**一條隱形的 y2 並把門檻畫在那條軸的
       座標上 —— 又是一條位置錯誤但外觀正常的虛線。
    """
    fig = go.Figure()
    _add_axis_trace(fig, series, color=color, yaxis="y")
    _v2_base_layout(fig, left_margin=(78 if side == _THR_SIDE_LEFT else 8),
                    right_margin=(78 if side == _THR_SIDE_RIGHT else 8))
    # ↓ 修正點:降級後主軸是 "y" 而非 "y2"(見本函式 docstring 第 2 點)
    _threshold_lines_ssot(fig, series.spec, yref="y", side=side)
    return DualAxisPlot(
        fig=fig,
        mode=(MODE_LEFT_ONLY if side == _THR_SIDE_LEFT else MODE_RIGHT_ONLY),
        notes=notes)


def build_dual_axis_figure(left: AxisSeries, right: AxisSeries) -> DualAxisPlot:
    """兩條量級差很大的序列 → 左右雙軸 `go.Figure`。**純函式,可離線斷言。**

    `left` / `right` 是**兩個對稱的具名參數**,各自帶自己的 `DangerSpec` ——
    理由見 `AxisSeries` 的 docstring。

    降級(§1,一律誠實交代,不留看起來正常的空殼):

    ==================  ==========================================
    情況                 結果
    ==================  ==========================================
    兩條都有             `MODE_DUAL`,左軸 + 右軸
    只有左邊有           `MODE_LEFT_ONLY`,單軸單線,**不建 y2**
    只有右邊有           `MODE_RIGHT_ONLY`,單軸單線,**不建 y2**
    兩條都沒有           `MODE_NONE`,`fig` 為 `None`(不畫空圖)
    ==================  ==========================================

    任何降級都會在 `notes` 裡逐條說明「哪一條沒有、為什麼」。
    """
    _l_ok, _r_ok = _has_points(left.ys), _has_points(right.ys)

    if not _l_ok and not _r_ok:
        return DualAxisPlot(fig=None, mode=MODE_NONE,
                            notes=[_miss_note(left), _miss_note(right)])
    if not _r_ok:
        return _build_single_axis(left, color=_SERIES_COLOR_LEFT,
                                  side=_THR_SIDE_LEFT, notes=[_miss_note(right)])
    if not _l_ok:
        return _build_single_axis(right, color=_SERIES_COLOR_RIGHT,
                                  side=_THR_SIDE_RIGHT, notes=[_miss_note(left)])

    fig = go.Figure()
    _add_axis_trace(fig, left, color=_SERIES_COLOR_LEFT, yaxis="y")
    _add_axis_trace(fig, right, color=_SERIES_COLOR_RIGHT, yaxis="y2")
    _v2_base_layout(fig, left_margin=78, right_margin=78)
    # y2 必須在畫門檻線**之前**存在,否則右軸門檻會綁到一條 plotly 臨時生出來的軸。
    fig.update_layout(
        yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,.16)",
                   zeroline=False, tickfont=dict(size=10),
                   title=dict(text=left.row.label, font=dict(size=10))),
        yaxis2=dict(overlaying="y", side="right", showgrid=False,
                    zeroline=False, tickfont=dict(size=10),
                    title=dict(text=right.row.label, font=dict(size=10))),
    )
    _threshold_lines_ssot(fig, left.spec, yref="y", side=_THR_SIDE_LEFT)
    # ↓ 本卡最關鍵的一行:右軸的門檻**必須**綁 y2。漏了就是「黃線 32.0」畫在
    #   左軸的 32 —— 標籤寫對、位置全錯,而且畫面看不出來(見本區塊檔頭警語)。
    _threshold_lines_ssot(fig, right.spec, yref="y2", side=_THR_SIDE_RIGHT)
    return DualAxisPlot(fig=fig, mode=MODE_DUAL, notes=[])


def _axis_value_html(series: AxisSeries) -> str:
    """一條序列在卡頭的「名稱 + 值 + 燈」。值與燈全部沿用既有 `Row` 與 SSOT。"""
    zh, color = band_meta(series.row.band, series.spec)
    return (
        f'<div style="display:flex;align-items:baseline;gap:7px;margin:2px 0">'
        f'<span style="font-size:12px;opacity:.7">{series.row.label}</span>'
        f'<span style="font-size:22px;font-weight:700;'
        f'font-variant-numeric:tabular-nums">'
        f'{fmt_value(series.row.value, series.row.unit, series.row.decimals)}</span>'
        f'{pill(zh, color)}</div>')


def render_dual_axis_card(title: str, left: AxisSeries, right: AxisSeries, *,
                          series_note: str = "", key: str = "") -> None:
    """雙軸走勢卡(卡 A「美元指數 / 台幣」用)。

    L4 純渲染:序列由 L5 備妥,本函式**不取數、不判燈、不補值**。
    圖本身由 `build_dual_axis_figure` 建(可離線單測),這裡只負責擺上畫面。

    `key`: `st.plotly_chart` 的 key(同一頁多張圖不可撞);留空則由兩盞燈的
    key 組出來。**不參與任何判斷。**
    """
    plot = build_dual_axis_figure(left, right)
    with st.container(border=True):
        st.markdown(f'<p class="v2-t">{title}</p>', unsafe_allow_html=True)
        st.markdown(_axis_value_html(left) + _axis_value_html(right),
                    unsafe_allow_html=True)

        if plot.fig is None:
            st.caption("兩條序列都取不到 —— 不以合成資料替代。")
        else:
            _k = key or f"v2dual_{left.row.key}_{right.row.key}"
            st.plotly_chart(plot.fig, width="stretch",
                            config={"displayModeBar": False}, key=_k)
        for _n in plot.notes:
            st.caption(f"這條線畫不出來　·　{_n}")
        st.caption("門檻線由 SSOT 畫出,左右軸各綁自己的門檻"
                   + (f"　·　{series_note}" if series_note else ""))


# ══════════════════════════════════════════════════════════════════════
# 卡 B：K 線卡
# ══════════════════════════════════════════════════════════════════════
#
# 為什麼不是把 `render_chart_card` 撐成四態萬用函式:它的 `kind` 只有
# `line` / `bar`,兩者都吃**一條** `ys`。K 線要 open / high / low / close
# **四條**,不是多一個 kind 的事,是參數形狀根本不同。硬塞的話那支函式會變成
# 「有時吃一條、有時吃四條」—— 同一個參數位置意義會飄(§3.3 的第二把尺)。

#: 漲跌色 —— **台股慣例紅漲綠跌**(與美股相反)。色票走 L0 `shared.colors`,
#: 與本 repo 既有台股 K 線(`ui/tabs/macro/section_long.py` 的加權指數日K)
#: 同一組常數,不另外挑色。
_KL_UP: str = TRAFFIC_RED
_KL_DOWN: str = TRAFFIC_GREEN

#: OHLC 四欄的欄名與中文。**只在這裡定義一次** —— 缺欄訊息、契約檢查、
#: 取值全部走這張表,分兩個地方寫就會出現「檢查了 low、訊息卻說 close」。
OHLC_FIELDS: tuple[tuple[str, str], ...] = (
    ("open", "開盤"),
    ("high", "最高"),
    ("low", "最低"),
    ("close", "收盤"),
)


@dataclass(frozen=True)
class OHLC:
    """一段 K 線的四條序列 + x 軸。**四條缺一不可。**

    每一欄都可以是 `None`(上游根本沒給這一欄)或空 list(給了但沒有資料),
    兩種都算缺 —— 由 `ohlc_problems()` 判定並說出缺哪一欄。

    ⚠️ **沒有 `volume`。** 不是忘了加,是刻意不收:見
    `build_candlestick_figure` 的 docstring。
    """
    xs: list | None = None
    open: list[float] | None = None
    high: list[float] | None = None
    low: list[float] | None = None
    close: list[float] | None = None


def ohlc_problems(ohlc: OHLC) -> list[str]:
    """K 線畫不出來的原因(畫得出來 → 空 list)。**純函式,可離線斷言。**

    兩類問題,分開講(混在一起會讓契約漂移偽裝成缺資料而沒人去修):

    1. **缺欄** —— `xs` 或四欄任一為 `None` / 空。
    2. **長度對不上** —— 四欄長度彼此不同,或與 `xs` 不同。這不是「沒資料」,
       是上游給的東西**形狀不對**;plotly 會照畫(短的那欄補空),畫出來是一根
       根位置錯開的 K 棒,而畫面上完全看不出來。故一律擋掉。

    §1:一有問題就**不畫**,不挑能畫的欄位硬畫、也不 fallback 成折線。
    """
    _probs: list[str] = []
    # ↓ 修正點:`not seq` 對 pandas Series 會丟 ValueError(訊息與「沒有資料」
    #   無關,會害人查錯方向)—— 走 `_has_points` 統一判定
    if not _has_points(ohlc.xs):
        _probs.append("日期軸 xs：沒有資料")
    for _f, _zh in OHLC_FIELDS:
        if not _has_points(getattr(ohlc, _f)):
            _probs.append(f"{_zh}價 {_f}：沒有資料")
    if _probs:
        return _probs

    _lens = {_f: len(getattr(ohlc, _f)) for _f, _ in OHLC_FIELDS}
    _lens["xs"] = len(ohlc.xs)
    if len(set(_lens.values())) > 1:
        _probs.append(f"四欄與日期軸長度對不上（{_lens}）—— 這是上游契約漂移，"
                      f"不是缺資料")
    return _probs


def build_candlestick_figure(ohlc: OHLC, spec: DangerSpec, *,
                             name: str = "") -> go.Figure | None:
    """OHLC → 日 K `go.Figure`;畫不出來 → **回 `None`**。純函式,可離線斷言。

    ## 為什麼不畫成交量(客戶 2026-08-27 拍板)

    加權指數的 `volume` 欄自 **2026-07-09 起連續 33 個交易日全為 0**。
    畫出來就是圖表下方一整排貼在零軸上的空白 —— 版面看起來完整,傳達的
    卻是「這段期間沒有人交易」這個假訊息。與其畫一排零,不如不畫(§1)。
    ⚠️ 這是**資料現況**造成的決定,不是「K 線圖不該有量」。哪天 volume 修好了,
    要加回來是新的一次決策,不要看到這段就以為 by-design 永遠不畫。

    ## 為什麼關掉 rangeslider

    plotly `Candlestick` 預設會在圖下方長出一條時間縮放條。本卡 `height=210`,
    那條會吃掉將近一半的高度,K 棒被壓到只剩一百多 px —— 縮放條本身在小卡上
    也沒人拖得動。故 `xaxis.rangeslider.visible=False`。

    ## 缺欄降級

    四欄任一缺 → **不畫,而且不 fallback 成折線**。標題寫「日 K」卻畫出一條
    收盤折線,是畫面說 A 內容是 B —— 使用者會以為自己在看 K 線的高低影線。
    缺哪一欄由 `ohlc_problems()` 說,呼叫端負責印出來。
    """
    if ohlc_problems(ohlc):
        return None

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=ohlc.xs, open=ohlc.open, high=ohlc.high,
        low=ohlc.low, close=ohlc.close,
        name=name or "日 K", showlegend=False,
        increasing_line_color=_KL_UP, decreasing_line_color=_KL_DOWN,
    ))
    _v2_base_layout(fig, left_margin=8, right_margin=78)
    # ↓ 修正點:`_v2_base_layout` 的 xaxis 不含 rangeslider,而 Candlestick 的
    #   預設是**顯示**。不顯式關掉的話小卡會被縮放條吃掉近一半高度。
    fig.update_layout(xaxis=dict(rangeslider=dict(visible=False)))
    _threshold_lines_ssot(fig, spec, yref="y", side=_THR_SIDE_RIGHT)
    return fig


def render_candlestick_card(row: Row, spec: DangerSpec, ohlc: OHLC, *,
                            series_note: str = "", key: str = "") -> None:
    """K 線卡(卡 B「加權指數日 K」用)。

    L4 純渲染:OHLC 由 L5 從真實資料備妥,本函式**不取數、不判燈、不補值**。
    卡頭與既有 `render_chart_card` 同一組(指標名 + 現值 + 燈),圖由
    `build_candlestick_figure` 建(可離線單測)。

    §1 降級:四欄缺任一 → 不畫 K 線、**不改畫折線**,誠實印出缺哪一欄。

    ⚠️ 右上角的燈走 `band_meta(row.band, spec)` 而不是 `BAND_META[row.band]`
    —— 加權指數是**參考走勢、沒有門檻**,直讀 BAND_META 會印出「無資料」,
    而卡片同時畫著真實 K 棒(§1)。
    """
    zh, color = band_meta(row.band, spec)
    with st.container(border=True):
        head, meta = st.columns([7, 3])
        with head:
            st.markdown(f'<p class="v2-t">{row.label}</p>', unsafe_allow_html=True)
            st.markdown(
                f'<div style="font-size:26px;font-weight:700;'
                f'font-variant-numeric:tabular-nums">'
                f'{fmt_value(row.value, row.unit, row.decimals)}</div>',
                unsafe_allow_html=True)
        with meta:
            st.markdown(f'<div style="text-align:right">{pill(zh, color)}</div>',
                        unsafe_allow_html=True)

        _probs = ohlc_problems(ohlc)
        if _probs:
            st.caption("日 K 畫不出來 —— 不以折線或合成資料替代。")
            for _p in _probs:
                st.caption(f"　· {_p}")
            st.caption(f"門檻帶　{row.thr_text}")
            return

        st.plotly_chart(build_candlestick_figure(ohlc, spec, name=row.label),
                        width="stretch", config={"displayModeBar": False},
                        key=key or f"v2kline_{row.key}")
        # ↓ 修正點:原本無條件印「門檻線由 SSOT 畫出」,但本卡的 spec 四個
        #   門檻欄全 None,實測 `fig.layout.shapes == 0` —— 腳註說有、圖上
        #   沒有。改由 `threshold_caption(spec)` 依 SSOT 分支。
        st.caption(f"{threshold_caption(spec)}　·　不畫成交量（該欄目前恆為 0）"
                   + (f"　·　{series_note}" if series_note else ""))
