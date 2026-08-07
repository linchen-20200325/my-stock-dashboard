# -*- coding: utf-8 -*-
"""shared/edu_tokens.py — 教學文案「活門檻」token SSOT(L0 Infra,D3/B7)。

═══ 這個模組在解什麼問題 ══════════════════════════════════════════════
`src/data/core/data_registry.EDU_GUIDE` 的每一筆 `how_to_read` 都是
`list[(門檻條件, 判讀)]`,而那些門檻數字**全部是手打的**。稽核實測(2026-08-07)
最刺眼的一組:

    EDU_GUIDE['MI_MARGN'].how_to_read
        ('< 1500 億', '🟢 …') / ('1500 ~ 2200 億', '🟡 …') / ('> 2500 億', '🔴 散戶過熱')
    production 判定(`src/ui/render/macro_ui_components.margin_card`)
        > MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI(3400) → 🔴「超過3400億高危」
        > MARGIN_BALANCE_WARN_THRESHOLD_YI(2500)     → 🟡「超過2500億警戒」

⇒ 融資 2600 億時,🌍 總經頁的融資卡印 **🟡 警戒**,📚 說明書的教學卡印
  **🔴 散戶過熱,注意主力出貨** —— 同一份數字、同一個 app,兩個相反的結論。
  同一 block 的 `historical_anchor` 又手寫「健康區 1500–2000 億」,是**第三個版本**。

這不是單點錯字,是**結構問題**:教學文案裡的數字沒有任何機制與判定式綁在一起,
所以每次調門檻(v19.170 才剛把 2500 抽成 SSOT)文案都不會跟著動,只會愈漂愈遠。

═══ 對策(沿用 `tab_edu.py` B6-a v19.181 已驗證的機制)═════════════════
可被 code 證實或證偽的數字**一律不手寫**,寫成 `§§TOKEN§§`,由本模組在
**render 期**從 SSOT 取值替換:

- 改常數 → 文案自動跟著動,不可能漂移;
- 漏改 / 打錯的 token **原樣印在畫面上**(不是靜默消失)→ 自帶 §1 fail-loud;
- 用 `§§…§§` 而非 `str.format` 的 `{}`:教學段落含 markdown 表格與 code fence,
  `.format()` 會被 `{` 誤炸;token 取代是純字串替換,零風險。

═══ 為什麼放 L0(`shared/`)而不是 L5(`tab_edu`)══════════════════════
`tab_edu.py`(L5)已有一份 `_edu_tokens()` / `_resolve_edu_tokens()`,但那份**不能**
被 `data_registry.py` 用 —— data_registry 在 **L1**,§8.2 硬規則禁止 L1 import L5
(跨層上行)。三個候選位置:

    L5 `tab_edu`      ✗ L1 → L5 上行違憲
    L1 `data_registry` △ data_registry 自己能用,但 tab_edu(L5)要用就得 L5 → L1,
                        且「教學文案 token 解析」不是資料源註冊表的職責
    L0 `shared/`      ✓ 唯一兩邊都能合法 import 的層

且 token 的**值**本來就全部住在 L0(`shared/signal_thresholds.py`、
`shared/macro_buckets.py`),放 L0 等於「值與解析器同層」,無跨層依賴。
本檔零 I/O、零 streamlit、只 import 同層 L0 常數 → 合 §8.2「L0 不得依賴任何 L1+」。

═══ 與 `tab_edu.py` 的關係(F1 v19.184 收斂完成)═════════════════════
D3 當時留下兩份 token 表(本檔 L0 + `tab_edu._edu_tokens()` L5),並註記「長期應收斂」。
F1 已收斂,但**不是**收成一份 —— 收成「**一份 L0 主表 + 一小撮 L1 衍生 token**」:

    純 L0 常數推得的 token   → 全部住本檔,**唯一出處**
    需要 L1 才算得出的 token → 只能留 L5(`§§PMI_SOURCES§§` / `§§PMI_SOURCE_COUNT§§`)

為什麼不能全搬進來:那兩個 token 的值來自 `macro_core.PMI_SOURCE_REGISTRY`(**L1**),
而 §8.2 硬規則「L0 不得依賴任何 L1+」。硬搬 = 本檔違憲;硬留 = 兩份表繼續漂。
故 `tab_edu._edu_tokens()` 現在是 `{**edu_tokens(), **<L1 衍生>}` —— 同名 token
**物理上只有一個定義點**(本檔),L5 那層只負責補 L0 構不到的兩個。

⚠️ 因此「兩份表同名 token 值是否相同」這種 drift 守衛已無意義(同名 token 不可能
不同,因為只有一份定義)。改由 `tests/test_f1_edu_token_coverage.py` 斷言
「L5 表 ⊇ L0 表且同名 token 值相同(= 沒被 L5 覆寫)」。

═══ 門檻的來源(每一條都可回溯)═══════════════════════════════════════
- 融資 / 外資期貨口數 → `shared/signal_thresholds.py` 具名常數
- VIX / CPI / 10Y / DXY / 出口 / 外資現貨 / M1B-M2 / PMI
  → `shared/macro_buckets.BUCKET_DANGER_SPECS`(五桶危險門檻註冊表)。
    刻意**不**自己再鏡像一次 `macro_core.MACRO_THRESHOLDS`:那張表已由
    macro_buckets 鏡像 + `tests/test_macro_buckets.py` drift 守衛盯著,
    本檔再抄一次就是製造第四份真相(正是本模組要消滅的東西)。
"""
from __future__ import annotations

