"""tests/test_review_fixes_v19_82.py — 第五份外部 review 查證後修復守護。

TARGET:
- src/data/daily/daily_data_fetchers.py   (Bug D:_fetch_otc_via_finmind 死參數+凍結快照)
- src/data/core/data_loader.py            (UA 補漏 ×2 + 裸 except 收窄 ×4)
- src/data/stock/share_capital_fetcher.py (UA 補漏)
- src/data/etf/etf_fetch.py               (UA 補漏)
- app.py                                  (版號 v4.0 Pro / v3.0 同畫面矛盾)

查證裁決:其餘主張為已修過/誤判 — 詳 PR 描述。

⚠️ v19.170 更新:P0-3 資安推翻了本輪「token 維持走 query string」的決定,
   FinMind 憑證改走 `Authorization: Bearer` header。`TestFinMindUASweep`
   的斷言已同步更新為新契約(UA 的原意圖保留),詳見該 class docstring。
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
    """FinMind raw REST 三站(四個呼叫點)的 headers 契約守護。

    v19.78 S8 原始意圖:這幾站是手刻 requests 呼叫、沒帶 User-Agent
    (requests 預設 `python-requests/x.x` 易被上游辨識限流),必須改走
    `data_loader._fm_raw_headers` 這個 SSOT header builder。

    ⚠️ v19.170 P0-3 資安**推翻**了 v19.82 當時的其中一條決定 ——
    原本是「token 維持走 query string(`params`),headers 只補 UA」,所以這些站
    一律傳 `_fm_raw_headers('')`(空字串 = 不組 Authorization)。該決定不成立:
    **憑證進 query string 會被 proxy / API gateway / server access log 明文記錄**,
    而 FinMind token 等同帳號憑證。故改為只走 `Authorization: Bearer`。

    現行契約(本 class 守的三件事):
      1. header builder 收到的是**真 token 變數**(`_tok`),不再是 `''`
      2. `params` 不得再含 token
      3. v19.78 的原意圖仍在 —— header builder 依舊帶 User-Agent(不得被順手弄丟)
    """

    _FINMIND_SITES = ("src/data/core/data_loader.py",
                      "src/data/stock/share_capital_fetcher.py",
                      "src/data/etf/etf_fetch.py")

    def test_header_builder_keeps_ua_and_adds_bearer(self):
        """v19.78 的 UA 補漏不得被 v19.170 的憑證搬家順手弄丟(原意圖保留)。"""
        src = _src("src/data/core/data_loader.py")
        body = src.split("def _fm_raw_headers(")[1].split("\ndef ")[0]
        assert "'User-Agent': _FM_UA" in body, "S8 v19.78 UA 補漏不得回退"
        assert "h['Authorization'] = f'Bearer {token}'" in body, \
            "v19.170:憑證必須由 header builder 組 Authorization: Bearer"

    def test_data_loader_two_sites(self):
        """fetch_industry_category + fetch_bps_from_finmind 兩站帶真 token。"""
        src = _src("src/data/core/data_loader.py")
        for _fn in ("fetch_industry_category", "fetch_bps_from_finmind"):
            body = src.split(f"def {_fn}(")[1].split("\ndef ")[0]
            assert "headers=_fm_raw_headers(_tok)" in body, \
                f"{_fn} 應把真 token 交給 header builder(v19.170)"
        assert "_fm_raw_headers('')" not in src, \
            "全檔不得殘留 v19.82 舊契約(空字串 = 完全沒有 Authorization)"

    def test_share_capital_site(self):
        src = _src("src/data/stock/share_capital_fetcher.py")
        # UA 來源仍是 data_loader 的 SSOT builder(v19.78 原意圖)
        assert "import _fm_raw_headers as _fm_hdrs_sc" in src
        assert "headers=_fm_hdrs_sc(_tok)" in src, "v19.170:應傳真 token"
        assert "_fm_hdrs_sc('')" not in src

    def test_etf_zh_name_site(self):
        src = _src("src/data/etf/etf_fetch.py")
        assert "import _fm_raw_headers as _fm_hdrs_fn" in src
        assert "headers=_fm_hdrs_fn(_tok)" in src, "v19.170:應傳真 token"
        assert "_fm_hdrs_fn('')" not in src

    def test_no_token_in_query_string(self):
        """v19.170 P0-3:三站的 params 都不得再帶 token(憑證不進 access log)。"""
        import re
        _token_key = re.compile(r"""['"]token['"]\s*:""")
        for rel in self._FINMIND_SITES:
            _hit = _token_key.search(_src(rel))
            assert _hit is None, \
                f"{rel} 仍把 token 放進 query string({_hit.group(0) if _hit else ''})"

    def test_no_remaining_naked_finmind_get(self):
        """FINMIND_API_URL 的 requests 呼叫不得再有「無 headers」寫法。"""
        import re
        for rel in self._FINMIND_SITES:
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
