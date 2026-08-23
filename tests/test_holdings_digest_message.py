"""L2 守衛 — 每日持股續抱/換股推播訊息格式化（純函式,#35）。

golden 式:正常全區段、續抱空狀態、switch=None 降級、無字面 None、免責、held-only 換出、
SSOT 停利門檻。§1:數字全來自 digest/switch,不捏造。
"""
from __future__ import annotations

from shared import dividend_station_thresholds as T
from src.compute.notify.holdings_digest_message import format_holdings_message as F

_AS_OF = "2026-08-22 17:15"


def _full_digest():
    return {
        "total": 5, "vix": 22.3,
        "reds": [{"代號": "2412", "建議動作": "財報C 建議換出"}],
        "adds": [{"代號": "0056", "235": "🟡 急跌加碼", "加碼金": "30%"}],
        "errors": ["3008"],
        "allocation": {"core_pct": 72.0, "sat_pct": 28.0, "core_target": 80.0,
                       "sat_target": 20.0, "core_dev": -8.0, "partial": False},
        "take_profit": [{"代號": "2317", "損益%": 18.0}],
    }


def _full_switch():
    return {
        "regime": "bull", "loaded": True, "defense": False,
        "posture": "🟢 積極", "posture_range": "70–90%", "stance": "aggressive",
        "switch_out": [{"代號": "2412", "建議動作": "財報C 建議換出"}],
        "switch_in": [{"代號": "2330", "名稱": "台積電", "綜合分": 87.0}],
        "switch_in_src": "watchlist",
    }


def test_full_message_has_all_sections():
    msg = F(_full_digest(), _full_switch(), as_of=_AS_OF)
    assert "持股戰情室" in msg and _AS_OF in msg
    assert "bull" in msg and "70–90%" in msg           # 位階/姿態
    assert "VIX：22.3" in msg
    assert "建議換出" in msg and "2412" in msg
    assert "建議換入" in msg and "2330 台積電" in msg and "你的觀察清單" in msg
    assert "235" in msg and "0056" in msg
    assert "停利" in msg and "2317" in msg
    assert "核心 72%" in msg and "衛星 28%" in msg
    assert "3008" in msg and "未納入" in msg
    assert "非投資建議" in msg


def test_take_profit_threshold_from_ssot():
    """§3.3:停利門檻顯示走 SSOT,不硬寫 15。"""
    msg = F(_full_digest(), _full_switch(), as_of=_AS_OF)
    assert f"≥{T.SATELLITE_TAKE_PROFIT_PCT:.0f}%" in msg


def test_switch_in_source_screener_label():
    sw = _full_switch()
    sw["switch_in_src"] = "screener"
    msg = F(_full_digest(), sw, as_of=_AS_OF)
    assert "選股池排名" in msg


def test_empty_state_says_hold():
    d = {"total": 3, "vix": 15.0, "reds": [], "adds": [], "errors": [],
         "allocation": None, "take_profit": []}
    s = {"regime": "unknown", "loaded": False, "switch_out": [], "switch_in": [],
         "switch_in_src": "screener"}
    msg = F(d, s, as_of=_AS_OF)
    assert "無需動作" in msg and "續抱" in msg
    assert "未評估" in msg                       # 位階未載入誠實標
    assert "None" not in msg


def test_degraded_no_switch_uses_reds_with_caveat():
    """switch=None（極少數 build 失敗）→ 換出退 digest.reds 並標『含觀察清單』,不字面 None。"""
    msg = F(_full_digest(), None, as_of=_AS_OF)
    assert "2412" in msg and "含觀察清單" in msg
    assert "建議換入" not in msg                 # 無 switch → 無換入段
    assert "None" not in msg


def test_vix_missing_shows_honest_text():
    d = _full_digest()
    d["vix"] = None
    msg = F(d, _full_switch(), as_of=_AS_OF)
    assert "VIX：抓取失敗" in msg
    assert "None" not in msg


def test_no_switch_out_shows_hold_line():
    d = _full_digest()
    d["reds"] = []
    s = _full_switch()
    s["switch_out"] = []
    msg = F(d, s, as_of=_AS_OF)
    assert "無紅燈,續抱" in msg


def test_allocation_partial_flag_shown():
    d = _full_digest()
    d["allocation"]["partial"] = True
    msg = F(d, _full_switch(), as_of=_AS_OF)
    assert "僅供參考" in msg


