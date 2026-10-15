"""AUD-C3 守衛：每日持股推播不得對同一檔給出互相矛盾的指令。

修前（兩組以 production 函式實跑確認）：`build_station_digest` 的 `adds` 只看
`加碼金` 非空（＝235 燈 deploy_pct>0），繞過 `suggest_action` 的核准優先序
（汰弱 > 停利 > 趨勢暫停 > 加碼 > 高溢價 > 巡航）→

- 同一檔同時出現在「🔴 建議換出（汰弱）」與「➕ 235 逢低加碼 … 加碼50%」；
- 健檢 C 🟡（季線轉弱）必然同時亮 235 燈 → 每檔「暫停加碼」都被推成「加碼 ≥30%」；
- 觀察清單（未持有）也被推成持股加碼。

修法（單一來源，digest 層）：`row_from_assessment` 帶非顯示欄 `_action`
（`ds.action_branch`，即 `suggest_action` 那一份條件的分支代碼）；digest 的 `adds`
只收「持有列 且 `_action == ds.ACTION_ADD`」，觀察清單另列 `watch_adds`。

本檔全部走真實引擎路徑：`build_station_rows`（→ `assess_holding` → `row_from_assessment`）
→ `build_station_digest` → `build_switch_advice` → `format_holdings_message` /
`build_summary_prompt`。只 stub 掉網路（`metrics_fn` 依賴注入）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from shared import dividend_station_thresholds as T
from src.compute.etf import dividend_station as ds
from src.compute.notify.holdings_digest_message import format_holdings_message
from src.services import dividend_station_service as svc

# ── 週收序列（三種形態，各自穩定落在既定分支；前置斷言見 test_fixture_branches）──
_IDX = pd.date_range("2023-01-01", periods=120, freq="W-SUN")
_I = np.arange(120)
_SERIES = {
    # 緩升 + 小幅震盪：健檢 C 🟢、布林 z 不到 +2σ → 235 只看 VIX
    "up": pd.Series(20 + 0.01 * _I + 0.05 * np.sin(_I), index=_IDX),
    # 先升後連 8 週 -2%：週收 < 季線且季線下彎 → 健檢 C 🟡，235 同時亮燈
    "weak": pd.Series(np.r_[20 + 0.02 * _I[:112],
                            (20 + 0.02 * 111) * np.cumprod(np.full(8, 0.98))], index=_IDX),
    # 平盤後最後一週急漲：布林 z > +3σ → 強制停利（deploy 0）
    "spike": pd.Series(np.r_[20 + 0.05 * np.sin(_I[:119]), 23.0], index=_IDX),
}
_CALM_VIX = T.VIX_LIGHT1 - 5.0          # 平靜市況（< 燈一）
_CRASH_VIX = T.VIX_LIGHT3 + 2.0         # 崩盤（≥ 燈三）
_MID_VIX = (T.VIX_LIGHT2 + T.VIX_LIGHT3) / 2   # 燈二區間


def _holding(code: str, *, series: str, held: bool = True, tr1y: float = 10.0,
             yld: float = 5.0, sharpe: float = 0.8, premium: float = 0.1) -> dict:
    return {"ticker": code, "name": code, "asset_class": T.ASSET_CORE,
            "asset_kind": T.KIND_ETF, "held": held,
            "_m": {"weekly_close": _SERIES[series], "premium_pct": premium,
                   "sharpe": sharpe, "total_return_1y_pct": tr1y,
                   "annual_yield_pct": yld, "inception_years": 5,
                   "ann_return_3y_pct": 5.0, "cum_return_3y_pct": 15.0,
                   "peer_ranks": None}}


def _run(holdings: list[dict], vix: float):
    """真實引擎路徑（只 stub 網路）→ (rows, digest, switch, message, prompt)。"""
    _by = {h["ticker"]: h["_m"] for h in holdings}
    rows = svc.build_station_rows(holdings, vix=vix, metrics_fn=lambda tk, ak: _by[tk])
    digest = svc.build_station_digest(rows, vix)
    switch = svc.build_switch_advice(rows, {"loaded": False}, [])
    msg = format_holdings_message(digest, switch, as_of="2026-10-15")
    prompt = svc.build_summary_prompt(digest, switch=switch)
    return rows, digest, switch, msg, prompt


def _section_codes(msg: str, header_prefix: str) -> list[str]:
    """訊息中以 header_prefix 開頭的段落裡、`　・代號 …` 那幾行的代號。"""
    _codes: list[str] = []
    _in = False
    for _ln in msg.splitlines():
        if _ln.startswith(header_prefix):
            _in = True
            continue
        if _in and not _ln.strip():
            _in = False
        if _in and _ln.startswith("　・"):
            _codes.append(_ln[2:].split("（")[0].split(" ")[0])
    return _codes


def _section_lines(msg: str, header_prefix: str) -> list[str]:
    _out: list[str] = []
    _in = False
    for _ln in msg.splitlines():
        if _ln.startswith(header_prefix):
            _in = True
            continue
        if _in and not _ln.strip():
            break
        if _in:
            _out.append(_ln)
    return _out


_ADD_HDR = "➕ 235 逢低加碼觸發"
_OUT_HDR = "🔴 建議換出"
_WATCH_HDR = "🚦 觀察清單（未持有）235 燈號"


def _prompt_line(prompt: str, label: str) -> str:
    return next(_l for _l in prompt.splitlines() if _l.startswith(f"- {label}："))


# ════════════════════════════════════════════════════════════════
# 0. 前置：序列確實落在預期分支（否則以下測試等於沒測）
# ════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("series, vix, tr1y, expect", [
    ("up", _CALM_VIX, 10.0, ds.ACTION_CRUISE),
    ("up", _MID_VIX, 10.0, ds.ACTION_ADD),
    ("up", _CRASH_VIX, 10.0, ds.ACTION_ADD),
    ("up", _CRASH_VIX, 1.0, ds.ACTION_CUT),
    ("weak", _CALM_VIX, 10.0, ds.ACTION_PAUSE_ADD),
    ("weak", _CRASH_VIX, 10.0, ds.ACTION_PAUSE_ADD),
    ("spike", _CRASH_VIX, 10.0, ds.ACTION_TAKE_PROFIT_FORCE),
])
def test_fixture_branches(series, vix, tr1y, expect):
    rows, *_ = _run([_holding("00901", series=series, tr1y=tr1y)], vix)
    assert rows[0]["_action"] == expect


# ════════════════════════════════════════════════════════════════
# 1. 同一代號不能同時在換出段與加碼段（崩盤 + 平靜兩種市況）
# ════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("vix", [_CRASH_VIX, _MID_VIX, _CALM_VIX])
@pytest.mark.parametrize("series", ["up", "weak"])
def test_cut_holding_never_in_add_section(vix, series):
    # 健檢 A 🔴（年報酬 < 配息率）＋ 235 亮燈（VIX 或週線）
    rows, digest, switch, msg, prompt = _run(
        [_holding("00901", series=series, tr1y=1.0),
         _holding("00902", series=series, sharpe=-0.3)], vix)
    assert {r["_action"] for r in rows} == {ds.ACTION_CUT}
    _out = set(_section_codes(msg, _OUT_HDR))
    _add = set(_section_codes(msg, _ADD_HDR))
    assert _out == {"00901", "00902"}
    assert not (_out & _add), msg
    assert digest["adds"] == []


def test_crash_cut_and_pure_add_coexist_without_overlap():
    """崩盤：汰弱檔只在換出段；真正走加碼分支的檔只在加碼段。"""
    rows, digest, switch, msg, _ = _run(
        [_holding("00901", series="up", tr1y=1.0),       # 汰弱
         _holding("00903", series="up")], _CRASH_VIX)    # 加碼
    assert _section_codes(msg, _OUT_HDR) == ["00901"]
    assert _section_codes(msg, _ADD_HDR) == ["00903"]


# ════════════════════════════════════════════════════════════════
# 2. 健檢 C 🟡（暫停加碼）→ 不在加碼段
# ════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("vix", [_CALM_VIX, _CRASH_VIX])
def test_paused_holding_not_in_add_section(vix):
    rows, digest, switch, msg, prompt = _run([_holding("00904", series="weak")], vix)
    r = rows[0]
    assert r["加碼金"]                                   # 235 燈仍亮（欄位本身不動）
    assert "暫停加碼" in r["建議動作"]
    assert digest["adds"] == []
    assert _ADD_HDR not in msg
    assert "00904" not in _prompt_line(prompt, "235 加碼觸發")


# ════════════════════════════════════════════════════════════════
# 3. 停利 → 不在加碼段
# ════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("vix", [_CALM_VIX, _CRASH_VIX])
def test_take_profit_holding_not_in_add_section(vix):
    rows, digest, switch, msg, _ = _run([_holding("00905", series="spike")], vix)
    assert rows[0]["_action"] == ds.ACTION_TAKE_PROFIT_FORCE
    assert digest["adds"] == []
    assert "00905" not in _section_codes(msg, _ADD_HDR)


# ════════════════════════════════════════════════════════════════
# 4. 只有「加碼」分支才進加碼段；N% 與 deploy_pct 一致、字串逐字不變
# ════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("vix, pct", [(_MID_VIX, 30), (_CRASH_VIX, 50)])
def test_only_add_branch_in_add_section_with_unchanged_text(vix, pct):
    rows, digest, switch, msg, prompt = _run([_holding("00906", series="up")], vix)
    r = rows[0]
    assert r["_action"] == ds.ACTION_ADD
    assert r["加碼金"] == f"{pct}%"
    assert digest["adds"] == [{"代號": "00906", "235": r["235 燈號"], "加碼金": f"{pct}%"}]
    # 推播行逐字（與修前同一格式）
    assert _section_lines(msg, _ADD_HDR) == [f"　・00906 {r['235 燈號']} 加碼{pct}%"]
    # AI prompt 行逐字（與修前同一格式）
    assert _prompt_line(prompt, "235 加碼觸發") == (
        f"- 235 加碼觸發：00906 {r['235 燈號']} 加碼{pct}%")
    # 有加碼 → 不得說「今日無需動作」
    assert "今日無需動作" not in msg


def test_suggest_action_strings_are_unchanged():
    """`action_branch` 抽出後，`suggest_action` 每條分支的輸出字串逐字不變（golden）。"""
    def _a(series, vix, tr1y=10.0, sharpe=0.8, premium=0.1):
        return ds.assess_holding(
            ticker="00901", name="x", asset_class=T.ASSET_CORE, asset_kind=T.KIND_ETF,
            weekly_close=_SERIES[series], vix=vix, premium_pct=premium, sharpe=sharpe,
            total_return_1y_pct=tr1y, annual_yield_pct=5.0, inception_years=5,
            ann_return_3y_pct=5.0, cum_return_3y_pct=15.0, peer_ranks=None)
    assert ds.suggest_action(_a("up", 15.0)) == "⚪ 巡航：維持定期定額"
    assert ds.suggest_action(_a("up", 26.0)) == "🟡 加碼 30%：VIX 25~30"
    assert ds.suggest_action(_a("up", 32.0)) == "🔴 加碼 50%：VIX≥30"
    assert ds.suggest_action(_a("up", 32.0, tr1y=1.0)) == (
        "🔴 汰弱：賺息賠本：年報酬 1.0% < 配息率 5.0%（吃到本金）")
    assert ds.suggest_action(_a("weak", 15.0)) == "🟡 🔴 訊號亮但季線轉弱 → 暫停加碼、先觀望"
    assert ds.suggest_action(_a("spike", 15.0)) == "💰 強制停利（>+3σ）：獲利轉回核心資產"
    assert ds.suggest_action(_a("up", 15.0, premium=2.0)).startswith("🟡 高溢價")


# ════════════════════════════════════════════════════════════════
# 5. 觀察清單 → 不在持股加碼段；另列段落須標「觀察清單（未持有）」、不寫加碼 N%
# ════════════════════════════════════════════════════════════════
def test_watchlist_add_signal_is_separated_from_holding_adds():
    rows, digest, switch, msg, prompt = _run(
        [_holding("00907", series="up", held=False),
         _holding("00908", series="weak", held=False)], _CRASH_VIX)
    assert digest["adds"] == []
    assert [d["代號"] for d in digest["watch_adds"]] == ["00907"]   # 暫停者不列
    assert _ADD_HDR not in msg
    _icon = rows[0]["235 燈號"].split(" ", 1)[0]
    assert _icon == "🔴"                                         # 崩盤燈三的 emoji
    assert digest["watch_adds"] == [{"代號": "00907", "燈號": _icon}]
    _w = _section_lines(msg, _WATCH_HDR)
    assert _w == [f"　・00907 {_icon}"]                          # 只列代號 + 燈號 emoji
    assert not any("%" in _l for _l in _w)                       # 不是加碼指令
    _p_watch = _prompt_line(prompt, "觀察清單（未持有）235 燈號")
    assert _p_watch == f"- 觀察清單（未持有）235 燈號：00907 {_icon}"
    # 觀察清單段與其 prompt 行不得出現「加碼」二字（燈號名稱「崩盤/深水加碼」不得帶入）
    assert "加碼" not in "\n".join([_WATCH_HDR, *_w])
    assert "加碼" not in _p_watch
    assert "00907" not in _prompt_line(prompt, "235 加碼觸發")
    # 觀察清單不是持股動作 → 不阻擋「今日無需動作」
    assert "今日無需動作" in msg


def test_no_watchlist_line_when_empty_keeps_prompt_unchanged():
    *_, msg, prompt = _run([_holding("00906", series="up")], _CRASH_VIX)
    assert "觀察清單（未持有）235 燈號" not in prompt
    assert _WATCH_HDR not in msg


# ════════════════════════════════════════════════════════════════
# 「今日無需動作」：無加碼但有換出 → 不可說無需動作
# ════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("vix", [_CALM_VIX, _CRASH_VIX])
def test_no_action_line_absent_when_switch_out_exists(vix):
    *_, msg, _ = _run([_holding("00901", series="up", tr1y=1.0)], vix)
    assert _section_codes(msg, _OUT_HDR) == ["00901"]
    assert "今日無需動作" not in msg


# ════════════════════════════════════════════════════════════════
# 6. AI prompt 同樣不含矛盾的加碼行
# ════════════════════════════════════════════════════════════════
def test_prompt_has_no_contradictory_add_line():
    *_, prompt = _run(
        [_holding("00901", series="up", tr1y=1.0),       # 汰弱
         _holding("00904", series="weak"),               # 暫停
         _holding("00905", series="spike"),              # 停利
         _holding("00907", series="up", held=False)], _CRASH_VIX)
    assert _prompt_line(prompt, "235 加碼觸發") == "- 235 加碼觸發：無"
    assert "00901" in _prompt_line(prompt, "健檢紅燈需汰弱")


# ════════════════════════════════════════════════════════════════
# 7. property-style：隨機多檔 × 多情境，任一代號的指令集合不含矛盾組合
# ════════════════════════════════════════════════════════════════
_NOT_ADD = {ds.ACTION_CUT, ds.ACTION_TAKE_PROFIT_FORCE, ds.ACTION_TAKE_PROFIT_PARTIAL,
            ds.ACTION_PAUSE_ADD}


@pytest.mark.parametrize("seed", range(40))
def test_random_portfolios_never_get_contradictory_directives(seed):
    rng = np.random.default_rng(seed)
    vix = float(rng.choice([_CALM_VIX, T.VIX_LIGHT1 + 1, _MID_VIX, _CRASH_VIX]))
    n = int(rng.integers(1, 7))
    hs = [_holding(f"009{10 + j}",
                   series=str(rng.choice(list(_SERIES))),
                   held=bool(rng.random() < 0.7),
                   tr1y=float(rng.choice([1.0, 10.0])),
                   sharpe=float(rng.choice([-0.3, 0.8])),
                   premium=float(rng.choice([0.1, 2.0])))
          for j in range(n)]
    rows, digest, switch, msg, prompt = _run(hs, vix)
    by = {r["代號"]: r for r in rows}
    _add = set(_section_codes(msg, _ADD_HDR))
    _out = set(_section_codes(msg, _OUT_HDR))
    _watch = set(_section_codes(msg, _WATCH_HDR))
    assert "加碼" not in "\n".join(_section_lines(msg, _WATCH_HDR))
    if digest["watch_adds"]:
        assert "加碼" not in _prompt_line(prompt, "觀察清單（未持有）235 燈號")
    _p_add = _prompt_line(prompt, "235 加碼觸發")
    for code, r in by.items():
        if code in _add:
            # 進持股加碼段 ⇔ 持有 且 建議動作就是加碼分支
            assert r["held"] and r["_action"] == ds.ACTION_ADD, (code, r["建議動作"])
            assert code not in _out and code not in _watch
        if r["_action"] in _NOT_ADD:
            assert code not in _add and code not in _watch, (code, r["建議動作"])
            assert code not in _p_add
        if not r["held"]:
            assert code not in _add and code not in _out
            assert code not in _p_add
        if r["held"] and r["_action"] == ds.ACTION_ADD:
            assert code in _add
    if _out or _add:
        assert "今日無需動作" not in msg
