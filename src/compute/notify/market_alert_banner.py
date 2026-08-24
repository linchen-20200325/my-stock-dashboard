# -*- coding: utf-8 -*-
"""src/compute/notify/market_alert_banner.py — 推播用風險警語組字（L2 純函式,零 I/O）。

三層,語意刻意不同 —— **越罕見的觸發、指令越強**:

  **動作層 A** `format_extreme_banner` —— 台股本地兩腿共振(20 日跌幅 + 外資 5 日賣超)。
      實測 1.25 次/年(20.0 年,n=4,895 交易日)。成立 → 「持股降至 10%、停止買賣」。
  **動作層 B** `format_broad_selloff_banner` —— 國際盤**至少 3 個**領先市場同日大跌。
      實測約 13 次/年(n=59 配對日,樣本小)。成立 → 「持股降至 20%」。
  **提示層**   `format_global_lead_line` —— **任一**領先市場大跌(-1.5%)。
      實測 31% 的交易日會出現(約 77 次/年)。**只描述事實,不下動作指令。**

⚠️ 2026-08-24 更正:上面提示層的「53%」原本寫錯,那是拿 mynews 歸檔裡一個**有 bug 的
欄位**(把五日累計變動當日變動)算出來的。真實日變動重測後是 31%。完整原委見
`shared/global_lead_markets.py` 檔頭。

為什麼要分層:一年響 77 次的東西寫上動作指令,使用者會學會忽略它,然後在真正該跑的
那次也一起忽略。常響的那層不下指令,罕見的那層才下 —— 這樣罕見那層的訊號強度才不會
被稀釋。兩個動作層同時成立時**取較嚴的**(10% 蓋過 20%),避免同一則訊息出現兩個
互相打架的持股數字。門檻依據見 `shared/signal_thresholds.py` 的「極端風險閘門」段
與 `shared/global_lead_markets.py` 檔頭。

═══ §1 Fail Loud:本檔最重要的一條 ═════════════════════════════════════
「算不出來」與「算過了、沒事」**必須長得不一樣**:

    extreme → 🚨 區塊        (兩腿都評估過,且都成立)
    clear   → **空字串**      (兩腿都評估過,未同時成立 → 訊息乾淨)
    unknown → ⬜ 區塊 + 明講缺哪一腿 + 「不代表安全」

只有在**兩腿都真的評估過**時,才可以用「沒有警語」來表示安全。任一腿缺料 / 過舊,
一律 unknown —— 絕不可以因為「拿不到外資資料」就靜靜地不印警語,那等於把
「不知道」偽裝成「安全」,是本 repo 這一輪稽核從頭到尾在修的同一個病。

§8.2 分層:L2 Compute —— 純函式。**不得** import requests / yfinance / proxy_helper /
FinMind / streamlit,也不得讀檔。取數是 orchestrator(scripts/push_*.py)的事,
本檔只吃已經抓好的數值。守衛:tests/test_extreme_risk_banner.py 的 AST 純度測試。
"""
from __future__ import annotations

from dataclasses import dataclass

from shared.global_lead_markets import (
    GLOBAL_LEAD_DROP_PCT,
    LEAD_BROAD_DROP_MIN_MARKETS,
    LEAD_MARKETS,
    LEAD_TARGET_POSITION_PCT,
    is_lead_drop,
)
from shared.signal_thresholds import (
    EXTREME_TARGET_POSITION_PCT,
    EXTREME_TWII_20D_DROP_PCT,
    FOREIGN_5D_NET_THRESHOLD_YI,
)

LEG_TWII = "大盤 20 日跌幅"
LEG_FOREIGN = "外資 5 日買賣超"

STATE_EXTREME = "extreme"
STATE_CLEAR = "clear"
STATE_UNKNOWN = "unknown"
STATE_FIRED = "fired"   # 動作層 B 專用（動作層 A 用 STATE_EXTREME）


@dataclass(frozen=True)
class ExtremeRiskVerdict:
    """兩腿共振的判定結果。

    state   : STATE_EXTREME / STATE_CLEAR / STATE_UNKNOWN
    missing : 無法評估的腿名(供訊息明講缺什麼);state 為 unknown 時必非空
    """

    state: str
    missing: tuple[str, ...]
    twii_20d_pct: float | None
    foreign_5d_yi: float | None

    @property
    def is_extreme(self) -> bool:
        return self.state == STATE_EXTREME


