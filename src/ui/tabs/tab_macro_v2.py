"""src/ui/tabs/tab_macro_v2.py — L5 總經 v2 分頁(位階評估 + 五桶)。

現行「🌍 總經」分頁把同一組數字重講很多次,而且畫面上「從沒亮過的燈」與
「正常的綠燈」長得一模一樣。本分頁用三層結構重新呈現**同一批資料**:

    第 1 層 · 結論     位階 verdict + 訊號可信度 + 五桶卡
    第 2 層 · 為什麼   有真實歷史序列的指標畫走勢 + 門檻線
    第 3 層 · 全部明細 16 盞燈總表(可搜尋 + 分類篩選),點任一列右側就地展開

⚠️ **範圍**(2026-08-25 user 核准):只做「位階評估 + 五桶」。
   戰情室 / 新聞 AI / 跨市場 AI / 短中長期分區仍在舊「🌍 總經」分頁,
   本頁**不重做**也**不取代**它們 —— 兩個分頁並排,舊版原封不動。

§3.3 反捏造 —— 本檔不維護任何指標名單、不寫死任何門檻:
  · 16 盞燈與門檻 ← `shared.macro_buckets.BUCKET_DANGER_SPECS`(L0 SSOT)
  · 判燈         ← `shared.macro_buckets.classify_danger`(用上游函式,不重寫)
  · 值 / 可信度   ← `compute_five_bucket_summary(readiness_out=...)` 側車
    **刻意走側車而不自己從 session_state 抽** —— 自己抽就會出現第二條取數
    路徑,必然與上游漂移。側車的 `value` 欄與 `wired`/`state` 同源同刻。

§1 Fail Loud —— 沒按更新鈕時 16 盞全部誠實顯示「無資料」,不代任何預設值;
  沒有落地歷史序列的指標**不畫圖**,改用純數值卡。

§8.2 分層 —— L5。取數走 L3 `services.section_inputs` + L2 `macro_helpers`,
  長歷史序列與教學文案走 L3 `services.macro_v2_service`(該層負責 cache —— parquet
  是 4,900+ 列,Streamlit 每次 rerun 重讀不可接受);渲染全部下放 L4
  `render.macro_v2_cards`。**本檔與 L4 都不直接 import 任何 L1 模組**(§8.2 R4)。
"""
from __future__ import annotations

import streamlit as st

from dataclasses import dataclass

from shared.macro_buckets import (
    BUCKET_DANGER_SPECS,
    CL_INTL_KEY_DXY,
    CL_INTL_KEY_US10Y,
    CL_TW_KEY_USDTWD,
    MISSING_NO_EXTRACTION,
    MISSING_NO_VALUE,
    MISSING_NOT_LOADED,
    MISSING_OUT_OF_RANGE,
    REF_SPECS_BY_KEY,
    REFERENCE_BUCKET,
    SPECS_BY_KEY,
    classify_danger,
    has_thresholds,
)
from src.compute.macro.macro_helpers import compute_five_bucket_summary
from src.services.macro_v2_service import get_chart_series, get_edu, get_twii_ohlc
from src.services.section_inputs import load_section_inputs
from src.ui.render.macro_v2_cards import (
    BAND_META,
    CSS,
    OHLC,
    AxisSeries,
    Row,
    fmt_value,
    print_table_html,
    render_bucket_cards,
    render_candlestick_card,
    render_chart_card,
    render_detail,
    render_dual_axis_card,
    render_signal_health,
    render_value_card,
    state_cell,
    threshold_text,
)

#: 桶 key → 中文名(對齊現行五桶用語)
_BUCKET_ZH = {
    "long": "長期", "mid": "中期", "short": "短線急殺",
    "chips": "籌碼", "news": "新聞",
}
_BUCKET_ORDER = ["long", "mid", "short", "chips", "news"]

#: state=missing 時給使用者的「該做什麼」。與資料看板同一組 MISSING_* 常數,
#: 文案在此獨立寫是因為兩處的語境不同(這裡是總經頁,那裡是診斷頁)。
_REASON_TXT = {
    MISSING_NOT_LOADED: "尚未載入 —— 到「🌍 總經」分頁按「🚀 一鍵更新全部數據」。",
    MISSING_NO_VALUE: "上游來源這輪沒有回值 —— 到「🔎 資料診斷」看 API 根因。",
    MISSING_OUT_OF_RANGE: "取到的值超出合理範圍,已被擋下 —— 通常是上游換了標的或報價慣例"
                          "(如 DXY→UUP、殖利率×10)。**不猜換算**,故顯示無資料。",
    MISSING_NO_EXTRACTION: "這盞燈的 spec 沒有對應的取值路徑 —— 這是程式 bug,不是資料問題。",
}

#: ── 第 2 層卡片的四種來源／形狀 ────────────────────────────────────────
#: 具名常數而非裸字串:字串打錯會靜默走到 else 分支(畫成另一種卡),
#: 常數打錯是 NameError(§1 立刻炸)。
KIND_PARQUET: str = "parquet"   # 走 L3 `get_chart_series()` 的落地長序列
KIND_SESSION: str = "session"   # 當輪抓取的記憶體內短窗(隨 session 消失)
KIND_DUAL: str = "dual"         # 雙軸走勢卡(左右各一條,量級差很大)
KIND_OHLC: str = "ohlc"         # 日 K 卡(open/high/low/close 四條)
CHART_KINDS: tuple[str, ...] = (KIND_PARQUET, KIND_SESSION, KIND_DUAL, KIND_OHLC)

#: 卡 B 要畫幾根 K 棒。**「畫幾天」是畫面決策,所以常數住在 L5**;
#: L3 `get_twii_ohlc(n)` 沒有預設值,天數只有這裡一份(§3.3)。
#:
#: 為什麼是 60 而不是全部 4,919 列(客戶 2026-08-27 拍板):本機實測
#: (2026-08-27,plotly 6.9.0,`fig.to_json()` 位元組數)——
#:     60 根    →   8.0 KB
#:     4,919 根 → 361.1 KB(**45 倍**)
#: 而 3 欄版面下單張圖的繪圖區約 304 px,4,919 根等於**每根 0.06 px** ——
#: 那已經不是「資訊很密」,是根本畫不出 K 棒,實心色塊而已。
#: ⚠️ 工單寫的是「286 KB」,本機量到 361.1 KB。**結論不變,數字以實測為準。**
TWII_KLINE_TRADING_DAYS: int = 60