import math
import re
from typing import Iterable, Optional, Sequence

from shared.macro_buckets import SPECS_BY_KEY
from shared.signal_thresholds import (
    BREADTH_BULL_PCT,
    BREADTH_NEUTRAL_PCT,
    ETF_QUICK_SIGMA_CHEAP,
    ETF_QUICK_SIGMA_DISASTER,
    ETF_QUICK_SIGMA_HIGH,
    ETF_QUICK_SIGMA_OVERBOUGHT,
    ETF_QUICK_SIGMA_OVERSOLD,
    FOREIGN_5D_NET_THRESHOLD_YI,
    FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD,
    FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS,
    FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS,
    HEALTH_WEIGHT_JQ,
    HEALTH_WEIGHT_SCORE,
    MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI,
    MARGIN_BALANCE_WARN_THRESHOLD_YI,
    RECESSION_LOGIT_COEF_INTERCEPT,
    RECESSION_LOGIT_COEF_SPREAD,
    TNX_NEUTRAL_PCT,
    TOP5_LARGE_TRADER_NET_BULL_LOTS,
    TOP5_LARGE_TRADER_NET_WARN_LOTS,
    TWII_20D_DROP_THRESHOLD_PCT,
    US_CORE_CPI_YOY_BANDS,
    VIX_HIGH_RISK_THRESHOLD,
    VIX_MEDIUM_RISK_THRESHOLD,
)
from shared.thresholds import YIELD_HIGH, YIELD_LOW, YIELD_MID

#: token 的字面樣式。用 `§§` 是因為它在中文教學文案裡幾乎不可能自然出現,
#: 而 `{}` / `%s` 都會與 markdown / f-string 打架。
TOKEN_PATTERN = re.compile(r"§§[A-Z0-9_]+§§")


def _spec(key: str, field: str) -> str:
    """從 `BUCKET_DANGER_SPECS` 取某條門檻並格式化成人看的字串。

    §1 Fail Loud:key / field 不存在時**不回空字串也不回 0**,而是回一個
    看得見的錯誤標記 —— 教學卡上出現 `⟪MISSING:xxx⟫` 遠比印出一個腦補的
    數字安全(錯的數字比沒有數字更危險)。
    """
    _s = SPECS_BY_KEY.get(key)
    if _s is None:
        return f"⟪MISSING-SPEC:{key}⟫"
    _v = getattr(_s, field, None)
    if _v is None:
        return f"⟪MISSING-FIELD:{key}.{field}⟫"
    return f"{float(_v):g}"