def evaluate_extreme_risk(
    *,
    twii_20d_pct: float | None,
    foreign_5d_yi: float | None,
) -> ExtremeRiskVerdict:
    """兩腿共振判定。任一腿為 None(缺料/過舊)→ unknown,**不做任何樂觀推定**。

    twii_20d_pct  : 加權指數 20 交易日報酬（%,跌為負）
    foreign_5d_yi : 外資 5 日累計淨買賣（億 TWD,賣超為負）

    刻意**不**接受「其中一腿成立就夠」的短路:即使 20 日跌幅已達 -30%,只要外資那腿
    缺料,仍回 unknown。理由是這條警語會叫使用者把持股砍到一成 —— 這種強度的指令
    不該建立在半套資料上;而 unknown 本身就會在訊息裡明白顯示,不會被吞掉。
    """
    missing: list[str] = []
    if twii_20d_pct is None:
        missing.append(LEG_TWII)
    if foreign_5d_yi is None:
        missing.append(LEG_FOREIGN)
    if missing:
        return ExtremeRiskVerdict(STATE_UNKNOWN, tuple(missing), twii_20d_pct, foreign_5d_yi)

    hit = (twii_20d_pct <= EXTREME_TWII_20D_DROP_PCT
           and foreign_5d_yi <= FOREIGN_5D_NET_THRESHOLD_YI)
    return ExtremeRiskVerdict(
        STATE_EXTREME if hit else STATE_CLEAR, (), twii_20d_pct, foreign_5d_yi
    )


def format_extreme_banner(verdict: ExtremeRiskVerdict) -> str:
    """動作層警語。clear → 空字串;unknown → ⬜ 區塊(絕不靜默)。

    措辭上刻意避開既有訊息模組的否定斷言用詞,避免跨模組測試互撞。
    """
    if verdict.state == STATE_CLEAR:
        return ""

    if verdict.state == STATE_UNKNOWN:
        return "\n".join([
            f"⬜ 極端風險：無法判斷（缺 {'、'.join(verdict.missing)}）",
            "　這不代表安全 —— 只代表這次沒算出來，請自行確認。",
        ])

    _t = verdict.twii_20d_pct
    _f = verdict.foreign_5d_yi
    return "\n".join([
        f"🚨 極端風險：建議持股降至 {EXTREME_TARGET_POSITION_PCT}%",
        "　停止買賣，現有部位盡量脫手。",
        f"　觸發：大盤 20 日 {_t:+.1f}%　外資 5 日{_fmt_yi(_f)}",
        "　（規則式警語，非投資建議；判斷依據見看板）",
    ])


def _fmt_yi(v: float) -> str:
    """億元金額 → 中文語意字串。賣超講「賣超」,不用負號讓人自己翻譯。"""
    return f"賣超 {abs(v):,.0f} 億" if v < 0 else f"買超 {v:,.0f} 億"


def format_global_lead_line(changes: "dict[str, float | None] | None") -> str:
    """提示層:國際盤領先市場。

    changes: {Yahoo symbol: 日變動%}。缺料的標的給 None 或直接不放進 dict。

    回傳:
        有標的達 -1.5%   → "⚠️ 國際盤：那斯達克綜合 -4.2%、費城半導體 -6.1%（開盤留意）"
        全部缺料         → "⬜ 國際盤：報價未取得"
        部分缺料且無大跌 → "⬜ 國際盤：部分報價未取得（4/6）"
        都有料且無大跌   → ""（不佔行）

    「部分缺料且無大跌」不能回空字串:沒抓到的那兩個可能正在崩。
    """
    changes = changes or {}
    known = [(m, changes.get(m.symbol)) for m in LEAD_MARKETS]
    got = [(m, v) for m, v in known if v is not None]
    if not got:
        return "⬜ 國際盤：報價未取得"

    drops = [(m, v) for m, v in got if is_lead_drop(v)]
    if drops:
        _body = "、".join(f"{m.name} {v:+.1f}%" for m, v in drops)
        return f"⚠️ 國際盤：{_body}（開盤留意）"

    if len(got) < len(LEAD_MARKETS):
        return f"⬜ 國際盤：部分報價未取得（{len(got)}/{len(LEAD_MARKETS)}）"
    return ""


@dataclass(frozen=True)
class BroadSelloffVerdict:
    """國際盤「全面性大跌」判定（動作層 B）。

    state    : STATE_FIRED / STATE_CLEAR / STATE_UNKNOWN
    n_drops  : 已知達標(<= -1.5%)的市場數
    n_missing: 缺料的市場數 —— unknown 判定的關鍵
    names    : 達標市場的顯示名（依 LEAD_MARKETS 順序）
    """

    state: str
    n_drops: int
    n_missing: int
    names: tuple[str, ...]

    @property
    def is_fired(self) -> bool:
        return self.state == STATE_FIRED


