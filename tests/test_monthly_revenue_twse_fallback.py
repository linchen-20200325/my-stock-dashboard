"""test_monthly_revenue_twse_fallback.py — 致命03 去 FinMind 單點:月營收 TWSE/TPEx
OpenAPI keyless fallback 的**純轉換**單測(offline,不打網路)。

覆蓋:
- 民國年月 → 西元日期(`_roc_ym_to_date`)
- 營收字串清洗(千分位逗號 / 空 / '-' / 非數)(`_clean_revenue_amount`)
- raw JSON records → [{stock_id, date, revenue(元)}](`_parse_twse_revenue_records`)
  ★ §4.1 單位陷阱 golden:「營業收入-當月營收」千元 × 1000 = 元(對齊 FinMind)
- Fail-Loud:非數字代號 / 缺年月 / 缺營收 / 非正營收 → 略過該筆(§1 不造假)

網路 I/O(`_batch_twse_openapi` / 公開 orchestrator 的 fallback 分支)在真 GitHub
Actions run(NAS proxy,TW IP)驗證 — 本 sandbox 封 TW gov 站無法打(§7 已註)。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import src.data.proxy as _proxy_pkg  # noqa: E402
from src.data.stock import monthly_revenue_fetcher as MR  # noqa: E402
from src.data.stock.monthly_revenue_fetcher import (  # noqa: E402
    _batch_twse_openapi,
    _clean_revenue_amount,
    _first_field,
    _parse_twse_revenue_records,
    _roc_ym_to_date,
    fetch_batch_monthly_revenue,
)


class _FakeResp:
    """最小 requests.Response 替身(status_code + json)。"""

    def __init__(self, payload, status=200):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _clear_mr_cache():
    """清 @st.cache_data 快取,避免 orchestrator 測試間相同 args 命中前一筆結果。"""
    for _fn in (MR.fetch_batch_monthly_revenue, MR.fetch_monthly_revenue):
        try:
            _fn.clear()
        except Exception:
            pass
    yield


def _install_fake_fetch(monkeypatch, twse_payload, tpex_payload):
    """把 src.data.proxy.fetch_url 換成回固定 JSON 的替身(offline,不打網路)。"""
    def _fake(url, headers=None, params=None, timeout=20, attempts=3):
        if "openapi.twse.com.tw" in url:
            return _FakeResp(twse_payload)
        if "tpex.org.tw" in url:
            return _FakeResp(tpex_payload)
        return _FakeResp([], status=404)
    monkeypatch.setattr(_proxy_pkg, "fetch_url", _fake, raising=False)


# ─────────────────────────────────────────────── 民國年月 → 西元
def test_roc_ym_to_date_normal():
    assert _roc_ym_to_date("11505") == "2026-05-01"   # 民國115年5月
    assert _roc_ym_to_date("11512") == "2026-12-01"
    assert _roc_ym_to_date("11401") == "2025-01-01"   # 民國114年1月
    assert _roc_ym_to_date("10001") == "2011-01-01"   # 民國100年 = 2011


def test_roc_ym_to_date_bad_returns_none():
    # §1 不臆造:壞值一律 None
    assert _roc_ym_to_date("") is None
    assert _roc_ym_to_date("abc") is None
    assert _roc_ym_to_date("115") is None       # 太短 → month '15' 非法
    assert _roc_ym_to_date("11500") is None     # month 00 非法
    assert _roc_ym_to_date("11513") is None     # month 13 非法
    assert _roc_ym_to_date("  11505  ") == "2026-05-01"   # 前後空白容忍


# ─────────────────────────────────────────────── 營收字串清洗
def test_clean_revenue_amount_variants():
    assert _clean_revenue_amount("2,392,022") == 2392022.0   # 千分位逗號
    assert _clean_revenue_amount("2392022") == 2392022.0
    assert _clean_revenue_amount("0") == 0.0                  # 0 由 parser 端剔除
    assert _clean_revenue_amount(1513000) == 1513000.0        # 已是數字型


def test_clean_revenue_amount_bad_returns_none():
    for bad in ("", "-", "N/A", "None", "nan", "abc", None):
        assert _clean_revenue_amount(bad) is None


# ─────────────────────────────────────────────── raw records → rows(★ 單位 golden)
def test_parse_unit_trap_thousand_to_yuan():
    """★ §4.1 千元 → 元:TWSE 回 2392022(千元)→ 落地 2,392,022,000 元(對齊 FinMind)。

    真實案例(TLOGBen/stock-viewer 註記):1513 2026-05 = 2392022 千元 = 23.92 億。
    """
    recs = [{
        "公司代號": "1513", "公司名稱": "中興電",
        "資料年月": "11505", "營業收入-當月營收": "2,392,022",
    }]
    out = _parse_twse_revenue_records(recs, market="上市")
    assert len(out) == 1
    row = out[0]
    assert row["stock_id"] == "1513"
    assert row["date"] == "2026-05-01"
    # 千元 × 1000 = 元 —— 若忘了 ×1000 會是 2392022,差 1000 倍
    assert row["revenue"] == 2392022.0 * 1000
    assert row["revenue"] == 2_392_022_000.0


def test_parse_multiple_and_sort_agnostic():
    recs = [
        {"公司代號": "2330", "資料年月": "11505", "營業收入-當月營收": "263,714,000"},
        {"公司代號": "2317", "資料年月": "11505", "營業收入-當月營收": "500,000"},
    ]
    out = _parse_twse_revenue_records(recs)
    got = {r["stock_id"]: r["revenue"] for r in out}
    assert got["2330"] == 263_714_000.0 * 1000
    assert got["2317"] == 500_000.0 * 1000
    assert all(r["date"] == "2026-05-01" for r in out)


def test_parse_fail_loud_skips_bad_rows():
    recs = [
        {"公司代號": "0050", "資料年月": "11505", "營業收入-當月營收": "1000"},   # ETF-like 但純數字 → 收
        {"公司代號": "1101B", "資料年月": "11505", "營業收入-當月營收": "1000"},  # 非純數字代號 → 略過
        {"公司代號": "2330", "資料年月": "", "營業收入-當月營收": "1000"},        # 缺年月 → 略過
        {"公司代號": "2331", "資料年月": "11505", "營業收入-當月營收": ""},        # 缺營收 → 略過
        {"公司代號": "2332", "資料年月": "11505", "營業收入-當月營收": "0"},       # 非正 → 略過(§1)
        {"公司代號": "2333", "資料年月": "11505", "營業收入-當月營收": "-5"},      # 負 → 略過
        {"公司代號": "2334", "資料年月": "11505"},                                # 無營收欄 → 略過
        "not-a-dict",                                                             # 壞型別 → 略過
    ]
    out = _parse_twse_revenue_records(recs)
    codes = {r["stock_id"] for r in out}
    assert codes == {"0050"}     # 僅合法 1 筆存活,其餘顯式剔除不造假


def test_parse_empty_and_non_list():
    assert _parse_twse_revenue_records([]) == []
    assert _parse_twse_revenue_records(None) == []
    assert _parse_twse_revenue_records("garbage") == []
    assert _parse_twse_revenue_records([{}]) == []   # 空 dict → 無代號 → 略過


def test_first_field_english_fallback():
    # 容錯中英欄名(部分 OpenAPI 變體用 'Code')
    assert _first_field({"公司代號": "2330"}, ("公司代號", "Code")) == "2330"
    assert _first_field({"Code": "2330"}, ("公司代號", "Code")) == "2330"
    assert _first_field({"其他": "x"}, ("公司代號", "Code")) is None
    assert _first_field({"公司代號": "  "}, ("公司代號", "Code")) is None   # 空白視為缺


# ─────────────────────────────────────────────── I/O 編排(monkeypatch fetch_url,offline)
def test_batch_twse_openapi_builds_df(monkeypatch):
    """上市 + 上櫃 兩端點合併 → df(stock_id/date/revenue 元)+ provenance attrs。"""
    _install_fake_fetch(
        monkeypatch,
        twse_payload=[{"公司代號": "2330", "資料年月": "11505",
                       "營業收入-當月營收": "263,714,000"}],   # 上市
        tpex_payload=[{"公司代號": "6488", "資料年月": "11505",
                       "營業收入-當月營收": "1,000"}],          # 上櫃
    )
    df = _batch_twse_openapi()
    assert list(df.columns) == ["stock_id", "date", "revenue"]
    assert set(df["stock_id"]) == {"2330", "6488"}            # 兩市場都併進來
    assert str(df["revenue"].dtype) == "float64"
    got = dict(zip(df["stock_id"], df["revenue"]))
    assert got["2330"] == 263_714_000.0 * 1000                # 千元 → 元
    assert got["6488"] == 1_000.0 * 1000
    assert pd.api.types.is_datetime64_any_dtype(df["date"])
    assert "TWSE-OpenAPI:t187ap05_L" in df.attrs.get("source", "")   # §2.2 provenance
    assert df.attrs.get("fetched_at")


def test_batch_twse_openapi_all_empty_returns_empty(monkeypatch):
    """兩端點皆空 → 回空 df(§1 不造假、不寫空表)。"""
    _install_fake_fetch(monkeypatch, twse_payload=[], tpex_payload=[])
    assert _batch_twse_openapi().empty


def test_orchestrator_falls_back_when_finmind_empty(monkeypatch):
    """FinMind 回空 → 公開 fetch_batch_monthly_revenue 自動改走 TWSE fallback(去單點)。"""
    monkeypatch.setattr(MR, "_batch_finmind", lambda months=18: pd.DataFrame())   # FinMind 全敗
    _install_fake_fetch(
        monkeypatch,
        twse_payload=[{"公司代號": "2317", "資料年月": "11505",
                       "營業收入-當月營收": "500,000"}],
        tpex_payload=[],
    )
    df = fetch_batch_monthly_revenue()
    assert not df.empty
    assert df.iloc[0]["stock_id"] == "2317"
    assert df.iloc[0]["revenue"] == 500_000.0 * 1000


def test_orchestrator_prefers_finmind_when_present(monkeypatch):
    """FinMind 有資料 → 直接用,不觸發 fallback(不打 OpenAPI)。"""
    finmind_df = pd.DataFrame({"stock_id": ["9999"], "date": pd.to_datetime(["2026-05-01"]),
                               "revenue": [1.23e9]})
    monkeypatch.setattr(MR, "_batch_finmind", lambda months=18: finmind_df)

    def _boom(*a, **k):
        raise AssertionError("FinMind 有資料時不該呼叫 OpenAPI fallback")
    monkeypatch.setattr(_proxy_pkg, "fetch_url", _boom, raising=False)

    df = fetch_batch_monthly_revenue()
    assert df.iloc[0]["stock_id"] == "9999"