def _band(bands: Sequence[Sequence], level: str) -> str:
    """從 `signal_thresholds` 的 `*_BANDS`(list[(門檻, level, 標籤, 說明)])取某級門檻。

    以 `level`(green/yellow/red)查而非用位置索引 —— 位置會隨帶數增減而位移,
    level 名不會。查不到同樣回看得見的錯誤標記(§1,理由同 `_spec`)。
    """
    for _b in bands or ():
        if len(_b) >= 2 and _b[1] == level:
            try:
                return f"{float(_b[0]):g}"
            except (TypeError, ValueError):
                break
    return f"⟪MISSING-BAND:{level}⟫"


def _recession_p_pct(spread_pct: float) -> float:
    """複刻 `macro_core.recession_probability` 的算式(同一組 SSOT 係數)。

    ⚠️ 為什麼 L0 要複刻而不 import:`recession_probability` 住 `src/data/macro/`(**L1**),
    §8.2 硬規則禁止 L0 依賴 L1。本函式**只用 L0 常數**做一次 logistic,
    與 L1 那份是否同步由 `tests/test_b6a_edu_doc_parity.py::test_doc_number_matches_
    production_function` 直接對帳(拿 L1 真函式的回傳值比,不是比字面)。
    """
    _logit = RECESSION_LOGIT_COEF_SPREAD * spread_pct + RECESSION_LOGIT_COEF_INTERCEPT
    return round(1 / (1 + math.exp(-_logit)) * 100, 1)


def _leek_alert_pct() -> tuple[str, str]:
    """韭菜(法人空多比)極端值警示門檻 → (高, 低) 格式化字串。

    `LEEK_ALERT_*_PCT` 住 `src/config/config.py`(同屬 L0,合法平行 import),
    但採**函式內 late import**:本檔被 `data_registry`(L1)在 module load 期 import,
    而 `src.config` 會條件 import streamlit(EX-L0-1)。延後可避免把那條依賴
    拉進每一次 `import data_registry` 的啟動路徑。

    §1:import 失敗**不回 0 也不吞掉**,回看得見的錯誤標記。
    """
    try:
        from src.config import LEEK_ALERT_HIGH_PCT, LEEK_ALERT_LOW_PCT
    except Exception as _e:   # noqa: BLE001 — 教學文案不因 config 載入失敗整頁炸
        print(f"[edu_tokens] ⚠️ 讀不到 LEEK_ALERT_*_PCT: {type(_e).__name__}: {_e}")
        return "⟪MISSING-CONST:LEEK_ALERT_HIGH_PCT⟫", "⟪MISSING-CONST:LEEK_ALERT_LOW_PCT⟫"
    return f"{LEEK_ALERT_HIGH_PCT:+g}", f"{LEEK_ALERT_LOW_PCT:+g}"


