"""批 Z60（2026-10-14）—— RA-1：新 UI 平行路徑自己組 `warroom_summary`（舊檔零改動、計算零複製）。

背景
────────────────────────────────────────────────────────────────
新 UI 讀總經位階／建議持股全部經 `warroom_summary`，但它全 repo 只有舊 UI 兩處寫入：
  · TL ＝ `section_traffic_light.render_traffic_light_top`（整包賦值 13 欄，含 throttle）
  · SS ＝ `section_state.render_section_state`（就地 update 12 欄，保留 TL 的 throttle）
舊頁 rerun 順序 TL 先、SS 後。頁1「🚀 更新今日戰情」修前一欄都不寫。

本批（總管拍板方案 a）：
  · L2 `src/compute/macro/warroom_summary.py::build_warroom_summary` —— 純組裝。
  · L3 `src/services/warroom_apply.py::compute_and_store_warroom_summary` —— 取輸入 → 判燈 → 組裝 → 寫入／pop。
  · L3 `macro_refresh_service`：新 `STEP_WARROOM`（市場評估之後、資料登錄中心之前）。

本檔守什麼（每一條對應一個宣稱，不是覆蓋率）
────────────────────────────────────────────────────────────────
  1. `TestEndToEndGolden` —— 同一份假 session，**真的依序跑**舊 TL 與 SS 得到舊 warroom；
     新 L3 在同一初始 session 的複本上產出；`_canon` 全等（含 NaN 序列化）。
  2. `TestNoConclusion` —— 整理不出結論時新路徑最後**沒有** warroom（含已有舊 warroom）。
  3. `TestGridAgainstTheOldSource` —— 用字面錨把舊檔兩段寫入區塊切出來依序 exec，
     與 `build_warroom_summary` 做格點比對（itertools.product ＋ 固定 seed）。
  4. `TestDownstreamAgrees` —— `get_macro_state` / `get_allocation` / 五桶 health readiness
     吃新舊兩份 warroom 的輸出全等。
  5. `TestMutations` —— 四個突變（regime 預設改 'neutral'、拿掉 throttle 的 health 守衛、
     對調 fnet/fut_net、不 pop），每一個都必須讓 golden 轉紅。
  6. `TestRefreshIntegration` —— 接進 `refresh_macro_now` 之後：寫入被量到、對帳通過、
     順序對、pop 有記、市場評估失敗時有揭露。
  7. `TestOldFilesUntouched` —— 舊 UI 檔對基底 `e64ea2f5` 零 diff。
  8. `TestVerdictIdleExitIsRetry` —— 卡①③ 未評估（非錯誤）時出口是「按本頁按鈕可重抓」，
     ⛔ 不再是「不在本頁射程內」（Z60 QA 阻擋項）；錯誤分支出口不變。
  9. `TestDegradedRegimeExitIsRetry` / `TestNoContractNoExitOnThePage` —— 沿用對面
     `tab_today` 總經契約 Note 的卡（卡③ degraded、狀態列「總經」、三欄摘要「位階」），
     `where` 不得再是 `CONTRACT_NO_EXIT_WHERE`（Z60 複驗）。

harness 沿用 `tests/test_batch_z8.py`（`_FakeST`、情境 N1–N5／F1–F4、門檻釘死、不觸網、cwd 換到
tmp）與 `tests/test_p01_macro_refresh.py`（`_mutated_module`、`_FakeST` 型 session 替身）。

⚠️ 一處**刻意與舊頁 rerun 不同**（寫在 `warroom_apply` 檔頭，這裡以 `TestNoConclusion` 釘住）：
session 的 `mkt_info`／`jingqi_info`／`cl_data` 三個都是假值、但留著上一份 warroom 時，
舊頁 rerun 會拿上一份的 `jingqi_avg` 合成一份新的 warroom（＝上一輪結論冒充今天的）；
新路徑判為「整理不出結論」並刪掉舊的 —— 與舊頁「按一鍵更新」（先 pop 再算）相同。
"""
from __future__ import annotations
# ⚠️ DEC-074/075 行為變更（回修 QA1 S-6，2026-10-23）：`shared.macro_provenance.is_breadth_proxy` 改 fail-safe
#   （缺 `is_proxy` 旗標＝代理、不計分；ADL DataFrame 缺欄同）。本檔代表**真值**的旌旗／ADL fixture 因此
#   一律明示 `is_proxy: False`（production 寫入點恆帶旗標）；斷言與 golden 未因此放寬。

import copy
import itertools
import math
import random
import textwrap

import pytest

import src.compute.macro.macro_helpers as MH
import src.compute.macro.warroom_summary as WS
import src.services.allocation_service as AS
import src.services.warroom_apply as WA
import src.ui.tabs.macro.handlers as H
import src.ui.tabs.macro.section_state as SS
import src.ui.tabs.macro.section_traffic_light as STL
import src.ui.tabs.macro_classroom as MC
from shared.inst_net import InstNetDict
from shared.position_throttle import compute_position_throttle
from src.services import macro_refresh_service as RS
from tests.test_batch_z8 import (
    _ADL,
    _FIXED_DT_MOD,
    _INST,
    _PIN_BULL_MIN,
    _PIN_HEALTH_DEFENSE,
    _canon,
    _cl_data,
    _deny_network,
    _li,
    _patch_st,
    _scenario,
)
from tests.test_m2n2_no_zero_fill import _FakeST
from tests.test_p01_macro_refresh import _mutated_module

_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
_BASE_COMMIT = "e64ea2f5"
_ABSENT = "<無 warroom_summary>"


@pytest.fixture
def _pinned(monkeypatch, tmp_path):
    """同 `tests/test_batch_z8.py::_pinned`：門檻釘死、不觸網、cwd 換到空目錄（不讀 repo 的 macro_state.json）。"""
    monkeypatch.setattr(MH, "HEALTH_DEFENSE_THRESHOLD", _PIN_HEALTH_DEFENSE)
    monkeypatch.setattr(MH, "BULL_MIN_SCORE", _PIN_BULL_MIN)
    monkeypatch.setattr(MC, "HEALTH_DEFENSE_THRESHOLD", _PIN_HEALTH_DEFENSE)
    monkeypatch.setattr(MC, "BULL_MIN_SCORE", _PIN_BULL_MIN)
    _deny_network(monkeypatch, tmp_path)
    return monkeypatch


# ══════════════════════════════════════════════════════════════════════════
# 情境：z8 的 N1–N5、F1–F4 ＋ 本批追加
# ══════════════════════════════════════════════════════════════════════════
_Z8 = ("N1_bull", "N2_trend_bear", "N3_futures_defense", "N4_score_missing",
       "N5_health_zero", "F1_all_failed", "F2_inst_none_legacy",
       "F3_twii_dead_others_alive", "F4_health_legs_missing_adl_ok")

_STALE_WR = {
    "traffic_light": "上一輪的燈", "health_score": 99.0, "regime": "bull",
    "effective_regime": "bull", "light": "🟢", "regime_source": "上一輪",
    "market_score": 4, "jingqi_avg": 63.0, "leek_index": 1.0,
    "foreign_net_bn": 1.0, "futures_net": 1.0, "confidence_pct": 100,
    # 過期 throttle：TL 是整包賦值，這一份必須被本輪的取代，⛔ 殘留
    "throttle": {"lo_pct": 99, "hi_pct": 99, "mid_pct": 99, "posture": "過期",
                 "icon": "🟢", "regime_capped": False},
    "_上一輪多出來的鍵": "TL 整包賦值會把它丟掉",
}


def _n1(**over) -> dict:
    s = _scenario("N1_bull")
    s.update(over)
    return s


def _extra(name: str) -> dict:
    if name == "X_mkt_no_regime":             # mkt_info 沒有 regime 鍵：TL 寫 'neutral'、SS 蓋回 None
        s = _n1()
        s["mkt_info"] = {k: v for k, v in s["mkt_info"].items() if k != "regime"}
        return s
    if name == "X_feedback_prior_wr":         # jingqi_info 缺、上一份 warroom 有 jingqi_avg（自我回授）
        s = _n1(warroom_summary=copy.deepcopy(_STALE_WR))
        s.pop("jingqi_info")
        return s
    if name == "X_feedback_jq_empty_dict":    # jingqi_info 是空 dict（假值）＋上一份 warroom
        return _n1(jingqi_info={}, warroom_summary=copy.deepcopy(_STALE_WR))
    if name == "X_no_jq_no_prior":            # jingqi_info 缺、也沒有上一份 warroom
        s = _n1()
        s.pop("jingqi_info")
        return s
    if name == "X_futures_frozen":            # 外資大小連續 4 筆一模一樣 ⇒ 凍結 ⇒ fut_net None
        return _n1(li_latest=_li((-40000.0, -40000.0, -40000.0, -40000.0)))
    if name == "X_fnet_unobserved":           # 外資淨額未觀測（L1 預填 0.0）⇒ fnet None
        _inst = InstNetDict({"外資": {"net": 0.0}, "投信": {"net": 3.1}},
                            unobserved_net=("外資",))
        return _n1(cl_data=_cl_data(inst=_inst, adl=_ADL))
    if name == "X_score_nan":                 # 大盤評分 NaN ⇒ 當缺值
        s = _n1()
        s["mkt_info"] = dict(s["mkt_info"], score=float("nan"))
        return s
    if name == "X_inst_none_with_values":     # cl_data['inst'] 是 None（舊 session 形狀），其他都在
        return _n1(cl_data=dict(_cl_data(adl=_ADL), inst=None))
    if name == "X_prior_wr_stale_throttle":   # 上一份 warroom 帶過期 throttle ＋ 多餘鍵
        return _n1(warroom_summary=copy.deepcopy(_STALE_WR))
    if name == "X_jq_nan_leek_nan":           # 旌旗 NaN、韭菜 NaN（_canon 要能序列化）
        return _n1(jingqi_info={"is_proxy": False, "avg": float("nan")},
                   li_latest=_li((5000.0, 6000.0, 7000.0, 8000.0),
                                 leek=(-12.0, -8.0, -5.0, float("nan"))))
    if name == "X_prior_wr_not_dict":         # 上一份 warroom 壞成字串：SS 的 isinstance 守衛那一支
        return _n1(warroom_summary="壞掉的值")
    raise KeyError(name)


