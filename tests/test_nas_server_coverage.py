"""tests/test_nas_server_coverage.py — D 測試覆蓋 #11-19。

Target: src/data/proxy/nas_server.py (L1 NAS 中繼站 fetcher)。

只測 DETERMINISTIC pure helper,絕不發 HTTP:
- _num(s)         — 字串 → float 清洗(去逗號/空白/+,失敗回 None)
- _tw_today()     — TW (UTC+8) 今日 date
- _recent_date()  — 最近一個工作日(週末往前推)的 "YYYYMMDD" 字串

nas_server.py 頂層 `from fastapi import ...` / `from pydantic import ...`,
這兩個套件只裝在 NAS host(不在 dashboard / CI requirements),
故用 importorskip 在缺套件時整檔 graceful SKIP(§ 測試不可發網路 / skip OK)。
網路型 fetcher(_fetch_institutional / _fetch_margin_balance / ...)一律不呼叫。
"""
from __future__ import annotations

import datetime

import pytest

# fastapi / pydantic 只在 NAS host 安裝;缺套件時整檔 graceful skip
pytest.importorskip("fastapi", reason="fastapi 僅裝於 NAS host,非 dashboard/CI 依賴")
pytest.importorskip("pydantic", reason="pydantic 僅裝於 NAS host")

from src.data.proxy import nas_server  # noqa: E402


class TestNum:
    """_num — 寬鬆字串轉 float;清洗千分位逗號 / 空白 / 前綴 +。"""

    def test_plain_integer_string(self):
        assert nas_server._num("123") == 123.0

    def test_thousands_separator_stripped(self):
        # 千分位逗號須移除(TWSE 金額慣用 "1,234,567")
        assert nas_server._num("1,234,567") == 1234567.0

    def test_leading_plus_and_spaces_stripped(self):
        # 三大法人買超常帶 "+" 與空白
        assert nas_server._num("+ 1,500 ") == 1500.0

    def test_decimal_preserved(self):
        assert nas_server._num("3.14") == pytest.approx(3.14)

    def test_negative_value(self):
        # 賣超為負,負號不可被吃掉(只去 "+" 不去 "-")
        assert nas_server._num("-2,000") == -2000.0

    def test_numeric_input_passthrough(self):
        # 非字串輸入也能轉(str() 包裹)
        assert nas_server._num(42) == 42.0
        assert nas_server._num(42.5) == pytest.approx(42.5)

    def test_non_numeric_returns_none(self):
        # 無法轉換 → None(§1 fail-safe,不捏造 0)
        assert nas_server._num("abc") is None
        assert nas_server._num("") is None
        assert nas_server._num("--") is None

    def test_none_input_returns_none(self):
        # None → "None" 無法 float → None(不爆例外)
        assert nas_server._num(None) is None


class TestTwToday:
    """_tw_today — 回傳 TW (UTC+8) 當日 date。"""

    def test_returns_date_instance(self):
        d = nas_server._tw_today()
        assert isinstance(d, datetime.date)

    def test_matches_utc_plus_8(self):
        # 與手算 UTC+8 同日(允許測試跨午夜邊界容差 1 天)
        expected = datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=8))
        ).date()
        diff = abs((nas_server._tw_today() - expected).days)
        assert diff <= 1


class TestRecentDate:
    """_recent_date — 最近工作日(週六/日往前推)的 YYYYMMDD 字串。"""

    def test_format_is_yyyymmdd(self):
        ds = nas_server._recent_date()
        assert len(ds) == 8 and ds.isdigit()
        # 可被解析回 date
        parsed = datetime.datetime.strptime(ds, "%Y%m%d").date()
        assert isinstance(parsed, datetime.date)

    def test_result_is_a_weekday(self):
        # weekday() 0..4 = 週一~週五;週末必被推回
        ds = nas_server._recent_date()
        parsed = datetime.datetime.strptime(ds, "%Y%m%d").date()
        assert parsed.weekday() < 5

    def test_not_in_future(self):
        # 最近工作日不可晚於 TW 今日
        ds = nas_server._recent_date()
        parsed = datetime.datetime.strptime(ds, "%Y%m%d").date()
        assert parsed <= nas_server._tw_today()


class TestModuleSurface:
    """import smoke + public attribute 存在性(不觸發任何網路)。"""

    def test_helpers_callable(self):
        assert callable(nas_server._num)
        assert callable(nas_server._tw_today)
        assert callable(nas_server._recent_date)

    def test_fastapi_app_present(self):
        # FastAPI app 物件存在(僅檢查屬性,不啟動 server)
        assert nas_server.app is not None
        assert hasattr(nas_server, "FetchReq")

    def test_prov_log_shim_swallows_errors(self):
        # _prov_log 是 backward-compat shim,內部 try/except 不可外洩例外
        # (§2.2 provenance audit trail 不可阻斷主流程)
        nas_server._prov_log("unit_test", "test:source", "summary")


class TestSsrfGuard:
    """v19.86 第八份 review D:_assert_public_url SSRF 防護。

    只做 DNS 解析(不發 HTTP),擋內網/metadata/localhost,放行公開站。
    """

    def _raises_http(self, url):
        from fastapi import HTTPException
        try:
            nas_server._assert_public_url(url)
            return None
        except HTTPException as e:
            return e.status_code

    def test_blocks_cloud_metadata_endpoint(self):
        # 169.254.169.254 = 雲端 metadata(AWS/GCP);SSRF 最經典目標
        assert self._raises_http("http://169.254.169.254/latest/meta-data/") == 403

    def test_blocks_loopback(self):
        assert self._raises_http("http://127.0.0.1:8765/") == 403
        assert self._raises_http("http://localhost/admin") == 403
        assert self._raises_http("http://[::1]/") == 403

    def test_blocks_private_ranges(self):
        assert self._raises_http("http://192.168.1.1/") == 403
        assert self._raises_http("http://10.0.0.5/x") == 403
        assert self._raises_http("http://0.0.0.0/") == 403

    def test_blocks_non_http_scheme(self):
        assert self._raises_http("ftp://evil.example/x") == 400
        assert self._raises_http("file:///etc/passwd") == 400

    def test_blocks_missing_host(self):
        assert self._raises_http("http:///nohost") == 400

    def test_allows_public_dashboard_hosts(self):
        # 儀表板實際會抓的公開站不可被誤擋(解析為公網 IP)
        for ok in ("https://www.twse.com.tw/x",
                   "https://api.finmindtrade.com/x",
                   "https://fred.stlouisfed.org/x"):
            assert self._raises_http(ok) is None, f"誤擋公開站 {ok}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