def edu_tokens() -> dict[str, str]:
    """token → SSOT 實值字串。**每次呼叫現算**,不做 module-level 快取。

    不快取的理由:`macro_thresholds.json` 季度校準會改動部分下游常數,
    module-level 凍結會讓「改了常數但畫面沒跟著動」這個 bug 換一種形式復活。
    本函式只是幾十次屬性讀取 + 格式化,成本可忽略。
    """
    _leek_hi, _leek_lo = _leek_alert_pct()
    return {
        # ── 融資餘額(億 TWD)—— B7 主角 ────────────────────────────
        "§§MARGIN_WARN_YI§§": f"{MARGIN_BALANCE_WARN_THRESHOLD_YI:,.0f}",
        "§§MARGIN_OVERHEAT_YI§§": f"{MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI:,.0f}",
        # ── 外資期貨淨口數(口)。⚠️ 這是**外資期貨**的線,不是大額交易人留倉的線 ──
        "§§FUT_YELLOW_LOTS§§": f"{FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS:,}",
        "§§FUT_RED_LOTS§§": f"{FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS:,}",
        # 同二值的別名 —— tab_edu 既有文案用 `FUT_V4_*` 命名(強調「這是 v4 引擎
        # 風險燈那條線」)。F1 收斂時刻意**保留兩個名字指向同一常數**而不強制改名:
        # 改名要動教學文案,而文案改動是畫面變更;別名零風險且語意更清楚。
        # 兩者永遠相等由 `tests/test_f1_edu_token_coverage.py` 釘住。
        "§§FUT_V4_YELLOW_LOTS§§": f"{FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS:,}",
        "§§FUT_V4_RED_LOTS§§": f"{FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS:,}",
        # 紅綠燈「空頭防禦」旗標用的**絕對值**門檻,與上面兩條用途不同(見常數 docstring)
        "§§FUT_DEFENSE_LOTS§§": f"{FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD:,}",
        # ── 前五大交易人留倉(口)。⚠️ 與上面外資期貨的線同數字不同義,見常數 docstring ──
        "§§TOP5_WARN_LOTS§§": f"{TOP5_LARGE_TRADER_NET_WARN_LOTS:,}",
        "§§TOP5_BULL_LOTS§§": f"{TOP5_LARGE_TRADER_NET_BULL_LOTS:,}",
        # ── 五桶危險門檻註冊表(= macro_core.MACRO_THRESHOLDS 鏡像 + DESIGN 線)──
        "§§VIX_YELLOW§§": _spec("vix", "yellow"),
        "§§VIX_RED§§": _spec("vix", "red"),
        "§§CPI_YELLOW§§": _spec("us_core_cpi", "yellow"),
        "§§CPI_RED§§": _spec("us_core_cpi", "red"),
        "§§US10Y_YELLOW§§": _spec("us10y", "yellow"),
        "§§US10Y_RED§§": _spec("us10y", "red"),
        "§§DXY_YELLOW§§": _spec("dxy", "yellow"),
        "§§DXY_RED§§": _spec("dxy", "red"),
        "§§TW_EXPORT_YELLOW§§": _spec("tw_export", "yellow"),
        "§§TW_EXPORT_RED§§": _spec("tw_export", "red"),
        "§§FOREIGN_NET_YELLOW_YI§§": _spec("foreign_net", "yellow"),
        "§§FOREIGN_NET_RED_YI§§": _spec("foreign_net", "red"),
        "§§M1B_M2_YELLOW§§": _spec("m1b_m2_gap", "yellow"),
        "§§M1B_M2_RED§§": _spec("m1b_m2_gap", "red"),
        "§§PMI_YELLOW§§": _spec("ism_pmi", "yellow"),
        "§§PMI_RED§§": _spec("ism_pmi", "red"),
        # ── 同一指標的「第二把尺」——刻意保留並具名,不是重複 ──────────
        # 本專案有數條指標同時存在兩組**用途不同**的門檻。教學卡的責任是把
        # 「哪一條線屬於哪個畫面」講清楚,而不是自己挑一條(挑 = 製造第三種說法,
        # 正是 B7 這個 bug 的成因)。
        #   CPI  : 五桶危險門檻 3.5/4.0(MACRO_THRESHOLDS 鏡像)
        #          vs 總經「中期」卡片帶 US_CORE_CPI_YOY_BANDS 2.5/3.5
        #   VIX  : 五桶 22/30(MACRO_THRESHOLDS)vs v4 引擎風險燈 20/25
        #          (v4 只看 VIX + 外資期貨,見 config.VETO_V4_ENGINE_INPUTS)
        #   10Y  : 五桶 4.5/5.0 vs macro_compass 中性線 3.5(TNX_NEUTRAL_PCT)
        "§§CPI_MID_YELLOW§§": _band(US_CORE_CPI_YOY_BANDS, "yellow"),
        "§§CPI_MID_RED§§": _band(US_CORE_CPI_YOY_BANDS, "red"),
        "§§VIX_V4_YELLOW§§": f"{VIX_MEDIUM_RISK_THRESHOLD:g}",
        "§§VIX_V4_RED§§": f"{VIX_HIGH_RISK_THRESHOLD:g}",
        "§§TNX_NEUTRAL§§": f"{TNX_NEUTRAL_PCT:g}",
        # ── 外資現貨 5 日累積(億 TWD)——真正會亮燈的是 5 日,不是單日 ──
        "§§FOREIGN_5D_YI§§": f"{FOREIGN_5D_NET_THRESHOLD_YI:,.0f}",
        # ── 357 殖利率估值法則(%)——選股網「殖利率」入場帶 ──────────
        "§§YIELD_HIGH§§": f"{YIELD_HIGH:g}",
        "§§YIELD_MID§§": f"{YIELD_MID:g}",
        "§§YIELD_LOW§§": f"{YIELD_LOW:g}",
        # ── F1 v19.184 自 `tab_edu._edu_tokens()`(L5)搬入 ────────────────
        # 這些全部只依賴 L0 常數,原本沒有留在 L5 的理由;留著就是兩份定義。
        # 需要 L1 才算得出的兩個(§§PMI_SOURCES§§ / §§PMI_SOURCE_COUNT§§)
        # **刻意不搬** —— 見本檔 docstring「與 tab_edu.py 的關係」。
        # 市場廣度(旌旗指數 / ADL 上漲佔比 %)
        "§§BREADTH_BULL§§": f"{BREADTH_BULL_PCT:g}",
        "§§BREADTH_NEUTRAL§§": f"{BREADTH_NEUTRAL_PCT:g}",
        # 加權指數 20 日跌幅紅旗(%;負值)
        "§§TWII_20D_PCT§§": f"{TWII_20D_DROP_THRESHOLD_PCT:g}",
        # 韭菜(法人空多比)極端值警示(%;帶正負號,因為兩側都有意義)
        "§§LEEK_ALERT_HIGH§§": _leek_hi,
        "§§LEEK_ALERT_LOW§§": _leek_lo,
        # logistic 衰退機率係數 + 三個代入示例(%)
        "§§RECESSION_COEF_SPREAD§§": f"{RECESSION_LOGIT_COEF_SPREAD:g}",
        "§§RECESSION_COEF_INTERCEPT§§": f"{RECESSION_LOGIT_COEF_INTERCEPT:g}",
        "§§RECESSION_P_AT_0§§": f"{_recession_p_pct(0.0):.0f}",
        "§§RECESSION_P_AT_M1§§": f"{_recession_p_pct(-1.0):.0f}",
        "§§RECESSION_P_AT_M2§§": f"{_recession_p_pct(-2.0):.0f}",
        # ── F1 v19.184 新增:UI 說明文字(help= / st.caption)常手抄的門檻 ──
        # 總經健康評分:因子權重(%)與危險線。§§HEALTH_*§§ 兩條線來自五桶註冊表,
        # 權重兩條來自 signal_thresholds(v19.102 AUC 校準值)。
        "§§HEALTH_W_JQ_PCT§§": f"{HEALTH_WEIGHT_JQ * 100:g}",
        "§§HEALTH_W_SCORE_PCT§§": f"{HEALTH_WEIGHT_SCORE * 100:g}",
        "§§HEALTH_YELLOW§§": _spec("health", "yellow"),
        "§§HEALTH_RED§§": _spec("health", "red"),
        # 大盤年線乖離 BIAS240(%)。⚠️ 與個股的 `STOCK_BIAS_*` 同數字不同義,
        # 教學/說明文字若在講「大盤」請用本組,講「個股」不可套用。
        "§§BIAS240_YELLOW§§": _spec("bias_240", "yellow"),
        "§§BIAS240_RED§§": _spec("bias_240", "red"),
        # 前五大交易人留倉警戒線的**絕對值**(口)。常數本身是負數(-10000),
        # 但文案寫的是「淨空超過 1 萬口」這種絕對量級 → 另給一個絕對值 token,
        # 避免文案自己去掉負號(去負號 = 手動加工 = 又一次手抄)。
        "§§TOP5_WARN_LOTS_ABS§§": f"{abs(TOP5_LARGE_TRADER_NET_WARN_LOTS):,}",
        # ETF 衛星「跌了就買」σ 位階倍數(σ 的倍數,無單位)
        "§§ETF_SIGMA_DISASTER§§": f"{ETF_QUICK_SIGMA_DISASTER:g}",
        "§§ETF_SIGMA_OVERSOLD§§": f"{ETF_QUICK_SIGMA_OVERSOLD:g}",
        "§§ETF_SIGMA_CHEAP§§": f"{ETF_QUICK_SIGMA_CHEAP:g}",
        "§§ETF_SIGMA_HIGH§§": f"{ETF_QUICK_SIGMA_HIGH:g}",
        "§§ETF_SIGMA_OVERBOUGHT§§": f"{ETF_QUICK_SIGMA_OVERBOUGHT:g}",
    }