@dataclass(frozen=True)
class ChartCard:
    """第 2 層的一張卡。**名單與形狀寫在同一個地方**,不散在渲染函式裡。

    Attributes
    ----------
    key : str
        `SPECS_BY_KEY`(16 盞燈)或 `REF_SPECS_BY_KEY`(參考走勢)的 key。
        **只能來自這兩張註冊表** —— 由 `tests/test_macro_v2_tab.py` 守衛,
        不接受任意字串(否則這裡就變成第三份指標名單)。
    kind : str
        `CHART_KINDS` 之一。決定用哪一支 L4 渲染函式。
    note : str
        序列說明(來源 / 窗長 / 單位換算),印在卡片底部 caption。
    ref_key : str
        **只有 `kind=KIND_DUAL` 用**:右軸那條序列的 key。
        非 dual 卡必須留空(守衛會擋)—— 留著一個沒人讀的欄位,
        下一個人會以為它有作用。
    hold_reason : str
        非空 = **這張卡的數字照顯示,但圖暫不繪製**,而這一句就是印在卡片
        下方的原因。空字串 = 正常畫。

        為什麼做成欄位而不是在渲染函式裡另寫一份 key 名單:名單是第二把尺
        (§3.3)—— 哪天資料修好了,有人把這裡的旗標拿掉卻忘了改名單,
        卡片就會出現「說要畫、實際不畫」或反過來。旗標與卡片綁在同一列,
        物理上不會分岔。
    compact : bool
        **「精簡總覽」密度下要不要留這張卡。** 同樣是欄位而不是名單 ——
        名單是第二把尺:加一張卡卻忘了同步名單,就會出現「精簡模式反而
        多一張」這種沒人看得懂的行為。
    """
    key: str
    kind: str
    note: str
    ref_key: str = ""
    hold_reason: str = ""
    compact: bool = False


#: ── 第 2 層 · 密度切換(客戶 2026-08-27 拍板「方案乙:真的少畫」)────────
#: 「精簡」不是把卡片用 CSS 藏起來 —— 那樣圖照畫、序列照取,省的只有視覺,
#: CPU 與傳輸一毛都沒省。本頁的精簡是**真的不建那幾個 figure、也不去取
#: 它們的序列**(見 `visible_cards` 與取數 gating)。
#:
#: ⚠️ **預設是「完整走勢」**,不是精簡。理由:精簡會讓卡片消失,而「卡片
#: 不見了」與「這個指標今天沒資料」在畫面上很難分辨。最小破壞 = 不主動
#: 拿走任何東西,想要更快的人自己點一下。
#:
#: ── 實測收益(2026-08-27,plotly 6.9.0,7 次取中位數)────────────────────
#: `build` = 建 figure 耗時;`payload` = `fig.to_json()` 位元組數
#: (**不含** streamlit 自身的傳輸開銷,故為下界):
#:
#:     us10y 折線(60 點)       build  7.6 ms   payload   4.5 KB   ← 精簡時省掉
#:     加權指數日 K(60 根)      build  5.5 ms   payload   8.0 KB   ← 精簡時省掉
#:     卡 A 雙軸(60 點×2)      build 14.9 ms   payload   6.8 KB   ← 精簡保留
#:     bias_240 折線(4,680 點)  build 18.2 ms   payload 190.0 KB   ← 精簡保留
#:
#: 精簡模式實際省下 **≈ 13 ms CPU + ≈ 12.5 KB**,外加整個跳過
#: `get_twii_ohlc()` 的 parquet 讀檔。
#: ⚠️ 工單估的是「每張圖 ≈ 59 ms、省 0.18 s + 352 KB」——**本機量不到**。
#: 據實記錄實測值(§1:沒查證的數字比沒有數字更危險)。
#:
#: 📌 **量測帶出的重點**:本頁的傳輸成本 94% 集中在 `bias_240` 那一張
#: (4,680 點、190 KB),而它正是精簡模式保留的核心卡。真要省傳輸,該做的是
#: **在精簡模式縮短 bias_240 的窗長**(例如近 250 個交易日),而不是拿掉
#: 另外兩張小圖。那屬視覺規格取捨,已列入交付回報請客戶裁示,本段不自作主張。
DENSITY_COMPACT: str = "精簡總覽"
DENSITY_FULL: str = "完整走勢"
DENSITY_OPTIONS: tuple[str, ...] = (DENSITY_COMPACT, DENSITY_FULL)
DENSITY_DEFAULT_INDEX: int = DENSITY_OPTIONS.index(DENSITY_FULL)

#: 融資餘額「圖暫不繪製」的原因(客戶 2026-08-27 拍板)。
#:
#: 實測(2026-08-27,`data_cache/finmind_margin.parquet` 4,943 列):
#:   · 4,912 列(99.4%)的 `fetched_at` 是**同一個時間戳**
#:     `2026-07-11T21:32:59.059570+00:00` —— 一次性歷史回補;
#:     其後逐日新增的 31 列 100% 乾淨(4,939〜6,183 億)。
#:   · **那批回補列裡有 60.6%(2,975 列)掉到近零**(中位數 0.12 億),
#:     其餘落在 2,000〜6,300 億 —— 兩種單位混在同一欄。
#:   · 相鄰兩列有 **39.5%** 的機率在「近零」與「千億級」之間翻轉。
#: 畫出來就是一整塊實心色塊,門檻線(2,500 / 3,400 億)埋在裡面看不見 ——
#: 版面看起來完整,傳達的卻是假的(§1)。
#:
#: ⚠️ **卡片上的數字是對的**:那條走 `cl_data['margin']` 的即時路徑,
#:    與這份歷史檔無關。所以卡片不會變空白,只有圖不畫。
#: ⚠️ **本段不洗資料**(那是獨立工單)。判斷哪些列是髒的有一個乾淨的
#:    boolean —— `fetched_at == 那個時間戳` —— 但清洗屬 `src/data/**`,
#:    不在本次檔案邊界內。
_MARGIN_CHART_HOLD: str = (
    "⚠️ **資料疑義：圖暫不繪製。** 本地歷史檔的 4,912 列來自 2026-07-11 一次性"
    "回補，其中 60.6% 掉到近零、其餘落在 2,000〜6,300 億 —— 同一欄混用兩種單位"
    "（相鄰列有 39.5% 的機率在兩者之間翻轉）。照畫會是一整塊實心色塊，"
    "門檻線埋在裡面看不見。**上方的數字走另一條即時路徑，是對的**；"
    "歷史檔重抓後圖會自動恢復。"
)

#: 第 2 層要畫哪些卡。名單來自 2026-08-25 對 16 盞燈的歷史資料盤點
#: (只有這幾個有真序列)+ 2026-08-27 客戶加點的兩張新卡。
_CHART_SPECS: list[ChartCard] = [
    # compact=True 的兩張 = 精簡總覽保留的卡:一張回答「台股位階」
    # (年線乖離,唯一有長歷史的燈號走勢),一張回答「資金往哪走」(美元 / 台幣)。
    ChartCard("bias_240", KIND_PARQUET,
              "台股日線 2007 迄今,年線乖離由收盤價即時算出",
              compact=True),
    # ── B-4(2026-08-27 客戶拍板):融資餘額**只標資料疑義,圖暫不繪製** ──
    ChartCard("margin", KIND_PARQUET,
              "融資餘額日資料 2006 迄今(原始單位元,此處已換算為億)",
              hold_reason=_MARGIN_CHART_HOLD),
    ChartCard("us10y", KIND_SESSION,
              "本輪抓取的近 60 個交易日(即時取得,不落地)"),
    # ── 卡 A(2026-08-27 客戶拍板):左軸 DXY、右軸台幣 ──
    # 為什麼要雙軸:DXY ~105、USDTWD ~32,量級差 3.3 倍。擠在同一條 y 軸上
    # 台幣會被壓成一條貼底的水平線 —— 圖還在、線也在,但它不再傳達任何訊息。
    ChartCard("dxy", KIND_DUAL,
              "兩條都是本輪抓取的近 60 個交易日(即時取得,不落地)"
              "　·　台幣為**參考走勢**:有門檻但**不計入 16 盞燈的分母**",
              ref_key="usdtwd", compact=True),
    # ── 卡 B(2026-08-27 客戶拍板):加權指數日 K ──
    ChartCard("taiex", KIND_OHLC,
              f"本地 parquet 的最近 {TWII_KLINE_TRADING_DAYS} 個交易日"
              "　·　本卡為**參考走勢**:不判燈(右上灰標＝沒有燈號,"
              "不是沒有資料)、無門檻線、不計入 16 盞燈的分母"),
]

