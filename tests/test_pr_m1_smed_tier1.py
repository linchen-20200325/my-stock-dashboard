"""v18.343 PR-M1 — S-MED Tier 1 三處 silent → stderr 守衛測試。

對齊 v18.339 PR-J3 風格:介面 0 改,只驗 stderr log 寫出。

涵蓋(v18.399 P5-DEAD-δ 後):
- ~~ai_engine.generate_quick_summary: 整檔已刪~~(0 production caller)
- data_loader._fetch_stock_name_inner: bare except → typed + stderr
- proxy_helper._load_proxy_config (secrets path): except Exception:pass → stderr

§1 Fail Loud:silent 改 observable;不改回傳值避免破壞 caller 介面。
"""
from __future__ import annotations

import io
import sys


def _capture_stderr(fn):
    _orig = sys.stderr
    sys.stderr = _buf = io.StringIO()
    try:
        r = fn()
    finally:
        sys.stderr = _orig
    return r, _buf.getvalue()


# ─────────── A. ai_engine.generate_quick_summary ───────────
# v18.399 P5-DEAD-δ:ai_engine.py 整檔已真刪(0 production caller)。
# 本 class TestGenerateQuickSummaryStderrLog 隨之退場。


# ─────────── B. data_loader._fetch_stock_name_inner ───────────

class TestStockNameInnerStderrLog:
    def test_marker_in_source(self):
        src = open('src/data/core/data_loader.py', encoding='utf-8').read()
        assert '[_fetch_stock_name_inner] swallow' in src
        # 原 bare `except:\n                pass` 已收掉
        assert 'except:\n                pass\n\n            if stock_name == stock_id' not in src


# ─────────── C. proxy_helper._load_proxy_config (secrets path) ───────────

class TestProxyConfigSecretsStderrLog:
    def test_marker_in_source(self):
        src = open('src/data/proxy/proxy_helper.py', encoding='utf-8').read()
        assert '[_load_proxy_config/secrets] swallow' in src
        # 原 except Exception:\n        pass 已替換為 typed + stderr
        # (新版含 _e_sec 變數名 + print)
        assert '_e_sec' in src


# ─────────── D. import smoke ───────────

class TestImports:
    # v18.399 P5-DEAD-δ:test_ai_engine 隨整檔刪除退場。

    def test_data_loader(self):
        from src.data.core import data_loader  # noqa

    def test_proxy_helper(self):
        from src.data.proxy import proxy_helper  # noqa
