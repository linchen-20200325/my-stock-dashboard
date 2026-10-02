"""批 D3（DL-f1-s17 等）：M1B 代理值只顯示不計分 —— 守衛。"""
from __future__ import annotations

from shared.macro_provenance import m1b_m2_for_scoring

_PROXY = {'m1b_yoy': 3.65, 'm2_yoy': 0.91, 'gap': 2.74, 'source': 'TWII-proxy'}
_REAL = {'m1b_yoy': 7.34, 'm2_yoy': 7.42, 'gap': -0.08, 'source': 'CBC-tier2'}


class TestL0ScoringGate:
    def test_proxy_source_is_dropped(self):
        assert m1b_m2_for_scoring(_PROXY) is None

    def test_proxy_flag_is_dropped(self):
        assert m1b_m2_for_scoring({**_REAL, 'is_proxy': True}) is None
        assert m1b_m2_for_scoring({**_REAL, 'is_proxy_tier': True}) is None

    def test_real_returns_same_object(self):
        assert m1b_m2_for_scoring(_REAL) is _REAL

    def test_none_and_empty_passthrough(self):
        assert m1b_m2_for_scoring(None) is None
        _e = {}
        assert m1b_m2_for_scoring(_e) is _e


# ══════════════════════════════════════════════════════════════════════════
# DL-f1-s65：macro_state.json 裁決有效期限
# ══════════════════════════════════════════════════════════════════════════
import datetime as _dt
import json

import pytest

_TZ8 = _dt.timezone(_dt.timedelta(hours=8))
_NOW = _dt.datetime(2026, 10, 2, 18, 0, 0, tzinfo=_TZ8)


def _ts(dt: _dt.datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _write_state(path, **kw):
    d = {"market_regime": "空頭", "exposure_limit_pct": 30, "Macro_Phase": "資金緊縮"}
    d.update(kw)
    path.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


class TestVerdictExpiry:

    def test_threshold_is_existing_daily_ssot(self):
        from shared.staleness import MACRO_VERDICT_MAX_AGE_DAYS, STALE_DAYS_DAILY
        assert MACRO_VERDICT_MAX_AGE_DAYS == STALE_DAYS_DAILY

    @pytest.mark.parametrize("age, expired", [
        (_dt.timedelta(0), False),
        (_dt.timedelta(days=7), False),                     # 恰 7 天：仍有效（> 才過期）
        (_dt.timedelta(days=7, seconds=1), True),
        (_dt.timedelta(days=30), True),
    ])
    def test_age_boundary(self, age, expired):
        from src.services.macro_state_locker import macro_state_is_expired
        assert macro_state_is_expired({"timestamp": _ts(_NOW - age)}, now=_NOW) is expired

    @pytest.mark.parametrize("state", [None, {}, {"timestamp": ""}, {"timestamp": "garbage"},
                                       {"timestamp": None}, "x"])
    def test_unknown_time_is_expired(self, state):
        from src.services.macro_state_locker import macro_state_is_expired
        assert macro_state_is_expired(state, now=_NOW) is True

    def test_fresh_file_drives_cap(self, tmp_path):
        from src.services.macro_state_locker import get_macro_state
        f = tmp_path / "macro_state.json"
        _write_state(f, timestamp=_ts(_NOW - _dt.timedelta(days=1)))
        ms = get_macro_state(None, state_file_path=str(f), now=_NOW)
        assert ms["is_loaded"] is True and ms["exposure_limit_pct"] == 30

    def test_expired_file_is_like_no_file(self, tmp_path):
        from src.services.macro_state_locker import get_macro_state
        f = tmp_path / "macro_state.json"
        _write_state(f, timestamp=_ts(_NOW - _dt.timedelta(days=8)))
        ms = get_macro_state(None, state_file_path=str(f), now=_NOW)
        none = get_macro_state(None, state_file_path=str(tmp_path / "nofile.json"), now=_NOW)
        assert ms == none
        assert ms["is_loaded"] is False and ms["exposure_limit_pct"] is None
        # strict：過期 ≠ 讀壞 → 不拋
        assert get_macro_state(None, state_file_path=str(f), strict=True, now=_NOW) == none

    def test_expired_file_with_warroom_no_cap_no_file_error(self, tmp_path):
        from src.services.macro_state_locker import get_macro_state
        f = tmp_path / "macro_state.json"
        _write_state(f, timestamp=_ts(_NOW - _dt.timedelta(days=8)))
        wr = {"regime": "bull", "health_score": 70.0, "effective_regime": "bull"}
        ms = get_macro_state(wr, state_file_path=str(f), strict=True, now=_NOW)
        assert ms["is_loaded"] is True and ms["exposure_limit_pct"] is None
        assert "file_error" not in ms

    def test_ai_qa_extra_fields_dropped_when_expired(self, tmp_path, monkeypatch):
        import src.services.ai_qa_service as Q
        import src.services.macro_state_locker as MSL
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Q, "_macro_state", lambda: {"is_loaded": True, "regime": "bear"})
        _write_state(tmp_path / "macro_state.json", timestamp=_ts(
            _dt.datetime.now(_TZ8) - _dt.timedelta(days=8)))
        out = Q._tool_get_market_state()
        assert "鎖定快照額外欄位_macro_state_json" not in out["data"]
        _write_state(tmp_path / "macro_state.json", timestamp=MSL._now_str())
        out = Q._tool_get_market_state()
        assert out["data"]["鎖定快照額外欄位_macro_state_json"]["Macro_Phase"] == "資金緊縮"

    def test_mutant_without_expiry_check_keeps_stale_cap(self, tmp_path):
        """突變：拿掉期限判斷 → 過期裁決照樣給曝險上限（本測試抓得到）。"""
        import importlib.util
        import inspect

        import src.services.macro_state_locker as MSL
        src_code = inspect.getsource(MSL)
        old = "    _file_expired = _file_ok and macro_state_is_expired(_file, now=now)\n"
        assert src_code.count(old) == 1
        spec = importlib.util.spec_from_loader("_msl_mut", loader=None)
        m = importlib.util.module_from_spec(spec)
        exec(compile(src_code.replace(old, "    _file_expired = False\n"), MSL.__file__, "exec"),
             m.__dict__)
        f = tmp_path / "macro_state.json"
        _write_state(f, timestamp=_ts(_NOW - _dt.timedelta(days=8)))
        assert m.get_macro_state(None, state_file_path=str(f), now=_NOW)["exposure_limit_pct"] == 30