_EXTRA = ("X_mkt_no_regime", "X_feedback_prior_wr", "X_feedback_jq_empty_dict",
          "X_no_jq_no_prior", "X_futures_frozen", "X_fnet_unobserved", "X_score_nan",
          "X_inst_none_with_values", "X_prior_wr_stale_throttle", "X_jq_nan_leek_nan",
          "X_prior_wr_not_dict")
_GOLDEN = _Z8 + _EXTRA


def _state(name: str) -> dict:
    return _scenario(name) if name in _Z8 else _extra(name)


# ══════════════════════════════════════════════════════════════════════════
# 兩條路徑的 runner
# ══════════════════════════════════════════════════════════════════════════
def _old_rerun(monkeypatch, state: dict):
    """舊頁一次 rerun：真的依序跑 TL（`render_traffic_light_top`）→ SS（`render_section_state`）。

    `show_market_data` 照 production：取 TL 的第二個回傳值（tab_macro 就是這樣傳）。
    第一個參數 `_mkt_info` 傳 None ⇒ 拐點面板不跑（同 z8 `_run_state` 的理由：那段打 NDC／FinMind，
    與 warroom 無關，fast lane 不觸網）。
    """
    fake = _FakeST(copy.deepcopy(state))
    _patch_st(monkeypatch, fake, STL, H, AS, SS, MC)
    monkeypatch.setattr(STL, "_dt", _FIXED_DT_MOD)
    ph, show, _eff = STL.render_traffic_light_top()
    SS.render_section_state(None, ph, ph, fake.session_state.get("cl_data") or {},
                            show_market_data=show)
    return fake.session_state.get("warroom_summary", _ABSENT), fake


def _new(monkeypatch, state: dict, mod=WA):
    """新 L3 在同一個初始 session 的**複本**上跑一次。回 (warroom 或 _ABSENT, 結果或例外, fake)。"""
    fake = _FakeST(copy.deepcopy(state))
    monkeypatch.setattr(mod, "st", fake)
    try:
        res = mod.compute_and_store_warroom_summary()
    except Exception as e:  # noqa: BLE001 — 突變體會拋；拋了就是「與舊頁不同」
        res = e
    return fake.session_state.get("warroom_summary", _ABSENT), res, fake


def _mismatch(monkeypatch, name: str, mod=WA) -> bool:
    old, _ = _old_rerun(monkeypatch, _state(name))
    new, _, _ = _new(monkeypatch, _state(name), mod=mod)
    return _canon(old) != _canon(new)


# ══════════════════════════════════════════════════════════════════════════
# 1. 端到端 golden
# ══════════════════════════════════════════════════════════════════════════
class TestEndToEndGolden:

    @pytest.mark.parametrize("name", _GOLDEN)
    def test_new_equals_old_tl_then_ss(self, _pinned, name):
        old, _ = _old_rerun(_pinned, _state(name))
        new, res, fake = _new(_pinned, _state(name))
        assert not isinstance(res, Exception), res
        assert old != _ABSENT, f"[{name}] 舊頁這個情境沒寫 warroom —— 情境不是本測試要的形狀"
        assert _canon(new) == _canon(old), (
            f"[{name}] 新路徑與舊頁 TL→SS 的最終 warroom 不同\n"
            f"  舊：{_canon(old)}\n  新：{_canon(new)}")
        assert list(new) == list(WS.WARROOM_SUMMARY_KEYS), "鍵序與舊頁不同"
        assert res.written and not res.popped

    @pytest.mark.parametrize("name", _GOLDEN)
    def test_new_writes_a_new_object(self, _pinned, name):
        """`_writes_recorded` 以 id 量測 —— 必須是**新物件**，⛔ 就地 update 上一份。"""
        st0 = _state(name)
        fake = _FakeST(st0)
        prior = fake.session_state.get("warroom_summary")
        _pinned.setattr(WA, "st", fake)
        WA.compute_and_store_warroom_summary()
        assert fake.session_state["warroom_summary"] is not prior

    def test_assumptions_the_scenarios_really_hit_their_shapes(self, _pinned):
        """假設檢查：追加情境真的造出它聲稱的形狀（否則 golden 測的是別的東西）。"""
        def _wr(name):
            return _new(_pinned, _state(name))[0]
        assert _wr("X_mkt_no_regime")["regime"] is None
        assert _wr("X_feedback_prior_wr")["jingqi_avg"] == 63.0          # 自我回授真的發生
        assert _wr("X_feedback_jq_empty_dict")["jingqi_avg"] == 63.0
        assert _wr("X_no_jq_no_prior")["jingqi_avg"] is None
        assert _wr("X_futures_frozen")["futures_net"] is None
        assert _wr("X_fnet_unobserved")["foreign_net_bn"] is None
        assert _wr("X_score_nan")["market_score"] is None
        assert _wr("X_inst_none_with_values")["foreign_net_bn"] is None
        _t = _wr("X_prior_wr_stale_throttle")
        assert _t["throttle"]["posture"] != "過期" and "_上一輪多出來的鍵" not in _t
        assert _wr("X_jq_nan_leek_nan")["leek_index"] is None
        for n in ("F1_all_failed", "F4_health_legs_missing_adl_ok"):
            assert _wr(n)["health_score"] is None and _wr(n)["throttle"] is None
        assert _wr("N5_health_zero")["health_score"] == 0.0
        assert _wr("N5_health_zero")["throttle"] is not None             # 0 是合法值
        # TL 寫的 'neutral' 真的被 SS 蓋回 None（否則 regime 預設那條突變殺不掉）
        fake = _FakeST(_state("X_mkt_no_regime"))
        _patch_st(_pinned, fake, STL, H, AS)
        _pinned.setattr(STL, "_dt", _FIXED_DT_MOD)
        STL.render_traffic_light_top()
        assert fake.session_state["warroom_summary"]["regime"] == "neutral"

    def test_health_missing_is_reported(self, _pinned):
        _, res, _ = _new(_pinned, _state("F1_all_failed"))
        assert res.written and res.health_missing
        _, res, _ = _new(_pinned, _state("N1_bull"))
        assert res.written and not res.health_missing

    def test_session_macro_state_is_not_written(self, _pinned):
        """刻意不寫 session `macro_state`（只有舊頁讀）。"""
        _, _, fake = _new(_pinned, _state("N1_bull"))
        assert "macro_state" not in fake.session_state


# ══════════════════════════════════════════════════════════════════════════
# 2. 整理不出結論
# ══════════════════════════════════════════════════════════════════════════
def _three_empty(prior: bool) -> dict:
    s = {"cl_ts": "2026-10-06 09:00", "_is_refreshing": False, "chips_loaded": True}
    if prior:
        s["warroom_summary"] = copy.deepcopy(_STALE_WR)
    return s


class TestNoConclusion:

    def test_three_empty_with_prior_warroom_ends_with_none(self, _pinned):
        new, res, _ = _new(_pinned, _three_empty(prior=True))
        assert new == _ABSENT, "整理不出結論卻留著上一份 —— 上一輪的結論冒充今天的"
        assert not res.written and res.popped and res.reason == WA.REASON_NO_INPUT

    def test_three_empty_without_prior(self, _pinned):
        new, res, _ = _new(_pinned, _three_empty(prior=False))
        assert new == _ABSENT and not res.written and not res.popped
        old, _ = _old_rerun(_pinned, _three_empty(prior=False))
        assert old == _ABSENT

    def test_matches_the_old_update_click_not_the_old_rerun(self, _pinned):
        """據實釘住那一處刻意差異（不是假裝全等）。

        舊頁「按一鍵更新」＝ `_macro_session_reset()` 先 pop（含 warroom_summary）→ 本輪三來源全空
        → TL / SS 都不寫 ⇒ 沒有 warroom —— 新路徑與它相同。
        舊頁**單純 rerun**（沒按更新）則會拿上一份的 `jingqi_avg` 合成一份 —— 新路徑**不**這樣做。
        """
        fake = _FakeST(_three_empty(prior=True))
        _patch_st(_pinned, fake, STL, H, AS, SS, MC)
        _pinned.setattr(STL, "_dt", _FIXED_DT_MOD)
        H._macro_session_reset()                          # 舊頁 on_click
        fake.session_state.update(cl_ts="2026-10-06 09:00", _is_refreshing=False)  # 抓取段寫回（全空）
        ph, show, _ = STL.render_traffic_light_top()
        SS.render_section_state(None, ph, ph, {}, show_market_data=show)
        assert "warroom_summary" not in fake.session_state
        old_rerun, _ = _old_rerun(_pinned, _three_empty(prior=True))
        assert old_rerun != _ABSENT and old_rerun["jingqi_avg"] == 63.0, (
            "前提變了：舊頁 rerun 不再自我回授 —— 本差異的說明要改寫")

    def test_an_exception_pops_and_is_not_swallowed(self, _pinned):
        def _boom(*a, **k):
            raise RuntimeError("判燈炸了")
        _pinned.setattr(WA, "calc_traffic_light", _boom)
        new, res, _ = _new(_pinned, _state("X_prior_wr_stale_throttle"))
        assert isinstance(res, RuntimeError), "例外被吞掉了（§1）"
        assert new == _ABSENT, "例外之後還留著上一輪的 warroom"

    def test_calc_returning_none_pops(self, _pinned):
        """防禦分支：`calc_traffic_light` 真的回 None 時也要 pop（不只靠原始三 key 的判準）。"""
        _pinned.setattr(WA, "calc_traffic_light", lambda *a, **k: None)
        new, res, _ = _new(_pinned, _state("X_prior_wr_stale_throttle"))
        assert new == _ABSENT and res.popped and not res.written