#: 有值有燈、但**完全沒有歷史序列**可畫者 —— 顯示純數值卡。
#: VIX 是最典型的:天天在用,卻沒有任何落地序列。
_VALUE_CARD_KEYS: list[str] = ["vix"]

#: ── 第 2 層 · 卡片版面 ────────────────────────────────────────────────
#: **固定每列 3 張**,卡片變多就往下長,不是每張變窄。
#:
#: 為什麼是固定值而不是 `st.columns(len(cards))`:舊寫法讓每張卡的寬度
#: 隨卡片數量反比縮水,於是「多加一張卡」與「把整排圖壓到看不見」是同一個
#: 動作。1440px 螢幕實測(扣卡片內距與圖表固定右留白 78px 後的真正繪圖區):
#:
#:     3 欄 = 304px ✅ / 4 欄 = 192px 🟡 / 6 欄 = 85px 🔴 / 7 欄 = 54px
#:
#: 7 欄時**標註留白比繪圖區還寬**,圖等於消失 —— 而畫面上它還在,只是變成
#: 一團色塊(§1:看起來正常的壞畫面最危險)。3 是本 repo 既有慣例
#: (`ui/helpers/macro/helpers.py` 的 9 張卡同樣 3/列)。
#:
#: ⚠️ 最後一列不滿時**留空欄**(見 `_chart_row_columns`)—— 那是正確行為,
#: 不是瑕疵:把 2 張卡拉成半頁寬會讓同一張圖在不同篩選下長得不一樣。
CARDS_PER_ROW: int = 3


def chunk_cards(items: list, per_row: int = CARDS_PER_ROW) -> list[list]:
    """把卡片切成「每列固定 per_row 張」。**純函式,可離線斷言。**

    空 list → 回 `[]`(**不是** `[[]]`)。差別很重要:回 `[[]]` 的話呼叫端
    會為一列不存在的卡片開一次 `st.columns()`,在畫面上留下一段莫名的空白。

    `per_row` 必須 ≥ 1,否則 `range(0, n, 0)` 直接無窮迴圈 —— §1:寧可炸,
    不要吊死在一個沒有錯誤訊息的畫面上。
    """
    if per_row < 1:
        raise ValueError(f"per_row 必須 ≥ 1,收到 {per_row!r}")
    return [items[i:i + per_row] for i in range(0, len(items), per_row)]


def visible_cards(density: str, *, by_key: dict) -> list["ChartCard"]:
    """這一輪第 2 層要畫哪幾張卡。**純函式,可離線斷言。**

    兩層篩選,順序不可對調:

    1. **這盞燈存在嗎** —— 燈號卡要在 `by_key`(readiness 側車攤平後的 rows)
       裡;參考走勢卡不在側車裡,改看 `REF_SPECS_BY_KEY`。
    2. **這個密度要不要它** —— `DENSITY_COMPACT` 只留 `compact=True` 的卡。

    §1:未知的 `density` 直接 `raise`。若默默當成「完整」,使用者會看到
    一個點了沒反應的按鈕,而且永遠查不出為什麼。
    """
    if density not in DENSITY_OPTIONS:
        raise ValueError(
            f"未知的密度 {density!r}(可用:{list(DENSITY_OPTIONS)})")
    out = [c for c in _CHART_SPECS
           if c.key in by_key or c.key in REF_SPECS_BY_KEY]
    if density == DENSITY_COMPACT:
        out = [c for c in out if c.compact]
    return out


#: ── 第 3 層篩選 chip ──────────────────────────────────────────────────
#: 兩個**跨桶** chip 的 key;其餘 5 個 chip 的 key **就是桶 key 本身**。
_CHIP_ALL = "all"
_CHIP_PROBLEM = "problem"

#: chip key → 顯示名。5 個桶名一律**取自既有 `_BUCKET_ZH`**,不另寫一份中文
#: 字串 —— 兩份字串就是兩把尺,上游改桶名時必然有一邊沒跟上(§3.3)。
CHIP_LABELS: dict[str, str] = {
    _CHIP_ALL: "全部",
    _CHIP_PROBLEM: "只看有問題的",
    **{b: _BUCKET_ZH[b] for b in _BUCKET_ORDER},
}
#: chip 顯示順序。桶的先後同樣沿用 `_BUCKET_ORDER`,不在此另排一次。
CHIP_ORDER: list[str] = [_CHIP_ALL, _CHIP_PROBLEM, *_BUCKET_ORDER]


# ══════════════════════════════════════════════════════════════════════
# 組資料(無 st.* 副作用,純轉換)
# ══════════════════════════════════════════════════════════════════════

def build_rows(readiness: dict) -> list[Row]:
    """把 readiness 側車攤平成畫面用的列。

    值、可信度旗標、缺值原因全部來自側車 —— 本函式**不碰 session_state**,
    所以不存在第二條取數路徑。
    """
    out: list[Row] = []
    for spec in BUCKET_DANGER_SPECS:
        rec = readiness.get(spec.key, {})
        value = rec.get("value")
        # 判燈用上游 SSOT 函式,不自己重寫一套(§3.3)
        band = classify_danger(value, spec)

        # 四態的判定順序 = L0 SSOT `shared.station_specs.classify_state()`:
        #   1. wired=False → unwired   2. 沒值 → missing
        #   3. discriminative=False → degraded   4. 其餘 → live
        #
        # ⚠️ 這裡**刻意複製順序而不呼叫那個函式**,理由是型別不同,不是懶:
        #   `classify_state(spec: StationSpec, ...)` 讀的是 `station_specs.StationSpec`
        #   的 `spec.wired` / `spec.discriminative`(存股站的燈);本頁手上的是
        #   `macro_buckets.DangerSpec`,而且旗標**不從 spec 讀** —— 走 readiness 側車
        #   `rec`(見本函式 docstring:本檔不得有第二條取數路徑)。兩者是兩個獨立的
        #   dataclass,硬轉只會做出一層假的共用。**日後要改順序,兩邊一起改。**
        #
        # 為什麼「沒值」必須排在 discriminative 前面(**勿再對調**):degraded 的語意是
        # 「**有值**,但門檻失準,別照門檻讀」—— 它本身就預設有東西可讀。對著一個
        # 值都沒有的指標印「門檻已失準」,使用者會讀成「有值,只是別太當真」,
        # 而事實是**根本沒有值**。融資餘額(margin)正是實例:它 discriminative=False,
        # 沒抓到值時應印「無資料」(§1:錯的敘述比沒有敘述更危險)。
        has_value = rec.get("state") == "ok" and value is not None
        if not rec.get("wired", True):
            state = "unwired"
        elif not has_value:
            state = "missing"
        elif not rec.get("discriminative", True):
            state = "degraded"
        else:
            state = "live"

        out.append(Row(
            key=spec.key,
            label=spec.label,
            bucket=spec.bucket,
            unit=spec.unit or "",
            value=value,
            band=band,
            state=state,
            reason=rec.get("reason"),
            hit_source=rec.get("hit_source"),
            thr_text=threshold_text(spec),
            source=spec.source or "—",
            note=spec.note or "",
            decimals=spec.decimals,
        ))
    order = {b: i for i, b in enumerate(_BUCKET_ORDER)}
    out.sort(key=lambda r: (order.get(r.bucket, 99), r.label))
    return out