# ══════════════════════════════════════════════════════════════════════════
# §十一 規則引擎 → macro_state.json（建議持股上限）：代理值不計分；落檔帶資料月
# ══════════════════════════════════════════════════════════════════════════
class TestNewsVerdictPositionCap:

    def _run(self, info, monkeypatch):
        from tests.test_m2n2_no_zero_fill import _run_news, _mod
        return _run_news(_mod("news"), info, monkeypatch)

    def test_real_value_scored_and_month_recorded(self, monkeypatch):
        got = self._run({**_REAL, "m1b_yoy": 5.1, "m2_yoy": 2.0, "data_month": "2026-07"},
                        monkeypatch)
        assert got["numbers"][0]["M1B_YoY_pct"] == 5.1
        assert got["locked"][0]["m1b_m2_data_month"] == "2026-07"

    def test_proxy_value_not_scored_no_month(self, monkeypatch):
        got = self._run({**_PROXY, "m1b_yoy": 5.1, "m2_yoy": 2.0}, monkeypatch)
        empty = self._run({}, monkeypatch)
        assert got["numbers"][0]["M1B_YoY_pct"] is None and got["numbers"][0]["M2_YoY_pct"] is None
        assert got["locked"] == empty["locked"]
        assert got["locked"][0]["m1b_m2_data_month"] is None
        assert got["locked"][0]["exposure_limit_pct"] == empty["locked"][0]["exposure_limit_pct"]


# ══════════════════════════════════════════════════════════════════════════
# 五桶（v1）：代理燈 gray、值照樣顯示
# ══════════════════════════════════════════════════════════════════════════
class TestFiveBucketProxyGray:

    def _m1b_detail(self, info):
        from src.compute.macro.macro_helpers import compute_five_bucket_summary
        out = compute_five_bucket_summary(m1b_m2_info=info)
        return out["long"], [d for d in out["long"]["details"] if d["key"] == "m1b_m2_gap"][0]

    def test_proxy_is_gray_but_shown(self):
        from shared.macro_provenance import M1B_PROXY_VALUE_NOTE
        bucket, d = self._m1b_detail({**_PROXY, "gap": -5.0})
        assert d["danger"] == "gray"
        assert d["value_str"].endswith(M1B_PROXY_VALUE_NOTE)
        assert bucket["level"] == "gray"          # 其餘長期燈無資料 → 桶未載入（既有字樣）

    def test_real_still_scored(self):
        bucket, d = self._m1b_detail({**_REAL, "gap": -5.0})
        assert d["danger"] in ("yellow", "red") and bucket["level"] == d["danger"]