def resolve_edu_tokens(text: str, tokens: Optional[dict[str, str]] = None) -> str:
    """把教學文字裡的 `§§TOKEN§§` 換成 SSOT 實值。

    `tokens` 省略時現算一份(單段用);批次渲染請先取一份重複傳入。

    **未登記的 token 保持原樣**印在畫面上 —— 這是刻意的:漏改的佔位符要看得見
    (§1 降級不靜默),不可悄悄消失成空字串。`unresolved_tokens()` + 回歸測試
    負責在 CI 就攔下,不必等使用者看到。
    """
    if not text:
        return text
    _tk = edu_tokens() if tokens is None else tokens
    for _k, _v in _tk.items():
        text = text.replace(_k, _v)
    return text


def resolve_edu_rules(
    rules: Optional[Sequence[Sequence[str]]],
    tokens: Optional[dict[str, str]] = None,
) -> list[tuple[str, str]]:
    """把 `how_to_read` 的 `[(門檻, 判讀), ...]` 兩欄都做 token 取代。

    回傳一律是 `list[tuple[str, str]]`(呼叫端可能傳 list of list)。
    `rules` 為 None / 空 → 回 `[]`(不拋例外:教學卡缺這段只是少一張表)。
    """
    if not rules:
        return []
    _tk = edu_tokens() if tokens is None else tokens
    _out: list[tuple[str, str]] = []
    for _r in rules:
        _pair = tuple(_r)
        if len(_pair) != 2:
            # 結構壞掉要出聲(否則畫面只是少一列,沒人會發現)
            print(f"[edu_tokens] ⚠️ how_to_read 列不是 (門檻, 判讀) 兩欄,已略過: {_r!r}")
            continue
        _out.append((
            resolve_edu_tokens(str(_pair[0]), _tk),
            resolve_edu_tokens(str(_pair[1]), _tk),
        ))
    return _out


