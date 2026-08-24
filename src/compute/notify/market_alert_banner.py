# -*- coding: utf-8 -*-
"""src/compute/notify/market_alert_banner.py — 推播用風險警語組字（L2 純函式,零 I/O）。

兩層,語意刻意不同:

  **動作層** `format_extreme_banner` —— 兩腿共振(台股 20 日跌幅 + 外資 5 日賣超)。
      實測 1.25 次/年(20.0 年,n=4,895 交易日)。成立時明講「持股降至 10%、停止買賣」。
  **提示層** `format_global_lead_line` —— 國際盤領先市場大跌(-1.5%)。
      實測 53% 的交易日會出現。**只描述事實,不下動作指令。**

為什麼要分兩層:一年響 15 次以上的東西寫上動作指令,使用者會學會忽略它,
然後在真正該跑的那次也一起忽略。常響的那層不下指令,罕見的那層才下 —— 這樣
罕見那層的訊號強度才不會被稀釋。門檻的實測依據見
`shared/signal_thresholds.py` 的「極端風險閘門」段與 `shared/global_lead_markets.py` 檔頭。

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

from shared.global_lead_markets import LEAD_MARKETS, is_lead_drop
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


def build_alert_block(
    verdict: ExtremeRiskVerdict,
    changes: "dict[str, float | None] | None" = None,
) -> str:
    """把兩層併成一塊,供訊息模組插在標題之後。全部無話可說 → 空字串。

    順序固定「動作層在上、提示層在下」:LINE 通知預覽只顯示開頭幾十個字,
    真正需要行動的那則必須搶到第一行。
    """
    return "\n".join(x for x in (format_extreme_banner(verdict),
                                 format_global_lead_line(changes)) if x)
