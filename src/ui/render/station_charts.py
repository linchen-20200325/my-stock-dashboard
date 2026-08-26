"""src/ui/render/station_charts.py — L4 戰情室週線走勢圖渲染（週K vs 均線 / 布林 z）。

`station_cards.py` 的兄弟檔,**沿用同一份契約:不取數、不判燈、不碰 session_state。**
序列由 L3 `services.dividend_station_service` 在抓取那一次算好,經 row 的
`KEY_WEEKLY_SERIES`(`_weekly_series`)鍵傳進來;本層只負責把它畫出來。

## 為什麼本檔一條計算都不做

L3 `_weekly_series_payload` 的 docstring 已把理由寫完,這裡只記結論:
均線與布林 z **在 L3 就算好了**,而且與 235 燈吃的是**同一組 L2 純函式**
(序列版與純量版已在 L2 逐點對帳)。本層若自己再算一份,遲早會出現
「線說沒破季線、燈說破了」——同一頁兩個答案。故本檔:

  · **不 import `src.compute.*`**(L4→L2 是上行依賴,且會變成第二把尺)
  · **不 import `src.data.*`**(L4 不取數)

⚠️ `§8.2.A EX-PASSTHRU-1` 的「L4 Render lazy fallback」那一條**不適用於本檔**:
   它的前提是「該 fetcher 無對應 L3 service、caller 只是取數」,而走勢圖兩個前提
   都不成立(有對應 L3、序列要經過計算)。本檔不需要、也沒有新增任何例外。

## 顏色只編碼一件事:這條線對應哪一盞 235 燈

單一規則,全檔通用(`_LIGHT_COLOR`):

| 線 | 對應的燈 | 依據(L2 `light_235`) |
|---|---|---|
| 4 週月線   | 燈一 🟢 | `週收 < ma4w`  → `LIGHT_1` |
| 13 週季線  | 燈二 🟡 | `週收 < ma13w` → `LIGHT_2` |
| 52 週年線  | 燈三 🔴 | `週收 < ma52w 且 z < -2σ` → `LIGHT_3` |
| z = −1 / −2 / −3σ | 燈一 / 燈二 / 燈三 | 同上三條 z 判定 |
| z = +2 / +3σ | 停利 💰 | `Z_TAKE_PROFIT_PARTIAL` / `_FORCE` |

三條均線**全畫**(user 2026-08-26 核准):235 的三個檔位分別看月線 / 季線 / 年線,
只畫季線的話燈一與燈三亮起來時,使用者在圖上找不到依據。

§3.3 反捏造 —— 本檔不寫死任何門檻數字、週期或色碼:
  · 均線週期 ← `shared.dividend_station_thresholds.MA_{MONTH,QUARTER,YEAR}_WEEKS`
  · 布林門檻 ← 同檔 `Z_LIGHT{1,2,3}` / `Z_TAKE_PROFIT_{PARTIAL,FORCE}`
  · 燈的圖示 / 名稱 ← 同檔 `LIGHT_META`
  · 色碼     ← `shared.colors`(L0 SSOT,**不從 `station_cards` 轉手**)
  · 缺值文案 ← `shared.station_specs.MISS_TEXT`(L0 SSOT,本層一律不編字)

§1 Fail Loud —— 沒有序列就**不畫圖**,改印該原因的既有文案;序列中的 NaN 破洞
  **保持斷線**(`connectgaps` 一律不設 True)—— 把破洞連起來等於用視覺捏造
  一段不存在的資料。同 `macro_v2_cards.render_value_card`:與其用合成序列讓版面
  「看起來完整」,不如誠實顯示為什麼沒有。

## 版面

`plot_bgcolor` / `paper_bgcolor` 一律透明、格線用中性灰 —— 與 `station_cards.CSS`
全篇同一個作法,套進 `st.container(border=True)`(右側明細面板正在用)不會出現
色塊接縫。⚠️ 刻意**不用** `chart_plotter._DARK_LAYOUT_BASE` 或
`macro_ui_components._base_layout`:那兩者硬碼 `#0e1117` 背景,塞進有框容器會接縫。
"""
from __future__ import annotations

from dataclasses import dataclass

import plotly.graph_objects as go
import streamlit as st

