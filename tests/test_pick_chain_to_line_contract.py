"""離線契約測試 — 選股排名 → 換股池 → LINE 訊息 的真生產者接縫（DEC-178 Quality Batch 2 ④-B）。

範圍（誠實界線）：這是 **離線契約測試**，輸入全為本檔手建的**合成**資料（非 data_cache、非真實市場資料、
不是任何「正式資料證據」）。它**不是** Production E2E，**不證明** LINE 實際送達、Secrets 有效，
也**不證明**選股結果的投資有效性 —— 只證明「真實生產者的輸出」與「真實消費者的輸入」在接縫上契約一致。

為什麼需要：既有測試兩側都是手寫 fixture（`test_dividend_station_service` 把 get_ranked_picks 換成手寫表、
`test_holdings_digest_message` 的 picks 全手寫、`test_push_holdings_daily` 把 get_switch_in_candidates 換成手寫清單），
從未讓**真** `get_ranked_picks` / `composite_rank_candidates` → **真** `get_switch_in_candidates` /
`_pick_candidates` → **真** `format_holdings_message._picks_lines` 串起來；`_pick_candidates` 在 tests/ 原本 0 命中。

做法：只 monkeypatch `fundamental_screener_service.get_ranked_picks` 成「呼叫真實函式並注入合成
survivors_df / pe_map / name_map / shortage_rows / rs_rows / trend_map、auto_fetch=False」的 wrapper
（避免網路與快照讀取）；其餘全用真實碼。

── 合成情境與手算複核（pe_low / eps_high / rs_leader 三因子有資料；shortage / trend 無任何資料 → 不計入涵蓋分母）──
  effective_n = 3 → 涵蓋門檻 min_present = 0.5×3 = 1.5，嚴格 > ：需 ≥2 個因子有值才入榜。
  百分位 = rank(pct)*100 四捨五入 0.1（higher_better；pe_low 反向，值越小分越高）：
    代碼  pe  eps  rs     pe分  eps分  rs分   綜合分(有值因子平均)
    1101  10   5   2.0    100    50    60    (100+50+60)/3 = 70.0
    2330  20  20   3.0     50   100    80    (50+100+80)/3 = 76.7   ← 持股，須被排除於換股池
    2317  15  10   1.0     75    75    40    (75+75+40)/3  = 63.3
    2412  30   2   0.5     25    25    20    (25+25+20)/3  = 23.3
    9999  —    —   5.0     —     —    100   只有 1 個因子有值（1 > 1.5 不成立）→ 被涵蓋門檻擋下（單因子衝頂）
    8888  —    —   —       —     —     —    全因子缺料 → 綜合分 None → drop_unscored 剔除
  排名（高→低）：2330(76.7) > 1101(70.0) > 2317(63.3) > 2412(23.3)。
  換股池（exclude=2330.TW）：1101, 2317, 2412，LINE 以 `:.0f` 顯示 70 / 63 / 23。

突變反向驗證（tests/_fina_mutants.py::load_mutant；原碼為綠的對照在同一測試內）：
  `drop_unscored=True,`→False／涵蓋門檻比較放寬／`if not _code or _code in _exclude:`→只留 `if not _code:`。
"""
from __future__ import annotations

import pandas as pd
import pytest

import src.services.dividend_station_service as DS
import src.services.fundamental_screener_service as FS
from src.compute.notify.holdings_digest_message import format_holdings_message
from tests._fina_mutants import load_mutant

_FS_REL = "src/services/fundamental_screener_service.py"
_DS_REL = "src/services/dividend_station_service.py"

# ───────────────────────── 合成輸入（非真實資料）─────────────────────────
_SURVIVORS = pd.DataFrame({
    "stock_id": ["1101", "2330", "2317", "2412", "9999", "8888"],
    "eps": [5.0, 20.0, 10.0, 2.0, None, None],
})
_PE_MAP = {"1101": 10.0, "2330": 20.0, "2317": 15.0, "2412": 30.0}
_NAME_MAP = {"1101": "合成甲", "2330": "合成乙", "2317": "合成丙", "2412": "合成丁",
             "9999": "合成單因子", "8888": "合成全缺"}
