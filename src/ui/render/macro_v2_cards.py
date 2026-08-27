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

from shared.macro_buckets import DangerSpec

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


BAND_META: dict[str, tuple[str, str]] = {
    "green": ("綠", "#0ca30c"),
    "yellow": ("黃", "#fab219"),
    "red": ("紅", "#d03b3b"),
    "gray": ("無資料", "#8a8e96"),
}

CSS = """
<style>
/* 半透明底 + color:inherit —— 讓卡片在 Streamlit 亮/暗兩種佈景都成立,
   不寫死任何背景色(寫死必有一邊不能看)。 */
.v2-t{font-size:11px; font-weight:700; letter-spacing:.09em;
      text-transform:uppercase; opacity:.62; margin:0 0 10px;}
.v2-hero{font-size:46px; font-weight:700; line-height:1; letter-spacing:-.02em;}
.v2-hero small{font-size:19px; font-weight:500; opacity:.6; margin-left:3px;}
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
    band: str             # green / yellow / red / gray
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
    zh, color = BAND_META[row.band]
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
                      *, kind: str = "line", series_note: str = "") -> None:
    """走勢卡 —— 只給**有真實歷史序列**的指標用。

    `xs` / `ys` 由 L5 從真實資料備妥;本函式不生成任何序列。
    """
    zh, color = BAND_META[row.band]
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
            st.caption("歷史序列取得失敗 —— 不以合成資料替代。")
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
        st.caption(f"門檻線由 SSOT 畫出　·　{series_note}")


def render_detail(row: Row, spec: DangerSpec, edu: dict | None = None,
                  reason_text: str = "") -> None:
    """右側明細面板 —— Streamlit 沒有原生 Drawer,以常駐右欄取代:
    點左表任一列即就地更新,不跳頁。"""
    zh, color = BAND_META[row.band]
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