from shared import dividend_station_thresholds as T
from shared import station_specs as SS
from shared.colors import (
    COLORS_7,
    TRAFFIC_GREEN,
    TRAFFIC_ORANGE,
    TRAFFIC_RED,
    TRAFFIC_YELLOW,
)

# ══════════════════════════════════════════════════════════════════════
# 一、視覺常數（**呈現決定**,故放 L4;數值本身一律引 L0）
# ══════════════════════════════════════════════════════════════════════

#: 燈 → 線色。這是本檔唯一的顏色規則(見檔頭表)。
#: 前三個對應 `LIGHT_META` 的 🟢 / 🟡 / 🔴;停利的圖示是 💰,traffic 調色盤裡
#: **沒有**對應色,故另給橙 —— 它與加碼是兩個相反方向的軸,不該共用加碼的紅。
_LIGHT_COLOR: dict[str, str] = {
    T.LIGHT_1: TRAFFIC_GREEN,
    T.LIGHT_2: TRAFFIC_YELLOW,
    T.LIGHT_3: TRAFFIC_RED,
    T.LIGHT_TAKE_PROFIT: TRAFFIC_ORANGE,
}

#: 週收 / z 本身的線色。取 L0 `COLORS_7` 的第一色(藍)—— 它在本站是「這是資料
#: 本身」的既有慣例(macro 多序列圖第一條),不與上面四個「這是門檻」的色撞。
_SERIES_COLOR: str = COLORS_7[0]

#: 均線週期 → 中文線名。**週數不寫字面值**,一律由 L0 常數代入。
#: 名稱取自 L2 `light_235` 的觸發理由用詞(「週收<月線 / 季線 / 年線」),
#: 讓圖上的線名與燈的說明是同一組詞。
_MA_ZH: dict[int, str] = {
    T.MA_MONTH_WEEKS: "月線",
    T.MA_QUARTER_WEEKS: "季線",
    T.MA_YEAR_WEEKS: "年線",
}
#: 均線 → 對應哪一盞燈（依據見檔頭表）。
_MA_LIGHT: dict[int, str] = {
    T.MA_MONTH_WEEKS: T.LIGHT_1,
    T.MA_QUARTER_WEEKS: T.LIGHT_2,
    T.MA_YEAR_WEEKS: T.LIGHT_3,
}
#: 畫圖順序 = L0 由短到長,不另排。
MA_WINDOWS: tuple[int, ...] = (T.MA_MONTH_WEEKS, T.MA_QUARTER_WEEKS, T.MA_YEAR_WEEKS)

#: 圖高。三張圖疊起來在手機上剛好一個螢幕,不要更高。
CHART_HEIGHT: int = 210
#: 手機上 plotly 的工具列會擋住圖,一律關掉。
PLOTLY_CONFIG: dict = {"displayModeBar": False}

_GRID = "rgba(128,128,128,.16)"


def _minus(text: str) -> str:
    """ASCII `-` → U+2212 真減號(同 `macro_v2_cards.fmt_value`,純排版)。"""
    return text.replace("-", "−")


# ══════════════════════════════════════════════════════════════════════
# 二、純函式（無 st.*、無 I/O,可離線單測）
# ══════════════════════════════════════════════════════════════════════

def ma_line_label(window_weeks: int) -> str:
    """均線線名,例:`4 週月線`。週數來自 L0,本層不寫字面值。

    L0 沒有登記的週期 → 回 `N 週均線`(不猜它是月/季/年線)。
    """
    _zh = _MA_ZH.get(window_weeks, "均線")
    return f"{window_weeks} 週{_zh}"


def miss_text_for(reason: str) -> str:
    """`MISS_*` → 給使用者看的一句話。**文字一律走 L0 `MISS_TEXT`,本層不編字。**

    查不到的原因**不猜**(挑錯一個就會給出「重跑一次就好」這種錯誤指引,
    §1)—— 直接說這是程式要修的事,並把原始代碼原樣印出來。
    """
    _txt = SS.MISS_TEXT.get(reason)
    if _txt:
        return _txt
    return f"上游給的缺值原因「{reason}」不在 L0 MISS_TEXT 裡（程式要修）"


