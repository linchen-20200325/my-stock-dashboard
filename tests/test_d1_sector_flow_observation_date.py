"""tests/test_d1_sector_flow_observation_date.py — D1(客戶 2026-11-08 核准,DEC-148):
板塊資金潮汐新鮮度改取「可信的實際來源觀測日」,cron 執行時間(updated_at)不得冒充資料日。

守的是:
  L1 `src/data/sector_flow/reader.py::_compute_staleness` / `read_sector_flow_cache(today=…)`
  L5 `page_find.SectorFlowReadout` / `build_sector_flow_card` ＋ `_target_blocks._asof_chip` / `industry_chips` / `basis_industry`

情境(客戶任務 a~h):
  (a) cron 成功執行但資料沒變 ⇒ updated_at 新、last_updated 舊且超門檻 ⇒ stale
  (b) 上游全敗但 metadata 仍被重寫 ⇒ 同 (a)
  (c) 真正新資料(last_updated=今天)⇒ fresh
  (d) 缺 last_updated / 格式壞 ⇒ stale 且 reason 含「觀測日未知」(⛔ 不以 updated_at 頂替)
  (e) last_updated 為未來(或晚於排程執行日)⇒ stale、reason「無法判定」
  (f) 週末/休市無新觀測:純依日曆日門檻,不做週末推論
  (g) UI 資料日 chip / Basis.as_of 顯示 observation_date;缺值不頂替
  (h) 突變:還原核心判斷 ⇒ 上述檢查轉紅
"""
from __future__ import annotations

import dataclasses
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from shared.sector_flow_thresholds import SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS as MAXD

REPO = Path(__file__).resolve().parents[1]
_READER_REL = "src/data/sector_flow/reader.py"

TODAY = date(2026, 11, 9)                       # 週一(台北)
_EXEC = "2026-11-09T09:00:00+00:00"             # cron 剛跑完:UTC 09:00 = 台北 17:00(同日)


def _meta(*, last_updated="2026-11-09", updated_at=_EXEC, **extra) -> dict:
    m = {"updated_at": updated_at}
    if last_updated is not None:
        m["last_updated"] = last_updated
    m.update(extra)
    return m


# ═══════════════════════════════════════════════════════════════════════
# 一組「對任一 reader 模組都成立」的行為檢查:真模組要全過,突變模組要紅(h)
# ═══════════════════════════════════════════════════════════════════════
def check_a_b_cron_ran_but_data_unchanged(R):
    # (a) 排程剛成功跑完(updated_at 很新)但資料沒變(last_updated 停在 10 天前)
    stale, reason, upd, obs = R._compute_staleness(
        _meta(last_updated="2026-10-30"), today=TODAY)
    assert stale is True
    assert "超過" in reason and f"{MAXD} 日門檻" in reason and "2026-10-30" in reason
    assert obs == "2026-10-30" and upd == _EXEC
    # (b) 上游全敗但 cron 仍重寫 updated_at=now;last_error 照實存在
    stale, reason, _upd, obs = R._compute_staleness(
        _meta(last_updated="2026-11-02", last_error="HTTPError: upstream down"), today=TODAY)
    assert stale is True and obs == "2026-11-02" and "超過" in reason


def check_c_real_fresh_data(R):
    stale, reason, _upd, obs = R._compute_staleness(_meta(last_updated="2026-11-09"), today=TODAY)
    assert (stale, reason, obs) == (False, None, "2026-11-09")
    # 門檻邊界:剛好 MAXD 日仍 fresh、MAXD+1 日 stale(門檻數值不變,見 test_threshold_value_unchanged)
    edge = (TODAY - timedelta(days=MAXD)).isoformat()
    over = (TODAY - timedelta(days=MAXD + 1)).isoformat()
    assert R._compute_staleness(_meta(last_updated=edge), today=TODAY)[0] is False
    assert R._compute_staleness(_meta(last_updated=over), today=TODAY)[0] is True