# ══════════════════════════════════════════════════════════════════════════
# 3. 格點比對：舊檔兩段寫入區塊（字面錨切出，原文未改一字）依序 exec
# ══════════════════════════════════════════════════════════════════════════
_TL_START = "_tl_eff_reg = (_tl_init or {}).get('effective_regime') or None"
_TL_END = "'throttle':      _wr_throttle,"
_SS_START = "    if _tl_final:"
_SS_END = "st.session_state['warroom_summary'] = _wr_sum"


def _slice(rel: str, start: str, end: str, *, end_extra: int = 0) -> str:
    lines = (_ROOT / rel).read_text(encoding="utf-8").splitlines()
    b = [i for i, ln in enumerate(lines) if start in ln]
    e = [i for i, ln in enumerate(lines) if end in ln]
    assert len(b) == 1 and len(e) == 1, (rel, start, end, b, e)
    return textwrap.dedent("\n".join(lines[b[0]:e[0] + 1 + end_extra]))


def _tl_block():
    src = _slice("src/ui/tabs/macro/section_traffic_light.py", _TL_START, _TL_END, end_extra=1)
    assert src.rstrip().endswith("}"), "TL 寫入段結尾形狀變了 —— 重新確認切的範圍，⛔ 只改錨點"
    return compile(src, "<TL-block>", "exec"), src


def _ss_block():
    src = _slice("src/ui/tabs/macro/section_state.py", _SS_START, _SS_END)
    return compile(src, "<SS-block>", "exec"), src


class _Sess:
    def __init__(self, d):
        self.session_state = d


def _old_blocks(tl, mkt, prior):
    """舊兩段依序 exec（TL 的 `_tm_mkt_init` 與 SS 的 `_tl2_mkt` 都是 `mkt_info or {}`）。"""
    sess = {} if prior is _ABSENT else {"warroom_summary": copy.deepcopy(prior)}
    st = _Sess(sess)
    exec(_TL_CODE, {"_tl_init": tl, "_tm_mkt_init": mkt or {}, "st": st,
                    "compute_position_throttle": compute_position_throttle})
    exec(_SS_CODE, {"_tl_final": tl, "_tl2_mkt": mkt or {}, "st": st})
    return sess.get("warroom_summary", _ABSENT)


_TL_CODE, _TL_SRC = _tl_block()
_SS_CODE, _SS_SRC = _ss_block()

_H = (None, 0.0, 20.0, 34.9, 35.0, 50.0, 62.5, 80.0, 100.0)
_EFF = ("bull", "neutral", "bear", "caution", "unknown", None, "")
_DEF = (True, False, None, "<缺鍵>")
_MKT = ("bull", "bear", "neutral", None, "<缺鍵>", "<mkt_info=None>")
_PRIOR = (_ABSENT, {}, "壞掉的值", "stale")


def _grid():
    rng = random.Random(20261014)
    pool = (None, 0.0, -1.5, 12.0, float("nan"), -40000.0, 15.2, 100)
    for h, eff, de, mk, pr in itertools.product(_H, _EFF, _DEF, _MKT, _PRIOR):
        tl = {"label": rng.choice(("多頭", "空頭防禦", "震盪", None)),
              "health": h, "effective_regime": eff,
              "light": rng.choice(("🟢", "🟡", "🔴", "⬜", None)),
              "regime_source": rng.choice(("bull", "unloaded", "defense", None)),
              "score": rng.choice(pool), "jqavg": rng.choice(pool),
              "leek": rng.choice(pool), "fnet": rng.choice(pool),
              "fut_net": rng.choice(pool), "conf": rng.choice((0, 40, 60, 100)),
              "color": "#000", "icon": "x", "regime": rng.choice(("bull", "neutral"))}
        if de != "<缺鍵>":
            tl["defense"] = de
        if mk == "<mkt_info=None>":
            mkt = None
        elif mk == "<缺鍵>":
            mkt = {"score": 1}
        else:
            mkt = {"regime": mk, "score": 1}
        prior = copy.deepcopy(_STALE_WR) if pr == "stale" else pr
        yield tl, mkt, prior


class TestGridAgainstTheOldSource:

    def test_the_blocks_really_came_from_the_old_files(self):
        """假設檢查：切到的是那兩段寫入（不是空字串照樣「相等」）。"""
        assert "compute_position_throttle(" in _TL_SRC
        assert "st.session_state['warroom_summary'] = {" in _TL_SRC
        assert "'regime': _tm_mkt_init.get('regime', 'neutral')" in _TL_SRC
        assert "_wr_sum.update({" in _SS_SRC and "'regime': _tl2_mkt.get('regime')" in _SS_SRC

    def test_every_grid_point_matches(self):
        n = 0
        for tl, mkt, prior in _grid():
            old = _old_blocks(tl, mkt, prior)
            new = WS.build_warroom_summary(tl, mkt)
            assert old != _ABSENT
            assert _canon(new) == _canon(old), (tl, mkt, prior)
            n += 1
        assert n == len(_H) * len(_EFF) * len(_DEF) * len(_MKT) * len(_PRIOR) == 6048

    @pytest.mark.parametrize("tl", [None, {}])
    @pytest.mark.parametrize("prior", [_ABSENT, "stale"])
    def test_falsy_tl_old_blocks_do_not_write_and_build_returns_none(self, tl, prior):
        _p = copy.deepcopy(_STALE_WR) if prior == "stale" else prior
        assert _canon(_old_blocks(tl, {"regime": "bull"}, _p)) == _canon(_p)
        assert WS.build_warroom_summary(tl, {"regime": "bull"}) is None

    def test_keys_are_exactly_what_the_old_blocks_leave(self):
        tl, mkt, _ = next(_grid())
        assert tuple(_old_blocks(tl, mkt, _ABSENT)) == WS.WARROOM_SUMMARY_KEYS
        assert len(WS.WARROOM_SUMMARY_KEYS) == 13

    def test_missing_contract_key_raises_like_the_old_writer(self):
        """契約缺欄：舊 TL 以 `[...]` 取值會 KeyError —— 新組裝同樣拋，⛔ 悄悄填 None。"""
        tl, mkt, _ = next(_grid())
        tl = {k: v for k, v in tl.items() if k != "light"}
        with pytest.raises(KeyError):
            _old_blocks(tl, mkt, _ABSENT)
        with pytest.raises(KeyError):
            WS.build_warroom_summary(tl, mkt)


# ══════════════════════════════════════════════════════════════════════════
# 4. 下游一致
# ══════════════════════════════════════════════════════════════════════════
class TestDownstreamAgrees:

    @pytest.mark.parametrize("name", _GOLDEN)
    def test_get_macro_state(self, _pinned, name):
        from src.services.macro_state_locker import get_macro_state
        old, _ = _old_rerun(_pinned, _state(name))
        new, _, _ = _new(_pinned, _state(name))
        assert _canon(get_macro_state(new)) == _canon(get_macro_state(old))

    @pytest.mark.parametrize("name", _GOLDEN)
    def test_get_allocation(self, _pinned, name):
        old, _ = _old_rerun(_pinned, _state(name))
        new, _, _ = _new(_pinned, _state(name))
        outs = []
        for wr in (old, new):
            s = _state(name)
            s["warroom_summary"] = copy.deepcopy(wr)
            fake = _FakeST(s)
            _pinned.setattr(AS, "st", fake)
            outs.append(repr(AS.get_allocation()))
        assert outs[0] == outs[1]

    @pytest.mark.parametrize("name", _GOLDEN)
    def test_five_bucket_health_readiness(self, _pinned, name):
        old, _ = _old_rerun(_pinned, _state(name))
        new, _, _ = _new(_pinned, _state(name))
        res = []
        for wr in (old, new):
            rd: dict = {}
            summ = MH.compute_five_bucket_summary(warroom_summary=copy.deepcopy(wr),
                                                  readiness_out=rd)
            res.append(_canon({"readiness": rd, "summary": summ}))
        assert res[0] == res[1]


# ══════════════════════════════════════════════════════════════════════════
# 5. 突變：每一個都必須讓 golden 轉紅
# ══════════════════════════════════════════════════════════════════════════
_L2 = "src/compute/macro/warroom_summary.py"
_L3 = "src/services/warroom_apply.py"
_MUTANTS_L2 = {
    "regime 預設改 'neutral'": ('"regime": _mkt.get("regime"),',
                              '"regime": _mkt.get("regime", "neutral"),'),
    "拿掉 throttle 的 health 守衛": ('    if tl["health"] is not None:\n        _throttle',
                                 '    if True:\n        _throttle'),
    "對調 fnet / fut_net": ('"foreign_net_bn": tl["fnet"],\n        "futures_net": tl["fut_net"],',
                          '"foreign_net_bn": tl["fut_net"],\n        "futures_net": tl["fnet"],'),
}


def _golden_red(monkeypatch, mod_l3=WA) -> list[str]:
    """跑全部 golden（端到端 ＋ 整理不出結論那一條），回傳紅掉的情境名。"""
    red = [n for n in _GOLDEN if _mismatch(monkeypatch, n, mod=mod_l3)]
    new, _, _ = _new(monkeypatch, _three_empty(prior=True), mod=mod_l3)
    if new != _ABSENT:
        red.append("三來源全空＋已有舊 warroom")
    return red