def build_reference_row(key: str, value: float | None) -> Row:
    """把一條**參考走勢**包成畫面用的 `Row`。**不是一盞燈。**

    參考走勢(台幣 / 加權指數)與 16 盞燈的差別,不只是「不進分母」——
    連取數路徑都不同:

        16 盞燈 → `compute_five_bucket_summary` 的 readiness 側車
        參考走勢 → **序列自己的最後一點**(本函式的 `value`)

    為什麼參考走勢不走側車:它根本不在側車裡(`REFERENCE_TREND_SPECS` 與
    `BUCKET_DANGER_SPECS` 是兩張物理隔離的表,見 `shared/macro_buckets.py`)。
    這裡沒有「第二條取數路徑」的問題 —— 序列就是唯一的那一條。

    `band` 的兩種情形(§1:沒有門檻的東西**不判燈**,不偽綠):

        有門檻(usdtwd) → `classify_danger` 判燈,與 16 盞燈同一支上游函式
        無門檻(taiex)  → 一律 `"gray"`,**不呼叫** `classify_danger`
                         (呼叫會 TypeError —— L0 刻意留的 fail loud)

    ⚠️ **已知的畫面瑕疵,不是漏看**:L4 `BAND_META` 只有四個 band
    (green/yellow/red/gray),沒有一個代表「參考走勢,不判燈」。故無門檻卡
    的右上角會顯示灰標「無資料」,而卡片同時秀著真實數字 —— 兩者看似矛盾。
    本檔的處置是在 `ChartCard.note` 明講「右上灰標＝沒有燈號,不是沒有資料」,
    並**不動 L4**(那是另一組的檔案邊界)。正解是 L4 加第五個 band「參考」,
    已列為交付回報中的建議事項。
    """
    spec = REF_SPECS_BY_KEY[key]
    band = classify_danger(value, spec) if has_thresholds(spec) else "gray"
    return Row(
        key=spec.key,
        label=spec.label,
        bucket=REFERENCE_BUCKET,   # 刻意不是五桶之一 —— 誤餵進彙總時要落空
        unit=spec.unit or "",
        value=value,
        band=band,
        # `state` 對這兩張卡的渲染函式而言是不讀的欄位,但仍誠實填 ——
        # 填一個假值等於留一顆定時炸彈給下一個開始讀它的人。
        state="live" if value is not None else "missing",
        reason=None if value is not None else MISSING_NO_VALUE,
        hit_source=None,
        thr_text=threshold_text(spec),   # 無門檻 → "—"
        source=spec.source or "—",
        note=spec.note or "",
        decimals=spec.decimals,
    )


def bucket_summary(rows: list[Row]) -> list[dict]:
    """每桶:最差燈 + 指標數 + 不可信數。worst-of rollup,與現行五桶同語意。"""
    rank = {"green": 0, "yellow": 1, "red": 2, "gray": -1}
    out = []
    for bkey in _BUCKET_ORDER:
        members = [r for r in rows if r.bucket == bkey]
        if not members:
            continue
        graded = [r for r in members if r.band != "gray"]
        worst = max(graded, key=lambda r: rank[r.band]) if graded else None
        out.append({
            "name": _BUCKET_ZH.get(bkey, bkey),
            "band": worst.band if worst else "gray",
            "worst_label": worst.label if worst else "全部無資料",
            "worst_value": (fmt_value(worst.value, worst.unit, worst.decimals)
                            if worst else "—"),
            "n": len(members),
            "n_bad": sum(1 for r in members if r.state != "live"),
        })
    return out


def overall_verdict(summary: list[dict]) -> tuple[str, str]:
    """全域位階 = 五桶取最差(worst-of),與現行五桶 rollup 同語意。

    Returns: (band, 說明文字)
    """
    rank = {"green": 0, "yellow": 1, "red": 2}
    graded = [b for b in summary if b["band"] in rank]
    if not graded:
        return "gray", "尚未載入資料"
    worst = max(graded, key=lambda b: rank[b["band"]])
    n_red = sum(1 for b in graded if b["band"] == "red")
    n_yellow = sum(1 for b in graded if b["band"] == "yellow")
    bits = []
    if n_red:
        bits.append(f"{n_red} 桶紅")
    if n_yellow:
        bits.append(f"{n_yellow} 桶黃")
    detail = "、".join(bits) or "五桶全綠"
    return worst["band"], f"{detail}　·　最差是「{worst['name']}」"


# ══════════════════════════════════════════════════════════════════════
# 第 3 層 · 篩選(全部是純 Python,對**已經算好的 rows** 過濾,不重新取數)
#
# ⚠️ 效能:app.py 是 7 個頂層 `st.tabs`,每次 rerun **所有 tab body 都會執行**
#    (STATE.md 產業熱力圖冷抓事故)。所以篩選一律在記憶體內做,這一段
#    **不得**出現任何取數 / `@st.cache_data` / 網路呼叫。
# ══════════════════════════════════════════════════════════════════════

def is_problem(row: Row) -> bool:
    """「只看有問題的」的判定:**市場有問題 ∪ 系統有問題**(取聯集)。

        市場有問題 = 燈是黃或紅            → `band in {"yellow", "red"}`
        系統有問題 = 這盞燈不能信          → `state != "live"`
                     (未接線 / 無資料 / 門檻已失準)

    **為什麼取聯集,而不是只認黃紅燈**:本分頁存在的第一個理由,就是
    「從沒亮過的燈」與「正常的綠燈」在舊畫面上長得一模一樣。若「有問題」
    只認黃紅燈,使用者按下這個 chip 會看到一張很短的清單,然後合理推論
    「其他都沒事」—— 但其他之中有一部分**不是沒事,是根本沒在回報**。
    那正是本頁要消滅的誤解;把它做成預設篩選等於把 bug 產品化(§1:
    灰燈不是綠燈,沒有數字比錯的數字安全,但**假裝沒問題**兩者都輸)。

    **「未接線」算不算有問題**:算。它確實不是**市場**的問題,是**系統**的
    問題(決策端刻意沒接取值)。但這個 chip 的語意是「**還需要我看一眼的**」,
    不是「市場現在很糟」—— 一盞永遠不會亮的燈,正是最需要被看見的那種。
    想「只看市場黃紅燈」的人改點對應的桶 chip 即可,資訊沒有損失;
    反過來若把未接線藏起來,那個資訊在整頁上就再也沒有入口了。

    ⚠️ 本函式只做**分類**,判燈完全沿用上游 `classify_danger` 的結果,
    不重新判定任何門檻(§3.3;本次是純顯示層改動)。
    """
    return row.band in ("yellow", "red") or row.state != "live"