BAD_LAST_UPDATED = [None, "", "   ", "2026/11/09", "20261109", "2026-11-9", "2026-13-40",
                    "2026-02-30", "2026-11-09T10:00:00+00:00", 20261109, True, ["2026-11-09"]]


def check_d_missing_or_bad_observation_date(R):
    for bad in BAD_LAST_UPDATED:
        meta = _meta(last_updated=None)             # updated_at 是「剛剛」⇒ 若被拿來頂替就會判 fresh
        if bad is not None:
            meta["last_updated"] = bad
        stale, reason, upd, obs = R._compute_staleness(meta, today=TODAY)
        assert stale is True, f"last_updated={bad!r} 不得判 fresh(updated_at 不可頂替觀測日)"
        assert "觀測日未知" in reason, (bad, reason)
        assert obs is None and upd == _EXEC
    # metadata 整份缺 / 型別不對
    for meta in (None, [], "x", 0):
        stale, reason, _u, obs = R._compute_staleness(meta, today=TODAY)
        assert stale is True and "觀測日未知" in reason and obs is None


def check_e_future_or_contradictory(R):
    # 資料日晚於今日(台北)⇒ 無法判定;觀測日不可信 ⇒ 不外露
    stale, reason, _u, obs = R._compute_staleness(_meta(last_updated="2026-11-12"), today=TODAY)
    assert stale is True and "晚於今日" in reason and "無法判定" in reason and obs is None
    # 矛盾:資料日不晚於今日,卻晚於排程執行日(台北日期)
    stale, reason, _u, obs = R._compute_staleness(
        _meta(last_updated="2026-11-09", updated_at="2026-11-07T16:53:21+00:00"), today=TODAY)
    assert stale is True and "矛盾" in reason and "無法判定" in reason and obs is None


def check_f_weekend_no_new_observation(R):
    fri = "2026-11-06"
    # 週日(11/08)、週一(11/09)、週二(11/10):距週五 2/3/4 日 ≤ 門檻 ⇒ 仍 fresh(不做週末推論,純依門檻)
    for today in (date(2026, 11, 8), date(2026, 11, 9), date(2026, 11, 10)):
        stale, reason, _u, obs = R._compute_staleness(
            _meta(last_updated=fri, updated_at="2026-11-06T16:53:21+00:00"), today=today)
        assert (stale, reason, obs) == (False, None, fri), today
    # 週三(11/11)距週五 5 日 > 門檻 ⇒ stale
    stale, reason, _u, obs = R._compute_staleness(
        _meta(last_updated=fri, updated_at="2026-11-06T16:53:21+00:00"), today=date(2026, 11, 11))
    assert stale is True and "超過" in reason


ALL_CHECKS = [check_a_b_cron_ran_but_data_unchanged, check_c_real_fresh_data,
              check_d_missing_or_bad_observation_date, check_e_future_or_contradictory,
              check_f_weekend_no_new_observation]


def _real():
    import src.data.sector_flow.reader as R
    return R


@pytest.mark.parametrize("chk", ALL_CHECKS, ids=lambda f: f.__name__)
def test_real_reader_passes(chk):
    chk(_real())


def test_threshold_value_unchanged():
    """客戶核准:保留 SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS=4,不得改數值。"""
    assert MAXD == 4