class TestMutations:

    def test_the_real_code_is_all_green(self, _pinned):
        assert _golden_red(_pinned) == []

    @pytest.mark.parametrize("why", sorted(_MUTANTS_L2))
    def test_l2_mutants_turn_the_golden_red(self, _pinned, why):
        mutant = _mutated_module(_L2, _MUTANTS_L2[why])
        _pinned.setattr(WA, "build_warroom_summary", mutant.build_warroom_summary)
        red = _golden_red(_pinned)
        assert red, f"突變體（{why}）golden 全綠 —— golden 守不到這一行"

    def test_regime_default_is_killed_by_the_no_regime_scenario(self, _pinned):
        mutant = _mutated_module(_L2, _MUTANTS_L2["regime 預設改 'neutral'"])
        _pinned.setattr(WA, "build_warroom_summary", mutant.build_warroom_summary)
        assert _mismatch(_pinned, "X_mkt_no_regime")

    def test_throttle_guard_is_killed_by_the_failed_scenarios(self, _pinned):
        mutant = _mutated_module(_L2, _MUTANTS_L2["拿掉 throttle 的 health 守衛"])
        _pinned.setattr(WA, "build_warroom_summary", mutant.build_warroom_summary)
        assert all(_mismatch(_pinned, n) for n in ("F1_all_failed", "F3_twii_dead_others_alive"))

    def test_no_pop_mutant_turns_the_golden_red(self, _pinned):
        mutant = _mutated_module(
            _L3,
            ('''        _had = "warroom_summary" in st.session_state
        st.session_state.pop("warroom_summary", None)
        print(f"[warroom_apply] ⚠️ {REASON_NO_INPUT}"''',
             '''        _had = "warroom_summary" in st.session_state
        print(f"[warroom_apply] ⚠️ {REASON_NO_INPUT}"'''))
        red = _golden_red(_pinned, mod_l3=mutant)
        assert red == ["三來源全空＋已有舊 warroom"], red


# ══════════════════════════════════════════════════════════════════════════
# 6. 接進 refresh_macro_now
# ══════════════════════════════════════════════════════════════════════════
def _run_refresh(monkeypatch, *, initial=None, market_ok=True, write_inputs=True, apply_ok=True):
    """`refresh_macro_now` 一輪：外部相依全換替身，**`warroom_apply` 用真的**，同一個假 session。"""
    import src.services.data_registry_scanner as _REG
    import src.services.jingqi_calc as _JQ
    import src.services.macro_fetch_orchestrator as _ORCH
    import src.services.macro_session_apply as _APPLY
    import src.services.macro_trio_orchestrator as _TRIO
    import src.services.market_assessment_apply as _MKT
    from tests.test_p01_macro_refresh import _content_bundle

    fake = _FakeST(copy.deepcopy(initial or {}))
    monkeypatch.setattr(RS, "st", fake)
    monkeypatch.setattr(WA, "st", fake)
    seen: dict = {}

    def _bundle(**kw):
        for n in RS.SOURCE_LABELS:
            kw["on_job_done"](n, True, "1.0s")
        return _content_bundle()

    def _apply(*a, **k):
        if not apply_ok:
            raise RuntimeError("寫 session 炸了")
        if write_inputs:
            fake.session_state["cl_data"] = _cl_data(inst=_INST, adl=_ADL)
            fake.session_state["li_latest"] = _li((5000.0, 6000.0, 7000.0, 8000.0))
        return {}, ()

    def _market(**k):
        if not market_ok:
            raise TimeoutError("市場評估逾時")
        fake.session_state["mkt_info"] = {"score": 4, "max_score": 4, "regime": "bull"}

    def _registry(**k):
        from src.services import load_section_inputs
        seen["wr_at_registry"] = load_section_inputs(fake.session_state).warroom_summary
        fake.session_state["data_registry"] = {}

    monkeypatch.setattr(_ORCH, "fetch_macro_bundle", _bundle)
    monkeypatch.setattr(_APPLY, "apply_macro_bundle", _apply)
    monkeypatch.setattr(_JQ, "compute_and_store_jingqi",
                        lambda df: fake.session_state.__setitem__("jingqi_info", {"is_proxy": False, "avg": 70.0})
                        if write_inputs else None)
    monkeypatch.setattr(_TRIO, "run_macro_trio_and_persist", lambda **k: None)
    monkeypatch.setattr(_MKT, "compute_and_apply_market_assessment", _market)
    monkeypatch.setattr(_REG, "scan_and_write_data_registry", _registry)
    # 批 Z65：新步驟 `STEP_RISK_CAP` 的替身（真模組會取 L1 休市表／parquet、寫 macro_state.json）。
    #   本檔守的是 warroom；risk cap 的真模組＋refresh 整合由 `tests/test_batch_z65.py` 實跑驗證。
    import src.services.risk_cap_apply as _RC
    monkeypatch.setattr(_RC, "compute_and_lock_risk_cap", lambda session, *, now: _RC.RiskCapApplyResult(
        True, "", {"not_evaluated": [], "red_lines": {}}, {"exposure_limit_pct": 60}))
    return RS.refresh_macro_now(mode=RS.MODE_WARM), fake, seen


def _step(r, name):
    (s,) = [s for s in r.steps if s.name == name]
    return s


class TestRefreshIntegration:

    def test_declared_and_measured(self, _pinned):
        assert RS.STEP_WRITES[RS.STEP_WARROOM] == ("warroom_summary",)
        assert "warroom_summary" in RS.WRITES_SESSION_KEYS
        r, fake, _ = _run_refresh(_pinned)
        assert "warroom_summary" in r.written_keys
        assert _step(r, RS.STEP_WRITE_AUDIT).ok
        assert _step(r, RS.STEP_WARROOM).ok and not _step(r, RS.STEP_WARROOM).skipped
        assert r.ok, r.failures
        wr = fake.session_state["warroom_summary"]
        assert wr["regime"] == "bull" and wr["jingqi_avg"] == 70.0 and wr["throttle"] is not None

    def test_the_result_is_what_tl_then_ss_would_leave(self, _pinned):
        """refresh 寫完的 session 拿去跑一次舊頁 TL→SS，warroom 不變（同一份結論）。"""
        _, fake, _ = _run_refresh(_pinned)
        st_after = dict(fake.session_state, cl_ts="2026-10-06 09:00", _is_refreshing=False)
        st_after.pop("warroom_summary")
        old, _ = _old_rerun(_pinned, st_after)
        assert _canon(old) == _canon(fake.session_state["warroom_summary"])

    def test_step_order(self, _pinned):
        r, _, seen = _run_refresh(_pinned)
        names = [s.name for s in r.steps]
        assert names.index(RS.STEP_MARKET) < names.index(RS.STEP_WARROOM) < names.index(RS.STEP_REGISTRY)

    def test_registry_sees_this_rounds_warroom(self, _pinned):
        _, fake, seen = _run_refresh(_pinned, initial={"warroom_summary": copy.deepcopy(_STALE_WR)})
        assert seen["wr_at_registry"] is fake.session_state["warroom_summary"]
        assert seen["wr_at_registry"]["traffic_light"] != "上一輪的燈"

    def test_pop_is_recorded(self, _pinned):
        r, fake, _ = _run_refresh(_pinned, initial={"warroom_summary": copy.deepcopy(_STALE_WR)},
                                  market_ok=False, write_inputs=False)
        assert "warroom_summary" not in fake.session_state
        assert "warroom_summary" in r.popped_keys
        assert "warroom_summary" not in r.written_keys
        assert "warroom_summary" not in r.not_written_keys
        s = _step(r, RS.STEP_WARROOM)
        assert s.skipped and "已刪除上一份" in s.detail

    def test_market_failure_is_disclosed(self, _pinned):
        r, _, _ = _run_refresh(_pinned, initial={"mkt_info": {"score": 1, "regime": "bear"}},
                               market_ok=False)
        assert "市場評估這一輪沒有成功" in _step(r, RS.STEP_WARROOM).detail
        r, _, _ = _run_refresh(_pinned)
        assert "市場評估這一輪沒有成功" not in _step(r, RS.STEP_WARROOM).detail

    def test_apply_failure_is_disclosed(self, _pinned):
        """批 Z60 QA：`STEP_APPLY` 失敗 ⇒ `cl_data` 沿用上一輪，`STEP_WARROOM` 的報告要講出來。"""
        prior = {"cl_data": _cl_data(inst=_INST, adl=_ADL),
                 "li_latest": _li((5000.0, 6000.0, 7000.0, 8000.0))}
        r, fake, _ = _run_refresh(_pinned, initial=prior, apply_ok=False)
        assert not _step(r, RS.STEP_APPLY).ok and not r.ok
        s = _step(r, RS.STEP_WARROOM)
        assert s.ok and "warroom_summary" in fake.session_state     # 照樣寫 —— 所以才要揭露
        # 揭露與實際行為一致：`apply_macro_bundle` 負責的 key 裡，warroom 吃的是 cl_data 與 li_latest
        from src.compute.macro.macro_session_patch import MACRO_PATCH_KEYS
        assert {"cl_data", "li_latest"} <= set(MACRO_PATCH_KEYS)
        assert "本輪未更新" in s.detail
        assert "cl_data" in s.detail and "li_latest" in s.detail
        assert "籌碼資料" in s.detail and "先行指標" in s.detail
        assert "市場評估這一輪沒有成功" not in s.detail             # 兩條揭露各管各的
        r, _, _ = _run_refresh(_pinned)
        assert "本輪未更新" not in _step(r, RS.STEP_WARROOM).detail

    def test_an_exception_is_a_failed_step_and_a_pop(self, _pinned):
        def _boom(*a, **k):
            raise RuntimeError("判燈炸了")
        _pinned.setattr(WA, "calc_traffic_light", _boom)
        r, fake, _ = _run_refresh(_pinned, initial={"warroom_summary": copy.deepcopy(_STALE_WR)})
        s = _step(r, RS.STEP_WARROOM)
        assert not s.ok and "判燈炸了" in s.detail and not r.ok
        assert "warroom_summary" in r.popped_keys and "warroom_summary" not in fake.session_state

    def test_untouched_block_rewritten_truthfully(self):
        keys = [b.session_key for b in RS.UNTOUCHED_BLOCKS]
        assert not any("warroom_summary" in k for k in keys)
        # 批 Z65（有意識的修改，不是放寬）：Z60 改寫後剩下的 `macro_state.json`（系統風險上限）那一列
        #   自 Z65 起已不成立（`STEP_RISK_CAP` 重算並寫該檔）⇒ 整列移除；正向斷言改由
        #   `tests/test_batch_z65.py` 接手。這裡改成反向守衛：清單裡不得再說它摸不到。
        assert "macro_state.json" not in keys
        assert not any("系統風險上限" in b.label for b in RS.UNTOUCHED_BLOCKS)

    def test_macro_state_json_writer_api_list_is_complete(self):
        """`test_p01` 量 `macro_state.json` 寫入點用的兩支 API ＝ 真的會走到 `_write_state_lock` 的全部。"""
        import ast
        tree = ast.parse((_ROOT / "src/services/macro_state_locker.py").read_text(encoding="utf-8"))
        callers = set()
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef):
                for n in ast.walk(fn):
                    if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                            and n.func.attr == "_write_state_lock"):
                        callers.add(fn.name)
        # ~~assert callers == {"execute_and_lock", "lock_system_state_only"}~~
        # 📌 AUD-C21（客戶 2026-10-16，有意識的變更，⛔ 不是放寬）：新 UI 雙寫需要第二份檔與第一份逐位元組相同
        #   ⇒ `MacroStateLocker` 多一支 `write_state_snapshot`（寫已組好的快照）。清單照舊窮舉、照舊「＝」比對，
        #   `test_p01_macro_refresh._FILE_KEY_WRITER_API` 同步補上（兩邊一起改，量法仍是全部 API）。
        assert callers == {"execute_and_lock", "lock_system_state_only", "write_state_snapshot"}

    def test_health_light_is_in_reach(self):
        from src.ui.views import page_today as P
        assert P.OUT_OF_REACH_LIGHT_KEYS == frozenset({"news_systemic"})

    def test_new_files_respect_layering(self):
        import ast
        for rel, banned in ((_L2, ("streamlit", "requests", "yfinance", "src.data", "src.services",
                                   "src.ui", "proxy_helper")),
                            (_L3, ("src.ui",))):
            tree = ast.parse((_ROOT / rel).read_text(encoding="utf-8"))
            for n in ast.walk(tree):
                mods = ([n.module or ""] if isinstance(n, ast.ImportFrom)
                        else [a.name for a in n.names] if isinstance(n, ast.Import) else [])
                for m in mods:
                    assert not any(m == b or m.startswith(b + ".") for b in banned), (rel, m)

    def test_l2_has_no_threshold_numbers(self):
        """L2 組裝不含任何門檻數字（數字常數只允許 0 個）。"""
        import ast
        tree = ast.parse((_ROOT / _L2).read_text(encoding="utf-8"))
        nums = [n.value for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
                and not isinstance(n.value, bool)]
        assert nums == [], nums