def _payload_ok(series) -> bool:
    """L3 契約檢查:該有的鍵在不在。**不看內容,只看形狀。**

    形狀不對是 `MISS_CONTRACT_DRIFT`（「不是沒資料,是資料長得不對」）,
    與「沒有序列」是兩件事 —— 混在一起會讓契約漂移偽裝成缺資料而沒人去修。
    """
    return isinstance(series, dict) and all(
        _k in series for _k in
        ("n_weeks", "close", "ma", "ma_miss", "boll_z", "boll_z_miss", "miss_reason"))


def _empty(s) -> bool:
    """序列是空的 / 是 None / 整條沒有任何有限值 → True。"""
    if s is None:
        return True
    try:
        if len(s) == 0:
            return True
        return not bool(s.notna().any())
    except AttributeError:      # 不是 pandas 物件 = 契約漂移,交給呼叫端標
        return True


def weekly_ma_miss_reason(series) -> str:
    """週K 圖畫不畫得出來 → `MISS_*`（畫得出來回 `""`）。純函式。

    ⚠️ 判準只看**整張圖**:三條均線各自缺不缺是**逐條**的事,走
    `missing_line_notes` —— 均線全缺但週收還在,那張圖仍有真資料可畫,
    不該整張砍掉。
    """
    if not _payload_ok(series):
        return SS.MISS_CONTRACT_DRIFT
    _r = str(series.get("miss_reason") or "")
    if _r:
        return _r
    # `miss_reason` 為空 = L3 宣稱有序列。此時週收卻是空的 → 契約漂移,不是缺資料。
    return SS.MISS_CONTRACT_DRIFT if _empty(series.get("close")) else ""


def boll_z_miss_reason(series) -> str:
    """布林 z 圖畫不畫得出來 → `MISS_*`（畫得出來回 `""`）。純函式。

    整組沒有序列(`miss_reason`)與這一條算不出來(`boll_z_miss`)可能同時成立,
    取**最根本**的那個 —— 走 L0 `most_fundamental_miss`,不在這裡自訂優先序。
    """
    if not _payload_ok(series):
        return SS.MISS_CONTRACT_DRIFT
    _r = SS.most_fundamental_miss(
        [str(series.get("miss_reason") or ""), str(series.get("boll_z_miss") or "")])
    if _r:
        return _r
    return SS.MISS_CONTRACT_DRIFT if _empty(series.get("boll_z")) else ""


def missing_line_notes(series) -> list[str]:
    """**逐條**均線畫不出來的原因(能畫的線不列)。純函式,文字走 L0 `MISS_TEXT`。

    兩種來源:
      1. L3 已登記在 `ma_miss` 的(週數 < 該線視窗 / 整條無有限值)。
      2. L3 **沒有**登記、但序列實際上是空的 —— 那是契約漂移,如實標出來;
         靜默不畫等於畫面上少一條線而沒有人交代(§1)。
    """
    if not _payload_ok(series):
        return []
    _ma = series.get("ma") or {}
    _miss = series.get("ma_miss") or {}
    _notes: list[str] = []
    for _w in MA_WINDOWS:
        _r = str(_miss.get(_w) or "")
        if not _r and _empty(_ma.get(_w)):
            _r = SS.MISS_CONTRACT_DRIFT
        if _r:
            _notes.append(f"{ma_line_label(_w)}畫不出來：{miss_text_for(_r)}")
    return _notes


@dataclass(frozen=True)
class ThresholdLine:
    """一條布林門檻線。`y` 直接引 L0 常數,本層不算、不四捨五入、不改寫。"""
    y: float
    color: str
    label: str