# ═══════════════════════════════════════════════════════════════════════
# read_sector_flow_cache 端到端(tmp 檔 + 注入 today)
# ═══════════════════════════════════════════════════════════════════════
def _point(monkeypatch, tmp_path, meta, *, with_meta=True):
    R = _real()
    monkeypatch.setattr(R, "BUBBLE_PATH", tmp_path / "bubble_latest.json")
    monkeypatch.setattr(R, "META_PATH", tmp_path / "metadata.json")
    monkeypatch.setattr(R, "TICKER_SECTOR_PATH", tmp_path / "ticker_sector.json")
    (tmp_path / "bubble_latest.json").write_text(json.dumps({
        "updated_at": _EXEC, "window_size": 20, "n_trading_days_used": 20, "sectors": []}),
        encoding="utf-8")
    if with_meta:
        (tmp_path / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    return R


def test_read_cache_exposes_observation_date_and_keeps_old_keys(monkeypatch, tmp_path):
    R = _point(monkeypatch, tmp_path, _meta(last_updated="2026-11-09"))
    v = R.read_sector_flow_cache(today=TODAY)
    assert v["ok"] is True and v["is_stale"] is False and v["stale_reason"] is None
    assert v["observation_date"] == "2026-11-09"
    # 向後相容:舊鍵仍在,語意是執行時間
    assert v["updated_at"] == _EXEC and v["meta_updated_at"] == _EXEC


def test_read_cache_cron_rewrote_updated_at_but_data_old_is_stale(monkeypatch, tmp_path):
    R = _point(monkeypatch, tmp_path, _meta(last_updated="2026-10-28", last_error="down"))
    v = R.read_sector_flow_cache(today=TODAY)
    assert v["is_stale"] is True and v["observation_date"] == "2026-10-28"
    assert "超過" in v["stale_reason"] and v["meta_updated_at"] == _EXEC


def test_read_cache_missing_last_updated_and_missing_meta_file(monkeypatch, tmp_path):
    R = _point(monkeypatch, tmp_path, _meta(last_updated=None))
    v = R.read_sector_flow_cache(today=TODAY)
    assert v["is_stale"] is True and v["observation_date"] is None and "觀測日未知" in v["stale_reason"]
    (tmp_path / "nometa").mkdir()
    R = _point(monkeypatch, tmp_path / "nometa", _meta(), with_meta=False)
    v = R.read_sector_flow_cache(today=TODAY)
    assert v["is_stale"] is True and v["observation_date"] is None and "觀測日未知" in v["stale_reason"]


def test_default_today_is_taipei_date(monkeypatch, tmp_path):
    """不注入 today ⇒ 用台北日期:UTC 還是 11/08 16:30,台北已是 11/09 00:30。"""
    R = _point(monkeypatch, tmp_path, _meta(last_updated="2026-11-09", updated_at=_EXEC))
    fake_now = datetime(2026, 11, 8, 16, 30, tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8)))
    monkeypatch.setattr(R, "tw_now", lambda: fake_now)
    v = R.read_sector_flow_cache()
    assert v["is_stale"] is False, "台北已是 11/09,資料日 11/09 不是未來"


def test_real_committed_metadata_has_parseable_observation_date():
    meta = json.loads((REPO / "data_cache/sector_flow/metadata.json").read_text(encoding="utf-8"))
    R = _real()
    assert R._parse_observation_date(meta.get("last_updated")) is not None, \
        "已提交的 metadata.json 應帶嚴格 YYYY-MM-DD 的 last_updated"


# ═══════════════════════════════════════════════════════════════════════
# (g) UI:資料日只顯示可信觀測日
# ═══════════════════════════════════════════════════════════════════════
def _flow(**kw):
    from tests import uit_fakes as U
    return dataclasses.replace(U.make_flow(), **kw)


def test_chip_shows_observation_date_not_cron_time():
    from src.ui.views import _target_blocks as B
    f = _flow(updated_at="2026-11-09T09:00:00+00:00", observation_date="2026-10-30")
    chips = B.industry_chips(f, [], fetched_at=None, aged=False)
    assert chips[0].kind == "asof" and "10/30" in chips[0].text and "11/09" not in chips[0].text
    assert B.basis_industry(f).as_of == "2026-10-30"


def test_chip_missing_observation_date_is_honest_not_substituted():
    from src.ui.views import _target_blocks as B
    f = _flow(updated_at="2026-11-09T09:00:00+00:00", observation_date="")
    chips = B.industry_chips(f, [], fetched_at=None, aged=False)
    assert chips[0].kind == "asof_missing" and "未提供" in chips[0].text
    assert "11/09" not in chips[0].text
    assert "2026-11-09" not in B.basis_industry(f).as_of