# ══════════════════════════════════════════════════════════════════════════
# 7. 舊檔沒動
# ══════════════════════════════════════════════════════════════════════════
class TestOldFilesUntouched:
    """`git diff --stat e64ea2f5 -- src/ui/tabs src/ui/etf src/ui/pages src/ui/render app.py` 為空的純 Python 版。

    ⚠️ 不呼叫 `git`：`tests/test_zz_test_portability.py` 禁止測試依賴外部 shell 工具（Windows 沒有）。
    改為釘住基底 `e64ea2f5` 時這 91 個 `.py` 的內容指紋（逐檔 sha256 → 依路徑排序 → 再 sha256；
    CRLF 先正規化成 LF，免得 Windows checkout 誤紅）。實作組於基底實跑寫死，當時
    `git diff --stat e64ea2f5 -- …` 為空、`git ls-files` 同為 91 檔（無未追蹤檔）。

    ⚠️ **這是本批（Z60）的一次性守衛，不是永久凍結舊 UI。** 日後若有**經核准**的舊 UI 改動
    （或舊 UI 增刪檔），本支會紅 —— 那時請同步更新 `_BASE_COUNT` / `_BASE_DIGEST`
    （與對應的基底 commit 說明），⛔ 不要為了讓它綠而回退那個核准過的改動。
    """

    _BASE_COUNT = 91
    # ~~"6922b203519e9679d4a29bfbdd123b401a4147ebc41d60a1e8f652636c19f819"~~（基底 e64ea2f5，至 d3425a91 仍成立）
    # 📌 UIA-01／UIA-07（2026-10-18，核准過的舊檔改動，⛔ 不是漏改）：只動到**新舊 UI 共用**的純函式 ——
    #   `src/ui/tabs/tab_macro_v2.py`（`bucket_summary` / `overall_verdict` ＋ 新增 `summary_coverage`）、
    #   `src/ui/tabs/tab_today.py`（`classify_macro_contract(attempt=)` 與轉交它的三支 builder，皆選填 kwarg、
    #   預設輸出不變）。其餘 89 檔一個字都沒動。指紋依本 docstring 的指示同步更新。
    # ~~"45f5162d4b71038eced69d7d119dcefacd2070dac4307f49659f41f237964e35"~~（UIA-01／UIA-07 後，至 87afe5ae 仍成立）
    # 📌 SEC-3（2026-10-18，核准過的共用 chrome 改動，⛔ 不是漏改）：只改 `app.py` 側欄兩句 caption
    #   （「使用 Service Account（舊版部署）」與「（或改用 Service Account）」在網頁端已無 SA 讀取後不實）。
    #   其餘 90 檔一個字都沒動。指紋依本 docstring 的指示同步更新。
    # ~~"a5293369d2f1a97ae3cfa28259fb8cb7d7dc7e4bac564723f2e75a1d3b243fd1"~~（SEC-3 第一版 caption，abb44a90）
    # 📌 SEC-3 審計 round 1（2026-10-18，核准過的共用 chrome 改動，⛔ 不是漏改）：`app.py` 側欄刪掉 SA caption
    #   分支（及其 `_gsa_secret` / `_sheet_id_secret` import），else caption 改為「網頁讀取持股一律需 Google 登入；
    #   Service Account 不再用於網頁」。其餘 90 檔一個字都沒動。
    # ~~"63fa451e9b9d269c710c5d57b2ab8fd8af2750b14e964cafae8d957282ad80d8"~~（SEC-3 審計 round 1 後，至 4a576b19 仍成立）
    # 📌 vNext 1.0-B2（2026-10-18，核准過的共用 chrome 改動，⛔ 不是漏改；DEC-062 Q2＝B）：`app.py` 只加最少的線 ——
    #   OAuth callback 之後呼叫 `maybe_silent_reauth()`（重新整理後靜默恢復 Google 登入）、側欄登出多 import 並呼叫
    #   `forget_silent_reauth()`（拿掉 `?gs=` 記號，否則登不出去）。其餘 90 檔一個字都沒動。
    # ~~"7e3aa5539fcafccda019218eeddce8acc2473ffdd6618c1065777912f5f87b88"~~（1.0-B2 首版 23596359，至 1d169927 仍成立）
    # 📌 vNext 1.0-B2 稽核修正第二輪（2026-10-19，核准過的共用 chrome 改動，⛔ 不是漏改）：`app.py` 再加最少的線 ——
    #   OAuth hook 處多呼叫 `sync_silent_marker()`、側欄寫入新 `?sheet=` 後就地呼叫它（登入後換 Sheet 重算 `?gs=`
    #   記號；稽核 MUST-1）。其餘 90 檔一個字都沒動。
    # ~~"bf2a00d0657f48efaf4e7ba40eb270a9513d2edc91e839a1d2c6d3cd7feb5897"~~（1.0-B2 稽核修正第二輪後，至 56904662 仍成立）
    # 📌 VN1-STORE Pre-Hardening（2026-10-20，經總管指派的 app.py 開機掛鉤，⛔ 不是漏改）：`app.py` 只加一行 import
    #   ＋一行 `run_smoke_if_flagged()`（reader 真連線 smoke，只寫 log、⛔ 畫面零輸出；secrets 旗標預設關）＋三行註解
    #   （回修第 1 輪更正：原寫「兩行註解」，實為三行）＋一行空行。
    #   其餘 90 檔一個字都沒動。指紋依本 docstring 的指示同步更新；掛鉤的形狀由
    #   `tests/test_vn1_store_poc.py::assert_app_only_smoke_hook` 另守。
    # ~~"1b47c591741190e6c9598d01129182a53e7a31ac13b649b9bbe81fc50e7614cc"~~（VN1-STORE Pre-Hardening 後，至 b9ed892d 仍成立）
    # 📌 DEC-074/075 批 A（2026-10-23，客戶指派，⛔ 不是漏改；DEC-019 揭露）：只動 3 檔，全是**共用層契約改變的
    #   連帶**或新 UI 共用純函式 ——
    #   `src/ui/tabs/tab_macro_v2.py`（新舊共用 `build_rows`：代理廣度兩盞走灰燈＋註記，同 M1B 先例）、
    #   `src/ui/tabs/macro/handlers.py`（健康分因缺廣度 None 時刪掉不再屬實的「權重已重新歸一化」，只改字）、
    #   `src/ui/tabs/macro/section_short.py`（TWSE 單日頂替寫進共用 `jingqi_info` 時標 `is_proxy=True`，D-2）。
    #   版面零改動；其餘 88 檔一個字都沒動。指紋依本 docstring 的指示同步更新。
    # ~~"1c911a3154e11020d0faf5180759eaaf781df186b92757607867c0f607d36a28"~~（DEC-074/075 批 A 後）
    # 📌 DEC-075 批 1'（2026-10-23，客戶指派「修正 ISM 教學對映」，⛔ 不是漏改；DEC-019 揭露）：只動
    #   `src/ui/tabs/tab_edu.py` —— PMI 教學卡 key 'NAPM'→'TW_PMI' 的兩個對映鍵同步（該卡在舊教學頁本就不顯示，
    #   孤兒張數仍為 2，畫面輸出零改動）。其餘 90 檔一個字都沒動。指紋依本 docstring 的指示同步更新。
    # ~~"933d5e3c6d04846f56de617d2e2d9cae781838a89098b44848162eb2f52a2296"~~（DEC-075 批 1' 後）
    # 📌 DEC-074/075 回修（QA1／QA2，2026-10-23，總管指派，⛔ 不是漏改；DEC-019 揭露）：只改字／共用欄位 ——
    #   `macro/handlers.py`（breadth 原因的擋燈理由與說明改為屬實、不叫人更新）、
    #   `tab_macro_v2.py`＋`render/macro_v2_cards.py`（代理廣度列不算進 N／M 的「有資料」，Row 加選填欄）、
    #   `pages/reconcile_panel.py`（健康分對帳經 `jingqi_for_scoring`，代理不計分）。版面零改動。
    # ~~"faba6d21a902663688e94d71765c8107a1e8fbce4d7d154a436047fc0aa7dad8"~~（DEC-074/075 回修後，至 5e2e6e23 仍成立）
    # 📌 📊 大盤頁（2026-10-25，客戶裁示 Q1=C，總管指派，⛔ 不是漏改；DEC-019 揭露）：只動 `app.py` ——
    #   新增 late-import wrapper `_ia_view_market()`、`_IA_VIEWS` 多登記一頁、`shared.ia_nav` import 多一個
    #   `PAGE_MARKET`（共 9 行，含註解）。「🚦 今天」的 wrapper 與舊 7 個頁籤一字未動；其餘 90 檔一個字都沒動。
    #   指紋依本 docstring 的指示同步更新。
    # ~~"780ce3256a158b3773c5e335210a7521123347a0fae7d28f6093f5641f11464a"~~（📊 大盤頁後，至 abbc200d 仍成立）
    # 📌 Sheet Safety 修復批（2026-10-25，客戶裁示 DEC-083 B3／B4／C／Q5，總管指派，⛔ 不是漏改；DEC-019 揭露）：
    #   只動 3 檔 —— `src/ui/tabs/portfolio_binder.py`（寫入委派 L1 唯一寫入契約、刪自帶 Sheet URL 正則、
    #   取消唯一本自動綁）、`app.py`（開機 `?sheet=` 還原／側欄貼 ID 改經契約、登出多清 Sheet 綁定、刪 `import re`）、
    #   `src/ui/tabs/portfolio_manager.py`（`parse_sheet_id` 本體委派 L0 單一 parser，0 production caller）。
    #   版面零改動（側欄解析失敗時多一行 st.error 白話拒絕）；其餘 88 檔一個字都沒動。指紋依本 docstring 的指示同步更新。
    # ~~"e05aea0489726d0de9568a737b96481ef4720f8432adfa98700d7c3950f75d01"~~
    # 📌 Sheet Safety 批 QA 回修 B-1／BLK-2（2026-10-25，PR #926 兩組 QA，總管指派，⛔ 不是漏改；DEC-019 揭露）：
    #   `portfolio_binder.py`（貼網址框改 on_change、Drive ✅ 成功訊息只在真的寫入時顯示／已是目前那本改說
    #   「已是目前使用的 Sheet」）、`app.py`（側欄貼 ID 框改 on_change）。版面零改動；其餘 89 檔一個字都沒動。
    # ~~"ce6e2b9253bb5a539f85d84231f734de668f96eb3a103e842dd731324c10230f"~~
    # 📌 Sheet Safety 批 QA 回修 N-2／N-3（2026-10-25，PR #926 QA，總管指派，⛔ 不是漏改；DEC-019 揭露）：
    #   `src/ui/tabs/portfolio_status_bar.py`（本數因讀取問題未知時改顯「🔴 我的組合：讀取有問題」）、
    #   `app.py`（前進式驗證對帳的雲端讀取問題改用 st.warning）。版面零改動；其餘 89 檔一個字都沒動。
    # ~~"c66a804e4f7f70a9c3af190f4dda779c409b97573a9491ab0aaea08a96579cc7"~~（Sheet Safety 批 QA 回修後，至 55601f42 仍成立）
    # 📌 👤 我的 P1-6（2026-10-25，客戶裁示 DEC-083 Q5，總管指派，⛔ 不是漏改；DEC-019 揭露）：只動 `app.py` 側欄
    #   「🚪 登出」—— inline 四步改呼叫 L1 共用 `logout_google_session`（四步順序一字不變，另清 active 組合／觀察清單
    #   選定與「👤 我的」頁的 key），import 換成那一支。舊模式畫面零改動；其餘 90 檔一個字都沒動。
    # ~~"dfbde3935a2da0ce73b6c27529cc73938da96fa6d614d52500a4eddc25b5cda7"~~（👤 我的 P1-6 後）
    # 📌 👤 我的 P1-7（2026-10-25，客戶裁示 DEC-083 Q1=A／D 段，總管指派，⛔ 不是漏改；DEC-019 揭露）：只動 `app.py` ——
    #   新增 late-import wrapper `_ia_view_me()`、`_IA_VIEWS` 多登記一頁、`shared.ia_nav` import 多三個名字；
    #   側欄三句指向舊「📁 組合管理」的說明**只在新版模式**（`_IA_PAGE is not None`）改指「👤 我的」，
    #   「不使用」模式一字不變；一段註解更正。舊 7 個頁籤一字未動；其餘 90 檔一個字都沒動。
    # ~~"2845049326bcbfc16066dd3a480f545d9a4434b74139b3f6277c8dfabb786aa0"~~（👤 我的 P1-7 後）
    # 📌 PR #927 QA-2 第 7 點（2026-10-25，總管指派，⛔ 不是漏改；DEC-019 揭露）：只動 `app.py` 側欄
    #   「✅ Sheet ID」那一行 —— 新版模式（`_IA_PAGE is not None`）改顯末 6 碼（`shared.sheet_id.sheet_id_tail`），
    #   「不使用」模式一字不變（仍顯完整 ID）。側欄貼 ID 框的預填值未動（舊行為，列為殘留）。其餘 90 檔一個字都沒動。
    # ~~"118450bfd13ad4aa86fc74394fd5d64304288300a68f9009b0a84a45dc0e8270"~~（PR #927 QA-2 第 7 點後）
    # 📌 PR #927 QA-1 複驗（2026-10-25，DEC-083 Q4，總管指派，⛔ 不是漏改；DEC-019 揭露）：只動 `app.py` 側欄貼 ID 框 ——
    #   新版模式不預填（`value=""`），且畫框前丟掉含目前綁定 ID 的沿用值（舊模式切過來 / 貼了「已是目前這本」）；
    #   從新版切回「不使用」時丟掉新版留下的空值，讓舊模式照舊預填。「不使用」模式行為不變；其餘 90 檔一個字都沒動。
    #   （同批修正：分支改用 `_sb_new_mode` 變數，避免在側欄多出一處 `if _IA_PAGE is not None:` 字面 ——
    #   `test_batch_z54` 以該字面的第一個位置定位新版分支 `st.stop()`。）
    # ~~"75cc2114cd4ef8c5d70a892eea5b8256d471d1dfcc52eb7968c9eec1795dfadc"~~（33605619，改用 `_sb_new_mode` 之前）
    # ~~"1d1d6b0328d68945b03811143e895c02bee628aff025d397ec4358a1c770e39f"~~（4e8c0876）
    # 📌 PR #927 QA-2 Playwright 複驗（2026-10-25，DEC-083 Q4，總管指派，⛔ 不是漏改；DEC-019 揭露）：只動 `app.py` 側欄貼 ID 框
    #   —— 33605619 的「pop ＋ value=''」在瀏覽器不成立（前端照舊顯示完整 ID），改為以 Session State API 明確指定
    #   （新版模式指定 ""、切回「不使用」指定目前綁定的 ID）。「不使用」模式沒進過新版時一行都沒多跑；其餘 90 檔一個字都沒動。
    # ~~"45985febc58ed26d3c6437a7ac252f37dab6bc0afef4a04e7cf08f33f0488469"~~（PR #927 QA-2 Playwright 複驗後）
    # 📌 D2 導覽殼（2026-10-26，客戶裁示 DEC-089 G1＝C／DEC-090 形式 (b)，總管指派，⛔ 不是漏改；DEC-019 揭露）：只動 `app.py` ——
    #   側欄「🆕 新版戰情室（試用中）」radio 由「不使用＋7 頁」改為「不使用＋六個方向」，多方向底下的第二層 radio、
    #   「⬜ ＝ 尚未建置」圖例；新增 late-import wrapper `_ia_view_shell()`；分派處多畫位置列／佔位頁；
    #   `_IA_VIEWS` 對帳旁多一行 `reconcile_nav`。「不使用」模式（舊 7 個頁籤）一個字沒動；其餘 90 檔一個字都沒動。
    # ~~"2e1a6b2ed58bf29fc44e258119fd26cdff8053e603c7745be54dff792919a67b"~~（D2 導覽殼後）
    # 📌 NAV-1 四頁導覽殼（2026-10-28，客戶裁示 DEC-097／DEC-092 Q6，總管指派，⛔ 不是漏改；DEC-019 揭露）：只動 `app.py` ——
    #   新增 `_nav4_resolve_legacy()`／`_ia_view_nav4()`／`_nav4_reconcile()` 三支 late-import wrapper、`set_page_config`
    #   前的 legacy 旗標、側欄 D2 radio 區塊包進 `if _NAV4_LEGACY:`（AST 與原文逐節點相同，只多一層縮排；由
    #   `tests/test_nav1_app_routing.py::test_s3_legacy_d2_block_is_ast_identical_to_head` 守）與 `else:` 新導覽、
    #   `_IA_VIEWS` 對帳旁的新模式分支。預設入口翻轉；`?legacy=1` 的舊 7 個頁籤一個字沒動；其餘 90 檔一個字都沒動。
    # ~~"fe294e31a999b8d31fdec8b82416657ade20bac8d48963badf2c5437f242ae6a"~~（NAV-1 首版）
    # 📌 NAV-1 QA 回修（2026-10-28，兩組獨立 QA 後，總管指派，⛔ 不是漏改；DEC-019 揭露）：只動 `app.py` ——
    #   legacy 旗標解析 `_nav4_resolve_legacy()` 改為不 import 任何模組的內聯小函式（legacy 路徑零依賴新模組）、
    #   `_nav4_reconcile(_IA_VIEWS)` 移進新模式分支。legacy 的 D2 radio 區塊與舊 7 個頁籤一個字沒動；其餘 90 檔一個字都沒動。
    _BASE_DIGEST = "e9cf2c80094c10fb4d00b5c3f6c9af54931302f2eaa1af30f977cad179ab7669"

    def test_no_diff_against_base(self):
        import hashlib
        files = []
        for d in ("src/ui/tabs", "src/ui/etf", "src/ui/pages", "src/ui/render"):
            files += [p for p in (_ROOT / d).rglob("*.py") if "__pycache__" not in p.parts]
        files.append(_ROOT / "app.py")
        h = hashlib.sha256()
        for p in sorted(files, key=lambda p: p.relative_to(_ROOT).as_posix()):
            body = p.read_bytes().replace(b"\r\n", b"\n")
            h.update(p.relative_to(_ROOT).as_posix().encode() + b"\0"
                     + hashlib.sha256(body).hexdigest().encode() + b"\n")
        assert (len(files), h.hexdigest()) == (self._BASE_COUNT, self._BASE_DIGEST), (
            "舊 UI 檔（src/ui/tabs|etf|pages|render、app.py）與基底 e64ea2f5 不同 —— "
            "本批承諾舊檔零改動")