def test_never_prints_literal_none_when_scores_missing():
    """§1:換入候選缺綜合分 → 不得印字面 None。"""
    s = _full_switch()
    s["switch_in"] = [{"代號": "2330", "名稱": "台積電", "綜合分": None}]
    msg = F(_full_digest(), s, as_of=_AS_OF)
    assert "2330 台積電" in msg
    assert "None" not in msg


def test_total_zero_never_gives_false_all_clear():
    """稽核🔴A:代號讀到但每檔抓取全失敗(total=0)→ 不得印「無需動作/續抱」的假安心,
    改誠實「未能判斷」（§1:不從零資料給結論）。"""
    d = {"total": 0, "vix": None, "reds": [], "adds": [], "errors": ["2412", "2330"],
         "allocation": None, "take_profit": []}
    s = {"regime": "unknown", "loaded": False, "switch_out": [], "switch_in": [],
         "switch_in_src": "screener"}
    msg = F(d, s, as_of=_AS_OF)
    assert "無需動作" not in msg and "續抱、定期定額" not in msg
    assert "未能判斷" in msg and "抓取全失敗" in msg
    assert "None" not in msg


def test_code_or_badge_none_never_prints_literal_none():
    """稽核🟡D:代號/235/加碼金 present-but-None（非缺席）不得印字面 None。"""
    d = {"total": 2, "vix": 20.0, "reds": [],
         "adds": [{"代號": None, "235": None, "加碼金": None}],
         "errors": [], "allocation": None, "take_profit": [{"代號": None, "損益%": 16.0}]}
    s = {"regime": "bull", "loaded": True, "posture": "x", "switch_out": [],
         "switch_in": [{"代號": None, "名稱": "台積電", "綜合分": None}], "switch_in_src": "screener"}
    msg = F(d, s, as_of=_AS_OF)
    assert "None" not in msg


def test_partial_allocation_does_not_crash():
    """稽核🟢E:allocation 缺鍵(上游契約漂移)→ 略過該段,不 KeyError 炸整則。"""
    d = _full_digest()
    d["allocation"] = {"core_pct": 72.0}   # 缺 sat_pct / core_target / ... 等鍵
    msg = F(d, _full_switch(), as_of=_AS_OF)   # 不應 raise
    assert "配置" not in msg
    assert "非投資建議" in msg


# ── 合併每日選股（§ user 2026-08-23）─────────────────────────────────────
def test_picks_section_rendered():
    """今日選股 Top N（換股池）併入同一則,含編號 + 代號/名稱/綜合分。"""
    picks = [{"代碼": "2330", "名稱": "台積電", "綜合分": 92},
             {"代碼": "2454", "名稱": "聯發科", "綜合分": 88}]
    msg = F(_full_digest(), _full_switch(), as_of=_AS_OF, picks=picks)
    assert "今日選股" in msg and "換股池" in msg
    assert "1. 2330 台積電" in msg and "2454 聯發科" in msg


def test_picks_none_omits_section():
    """picks 預設 None（向後相容）→ 不顯示選股段。"""
    msg = F(_full_digest(), _full_switch(), as_of=_AS_OF)
    assert "今日選股" not in msg


def test_picks_missing_score_no_literal_none():
    """§1:選股候選缺綜合分 → 不印字面 None。"""
    picks = [{"代碼": "2330", "名稱": "台積電", "綜合分": None}]
    msg = F(_full_digest(), _full_switch(), as_of=_AS_OF, picks=picks)
    assert "2330 台積電" in msg and "None" not in msg


def test_switch_in_suppressed_when_screener_and_picks_shown():
    """去重:換入來自 screener + 有選股清單 → 只留清單,不重印換入段。"""
    s = _full_switch()
    s["switch_in_src"] = "screener"
    picks = [{"代碼": "2330", "名稱": "台積電", "綜合分": 92}]
    msg = F(_full_digest(), s, as_of=_AS_OF, picks=picks)
    assert "建議換入" not in msg and "今日選股" in msg


def test_switch_in_kept_when_watchlist_even_with_picks():
    """換入來自你的觀察清單🟢 → 與選股清單各有價值,兩段都留。"""
    s = _full_switch()
    s["switch_in_src"] = "watchlist"
    picks = [{"代碼": "2454", "名稱": "聯發科", "綜合分": 88}]
    msg = F(_full_digest(), s, as_of=_AS_OF, picks=picks)
    assert "建議換入" in msg and "今日選股" in msg