def filter_rows(rows: list[Row], *, chip: str = _CHIP_ALL,
                query: str = "") -> list[Row]:
    """第 3 層總表的篩選。`chip` 與 `query` 是 AND(先分類,再搜尋)。

    `query` 比對 `Row.label`(指標名稱),**不分大小寫、部分字串即命中**;
    空字串 / 純空白 → 不篩(顯示全部),不當成「查無此指標」。

    ⚠️ 只比對 `label`、不比對 `key`:key 是內部識別字(`ism_pmi` 之類),
    畫面上從不出現。拿它當搜尋目標會出現「打了看得見的字找不到、打了
    看不見的字反而找得到」這種無法解釋的行為。

    §1:未知的 `chip` 直接 `raise`。若默默回傳全部,畫面會長得跟「全部」
    一模一樣 —— 一個永遠不會被發現的 bug。
    """
    if chip not in CHIP_LABELS:
        raise ValueError(
            f"未知的篩選 chip:{chip!r}(可用:{list(CHIP_LABELS)})")
    out = list(rows)
    if chip == _CHIP_PROBLEM:
        out = [r for r in out if is_problem(r)]
    elif chip != _CHIP_ALL:          # 其餘 chip 的 key 就是桶 key
        out = [r for r in out if r.bucket == chip]
    q = query.strip().casefold()
    if q:
        out = [r for r in out if q in r.label.casefold()]
    return out


def _table_columns(visible: list[Row]) -> dict[str, list]:
    """`st.dataframe` 用的欄位 dict。**吃什麼就畫什麼**,不在此再篩一次。

    狀態欄的 emoji 與中文字**都**取自 L4 `state_cell()`(背後是與訊號可信度
    卡同一份的 `STATE_META`),不在本層再抄一份四態字串或 emoji —— 抄了就是
    第二把尺(§3.3)。上一輪才剛把中文對照從本層收回 SSOT,emoji 再寫一份
    等於把它推回去。

    **「燈」欄維持純文字**(`BAND_META[...][0]` = 綠 / 黃 / 紅 / 無資料),
    user 2026-08-26 裁示:視覺重心要留給核心結論,不讓兩欄的符號互搶。
    這同時也是狀態欄敢出 emoji 的前提 —— 同列沒有第二個 🟢 可以撞
    (完整理由見 `macro_v2_cards.STATE_META` 上方那段與姊妹檔
    `render/station_cards.py` 檔頭)。
    """
    return {
        "桶": [_BUCKET_ZH.get(r.bucket, r.bucket) for r in visible],
        "指標": [r.label for r in visible],
        "目前值": [fmt_value(r.value, r.unit, r.decimals) for r in visible],
        "燈": [BAND_META[r.band][0] for r in visible],
        "狀態": [state_cell(r.state) for r in visible],
        "門檻帶": [r.thr_text for r in visible],
    }


def visible_table(rows: list[Row], *, chip: str = _CHIP_ALL,
                  query: str = "") -> tuple[list[Row], dict[str, list]]:
    """回 `(畫面上的列, st.dataframe 的欄位)` —— **同一份、同一刻**。

    刻意把「篩選」與「組表」綁進同一個回傳值:兩者一旦拆成兩次呼叫,就
    有機會餵到不同的 list,而那正是「右側面板顯示另一個指標」的成因
    (見 `selected_row`)。綁在一起之後,那個錯誤在呼叫端寫不出來。
    """
    visible = filter_rows(rows, chip=chip, query=query)
    return visible, _table_columns(visible)


def selected_row(visible: list[Row], idxs) -> Row | None:
    """把 `st.dataframe` 回傳的選取列索引解析成 `Row`。

    ⚠️ **這是本頁最容易寫錯的一行。** `selection.rows` 給的是「**畫面上那
    張表的列序**」,不是 `build_rows()` 的原始 16 列序。一旦有了篩選,兩者
    就不再相等 —— 拿原始清單去索引,右側面板會顯示**另一個指標**的值、
    門檻與教學文案:畫面說 A、內容是 B,而且兩邊都看起來很正常(§1)。
    故本函式**只吃 `visible`**,也就是與 `st.dataframe` 同一份的那個 list。

    索引越界(改了篩選、舊選取殘留在 widget state)→ 回 `None`,由 caller
    顯示「請重新點一列」。**不回退到第 0 列** —— 那等於默默換一個指標給
    使用者看,正是本函式要防的那個錯。
    """
    if not idxs:
        return None
    try:
        i = int(idxs[0])
    except (TypeError, ValueError):
        return None
    if not 0 <= i < len(visible):
        return None
    return visible[i]


def empty_hint(*, chip: str, query: str, total: int) -> str:
    """篩選後 0 筆時的說明 —— §1:不留一張空表讓人以為頁面壞了。

    必須把**目前的篩選條件原樣講出來**:0 筆的原因永遠是「條件太窄」或
    「打錯字」,而使用者未必看得出自己選了什麼(chip 在表格上方、搜尋字
    可能只差一個字)。只寫「沒有資料」等於把原因藏起來。
    """
    bits = [f"分類「{CHIP_LABELS.get(chip, chip)}」"]
    q = query.strip()
    if q:
        bits.append(f"搜尋「{q}」")
    # 沒打搜尋字時不要叫人「清掉搜尋字」—— 那會讓人去找一個不存在的東西。
    fix = "清掉搜尋字或改選" if q else "改選"
    return (f"沒有符合的指標。目前篩選:{'、'.join(bits)}。"
            f"{fix}「{CHIP_LABELS[_CHIP_ALL]}」即可看回全部 {total} 盞燈。")


def print_caption(*, chip: str, query: str, shown: int, total: int) -> str:
    """列印版表格的抬頭 —— **必須把目前的篩選條件講出來**。

    §1:一張印出來只有 3 列的表,若沒寫「16 盞裡篩了 3 盞」,拿到紙本的人
    (含幾個月後的自己)會理所當然地以為總共只有 3 盞燈。螢幕上還有 chip
    與搜尋框可以看出自己篩了什麼,紙上**什麼都沒有** —— 所以條件要跟著印。
    """
    bits = [f"分類「{CHIP_LABELS.get(chip, chip)}」"]
    q = query.strip()
    if q:
        bits.append(f"搜尋「{q}」")
    return (f"第 3 層 · 全部明細 —— 顯示 {shown} / {total} 盞燈"
            f"({'、'.join(bits)})")


#: session 短窗序列的取數路徑:key → (`cl_data` 群組, 該群組的中文 key)。
#:
#: 中文 key **一律走 L0 鏡像常數**(`shared.macro_buckets.CL_*_KEY_*`),
#: 不在此打字面值 —— 上游 `daily_checklist.INTL_MAP` / `TW_MAP` 改名時,
#: L0 那邊有 AST 漂移守衛會轉紅;寫死在這裡則是**無聲**變成「取不到」,
#: 而卡片會照畫(只是少一條線),畫面上看起來完全正常(§1 / §3.3)。
#:
#: ⚠️ 2026-08-27 修:本表取代原本寫死的 `intl.get("10Y公債殖利率")` ——
#:    那個字面值與 `CL_INTL_KEY_US10Y` 是同一個字串的第二份複本。
_SESSION_SERIES_SOURCE: dict[str, tuple[str, str]] = {
    "us10y": ("intl", CL_INTL_KEY_US10Y),
    "dxy": ("intl", CL_INTL_KEY_DXY),
    "usdtwd": ("tw", CL_TW_KEY_USDTWD),
}