# ══════════════════════════════════════════════════════════════════════════
# 8. 卡①③ 未評估時的出口（批 Z60 QA 阻擋項）
# ══════════════════════════════════════════════════════════════════════════
class TestVerdictIdleExitIsRetry:
    """Z60 起 `STEP_WARROOM` 寫得到 `warroom_summary`，卡①（建議持股）／卡③（市場位階）
    按一次「🚀 更新今日戰情」就能離開未評估 —— 未評估（非錯誤）時的出口必須是
    `EXIT_RETRY_HERE`，⛔ 不得再是 `EXIT_OUT_OF_REACH`（「按本頁按鈕不會讓它離開現在的狀態」
    已是假指路，且 `UNTOUCHED_BLOCKS` 不再列它）。錯誤分支維持 `EXIT_FIX_CODE`。

    alloc / regime 走**真的** L3 `get_allocation()` / `get_macro_regime()`（`_pinned`：cwd 在空
    tmp 目錄，沒有 `macro_state.json`），不是手捏的替身 —— 守的是 production 會走到的那一態。
    """

    @staticmethod
    def _tiles(monkeypatch, session: dict, *, alloc_error="", regime_error=""):
        from src.ui.views import page_today as P
        fake = _FakeST(copy.deepcopy(session))
        monkeypatch.setattr(AS, "st", fake)
        alloc = None if alloc_error else AS.get_allocation()
        regime = None if regime_error else AS.get_macro_regime()
        tiles = P.build_verdict_tiles(
            alloc=alloc, alloc_error=alloc_error, danger=None, danger_error="",
            danger_requested=False, regime=regime, regime_error=regime_error)
        return P, {t.card.key: t for t in tiles}

    @staticmethod
    def _health_none_session(monkeypatch) -> dict:
        """新路徑在 F1（三來源全敗）寫出的那份 warroom：`health_score is None`。"""
        wr, res, fake = _new(monkeypatch, _state("F1_all_failed"))
        assert res.written and res.health_missing and wr["health_score"] is None
        return dict(fake.session_state)

    def _assert_retry(self, P, tiles):
        for key in ("verdict.exposure", "verdict.regime"):
            card = tiles[key].card
            assert card.state != P.UI_LIVE, (key, card.state)   # 真的走到非 live 那一支
            assert card.note.where is P.EXIT_RETRY_HERE, key
            assert card.note.where is not P.EXIT_OUT_OF_REACH, key

    def test_no_warroom(self, _pinned):
        """📌 2026-10-23 DH-REGIME-NOWARROOM（PR #910，有意識的修改，⛔ 不是漏刪；決策者 AI 總管）：「冷啟動／無 warroom ⇒ 可重抓（`EXIT_RETRY_HERE`）」自 #910 起只在代理廣度計分開啟（`BREADTH_PROXY_SCORING_ENABLED=True`）時成立 —— 旗標關（現行）時按了載入後位階仍為未評估，出口改為 `EXIT_LOAD_PENDING_BREADTH`（見 `_flag_off` 那一支）。本支改在旗標 True 下守舊語意（斷言一字未改）。"""
        import shared.signal_thresholds as STH
        _pinned.setattr(STH, "BREADTH_PROXY_SCORING_ENABLED", True)
        P, tiles = self._tiles(_pinned, {})
        assert tiles["verdict.exposure"].card.state == P.UI_IDLE
        assert tiles["verdict.regime"].card.state == P.UI_IDLE
        self._assert_retry(P, tiles)

    def test_no_warroom_but_inputs_present(self, _pinned):
        """有本輪輸入、還沒組 warroom（按鈕前的典型 session）—— 同樣是可重抓。

        📌 2026-10-23 DH-REGIME-NOWARROOM（PR #910，有意識的修改，⛔ 不是漏刪；決策者 AI 總管）：「冷啟動／無 warroom ⇒ 可重抓（`EXIT_RETRY_HERE`）」自 #910 起只在代理廣度計分開啟（`BREADTH_PROXY_SCORING_ENABLED=True`）時成立 —— 旗標關（現行）時按了載入後位階仍為未評估，出口改為 `EXIT_LOAD_PENDING_BREADTH`（見 `_flag_off` 那一支）。本支改在旗標 True 下守舊語意（斷言一字未改）。"""
        import shared.signal_thresholds as STH
        _pinned.setattr(STH, "BREADTH_PROXY_SCORING_ENABLED", True)
        s = _state("N1_bull")
        s.pop("warroom_summary", None)
        P, tiles = self._tiles(_pinned, s)
        self._assert_retry(P, tiles)

    @pytest.mark.parametrize("with_inputs", [False, True])
    def test_no_warroom_flag_off(self, _pinned, with_inputs):
        """旗標 False（現行）：無 warroom ⇒ 卡①③ 灰（idle）、出口＝「可更新，但載入後仍未評估」（DH-REGIME-NOWARROOM）。"""
        s = {}
        if with_inputs:
            s = _state("N1_bull")
            s.pop("warroom_summary", None)
        P, tiles = self._tiles(_pinned, s)
        for key in ("verdict.exposure", "verdict.regime"):
            card = tiles[key].card
            assert card.state == P.UI_IDLE, (key, card.state)
            assert card.note.where is P.EXIT_LOAD_PENDING_BREADTH, key
            assert card.note.why == P.not_loaded_pending_breadth_why(), key

    def test_warroom_health_none(self, _pinned):
        """📌 2026-10-23 DEC-075 D-1(a)（QA3 MUST-R1，有意識的修改，⛔ 不是漏刪）：本支舊斷言「warroom 健康分缺 ⇒
        可重抓」只在**代理廣度計分開啟**（`BREADTH_PROXY_SCORING_ENABLED=True`）時仍成立 —— 旗標關時 repo 沒有
        任何真實廣度，健康分缺必然受缺廣度所限，L3 改標「缺真實廣度未評估」、出口改為「等正式廣度來源」
        （見下一支 `test_warroom_health_none_breadth_gate`）。本支改在旗標 True 下守舊語意。"""
        import shared.signal_thresholds as STH
        s = self._health_none_session(_pinned)
        _pinned.setattr(STH, "BREADTH_PROXY_SCORING_ENABLED", True)
        P, tiles = self._tiles(_pinned, s)
        self._assert_retry(P, tiles)

    def test_warroom_health_none_breadth_gate(self, _pinned):
        """旗標 False（現行）：F1 寫出的 health-None warroom ⇒ 卡①／卡③ 非 live、出口＝等正式廣度來源（DEC-075 D-1(a)）。"""
        P, tiles = self._tiles(_pinned, self._health_none_session(_pinned))
        for key in ("verdict.exposure", "verdict.regime"):
            card = tiles[key].card
            assert card.state not in (P.UI_LIVE, P.UI_DEGRADED), (key, card.state)
            assert card.note.where is P.EXIT_WAIT_BREADTH_SOURCE, key

    def test_exposure_requested_but_unloaded(self):
        """卡①第三支（契約叫過了、建議持股仍未評估）同樣是可重抓 —— 健康分補上就會 live。"""
        from types import SimpleNamespace

        from src.ui.views import page_today as P
        alloc = SimpleNamespace(is_loaded=False, range_text="--", posture="未評估",
                                drivers=(), cap_text="", conflicts=())
        regime = {"regime": "bull", "light": "🟢", "source": "warroom", "is_loaded": True}
        (t,) = [t for t in P.build_verdict_tiles(
            alloc=alloc, alloc_error="", danger=None, danger_error="", danger_requested=False,
            regime=regime, regime_error="") if t.card.key == "verdict.exposure"]
        assert t.card.state not in (P.UI_LIVE, P.UI_IDLE), t.card.state
        assert t.card.note.where is P.EXIT_RETRY_HERE

    def test_error_branches_unchanged(self, _pinned):
        P, tiles = self._tiles(_pinned, {}, alloc_error='RuntimeError("boom")',
                               regime_error='RuntimeError("boom")')
        assert tiles["verdict.exposure"].card.note.where is P.EXIT_FIX_CODE
        assert tiles["verdict.regime"].card.note.where is P.EXIT_FIX_CODE