# ══════════════════════════════════════════════════════════════════════════
# 頂部紅綠燈 chip（DL-f1-s23）
# ══════════════════════════════════════════════════════════════════════════
class TestMarketRegimeChip:

    _BASE = dict(index_close=100.0, ma60=90.0, ma120=80.0, foreign_buy=None)

    def _sig(self, **kw):
        from src.services.market_strategy import market_regime
        r = market_regime(**self._BASE, **kw)
        return r, [x for x in r["signals"] if "M1B-M2" in x]

    def test_disabled_leg_chip_real_and_proxy(self):
        from shared.macro_provenance import M1B_PROXY_VALUE_NOTE
        _r, real = self._sig(m1b_m2_gap=2.74)
        _p, prox = self._sig(m1b_m2_gap=2.74, m1b_m2_is_proxy=True)
        assert real == ["⬜ M1B-M2 資金活水已停用（+2.74%，AUC 0.54 無預測力）— 不計分"]
        assert prox == [f"⬜ M1B-M2 資金活水已停用（+2.74%{M1B_PROXY_VALUE_NOTE}，"
                        "AUC 0.54 無預測力）— 不計分"]
        assert _r["score"] == _p["score"] and _r["max_score"] == _p["max_score"]

    def test_enabled_leg_never_scores_proxy(self, monkeypatch):
        import src.services.market_strategy as MS
        monkeypatch.setattr(MS, "M1B_M2_LEG_ENABLED", True)
        none, _ = self._sig()
        prox, sig = self._sig(m1b_m2_gap=2.74, m1b_m2_is_proxy=True)
        real, _ = self._sig(m1b_m2_gap=2.74)
        assert sig == [] and prox["score"] == none["score"]
        assert prox["max_score"] == none["max_score"]
        assert real["score"] > none["score"], "反向對照：真值時腿確實計分"


# ══════════════════════════════════════════════════════════════════════════
# L1：DL-f1-s49（ms1 依資料月對齊）、DL-f1-s13（資料月 + 過期閘）、DL-f1-s12（代理排最後）
# ══════════════════════════════════════════════════════════════════════════
def _ms1_rows(months, m1b0=100.0, m20=200.0):
    return [{"年月": ym, "M1B": str(m1b0 + i), "M2": str(m20 + i)} for i, ym in enumerate(months)]