def threshold_line_specs() -> tuple[ThresholdLine, ...]:
    """布林 z 的 5 條門檻線 —— y 值**全部**來自 L0,順序由下而上。

    加碼三條(−1 / −2 / −3σ)與停利兩條(+2 / +3σ)是 L2 `light_235` 真的在用的
    同一組數字。**停利兩條要畫**:它們和加碼線走同一條 z 軸、由同一支函式判,
    不畫的話「💰 停利警示」亮起來時,使用者在圖上找不到依據 —— 與 user 核准
    畫三條均線是同一個理由。
    """
    _tp = T.LIGHT_META[T.LIGHT_TAKE_PROFIT]["icon"]
    return (
        ThresholdLine(T.Z_LIGHT3, _LIGHT_COLOR[T.LIGHT_3],
                      f'{T.LIGHT_META[T.LIGHT_3]["icon"]} {_minus(f"{T.Z_LIGHT3:g}")}σ'),
        ThresholdLine(T.Z_LIGHT2, _LIGHT_COLOR[T.LIGHT_2],
                      f'{T.LIGHT_META[T.LIGHT_2]["icon"]} {_minus(f"{T.Z_LIGHT2:g}")}σ'),
        ThresholdLine(T.Z_LIGHT1, _LIGHT_COLOR[T.LIGHT_1],
                      f'{T.LIGHT_META[T.LIGHT_1]["icon"]} {_minus(f"{T.Z_LIGHT1:g}")}σ'),
        ThresholdLine(T.Z_TAKE_PROFIT_PARTIAL, _LIGHT_COLOR[T.LIGHT_TAKE_PROFIT],
                      f"{_tp} +{T.Z_TAKE_PROFIT_PARTIAL:g}σ 分批"),
        ThresholdLine(T.Z_TAKE_PROFIT_FORCE, _LIGHT_COLOR[T.LIGHT_TAKE_PROFIT],
                      f"{_tp} +{T.Z_TAKE_PROFIT_FORCE:g}σ 強制"),
    )


def _base_layout(fig: go.Figure, *, right_margin: int, showlegend: bool) -> None:
    """透明底 + 中性格線。**不硬碼任何背景色** —— 見檔頭「版面」段。"""
    fig.update_layout(
        height=CHART_HEIGHT, margin=dict(l=8, r=right_margin, t=22, b=24),
        showlegend=showlegend, hovermode="x unified",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0,
                    font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(size=10)),
        yaxis=dict(showgrid=True, gridcolor=_GRID, zeroline=False,
                   tickfont=dict(size=10)),
    )


def build_weekly_ma_figure(series) -> go.Figure | None:
    """週收 + 三條均線 → `go.Figure`;整張圖畫不出來 → **回 `None`**（§1 不畫空圖）。

    `series` = L3 row 的 `KEY_WEEKLY_SERIES` payload。本函式**不算任何值**,
    只把已經算好的 `close` / `ma[週數]` 畫出來。

    - 缺哪一條均線就少畫哪一條(`ma_miss` 登記者),其餘照畫 —— 例:只有 30 週時
      年線缺,月線 / 季線仍然有效。缺的原因由 `missing_line_notes` 一併交代。
    - NaN 破洞**保持斷線**:全檔一律不設 `connectgaps`(預設 False)。均線前
      N−1 週本來就是 NaN(L3 刻意遮的),連起來等於畫出一段不存在的均線。
    """
    if weekly_ma_miss_reason(series):
        return None
    _close = series["close"]
    _ma = series.get("ma") or {}
    _miss = series.get("ma_miss") or {}

    fig = go.Figure()
    fig.add_scatter(
        x=list(_close.index), y=list(_close.values), mode="lines", name="週收",
        line=dict(color=_SERIES_COLOR, width=2),
        hovertemplate="週收 %{y:,.2f}<extra></extra>")
    for _w in MA_WINDOWS:
        if _miss.get(_w) or _empty(_ma.get(_w)):
            continue                      # 畫不出來的線不畫;原因走 missing_line_notes
        _s = _ma[_w]
        fig.add_scatter(
            x=list(_s.index), y=list(_s.values), mode="lines",
            name=ma_line_label(_w),
            line=dict(color=_LIGHT_COLOR[_MA_LIGHT[_w]], width=1.4, dash="dot"),
            hovertemplate=f"{ma_line_label(_w)} %{{y:,.2f}}<extra></extra>")
    _base_layout(fig, right_margin=10, showlegend=True)
    return fig


def build_boll_z_figure(series) -> go.Figure | None:
    """布林 z 走勢 + 5 條門檻線 → `go.Figure`;畫不出來 → **回 `None`**。

    門檻線的 y 值全部來自 L0(`threshold_line_specs`),本層不寫死任何數字;
    改門檻只改 L0,這張圖自動跟著動。NaN 破洞同樣保持斷線。
    """
    if boll_z_miss_reason(series):
        return None
    _z = series["boll_z"]

    fig = go.Figure()
    fig.add_scatter(
        x=list(_z.index), y=list(_z.values), mode="lines", name="布林 z",
        line=dict(color=_SERIES_COLOR, width=2),
        hovertemplate="z %{y:,.2f}σ<extra></extra>")
    for _t in threshold_line_specs():
        fig.add_hline(
            y=_t.y, line_dash="dash", line_color=_t.color, line_width=1.2,
            annotation_text=_t.label, annotation_position="right",
            annotation_font=dict(size=11, color=_t.color))
    _base_layout(fig, right_margin=78, showlegend=False)
    return fig