# ══════════════════════════════════════════════════════════════════════════
# 9. 沿用對面 `tab_today` 總經契約 Note 的卡：`where` 不得再是「按了也不會變」（批 Z60 複驗）
# ══════════════════════════════════════════════════════════════════════════
def _write_fresh_macro_state(tmp_path) -> None:
    """cwd（`_pinned` 已換到 tmp_path）放一份**未過期**的 `macro_state.json`。"""
    import json

    from src.services.macro_state_locker import _now_str
    (tmp_path / "macro_state.json").write_text(json.dumps(
        {"market_regime": "多頭", "exposure_limit_pct": 60, "timestamp": _now_str()},
        ensure_ascii=False), encoding="utf-8")


class TestDegradedRegimeExitIsRetry:
    """session 沒有可用的 warroom、cwd 有一份未過期的 `macro_state.json` ⇒ 卡③ degraded。

    修前卡③ 整份沿用 `build_status_bar_card().note`，`where` 是 `CONTRACT_NO_EXIT_WHERE`
    （「本批的按鈕還沒接上取數，按它不會讓這一格離開現在的狀態」）—— Z60 起按鈕會寫
    warroom，算得出健康分時 `get_macro_state` 就改走 warroom、卡③ 變 live ⇒ 假指路。
    """

    def test_degraded_card3_and_empty_card1(self, _pinned, tmp_path):
        """📌 2026-10-23 DH-REGIME-NOWARROOM（PR #910，有意識的修改，⛔ 不是漏刪；決策者 AI 總管）：「無 warroom ＋ 有效快照 ⇒ 卡③ degraded（退規則引擎快照）」自 #910 起只在代理廣度計分開啟（`BREADTH_PROXY_SCORING_ENABLED=True`）時成立 —— 旗標關（現行）時按了載入後位階仍為未評估，出口改為 `EXIT_LOAD_PENDING_BREADTH`（見 `_flag_off` 那一支）。本支改在旗標 True 下守舊語意（斷言一字未改）。"""
        import shared.signal_thresholds as STH
        from shared.ui_state import UI_DEGRADED, UI_EMPTY
        _pinned.setattr(STH, "BREADTH_PROXY_SCORING_ENABLED", True)
        _write_fresh_macro_state(tmp_path)
        P, tiles = TestVerdictIdleExitIsRetry._tiles(_pinned, {})
        reg, exp = tiles["verdict.regime"].card, tiles["verdict.exposure"].card
        assert reg.state == UI_DEGRADED, reg.state            # 前提自證：真的走到 degraded
        assert reg.note.where is P.EXIT_RETRY_HERE
        assert reg.note.where is not P.CONTRACT_NO_EXIT_WHERE
        assert "快照" in reg.note.now                          # now/why 照舊沿用對面
        assert exp.state == UI_EMPTY, exp.state
        assert exp.note.where is P.EXIT_RETRY_HERE

    def test_fresh_snapshot_no_warroom_flag_off(self, _pinned, tmp_path):
        """旗標 False（現行）：無 warroom ＋ 有效快照 ⇒ 卡③ ⛔ 不 degraded（不印規則引擎位階）、卡①③ 灰（idle）。"""
        from shared.ui_state import UI_IDLE
        _write_fresh_macro_state(tmp_path)
        P, tiles = TestVerdictIdleExitIsRetry._tiles(_pinned, {})
        for key in ("verdict.regime", "verdict.exposure"):
            c = tiles[key].card
            assert c.state == UI_IDLE, (key, c.state)
            assert c.note.where is P.EXIT_LOAD_PENDING_BREADTH, key
        assert "快照" not in tiles["verdict.regime"].card.note.now

    def test_degraded_with_health_none_warroom(self, _pinned, tmp_path):
        """warroom 在但健康分缺（視同未載入）＋ 快照 ⇒ 同樣 degraded、同樣可重抓。

        📌 2026-10-23 DEC-075 D-1(a)（QA3 MUST-R1，有意識的修改，⛔ 不是漏刪）：「健康分缺 ⇒ 退快照 degraded」
        正是 DEC-075 不採用的 (b)；自本批起只在代理廣度計分開啟（旗標 True）時仍可達 ⇒ 本支改在旗標 True 下守舊語意，
        旗標 False（現行）由下一支守「⛔ 不退快照」。"""
        import shared.signal_thresholds as STH
        from shared.ui_state import UI_DEGRADED
        s = TestVerdictIdleExitIsRetry._health_none_session(_pinned)
        _write_fresh_macro_state(tmp_path)
        _pinned.setattr(STH, "BREADTH_PROXY_SCORING_ENABLED", True)
        P, tiles = TestVerdictIdleExitIsRetry._tiles(_pinned, s)
        assert tiles["verdict.regime"].card.state == UI_DEGRADED
        assert tiles["verdict.regime"].card.note.where is P.EXIT_RETRY_HERE

    def test_health_none_warroom_with_snapshot_not_degraded(self, _pinned, tmp_path):
        """旗標 False（現行）：warroom 健康分缺 ＋ 有效快照 ⇒ ⛔ 不退快照（卡③ 非 degraded、出口＝等正式廣度來源）。"""
        from shared.regime_arbiter import SOURCE_UNEVALUATED_BREADTH
        s = TestVerdictIdleExitIsRetry._health_none_session(_pinned)
        _write_fresh_macro_state(tmp_path)
        P, tiles = TestVerdictIdleExitIsRetry._tiles(_pinned, s)
        card = tiles["verdict.regime"].card
        assert card.state not in (P.UI_LIVE, P.UI_DEGRADED), card.state
        assert card.note.where is P.EXIT_WAIT_BREADTH_SOURCE
        assert AS.get_macro_regime()["source"] == SOURCE_UNEVALUATED_BREADTH

    def test_retarget_only_touches_the_contract_exit(self):
        """`contract_exit_retargeted` 只換 `CONTRACT_NO_EXIT_WHERE`；未接線 / 失敗的出口原樣。"""
        from src.ui.tabs.tab_today import build_status_bar_cards
        from src.ui.views import page_today as P
        for regime, err in ((None, None), ({"source": "x", "is_loaded": True,
                                             "regime": "bull"}, None),
                            (None, 'RuntimeError("boom")')):
            for c in build_status_bar_cards(regime, error=err):
                out = P.contract_exit_retargeted(c)
                if c.note is not None and c.note.where is P.CONTRACT_NO_EXIT_WHERE:
                    assert out.note.where is P.EXIT_RETRY_HERE
                    assert (out.key, out.label, out.state, out.value, out.note.now, out.note.why) == (
                        c.key, c.label, c.state, c.value, c.note.now, c.note.why)
                else:
                    assert out is c