def unresolved_tokens(*texts: object) -> set[str]:
    """回傳這些文字裡「長得像 token 但沒登記」的集合(空 = 全部解得開)。

    接受字串 / 巢狀 list / tuple / dict(只掃 value),供測試一次掃整份
    `EDU_GUIDE`。用途是把「畫面上會印出 `§§XXX§§` 亂碼」這件事在 CI 就擋下來。
    """
    _known = set(edu_tokens())
    _found: set[str] = set()

    def _walk(o: object) -> None:
        if isinstance(o, str):
            _found.update(TOKEN_PATTERN.findall(o))
        elif isinstance(o, dict):
            for _v in o.values():
                _walk(_v)
        elif isinstance(o, (list, tuple, set)):
            for _v in o:
                _walk(_v)

    for _t in texts:
        _walk(_t)
    return _found - _known


def all_token_names(texts: Iterable[object]) -> set[str]:
    """回傳這些文字裡出現過的所有 token 字面(含已登記者),供測試做覆蓋率檢查。"""
    _found: set[str] = set()

    def _walk(o: object) -> None:
        if isinstance(o, str):
            _found.update(TOKEN_PATTERN.findall(o))
        elif isinstance(o, dict):
            for _v in o.values():
                _walk(_v)
        elif isinstance(o, (list, tuple, set)):
            for _v in o:
                _walk(_v)

    for _t in texts:
        _walk(_t)
    return _found
