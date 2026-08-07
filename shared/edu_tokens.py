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

⚠️ `tab_edu.py` 那份 L5-local token 表**本批未動**(該檔屬另一組的施工範圍)。
兩份 token 表的**值**都取自同一批 L0 常數,故不會打架;但長期應由 tab_edu 改吃本檔,
屆時 L5 那份縮成 `from shared.edu_tokens import resolve_edu_tokens`。
`tests/test_d3_toolbox_registry.py` 有守衛斷言兩份表對同名 token 的值相同。

═══ 門檻的來源(每一條都可回溯)═══════════════════════════════════════
- 融資 / 外資期貨口數 → `shared/signal_thresholds.py` 具名常數
- VIX / CPI / 10Y / DXY / 出口 / 外資現貨 / M1B-M2 / PMI
  → `shared/macro_buckets.BUCKET_DANGER_SPECS`(五桶危險門檻註冊表)。
    刻意**不**自己再鏡像一次 `macro_core.MACRO_THRESHOLDS`:那張表已由
    macro_buckets 鏡像 + `tests/test_macro_buckets.py` drift 守衛盯著,
    本檔再抄一次就是製造第四份真相(正是本模組要消滅的東西)。
"""
from __future__ import annotations

import re
from typing import Iterable, Optional, Sequence

from shared.macro_buckets import SPECS_BY_KEY
from shared.signal_thresholds import (
    FOREIGN_5D_NET_THRESHOLD_YI,
    FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS,
    FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS,
    MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI,
    MARGIN_BALANCE_WARN_THRESHOLD_YI,
    TNX_NEUTRAL_PCT,
    TOP5_LARGE_TRADER_NET_BULL_LOTS,
    TOP5_LARGE_TRADER_NET_WARN_LOTS,
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


def edu_tokens() -> dict[str, str]:
    """token → SSOT 實值字串。**每次呼叫現算**,不做 module-level 快取。

    不快取的理由:`macro_thresholds.json` 季度校準會改動部分下游常數,
    module-level 凍結會讓「改了常數但畫面沒跟著動」這個 bug 換一種形式復活。
    本函式只是幾十次屬性讀取 + 格式化,成本可忽略。
    """
    return {
        # ── 融資餘額(億 TWD)—— B7 主角 ────────────────────────────
        "§§MARGIN_WARN_YI§§": f"{MARGIN_BALANCE_WARN_THRESHOLD_YI:,.0f}",
        "§§MARGIN_OVERHEAT_YI§§": f"{MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI:,.0f}",
        # ── 外資期貨淨口數(口)。⚠️ 這是**外資期貨**的線,不是大額交易人留倉的線 ──
        "§§FUT_YELLOW_LOTS§§": f"{FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS:,}",
        "§§FUT_RED_LOTS§§": f"{FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS:,}",
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