#: session 短窗取不到時給使用者的一句話(雙軸卡的 `miss_reason` 用)。
#: 這一層的缺值只有一種成因:**這輪沒抓**。故文案單一,不猜其他理由(§1)。
SESSION_MISS_REASON: str = "本輪沒有抓到（到「🌍 總經」按「🚀 一鍵更新全部數據」）"


def _session_series(inputs, key: str):
    """從當輪抓取結果取記憶體內短窗序列。取不到回 (None, None)。

    §1:取不到就回 None 讓消費端顯示「歷史序列取得失敗」,不生成替代序列。
    """
    _src = _SESSION_SERIES_SOURCE.get(key)
    if _src is None:
        # §1:不靜默。走到這裡代表有人在 `_CHART_SPECS` 宣告了 session 卡,
        # 卻沒有在上表登記取數路徑 —— 那是程式 bug,不是資料問題。
        print(f"[tab_macro_v2/_session_series] {key} 沒有登記 session 取數路徑"
              f"(已登記:{list(_SESSION_SERIES_SOURCE)})")
        return None, None
    _group, _zh = _src
    cl = getattr(inputs, "cl_data", None) or {}
    grp = cl.get(_group) if isinstance(cl, dict) else None
    if not isinstance(grp, dict):
        return None, None
    df = grp.get(_zh)
    try:
        if df is None or getattr(df, "empty", True):
            return None, None
        # ── 收盤價欄位解析(2026-08-27 修)────────────────────────────
        # 【修的是什麼】原寫法 `df["Close"] if "Close" in df.columns else df.iloc[:, 0]`
        #   在 production **恆走 else 分支** —— 上游 `daily_data_fetchers.fetch_single`
        #   會把欄名整批小寫化(`h.columns = [c.lower()...]`),所以 `"Close"` 永遠不在
        #   欄位裡;而 yfinance 的欄序是 Open/High/Low/Close/… → `iloc[:, 0]` 取到的是
        #   **開盤價**。同一張卡的數字走 `macro_helpers._intl_close`(close/Close 都試)
        #   拿的是收盤價 → **同卡的數字與線來自不同欄位**,兩邊看起來都很正常(§1)。
        #   死碼能長期存活是因為既有測試 fixture 餵大寫 `Close` 走上分支,
        #   production 走下分支 —— 測試從來沒測到真實形狀。
        # 【為何兩種大小寫都要試】production 現況是小寫,但 pkl / cache_data 反序列化
        #   的舊資料、以及未來上游若改版都可能是大寫。順序對齊
        #   `macro_helpers._intl_close` 的 `("close", "Close")`,不另立第二套慣例。
        # 【為何不留 iloc 後備】拿不到 close 就是拿不到。退回「第一欄」等於拿一個
        #   不知道是什麼的欄位冒充收盤價 —— 正是 §1 禁止的「讓程式不報錯」。
        #   依本函式既有契約:回 (None, None) → 消費端顯示「歷史序列取得失敗」。
        _col = next((c for c in ("close", "Close") if c in df.columns), None)
        if _col is None:
            print(f"[tab_macro_v2/_session_series] {key} 無 close 欄"
                  f"(現有欄位:{list(df.columns)})→ 不以其他欄位替代")
            return None, None
        s = df[_col]
        s = s.dropna()
        if s.empty:
            return None, None
        return list(s.index), [float(v) for v in s.tolist()]
    except Exception as e:  # noqa: BLE001 — 單張圖取不到不該讓整頁炸
        print(f"[tab_macro_v2/_session_series] {key} 取序列失敗:{e}")
        return None, None


# ══════════════════════════════════════════════════════════════════════
# 渲染
# ══════════════════════════════════════════════════════════════════════

def _last_or_none(seq):
    """序列末項;空 / None → None。**不回 0**(0 會被讀成「值就是零」)。"""
    return seq[-1] if seq else None


def _render_dual_card(card: ChartCard, *, by_key: dict, inputs) -> None:
    """卡 A:左軸 DXY(一盞燈)、右軸台幣(參考走勢)。

    左右兩邊**各帶自己的 `DangerSpec`** —— 這是 L4 `AxisSeries` 的契約,
    右軸門檻才綁得到 y2。少給一邊在語法層就寫不出來。
    """
    _lx, _ly = _session_series(inputs, card.key)
    _rx, _ry = _session_series(inputs, card.ref_key)
    _ly, _ry = _ly or [], _ry or []
    left = AxisSeries(row=by_key[card.key], spec=SPECS_BY_KEY[card.key],
                      xs=_lx or [], ys=_ly, miss_reason=SESSION_MISS_REASON)
    right = AxisSeries(
        row=build_reference_row(card.ref_key, _last_or_none(_ry)),
        spec=REF_SPECS_BY_KEY[card.ref_key],
        xs=_rx or [], ys=_ry, miss_reason=SESSION_MISS_REASON)
    # 標題由兩條線的 label 組出,**不另外寫死一個第三個名字**(§3.3):
    # 上游改 label 時標題自動跟著改。
    render_dual_axis_card(f"{left.row.label} / {right.row.label}",
                          left, right, series_note=card.note)


def _render_kline_card(card: ChartCard, *, ohlc_raw: dict) -> None:
    """卡 B:加權指數日 K(參考走勢,不判燈、不畫門檻線)。

    `ohlc_raw` 是 L3 `get_twii_ohlc()` 的回傳(五個等長 list)。
    **本層不碰 pandas、不補值** —— 缺欄 / 長度對不上由 L4 `ohlc_problems()`
    判定並印出缺哪一欄(§1:不挑能畫的欄位硬畫、不 fallback 成折線)。

    ⚠️ **不傳 volume**:L4 的 `OHLC` 型別根本沒有這個欄位(該欄自 2026-07-09
    起連續 33 個交易日全為 0)。這裡順帶記一筆是因為 `get_twii_ohlc()` 也
    刻意沒有回傳它 —— 兩層都不碰,才不會有人「順手」把它接回來。
    """
    row = build_reference_row(card.key, _last_or_none(ohlc_raw.get("close")))
    ohlc = OHLC(
        xs=ohlc_raw.get("xs"),
        open=ohlc_raw.get("open"),
        high=ohlc_raw.get("high"),
        low=ohlc_raw.get("low"),
        close=ohlc_raw.get("close"),
    )
    render_candlestick_card(row, REF_SPECS_BY_KEY[card.key], ohlc,
                            series_note=card.note)