def test_card_facts_label_cron_time_as_execution_not_data_date():
    from src.ui.views import page_find as F
    _card, facts = F.build_sector_flow_card(_flow(updated_at="2026-11-09T09:00:00+00:00",
                                                  observation_date="2026-10-30"))
    d = dict(facts)
    assert d.get("排程更新於") == "2026-11-09T09:00:00+00:00"
    assert "快取更新於" not in d and "資料日" not in d      # ⛔ 不得把執行時間標成資料日;不新增 facts 列


def test_degraded_card_why_says_execution_time_is_not_data_date():
    from src.ui.views import page_find as F
    card, _f = F.build_sector_flow_card(_flow(stale=True, stale_reason="資料日 2026-10-30 距今 10 日,超過 4 日門檻",
                                              meta_updated_at="2026-11-09T09:00:00+00:00"))
    assert "不是資料日" in card.note.why and "2026-10-30" in card.note.why


def test_load_sector_flow_maps_observation_date(monkeypatch):
    from src.ui.views import page_find as F
    import src.services.sector_flow_service as svc
    base = {"ok": True, "sectors": [], "updated_at": _EXEC, "meta_updated_at": _EXEC,
            "is_stale": True, "stale_reason": "x"}
    monkeypatch.setattr(svc, "get_sector_flow_view", lambda **k: {**base, "observation_date": "2026-10-30"})
    r = F.load_sector_flow({}, requested=True)
    assert r.observation_date == "2026-10-30" and r.updated_at == _EXEC
    monkeypatch.setattr(svc, "get_sector_flow_view", lambda **k: {**base, "observation_date": None})
    assert F.load_sector_flow({}, requested=True).observation_date == ""


# ═══════════════════════════════════════════════════════════════════════
# (h) 突變:還原核心判斷 ⇒ 對應檢查必須轉紅(以原始碼替換產生突變模組)
# ═══════════════════════════════════════════════════════════════════════
def _mutant_reader(old: str, new: str):
    import types
    src = (REPO / _READER_REL).read_text(encoding="utf-8")
    assert src.count(old) == 1, f"突變錨點漂移:{old!r}"
    mod = types.ModuleType("d1_mutant_reader")
    mod.__file__ = str(REPO / _READER_REL)
    exec(compile(src.replace(old, new), mod.__file__, "exec"), mod.__dict__)
    return mod


def test_mutant_updated_at_substitutes_missing_observation_date_goes_red():
    """還原舊行為:觀測日缺失時拿 updated_at 頂替 ⇒ (d) 必須轉紅。"""
    M = _mutant_reader("    _obs = _parse_observation_date(_raw)\n",
                       "    _obs = _parse_observation_date(_raw) or _parse_observation_date((_upd or '')[:10])\n")
    with pytest.raises(AssertionError):
        check_d_missing_or_bad_observation_date(M)


def test_mutant_age_threshold_disabled_goes_red():
    """拿掉「觀測日距今 > 門檻 ⇒ stale」⇒ (a)(b)(f) 必須轉紅。"""
    M = _mutant_reader("    if _age_days > SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS:\n",
                       "    if False:\n")
    with pytest.raises(AssertionError):
        check_a_b_cron_ran_but_data_unchanged(M)
    with pytest.raises(AssertionError):
        check_f_weekend_no_new_observation(M)


def test_mutant_future_guard_removed_goes_red():
    """拿掉未來日期守衛 ⇒ (e) 必須轉紅。"""
    M = _mutant_reader("    if _obs > _today:\n", "    if False:\n")
    with pytest.raises(AssertionError):
        check_e_future_or_contradictory(M)


def test_mutant_contradiction_guard_removed_goes_red():
    M = _mutant_reader("        if _obs > _upd_tw_date:\n", "        if False:\n")
    with pytest.raises(AssertionError):
        check_e_future_or_contradictory(M)


def test_unmutated_reader_still_green_as_control():
    """對照組:同一套 exec 機制,不替換內容 ⇒ 全綠(證明上面的紅不是 exec 機制造成)。"""
    M = _mutant_reader("    _obs = _parse_observation_date(_raw)\n", "    _obs = _parse_observation_date(_raw)\n")
    for chk in ALL_CHECKS:
        chk(M)
