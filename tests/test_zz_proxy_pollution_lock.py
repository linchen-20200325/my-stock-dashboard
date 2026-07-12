# -*- coding: utf-8 -*-
"""zz — src.data.proxy PEP 562 轉發污染鎖(檔名 zz 前綴 = 字母序最後執行)。

地雷史(兩次實錘):
- v19.74:risk_radar CBOE 4 測全套件連跑 order-dependent 失敗 — 某測試對
  package `src.data.proxy` monkeypatch `fetch_url`,teardown「還原」把真函式
  寫成 package **實體屬性**,永久遮蔽 `__getattr__` 轉發 → 其後測試 patch
  `proxy_helper.fetch_url` 全部打不進 production 的
  `from src.data.proxy import fetch_url`。
- v19.112:test_cache_success_only / test_export_fail_trace 兩新檔重犯同雷,
  CI 紅(test_etf_moneydj_nav_parse 3 測 fixture 失效、GH runner 打真 MoneyDJ
  抓到 30 筆活資料)+ 本地全套 4 failed 同步實錘。

本鎖:跑完全套後,package 的實體命名空間只允許子模組與 _SUBMODULES —
任何被轉發的函式名(fetch_url / get_proxies / get_proxy_config …)一旦變成
實體屬性 = 有測試污染,具名炸出,不再讓下游測試背鍋。
"""
from __future__ import annotations

import pytest

_ALLOWED_CONCRETE = {'proxy_helper', 'yf_proxy', '_SUBMODULES'}


def _assert_forwarding_clean():
    import src.data.proxy as pkg
    concrete = {k for k in vars(pkg)
                if not k.startswith('__') and not k.endswith('__')}
    leaked = concrete - _ALLOWED_CONCRETE
    assert not leaked, (
        f'src.data.proxy 的 PEP 562 轉發被實體屬性遮蔽:{sorted(leaked)} — '
        f'某測試對 package monkeypatch 了這些名字(v19.74/v19.112 地雷)。'
        f'請改 patch 真正持有者 `src.data.proxy.proxy_helper`。')


def test_proxy_forwarding_not_shadowed_fast():
    _assert_forwarding_clean()


@pytest.mark.slow
def test_proxy_forwarding_not_shadowed_slow():
    """slow lane 也鎖(兩 lane 測試集合不同,污染源可能只在其中一邊)。"""
    _assert_forwarding_clean()