def _render_held_card(card: ChartCard, *, by_key: dict) -> None:
    """`hold_reason` 非空的卡:**數字照顯示,圖暫不繪製,原因寫在下面。**

    走既有的 `render_chart_card` 並餵空序列 —— 它會印「歷史序列取得失敗
    —— 不以合成資料替代。」+ 門檻帶,然後由本函式在卡片下方補上**那句
    「取得失敗」的實際成因**與復原條件。

    ⚠️ 兩個已知的取捨,都不是漏看:
    1. L4 那句固定文案講的是「取得失敗」,而本例的實情是「取到了但不可用」。
       L4 目前沒有「卡片層通知」這個管道,而該檔在本次的檔案邊界之外
       (見交付回報的建議事項:替 `render_chart_card` 加一個 `notice` 參數)。
       故改以緊接其後的說明句補齊,讀起來是**補述**而不是更正。
    2. 說明句落在卡片框線**外**(L4 的 `st.container(border=True)` 在函式
       內就關掉了),但仍在同一欄、緊貼卡片下方,歸屬不會被誤讀。

    標題加上「⚠️ 圖表資料疑義」讓它一眼看得出來。這個字串是**從
    `row.label` 衍生**的,不是另外寫死一個名字(§3.3)。
    """
    from dataclasses import replace as _replace

    row = by_key[card.key]
    render_chart_card(_replace(row, label=f"{row.label}　⚠️ 圖表資料疑義"),
                      SPECS_BY_KEY[card.key], [], [])
    st.caption(card.hold_reason)


def render_one_card(card: ChartCard, *, by_key: dict, inputs,
                    parquet_series: dict, ohlc_raw: dict) -> None:
    """第 2 層的一張卡 —— 依 `kind` 派給對應的 L4 渲染函式。

    §1:未知的 `kind` 直接 `raise`。若默默不畫,那張卡會**憑空消失**,
    而畫面上「少一張卡」與「這個指標今天沒資料」長得一模一樣。
    """
    # 資料疑義的卡先攔下 —— 它連自己那條序列都不該去取(見 `_render_held_card`)。
    if card.hold_reason:
        _render_held_card(card, by_key=by_key)
        return
    if card.kind == KIND_DUAL:
        _render_dual_card(card, by_key=by_key, inputs=inputs)
        return
    if card.kind == KIND_OHLC:
        _render_kline_card(card, ohlc_raw=ohlc_raw)
        return
    row, spec = by_key[card.key], SPECS_BY_KEY[card.key]
    if card.kind == KIND_PARQUET:
        pts = parquet_series.get(card.key) or []
        xs = [d for d, _ in pts]
        ys = [v for _, v in pts]
    elif card.kind == KIND_SESSION:
        xs, ys = _session_series(inputs, card.key)
        xs, ys = xs or [], ys or []
    else:
        raise ValueError(
            f"未知的卡片種類 {card.kind!r}(可用:{list(CHART_KINDS)})")
    render_chart_card(row, spec, xs, ys, series_note=card.note)


