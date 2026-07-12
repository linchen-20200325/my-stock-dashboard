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

    def json(self):
        raise ValueError('not json')


@pytest.mark.parametrize('name,fn', PMI_SOURCE_REGISTRY,
                         ids=[n for n, _ in PMI_SOURCE_REGISTRY])
def test_garbage_200_leaves_trace(name, fn, monkeypatch):
    """200+垃圾內容:8 源全數必須寫 errs(不得靜默)。"""
    from src.data.proxy import proxy_helper as _ph   # patch 真持有者(v19.74 雷)
    monkeypatch.setattr(_ph, 'fetch_url', lambda *a, **k: _GarbageResp())
    errs: list[str] = []
    out = fn(_TODAY, 90, errs)
    assert out is None, f'{name} 垃圾內容不得回值(§1 不捏造)'
    assert errs, f'{name} 200+garbage 必須留痕(SPEC §4),errs 竟為空'


@pytest.mark.parametrize('name,fn', PMI_SOURCE_REGISTRY,
                         ids=[n for n, _ in PMI_SOURCE_REGISTRY])
def test_no_response_leaves_trace(name, fn, monkeypatch):
    """全 None(斷線):8 源全數必須寫 errs。"""
    from src.data.proxy import proxy_helper as _ph
    monkeypatch.setattr(_ph, 'fetch_url', lambda *a, **k: None)
    errs: list[str] = []
    out = fn(_TODAY, 90, errs)
    assert out is None
    assert errs, f'{name} 無回應必須留痕(SPEC §4),errs 竟為空'


def test_cnyes_no_bare_except_pass():
    """§3.3:Cnyes 段的 `except: pass  # 靜默失敗` 已修,不得回歸。"""
    from pathlib import Path
    body = (Path(__file__).resolve().parent.parent /
            'src/data/macro/macro_core.py').read_text(encoding='utf-8')
    assert '鉅亨可能改 API，靜默失敗' not in body, 'except:pass 靜默註解應已移除'
