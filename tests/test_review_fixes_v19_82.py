"""tests/test_review_fixes_v19_82.py — 第五份外部 review 查證後修復守護。

TARGET:
- src/data/daily/daily_data_fetchers.py   (Bug D:_fetch_otc_via_finmind 死參數+凍結快照)
- src/data/core/data_loader.py            (UA 補漏 ×2 + 裸 except 收窄 ×4)
- src/data/stock/share_capital_fetcher.py (UA 補漏)
- src/data/etf/etf_fetch.py               (UA 補漏)
- app.py                                  (版號 v4.0 Pro / v3.0 同畫面矛盾)

查證裁決:其餘主張為已修過/誤判 — 詳 PR 描述。
"""
from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


def _src(rel: str) -> str:
    return (_REPO / rel).read_text(encoding="utf-8")


# ══════════════════════════════════════════════════════════════
# Bug D — _fetch_otc_via_finmind:token 參數不再是死參數
# ══════════════════════════════════════════════════════════════
class TestOtcTokenParam:
    def test_param_token_passes_gate_even_when_snapshot_frozen_empty(self, monkeypatch):
        """舊行為:module-level FINMIND_TOKEN 凍結空值 → 不論傳什麼 token 都在
        閘門 return None。新行為:token 參數優先 + 動態重讀,應通過閘門觸發抓取。"""
        from src.data.daily import daily_data_fetchers as D

        monkeypatch.setattr(D, "FINMIND_TOKEN", "", raising=True)
        monkeypatch.setattr(D, "_get_finmind_token", lambda: "", raising=True)

        calls: list = []

        class _HaltFetch(Exception):
            pass

        class _FakeSession:
            def get(self, *a, **k):
                calls.append(k.get("headers", {}))
                raise _HaltFetch("halt-after-gate")

        monkeypatch.setattr(D, "_bps", lambda: _FakeSession(), raising=True)
        logs: list = []
        monkeypatch.setattr(D, "_prov_log", lambda *a: logs.append(a), raising=True)

        out = D._fetch_otc_via_finmind("TOKEN_V1982_TEST")
        assert out is None
        assert calls, "傳入 token 應通過閘門觸發抓取(舊版在閘門就 return None)"
        # 順帶驗 UA 補漏:headers 走 _fm_raw_headers → UA + Authorization 都在
        assert "User-Agent" in calls[0], "S8 UA 補漏:OTC 呼叫應帶 User-Agent"
        assert calls[0].get("Authorization") == "Bearer TOKEN_V1982_TEST"
        assert any("exc" in str(rec[-1]) for rec in logs), "應走到 fetch 失敗路徑而非 no-token"

    def test_no_token_still_gates_cleanly(self, monkeypatch):
        from src.data.daily import daily_data_fetchers as D

        monkeypatch.setattr(D, "FINMIND_TOKEN", "", raising=True)
        monkeypatch.setattr(D, "_get_finmind_token", lambda: "", raising=True)
        logs: list = []
        monkeypatch.setattr(D, "_prov_log", lambda *a: logs.append(a), raising=True)
        assert D._fetch_otc_via_finmind("") is None
        assert any("no-token" in str(rec[-1]) for rec in logs)

    def test_source_no_frozen_snapshot_in_function_body(self):
        src = _src("src/data/daily/daily_data_fetchers.py")
        body = src.split("def _fetch_otc_via_finmind")[1].split("\ndef ")[0]
        assert "_tok = token or _get_finmind_token()" in body
        # 函式體內不得再讀 module-level 凍結快照(定義行之外)
        assert "if not FINMIND_TOKEN" not in body
        assert 'f"Bearer {FINMIND_TOKEN}"' not in body


# ══════════════════════════════════════════════════════════════
# UA 補漏 — S8 v19.78 漏網 4 站全補 _fm_raw_headers
# ══════════════════════════════════════════════════════════════
class TestFinMindUASweep:
    def test_data_loader_two_sites(self):
        src = _src("src/data/core/data_loader.py")
        assert src.count("headers=_fm_raw_headers('')") == 2, \
            "fetch_industry_category + fetch_bps 兩站應補 UA-only headers"

    def test_share_capital_site(self):
        src = _src("src/data/stock/share_capital_fetcher.py")
        assert "_fm_hdrs_sc('')" in src

    def test_etf_zh_name_site(self):
        src = _src("src/data/etf/etf_fetch.py")
        assert "_fm_hdrs_fn('')" in src

    def test_no_remaining_naked_finmind_get(self):
        """FINMIND_API_URL 的 requests 呼叫不得再有「無 headers」寫法。"""
        import re
        for rel in ("src/data/core/data_loader.py",
                    "src/data/stock/share_capital_fetcher.py",
                    "src/data/etf/etf_fetch.py"):
            src = _src(rel)
            for m in re.finditer(r"\.get\(\s*FINMIND_API_URL[^)]*\)", src, re.S):
                assert "headers=" in m.group(0), f"{rel} 存在無 headers 的 FinMind 呼叫"


# ══════════════════════════════════════════════════════════════
# 裸 except 收窄(§3.3)— data_loader 4 站
# ══════════════════════════════════════════════════════════════
class TestBareExceptNarrowed:
    def test_no_bare_except_left_in_data_loader(self):
        import re
        src = _src("src/data/core/data_loader.py")
        bare = re.findall(r"except\s*:", src)
        assert not bare, f"data_loader 仍有 {len(bare)} 個裸 except"


# ══════════════════════════════════════════════════════════════
# 版號統一 — 同畫面不得再出現 v4.0
# ══════════════════════════════════════════════════════════════
class TestVersionBadgeUnified:
    def test_no_v4_badge(self):
        src = _src("app.py")
        assert "v4.0 Pro" not in src
        assert "台股AI戰情室 v3.0" in src or "台股 AI 戰情室" in src