_RS_ROWS = [{"代碼": "1101", "RS(σ)": 2.0}, {"代碼": "2330", "RS(σ)": 3.0},
            {"代碼": "2317", "RS(σ)": 1.0}, {"代碼": "2412", "RS(σ)": 0.5},
            {"代碼": "9999", "RS(σ)": 5.0}]
_SHORTAGE_ROWS: list = []     # 無任何缺貨資料 → 該因子不計入涵蓋分母
_TREND_MAP: dict = {}         # 無任何跨季資料 → 同上

#: 手算 golden（見模組 docstring）。
_GOLDEN_RANKED = [("2330", 76.7), ("1101", 70.0), ("2317", 63.3), ("2412", 23.3)]
_GOLDEN_POOL = [("1101", 70.0), ("2317", 63.3), ("2412", 23.3)]     # 排除 2330 之後
_AS_OF = "2026-01-02 08:00"                                           # 合成固定值，不取時鐘


def _run_chain(fs_mod=FS, ds_mod=DS, *, exclude=("2330.TW",), top_n=5):
    """真生產者 → 真消費者。回 dict(df, note, cands, msg)。

    fs_mod / ds_mod 可替換為 load_mutant 載入的突變模組（同一 harness）。
    """
    seen: dict = {}
    _real_ranked = fs_mod.get_ranked_picks      # 在 patch 之前抓住（fs_mod 預設就是被 patch 的 FS 本身，否則遞迴）

    def _wrapper(factors, **kw):
        kw.update(survivors_df=_SURVIVORS.copy(), pe_map=_PE_MAP, name_map=_NAME_MAP,
                  shortage_rows=_SHORTAGE_ROWS, rs_rows=_RS_ROWS, trend_map=_TREND_MAP,
                  auto_fetch=False)
        df, note = _real_ranked(factors, **kw)                  # 真實（或突變）函式
        seen["df"], seen["note"] = df, note
        return df, note

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(FS, "get_ranked_picks", _wrapper)             # 供 ds.get_switch_in_candidates 內 late import
        cands = ds_mod.get_switch_in_candidates(exclude=list(exclude), top_n=top_n)
    msg = format_holdings_message({"total": 3}, None, as_of=_AS_OF, picks=cands)
    return {"df": seen["df"], "note": seen["note"], "cands": cands, "msg": msg}


def _codes(df) -> list[str]:
    return [str(c) for c in df["代碼"].tolist()]


# ───────────────────────── 契約斷言（真實/突變共用）─────────────────────────
def _check_single_factor_blocked(r):
    assert "9999" not in _codes(r["df"]), "單一因子衝頂股（只有 RS=100）須被涵蓋門檻擋下"
    assert "9999" not in [c["代碼"] for c in r["cands"]]


def _check_unscored_dropped(r):
    assert "8888" not in _codes(r["df"]), "全因子缺料股（綜合分 None）須被 drop_unscored 剔除"
    assert [c["代碼"] for c in r["cands"]] == [c for c, _ in _GOLDEN_POOL], \
        "換股池不得混入未評分股（否則 LINE 會把『從未被評分』的檔當入選推出去）"


def _check_held_excluded(r):
    assert "2330" not in [c["代碼"] for c in r["cands"]], "已持有股（含 .TW 後綴寫法）不得出現在換股池"
    assert "2330" not in r["msg"].split("今日選股", 1)[-1]