def evaluate_broad_lead_selloff(
    changes: "dict[str, float | None] | None",
) -> BroadSelloffVerdict:
    """至少 `LEAD_BROAD_DROP_MIN_MARKETS` 個領先市場同日大跌 → 動作層 B 成立。

    **缺料處理是本函式的重點**,三種結果不可混為一談:

        已達標數 >= 門檻                     → FIRED   (缺料再多也不影響結論)
        已達標數 + 缺料數 >= 門檻            → UNKNOWN (缺的那幾個可能正在崩)
        已達標數 + 缺料數 <  門檻            → CLEAR   (就算缺的全在崩也湊不到門檻)

    中間那條是重點:例如門檻 3、已知 2 個在跌、另有 2 個沒抓到 —— 這時候**不能**
    說「沒有全面大跌」,因為只要那 2 個裡有 1 個也在跌就成立了。回 CLEAR 等於把
    「不知道」偽裝成「安全」(§1)。反過來,若已知 1 個在跌、只缺 1 個,那最多湊到 2,
    低於門檻 3 → 這時 CLEAR 是**真的算得出來**的結論,不是猜的。
    """
    changes = changes or {}
    drops: list[str] = []
    n_missing = 0
    for m in LEAD_MARKETS:
        v = changes.get(m.symbol)
        if v is None:
            n_missing += 1
        elif is_lead_drop(v):
            drops.append(m.name)

    n = len(drops)
    if n >= LEAD_BROAD_DROP_MIN_MARKETS:
        state = STATE_FIRED
    elif n + n_missing >= LEAD_BROAD_DROP_MIN_MARKETS:
        state = STATE_UNKNOWN
    else:
        state = STATE_CLEAR
    return BroadSelloffVerdict(state, n, n_missing, tuple(drops))


def format_broad_selloff_banner(verdict: BroadSelloffVerdict) -> str:
    """動作層 B 警語。CLEAR → 空字串;UNKNOWN → ⬜ 區塊(絕不靜默)。"""
    if verdict.state == STATE_CLEAR:
        return ""

    if verdict.state == STATE_UNKNOWN:
        return "\n".join([
            f"⬜ 國際盤全面性大跌：無法判斷（{verdict.n_missing} 個市場報價未取得）",
            "　這不代表安全 —— 只代表這次沒算出來，請自行確認。",
        ])

    return "\n".join([
        f"🚨 國際盤全面大跌：建議持股降至 {LEAD_TARGET_POSITION_PCT}%",
        "　停止買賣，現有部位盡量脫手。",
        (f"　觸發：{verdict.n_drops} 個領先市場同日跌逾 "
         f"{abs(GLOBAL_LEAD_DROP_PCT):.1f}%（{'、'.join(verdict.names)}）"),
        "　（規則式警語，非投資建議；判斷依據見看板）",
    ])


def has_action_directive(
    verdict: ExtremeRiskVerdict,
    changes: "dict[str, float | None] | None" = None,
) -> bool:
    """本次是否含**動作指令**（任一動作層成立）。

    供訊息模組抑制「今日無需動作：續抱、定期定額即可。」——
    同一則訊息不可以同時出現「盡量脫手」與「續抱」。

    ⚠️ UNKNOWN **不算**動作指令:它沒有叫使用者做任何事,只是誠實說算不出來,
    與「今日無需動作」並不矛盾(⬜ 區塊自己會講「這不代表安全」)。
    """
    return verdict.is_extreme or evaluate_broad_lead_selloff(changes).is_fired


def build_alert_block(
    verdict: ExtremeRiskVerdict,
    changes: "dict[str, float | None] | None" = None,
) -> str:
    """把三層併成一塊,供訊息模組插在標題之前。全部無話可說 → 空字串。

    **順序與互斥規則**:

        1. 動作層 A(兩腿共振,10%)  ─┐ 兩者同時成立時只印 A ——
        2. 動作層 B(國際全面,20%)  ─┘ 取較嚴的,避免兩個持股數字打架
        3. 提示層(任一市場大跌,描述用)  ← 一律附上,它是 A/B 的佐證資料

    動作層排最前面:LINE 通知預覽只顯示開頭幾十個字,真正需要行動的那則必須搶到第一行。

    ⚠️ 「取較嚴的」只在**兩者都是動作**時適用。A=UNKNOWN 而 B=FIRED 時兩塊都要印:
    前者說「台股那兩腿算不出來」,後者說「國際盤全面在跌、降到 20%」—— 是兩件不同的
    事實,吃掉任何一個都會讓使用者少知道一件事。
    """
    _a = format_extreme_banner(verdict)
    _b = format_broad_selloff_banner(evaluate_broad_lead_selloff(changes))

    # 兩個動作層都成立 → 只留較嚴的 A(10%)。B 若是 UNKNOWN/CLEAR 則不受影響。
    if verdict.is_extreme and _b.startswith("🚨"):
        _b = ""

    return "\n".join(x for x in (_a, _b, format_global_lead_line(changes)) if x)