def _drive_page(monkeypatch, regime):
    """整頁 render（同 `tests/test_batch_z59.py::_drive`）：收集畫出來的每一張 Tile。"""
    from unittest import mock

    from src.ui.views import page_today as T
    drawn: list = []
    fake = mock.MagicMock(name="st")
    fake.session_state = {}
    fake.tabs.side_effect = lambda labels: [mock.MagicMock() for _ in labels]
    monkeypatch.setattr(T, "st", fake)
    for name, val in [
            ("_inject_v2_css", lambda: None), ("_render_update_form", lambda _s: None),
            ("section_header", lambda *a, **k: None), ("render_note", lambda *a, **k: None),
            ("load_macro_readout", lambda _s: T.MacroReadout(requested=False)),
            ("_load_l4_labels", lambda: (None, None, None, "")),
            ("_load_allocation", lambda: (None, "")), ("_load_regime", lambda: (regime, "")),
            ("_load_danger", lambda _r: (None, "", "")),
            ("_load_key_alerts", lambda _s: (None, False, "")),
            ("_load_lamp_directions", lambda _s=None: {}),
            ("load_sheet_binding", lambda: (None, "")),
            ("load_trading_day_status", lambda: (None, "")),
            ("_render_tiles", lambda tiles, cols=None: drawn.extend(tiles))]:
        monkeypatch.setattr(T, name, val)
    T.render_page_today()
    return T, drawn


class TestNoContractNoExitOnThePage:
    """整頁掃：沿用對面總經契約 Note 的三格（狀態列「總經」／三欄摘要「位階」／卡③）
    在冷啟動與 degraded 兩態下，`where` 都是可重抓；全頁沒有任何一張卡還掛著
    `CONTRACT_NO_EXIT_WHERE`。"""

    _COLD = {"regime": "unknown", "light": "⬜", "source": "unloaded", "is_loaded": False}  # 下方以 SOURCE_UNLOADED 自證

    @pytest.mark.parametrize("flag_on", [False, True])
    @pytest.mark.parametrize("which", ["cold", "degraded"])
    def test_the_three_contract_cells(self, monkeypatch, which, flag_on):
        import shared.signal_thresholds as _STH
        monkeypatch.setattr(_STH, "BREADTH_PROXY_SCORING_ENABLED", flag_on)   # DH-REGIME-NOWARROOM：兩態都守
        from shared.ui_state import UI_DEGRADED, UI_IDLE
        from shared.regime_arbiter import SOURCE_FILE_RULE_ENGINE, SOURCE_UNLOADED
        assert self._COLD["source"] == SOURCE_UNLOADED
        regime = (dict(self._COLD) if which == "cold" else
                  {"regime": "bull", "light": "🟢", "traffic_light": "多頭",
                   "source": SOURCE_FILE_RULE_ENGINE, "is_loaded": True})
        T, drawn = _drive_page(monkeypatch, regime)
        by_key = {}
        for t in drawn:
            by_key.setdefault(t.card.key, []).append(t)
        want = UI_IDLE if which == "cold" else UI_DEGRADED
        # 📌 2026-10-23 DH-REGIME-NOWARROOM（PR #910，有意識的修改，⛔ 不是漏刪；決策者 AI 總管）：冷啟動＋代理廣度不計分
        #   （現行）時三格出口改為 `EXIT_LOAD_PENDING_BREADTH`（按了載入後位階仍未評估，⛔ 不再寫「可重抓」）；
        #   degraded 與旗標 True 的冷啟動照舊 `EXIT_RETRY_HERE`。「全頁沒有 `CONTRACT_NO_EXIT_WHERE`」一字未改。
        import shared.signal_thresholds as STH
        want_where = (T.EXIT_LOAD_PENDING_BREADTH
                      if (which == "cold" and not STH.BREADTH_PROXY_SCORING_ENABLED) else T.EXIT_RETRY_HERE)
        for key in ("statusbar.macro", "summary.regime", "verdict.regime"):
            (t,) = by_key[key]
            assert t.card.state == want, (key, t.card.state)
            assert t.card.note.where is want_where, key
        assert not [t.card.key for t in drawn if t.card.note is not None
                    and t.card.note.where is T.CONTRACT_NO_EXIT_WHERE]


def test_nan_is_canonicalised():
    """`_canon` 對 NaN 可序列化且穩定（golden 含 NaN 的前提）。"""
    a = {"x": float("nan")}
    assert _canon(a) == _canon(copy.deepcopy(a)) and math.isnan(a["x"])