def render_tab_macro_v2() -> None:
    """總經 v2 分頁進入點。由 app.py 的「🌍 市場環境」子分頁呼叫。"""
    st.markdown(CSS, unsafe_allow_html=True)

    inputs = load_section_inputs(st.session_state)
    readiness: dict = {}
    compute_five_bucket_summary(
        macro_info=inputs.macro_info, mkt_info=inputs.mkt_info,
        warroom_summary=inputs.warroom_summary, m1b_m2_info=inputs.m1b_m2_info,
        bias_info=inputs.bias_info, cl_data=inputs.cl_data,
        li_latest=inputs.li_latest, jingqi_info=inputs.jingqi_info,
        news_items=inputs.news_items,
        readiness_out=readiness,
    )
    rows = build_rows(readiness)
    summary = bucket_summary(rows)

    st.caption(
        "本頁與「🌍 總經」讀**同一份資料**(同一個 `compute_five_bucket_summary`),"
        "只是換一種呈現。要更新數字請到「🌍 總經」按「🚀 一鍵更新全部數據」。"
    )

    # ── 第 1 層 · 結論 ────────────────────────────────────────────────
    st.subheader("第 1 層 · 結論", divider="gray")
    left, right = st.columns([7, 5], gap="medium")

    band, detail = overall_verdict(summary)
    zh, color = BAND_META[band]
    with left, st.container(border=True):
        st.markdown('<p class="v2-t">總經位階</p>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="v2-hero" style="color:{color}">{zh}</div>',
            unsafe_allow_html=True)
        st.markdown(f'<p style="opacity:.75;margin-top:6px">{detail}</p>',
                    unsafe_allow_html=True)
        st.caption("五桶取最差(worst-of)—— 與現行總經頁同一套判定，不是另一套演算法。")
    with right, st.container(border=True):
        render_signal_health(rows)

    render_bucket_cards(summary)

    # ── 第 2 層 · 為什麼 ──────────────────────────────────────────────
    st.subheader("第 2 層 · 為什麼", divider="gray")
    st.caption(
        "只有**具備真實歷史序列**的指標才畫走勢。16 盞燈裡多數沒有落地序列"
        "(如 VIX、台灣 PMI),那些改用純數值卡 —— 不以合成資料充當走勢(§1)。"
        "　·　台幣與加權指數是**參考走勢**:畫圖但**不算一盞燈**,"
        "不影響上方的「x / 16」、五桶彙總與訊號可信度。"
        "　·　「精簡總覽」是**真的少畫**(不建那幾張圖、也不去取它們的序列),"
        "不是把卡片藏起來。"
    )

    by_key = {r.key: r for r in rows}

    # ── 密度切換 ────────────────────────────────────────────────────────
    # widget 選型:`st.radio(horizontal=True)`。`st.pills`(1.40+)/
    # `st.segmented_control`(1.42+)在現行 floor(`requirements.txt` 已抬到
    # 1.56)底下**是可以用的**,但第 3 層的分類 chip 已經在用
    # `st.radio(horizontal=True)` —— 同一頁兩種外觀的單選器會讓人以為它們
    # 的行為不同。視覺一致優先(user 2026-08-27)。
    #
    # ⚠️ 切換一次 = 一次 rerun = app.py 七個頂層 tab 的 body 全部重跑
    #    (STATE.md v19.132 產業熱力圖冷抓事故的同一個性質)。所以這顆 widget
    #    的價值必須大於它自己的代價 —— 而它省下的正是**整頁**的圖表建置,
    #    不只是本分頁的。
    density = st.radio(
        "密度", DENSITY_OPTIONS, index=DENSITY_DEFAULT_INDEX, horizontal=True,
        label_visibility="collapsed", key="v2_chart_density",
    )

    # 參考走勢卡(taiex / usdtwd)**不在 `by_key` 裡** —— 它們不是燈,不進
    # readiness 側車。篩選與密度一次做完(見 `visible_cards`)。
    cards = visible_cards(density, by_key=by_key)

    # ── L3 取數:**看篩選後的 `cards`,不是看 `_CHART_SPECS` 這個常數** ──
    # 看常數的話「這一輪到底有沒有要畫 parquet 卡」永遠是同一個答案,
    # 於是就算一張 parquet 卡都沒有,還是會去讀 4,900+ 列的檔。
    # `hold_reason` 非空的卡不畫圖 → **也不該為它去取數**。
    # 若這裡漏了 `not c.hold_reason`,一張根本不畫的卡照樣會讓整頁去讀
    # 4,900+ 列的 parquet —— 花了成本、畫面上零產出。
    _kinds = {c.kind for c in cards if not c.hold_reason}
    parquet_series: dict = get_chart_series() if KIND_PARQUET in _kinds else {}
    ohlc_raw: dict = (get_twii_ohlc(TWII_KLINE_TRADING_DAYS)
                      if KIND_OHLC in _kinds else {})

    # 固定 3 張/列:卡片數變動時**列數**變多,每張卡永遠一樣寬(見 CARDS_PER_ROW)。
    for _row_cards in chunk_cards(cards):
        # ⚠️ 這裡傳的是 `CARDS_PER_ROW` 而不是 `len(_row_cards)` —— 最後一列
        #    不滿 3 張時要**留空欄**,不能讓剩下的卡把整列撐開變形。
        cols = st.columns(CARDS_PER_ROW, gap="medium")
        for col, card in zip(cols, _row_cards):
            with col:
                render_one_card(card, by_key=by_key, inputs=inputs,
                                parquet_series=parquet_series,
                                ohlc_raw=ohlc_raw)

    vcards = [k for k in _VALUE_CARD_KEYS if k in by_key]
    # 純數值卡走同一組欄寬 —— 兩種卡片用不同寬度會讓第 2 層看起來像兩個區塊。
    for _row_keys in chunk_cards(vcards):
        vcols = st.columns(CARDS_PER_ROW, gap="medium")
        for col, key in zip(vcols, _row_keys):
            with col:
                render_value_card(by_key[key], SPECS_BY_KEY[key])

    # ── 第 3 層 · 全部明細 ────────────────────────────────────────────
    st.subheader("第 3 層 · 全部明細", divider="gray")

    # 搜尋 + 分類 chip。**兩者都只做純 Python 篩選,不重新取數** —— app.py 是
    # 7 個頂層 `st.tabs`,每次 rerun 所有 tab body 都會執行,任何因篩選而觸發
    # 的取數都會被乘上 7(STATE.md 產業熱力圖冷抓事故)。
    #
    # ⚠️ widget 選型受 `requirements.txt` 的 floor 綁死 —— 沙箱裝的是 1.61,
    # 測起來一律會過,部署端解析到 floor 才 AttributeError。
    #
    # 【2026-08-27 更正】本段原本寫「floor 是 1.36,故 st.pills(1.40+)/
    # st.segmented_control(1.42+)/ st.fragment(1.37+) 一律不得使用」。
    # **那個版本號已經過期**:同日 commit `fa8e90b` 把 floor 抬到 1.56,
    # 上述三個 API 現在全都在 floor 之上,禁令的**理由已不成立**。
    # 保留 `st.radio(horizontal=True)` 的理由換成**視覺一致**:本頁第 2 層的
    # 密度切換也用同一種單選器,同一頁兩種外觀的單選器會讓人以為行為不同。
    # 真正的版本守衛是 `tests/test_macro_v2_tab.py::TestStreamlitFloorCompatibility`
    # (從 `requirements.txt` 反解 floor,唯一真相源)—— 不是這段註解。
    fcol_q, fcol_chip = st.columns([4, 8], gap="medium")
    with fcol_q:
        query = st.text_input(
            "搜尋指標", value="", placeholder="搜尋指標… 例如 VIX、融資",
            label_visibility="collapsed", key="v2_detail_query",
        )
    with fcol_chip:
        chip = st.radio(
            "分類", CHIP_ORDER, index=0, horizontal=True,
            format_func=lambda c: CHIP_LABELS[c],
            label_visibility="collapsed", key="v2_detail_chip",
        )

    # 篩選 + 組表**同一次呼叫、同一份 list** —— 見 `selected_row` 的警告。
    visible, table = visible_table(rows, chip=chip, query=query)

    tbl, panel = st.columns([7, 5], gap="medium")

    with tbl:
        if visible:
            sel = st.dataframe(
                table, hide_index=True, width='stretch',
                on_select="rerun", selection_mode="single-row",
                key="v2_detail_table",
            )
        else:
            # §1:不留一張空表讓人以為頁面壞了,把目前的篩選條件講出來。
            sel = None
            st.warning(empty_hint(chip=chip, query=query, total=len(rows)))
        st.caption(f"顯示 {len(visible)} / {len(rows)} 盞燈")

        # ── 列印雙軌:螢幕看上面那張互動表,列印看這一份純 HTML 表 ──────
        # 為什麼一定要多畫一份:`st.dataframe` 走 glide-data-grid,整張表畫在
        # <canvas> 上而且**虛擬捲動** —— 捲出視窗的列根本不在 DOM 裡,列印時
        # 沒有東西可以被印出來。這是 CSS 救不了的,只能另外給一份真表格。
        #
        # **為什麼選「常駐隱藏」而不是加一顆「列印版」toggle**:
        #   · 使用者的動作就是直接按 Ctrl+P。toggle 只幫得到「知道要先去點
        #     那顆 toggle」的人;沒點就按 Ctrl+P 的人拿到的還是壞掉的輸出 ——
        #     那正是這次要修的那個 bug,等於沒修。
        #   · toggle 是一個 widget,切一次 = 一次 rerun = app.py 七個頂層 tab
        #     的 body 全部重跑(STATE.md v19.132 產業熱力圖冷抓事故的同一個
        #     性質)。常駐隱藏零互動、零 rerun。
        #   · 互動表與右側面板完全不動,既有的「面板顯示的就是表格那一列」
        #     守衛一行都不用改。
        #
        # **餵的是同一個 `table`**(= 上面 `st.dataframe` 吃的那一個 dict),
        # 不是重新篩一次 —— 兩張表要分岔,得先有人在這裡換掉這個變數。
        #
        # **跟著篩選走**:印出來的必須就是螢幕上看到的那幾列。若印全部 16 盞,
        # 同一頁的螢幕與紙本會說不一樣的話(§1);抬頭會把篩選條件寫進紙裡,
        # 所以「只有 3 列」不會被誤讀成「總共只有 3 盞燈」。想印全部 → 把
        # chip 切回「全部」再印,那是一次點擊。
        #
        # 螢幕代價:多一個 `display:none` 的元素容器,在這一欄底部留下一段
        # 約 1rem 的空白(Streamlit 垂直區塊是 flex + gap,零高度子元素仍佔一個
        # gap)。它在**欄位底部的空白區**,沒有任何內容因此位移。
        if visible:
            st.markdown(
                print_table_html(
                    table,
                    print_caption(chip=chip, query=query,
                                  shown=len(visible), total=len(rows)),
                ),
                unsafe_allow_html=True,
            )

    with panel, st.container(border=True):
        idxs = (sel.selection.rows if sel and getattr(sel, "selection", None)
                else [])
        # ⚠️ 一定要用 `visible`(= 畫面那張表)去解析,不是原始 `rows`。
        row = selected_row(visible, idxs)
        if row is not None:
            render_detail(row, SPECS_BY_KEY[row.key], edu=get_edu(row.key),
                          reason_text=_REASON_TXT.get(row.reason or "", ""))
        elif idxs:
            st.markdown("#### 選取已失效")
            st.caption(
                "剛才點的那一列已經不在目前的篩選結果裡。**這裡刻意不自動改選"
                "別列** —— 那會讓右側悄悄換成另一個指標,畫面說 A 內容是 B(§1)。"
                "請在左表重新點一列。"
            )
        else:
            st.markdown("#### 點左表任一列")
            st.caption(
                "右側會就地展開該指標的完整資訊:目前值、門檻帶、命中來源、"
                "教學文案(門檻數字即時代入,不是抄的)、以及**為什麼這盞燈不能信**"
                "(未接線 / 門檻已失準的原因,直接讀自 SSOT)。"
            )