# ══════════════════════════════════════════════════════════════════════
# 三、渲染
# ══════════════════════════════════════════════════════════════════════

def _render_one(series, *, ticker: str, title: str, miss_fn, build_fn,
                key_prefix: str, notes: list[str], footer: str) -> None:
    """一張圖的共同骨架(標題 → 缺值就印原因收工 → 畫圖 → 圖說)。

    §1:`except Exception` **只隔離這一張圖**,不炸整頁;而且一定 log
    (靜默吞掉等於畫面少一張圖卻沒有任何人知道)。
    """
    st.markdown(f"**{title}**")
    _r = miss_fn(series)
    if _r:
        st.info(miss_text_for(_r), icon="📭")
        return
    try:
        fig = build_fn(series)
        if fig is None:                    # miss_fn 與 build_fn 判斷不一致 = 程式要修
            st.caption("這張圖的缺值判斷前後不一致（程式要修）—— 不以空圖充數。")
            return
        st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG,
                        key=f"{key_prefix}_{ticker}")
    except Exception as e:  # noqa: BLE001 — 單張圖失敗不該炸整頁,但必須留下紀錄
        print(f"[station_charts] {key_prefix} {ticker} 繪製失敗: "
              f"{type(e).__name__}: {e}")
        st.caption(f"這張圖畫不出來（{type(e).__name__}）—— 不以空圖或合成序列充數。")
        return
    for _n in notes:
        st.caption(_n)
    if footer:
        st.caption(footer)


def render_weekly_ma_chart(series, *, ticker: str = "") -> None:
    """週K vs 均線圖(週收 + 4 / 13 / 52 週三條均線)。

    `series`: L3 row 的 `KEY_WEEKLY_SERIES` payload;`ticker`: 只用來組
    `st.plotly_chart` 的 key(同一頁多張圖不可撞 key),**不參與任何判斷**。

    §1 降級:整組沒有序列 → 不畫圖,改印該 `MISS_*` 的 L0 文案;
    只缺某幾條均線 → 那幾條不畫、其餘照畫,並逐條交代原因。
    """
    _n = (series or {}).get("n_weeks") if isinstance(series, dict) else None
    _footer = (f"週K {int(_n)} 週　·　均線與 235 燈走同一組 L2 函式（同一把尺）"
               if isinstance(_n, int) and _n > 0 else "")
    _render_one(series, ticker=ticker, title="週K vs 均線",
                miss_fn=weekly_ma_miss_reason, build_fn=build_weekly_ma_figure,
                key_prefix="station_ma", notes=missing_line_notes(series),
                footer=_footer)


def render_boll_z_chart(series, *, ticker: str = "") -> None:
    """20 週布林 z 走勢圖(z 序列 + 加碼 −1/−2/−3σ 與停利 +2/+3σ 五條門檻線)。

    `series`: L3 row 的 `KEY_WEEKLY_SERIES` payload;`ticker`: 只用來組
    `st.plotly_chart` 的 key,**不參與任何判斷**。

    §1 降級:`boll_z_miss`(或整組 `miss_reason`)非空 → 不畫圖,改印該 `MISS_*`
    的 L0 文案 —— 週數不足 20 週時就是這一條路。
    """
    _p = ((series or {}).get("boll_period_weeks")
          if isinstance(series, dict) else None) or T.BOLL_PERIOD_WEEKS
    _footer = (f"{int(_p)} 週布林　·　門檻線由 L0 SSOT 畫出："
               + "　".join(f"{_t.label} = {_minus(f'{_t.y:g}')}"
                           for _t in threshold_line_specs()))
    _render_one(series, ticker=ticker, title=f"布林 z（{int(_p)} 週）",
                miss_fn=boll_z_miss_reason, build_fn=build_boll_z_figure,
                key_prefix="station_z", notes=[], footer=_footer)