def _yms(y0, m0, n):
    out = []
    y, m = y0, m0
    for _ in range(n):
        out.append(f"{y}M{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


class TestMs1DateAligned:

    def _dated(self, monkeypatch, rows):
        from src.data.macro import tw_macro as TW
        monkeypatch.setattr(TW, "fetch_cbc_ms1_rows", lambda *a, **k: rows)
        return TW._try_cbc_ms1_dated("https://x/ms1.json")

    def test_base_is_exactly_12_months_back_by_date(self, monkeypatch):
        rows = _ms1_rows(_yms(2025, 7, 13))
        m1b, m2, as_of = self._dated(monkeypatch, rows)
        assert as_of == _dt.date(2026, 7, 1)
        assert m1b == round((112 / 100 - 1) * 100, 2) and m2 == round((212 / 200 - 1) * 100, 2)

    def test_unsorted_and_one_side_missing_does_not_misalign(self, monkeypatch):
        rows = _ms1_rows(_yms(2025, 7, 14))          # 2025-07 … 2026-08
        rows[5]["M2"] = "-"                            # 2025-12 的 M2 缺（舊碼：兩欄各自 dropna → 錯配）
        rows = rows[::-1]                              # 亂序（舊碼不排序）
        m1b, m2, as_of = self._dated(monkeypatch, rows)
        assert as_of == _dt.date(2026, 8, 1)
        assert m1b == round((113 / 101 - 1) * 100, 2) and m2 == round((213 / 201 - 1) * 100, 2)

    @pytest.mark.parametrize("mutate", ["no_date_col", "dup_month", "no_base"])
    def test_rejects(self, monkeypatch, mutate):
        rows = _ms1_rows(_yms(2025, 7, 13))
        if mutate == "no_date_col":
            rows = [{k: v for k, v in r.items() if k != "年月"} for r in rows]
        elif mutate == "dup_month":
            rows[-2]["年月"] = rows[-1]["年月"]
        else:
            rows = rows[1:] + [{"年月": "2026M08", "M1B": "120", "M2": "220"}]
            rows = [r for r in rows if r["年月"] != "2025M08"]
        assert self._dated(monkeypatch, rows) is None

    def test_script_candidate_uses_same_parser(self):
        import inspect

        import scripts.update_macro_history as U
        assert "parse_cbc_ms1_rows(data)" in inspect.getsource(U._m1m2_ms1_candidate)


class TestCbcStaleGateAndProxyOrder:

    def _patch(self, monkeypatch, *, ef15=None, proxy=(3.65, 0.91),
               today=_dt.date(2026, 10, 2)):
        from src.data.macro import tw_macro as TW
        monkeypatch.setattr(TW, "_today_tw", lambda: today)
        monkeypatch.setattr(TW, "_try_cbc_ms1_dated", lambda url: None)   # ms1 現況兩網址都失效
        monkeypatch.setattr(TW, "_try_cbc_ef15m01_dated", lambda: ef15)
        monkeypatch.setattr(TW, "_try_twii_proxy", lambda: proxy)
        return TW

    def test_current_month_used_with_data_month(self, monkeypatch):
        TW = self._patch(monkeypatch, ef15=(7.34, 7.42, _dt.date(2026, 7, 1)))
        r = _call(TW)
        assert r["tier_used"] == 2 and r["data_month"] == "2026-07"

    def test_stale_month_rejected_falls_to_proxy(self, monkeypatch):
        TW = self._patch(monkeypatch, ef15=(7.34, 7.42, _dt.date(2026, 5, 1)))
        r = _call(TW)
        assert r["tier_used"] == 3 and r["is_proxy_tier"] is True and r["data_month"] is None

    def test_include_proxy_false_never_tries_proxy(self, monkeypatch):
        TW = self._patch(monkeypatch, ef15=None)

        def _boom():
            raise AssertionError("include_proxy=False 不得試代理")
        monkeypatch.setattr(TW, "_try_twii_proxy", _boom)
        r = _call(TW, include_proxy=False)
        assert r["tier_used"] is None and r["m1b_yoy"] is None


def _call(TW, **kw):
    """繞過 10 分鐘 TTL 快取直接呼叫本體（避免測試間互相污染）。"""
    return TW.fetch_cbc_m1b_m2.__wrapped__(**kw)


class TestSnapshotOrder:
    """DL-f1-s12：央行 → FRED → IMF → 代理（純排序；代理最後、只顯示不計分）。"""

    def _run(self, monkeypatch, *, cbc, fred_ok, imf_ok, proxy=(3.65, 0.91)):
        import src.data.macro as DM
        import src.data.macro.macro_snapshot as S
        import src.data.proxy.proxy_helper as P   # 不可 patch package（PEP 562 轉發地雷）
        order: list = []

        def _cbc(include_proxy=True):
            order.append(("cbc", include_proxy))
            return cbc
        monkeypatch.setattr(DM, "fetch_cbc_m1b_m2", _cbc, raising=False)

        def _fu(url, params=None, **k):
            if "stlouisfed" in url:
                order.append("fred")
                return fred_ok(params) if fred_ok else None
            if "imf.org" in url:
                order.append("imf")
                return imf_ok(url) if imf_ok else None
            return None
        monkeypatch.setattr(P, "fetch_url", _fu)

        def _px():
            order.append("proxy")
            return proxy
        monkeypatch.setattr(DM, "fetch_twii_m1b_m2_proxy", _px, raising=False)
        return S.fetch_m1b_m2_block.__wrapped__("k"), order

    def test_cbc_hit_carries_data_month(self, monkeypatch):
        cbc = {"m1b_yoy": 7.34, "m2_yoy": 7.42, "gap": -0.08, "tier_used": 2,
               "is_proxy_tier": False, "data_month": "2026-07"}
        r, order = self._run(monkeypatch, cbc=cbc, fred_ok=None, imf_ok=None)
        assert r["data_month"] == "2026-07" and r["source"] == "CBC-tier2"
        assert order == [("cbc", False)]

    def test_real_sources_tried_before_proxy(self, monkeypatch):
        empty = {"m1b_yoy": None, "m2_yoy": None, "gap": None}
        r, order = self._run(monkeypatch, cbc=empty, fred_ok=None, imf_ok=None)
        assert order == [("cbc", False), "fred", "fred", "imf", "imf", "proxy"]
        assert r["source"] == "TWII-proxy" and r["data_month"] is None
        from shared.macro_provenance import is_m1b_m2_proxy, m1b_m2_for_scoring
        assert is_m1b_m2_proxy(r) and m1b_m2_for_scoring(r) is None

    def test_stale_fred_rejected_not_shown_as_current(self, monkeypatch):
        """FRED 回 1960 年代的舊序列（asc + limit 36 的實況）→ 過期閘拒用，不冒充當期。"""
        class _R:
            status_code = 200

            def __init__(self, sid):
                self.sid = sid

            def json(self):
                obs = [{"date": f"{1961 + i // 12}-{i % 12 + 1:02d}-01", "value": str(100 + i)}
                       for i in range(36)]
                return {"observations": obs}
        empty = {"m1b_yoy": None, "m2_yoy": None, "gap": None}
        r, order = self._run(monkeypatch, cbc=empty,
                             fred_ok=lambda p: _R(p["series_id"]), imf_ok=None)
        assert r["source"] == "TWII-proxy" and "proxy" in order
