# -*- coding: utf-8 -*-
"""v19.114 — PMI 8 源「每段失敗必留痕」行為鎖(SPEC §4 設計原則落地)。

背景(user 錯誤碼面板截圖實錘):8 源全敗時 token 只見 NDC/dgtw/CIER-cid8,
CIER-EN/CIER/StockFeel/Cnyes/MoneyDJ 五源**完全無痕** — 解析器在「200 但
解析不中」「無回應」等路徑靜默返回,違反 SPEC §4 白紙黑字「每段失敗都必須
寫入 errs」;Cnyes 更有字面 `except: pass`(§3.3 違憲)。

三個最容易出錯的輸入(§6):
1. 200 + 垃圾 HTML(改版/攔截殼)→ 每源必須留痕(本檔主鎖)
2. 全 None(斷線)→ 每源必須留痕
3. Cnyes JSON 炸掉 → 不得再 except:pass 靜默

⚠️ v19.121 — **patch 目標更正 + 反空轉守衛**(CI run 33103157123 紅燈實錘)：
本檔原本 patch `proxy_helper.fetch_url`,那是抄自 `test_export_fail_trace_v19_112`
的寫法 —— 但**那一招只對「函式內 lazy import」的模組成立**。
`macro_snapshot` / `risk_radar` / `etf_fetch` 都在函式體內寫
`from src.data.proxy import fetch_url`,每次呼叫才經 PEP 562 `__getattr__` 轉發
到 `proxy_helper`,故 patch `proxy_helper` 打得進去;
而 **8 個 PMI src fn 全住在 `macro_core`,該檔在 module top(line 39)寫
`from src.data.proxy import fetch_url`** —— 那是 import 當下就綁死的**另一個
binding**,patch `proxy_helper` **完全動不到它**。

後果:本檔 16 個參數化測試**從 v19.114 起一路是空轉的** —— 8 源真的去打了外網,
沙箱 CONNECT 403 → 全回 None → 斷言 vacuously 通過。CI 有外網,其餘 7 源對真實
網路本來就抓不到(站台改版/404),**唯獨 data.gov.tw 是活的** → v19.120 把它的
shape 接對之後,它真的回了 61.5 → 兩條 dgtw 測試翻紅。
**紅的是對的:它抓到的是「這個 mock 從來沒生效」這件事實,不是 dgtw 的 bug。**

修法(不動任何斷言意圖):patch **真正被呼叫的 binding** `macro_core.fetch_url`
(全 repo 慣例:`test_dgtw_pmi_shape_v19_120` / `test_review_fixes_v19_78` /
`test_tw_macro_policy` 對 macro_core 都是這樣 patch),並新增
**反空轉守衛** —— 斷言 mock 真的被呼叫過。往後若有人再 patch 錯 binding,
測試會當場說「你的 mock 沒生效」,而不是靜靜地變綠。
⚠️ 連帶效果:本檔自此**完全不碰網路**,兩種環境(有網/無網)行為一致。
"""
from __future__ import annotations

import datetime

import pytest

from src.data.macro.macro_core import PMI_SOURCE_REGISTRY

_TODAY = datetime.date(2026, 7, 12)


class _GarbageResp:
    """200 但內容無關(站改版/攔截殼)— 今日雲端 CIER-EN 實況。"""
    status_code = 200
    text = '<html><body>maintenance page nothing relevant</body></html>'
    encoding = 'utf-8'
    # v19.121:dgtw 的 CSV 下載段讀 `.content`(非 .text)。目前 metadata 段就會
    # 先擋下來走不到那裡,但替身缺這個屬性會讓「哪天走到了」變成 AttributeError
    # 而非誠實的 no-parse — 補齊,讓垃圾回應在每條路徑都是「垃圾」而不是「爆炸」。
    content = b'<html><body>maintenance page nothing relevant</body></html>'

    def json(self):
        raise ValueError('not json')


class _CountingFetch:
    """固定回同一個替身,並記錄被呼叫次數(反空轉守衛用)。"""

    def __init__(self, resp):
        self._resp = resp
        self.calls = 0

    def __call__(self, *a, **k):
        self.calls += 1
        return self._resp


@pytest.mark.parametrize('name,fn', PMI_SOURCE_REGISTRY,
                         ids=[n for n, _ in PMI_SOURCE_REGISTRY])
def test_garbage_200_leaves_trace(name, fn, monkeypatch):
    """200+垃圾內容:8 源全數必須寫 errs(不得靜默)。"""
    from src.data.macro import macro_core as _mc   # patch 真 binding(見檔頭 v19.121)
    _fake = _CountingFetch(_GarbageResp())
    monkeypatch.setattr(_mc, 'fetch_url', _fake)
    errs: list[str] = []
    out = fn(_TODAY, 90, errs)
    assert _fake.calls, (
        f'{name} 一次都沒呼叫到被 patch 的 fetch_url — mock 沒生效,'
        f'本測試等於空轉(v19.121 反空轉守衛;patch 目標寫錯就會踩到這裡)')
    assert out is None, f'{name} 垃圾內容不得回值(§1 不捏造)'
    assert errs, f'{name} 200+garbage 必須留痕(SPEC §4),errs 竟為空'


@pytest.mark.parametrize('name,fn', PMI_SOURCE_REGISTRY,
                         ids=[n for n, _ in PMI_SOURCE_REGISTRY])
def test_no_response_leaves_trace(name, fn, monkeypatch):
    """全 None(斷線):8 源全數必須寫 errs。"""
    from src.data.macro import macro_core as _mc
    _fake = _CountingFetch(None)
    monkeypatch.setattr(_mc, 'fetch_url', _fake)
    errs: list[str] = []
    out = fn(_TODAY, 90, errs)
    assert _fake.calls, (
        f'{name} 一次都沒呼叫到被 patch 的 fetch_url — mock 沒生效,'
        f'本測試等於空轉(v19.121 反空轉守衛)')
    assert out is None
    assert errs, f'{name} 無回應必須留痕(SPEC §4),errs 竟為空'


def test_cnyes_no_bare_except_pass():
    """§3.3:Cnyes 段的 `except: pass  # 靜默失敗` 已修,不得回歸。"""
    from pathlib import Path
    body = (Path(__file__).resolve().parent.parent /
            'src/data/macro/macro_core.py').read_text(encoding='utf-8')
    assert '鉅亨可能改 API，靜默失敗' not in body, 'except:pass 靜默註解應已移除'