# ───────────────────────── 真實碼契約 ─────────────────────────
def test_producer_ranking_matches_hand_computed_golden():
    r = _run_chain(exclude=())
    got = list(zip(_codes(r["df"]), [round(float(s), 1) for s in r["df"]["綜合分"]]))
    assert got == _GOLDEN_RANKED
    # 各因子分（手算）：pe 反向、eps/rs 正向；缺料為 NaN 而非 0
    _row = r["df"].set_index("代碼").loc["1101"]
    assert (_row["估值分"], _row["EPS分"], _row["RS分"]) == (100.0, 50.0, 60.0)
    assert pd.isna(_row["缺貨分"]) and pd.isna(_row["跨季分"]), "缺料因子須為空白（None/NaN），不得被填成 0"


def test_single_factor_topper_blocked_by_coverage_gate():
    _check_single_factor_blocked(_run_chain())


def test_all_missing_stock_dropped_not_pushed():
    _check_unscored_dropped(_run_chain())


def test_held_stock_with_tw_suffix_excluded_from_switch_pool():
    r = _run_chain(exclude=("2330.TW",))
    _check_held_excluded(r)
    # 對照：不排除時 2330 是第一名 → 證明「消失」是 exclude 的功勞，不是排名本來就沒有它
    r0 = _run_chain(exclude=())
    assert r0["cands"][0]["代碼"] == "2330"


def test_pool_matches_golden_and_top_n_truncates():
    r = _run_chain()
    got = [(c["代碼"], round(float(c["綜合分"]), 1)) for c in r["cands"]]
    assert got == _GOLDEN_POOL
    assert [c["代碼"] for c in _run_chain(top_n=2)["cands"]] == ["1101", "2317"]


def test_column_contract_between_producer_and_line_consumer():
    """producer 欄名（代碼/名稱/綜合分）= `_pick_candidates` 輸出鍵 = `_picks_lines` 消費鍵。"""
    r = _run_chain()
    assert list(r["df"].columns[:3]) == ["代碼", "名稱", "綜合分"]
    assert all(set(c) == {"代碼", "名稱", "綜合分"} for c in r["cands"])
    assert [c["名稱"] for c in r["cands"]] == ["合成甲", "合成丙", "合成丁"]


def test_line_message_section_order_and_scores_match_hand_calc():
    r = _run_chain()
    _lines = r["msg"].splitlines()
    assert any(ln.startswith("📈 今日選股 Top3") for ln in _lines), "訊息應含『📈 今日選股 Top3』區塊"
    _i = next(i for i, ln in enumerate(_lines) if ln.startswith("📈 今日選股 Top"))
    assert _lines[_i + 1].strip() == "1. 1101 合成甲（綜合分 70）"
    assert _lines[_i + 2].strip() == "2. 2317 合成丙（綜合分 63）"
    assert _lines[_i + 3].strip() == "3. 2412 合成丁（綜合分 23）"
    assert "None" not in r["msg"] and "nan" not in r["msg"].lower()
    assert "9999" not in r["msg"] and "8888" not in r["msg"]


# ───────────────────────── 突變反向驗證（拔掉保護必須轉紅）─────────────────────────
#: name → (來源檔, old, new, 對應契約 check)；old 在原檔必須恰出現 1 次（load_mutant 內 assert）。
MUTANTS = {
    "drop_unscored_off": (_FS_REL, "drop_unscored=True,", "drop_unscored=False,", _check_unscored_dropped),
    "coverage_gate_relaxed": (_FS_REL, "len(_present) > _min_present", "len(_present) > 0",
                              _check_single_factor_blocked),
    "exclude_check_dropped": (_DS_REL, "if not _code or _code in _exclude:", "if not _code:",
                              _check_held_excluded),
}


@pytest.mark.parametrize("name", list(MUTANTS))
def test_mutant_is_killed(name):
    rel, old, new, chk = MUTANTS[name]
    chk(_run_chain())                                   # 原碼為綠（同 harness）
    mut = load_mutant(rel, old, new, name=f"_pick_{name}")
    if rel == _FS_REL:
        r = _run_chain(fs_mod=mut)
    else:
        r = _run_chain(ds_mod=mut)
    with pytest.raises(AssertionError):                 # 拔掉保護 → 契約轉紅
        chk(r)
