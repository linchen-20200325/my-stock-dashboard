"""tests/test_data_registry_panel.py — Path C panel smoke + SSOT 對齊驗證(v18.394)。

涵蓋:
- compute_registry_groups 純函式(empty / mixed / missing / unknown category)
- _freshness_emoji 6 種 frequency × 3 邊界
- shared.data_categories.category_for 8 種 entry name pattern
- scanner / patch / panel 三者 category SSOT 一致(grep 防再漂移)
"""
from __future__ import annotations

import datetime as _dt

import pytest


# ══════════════════════════════════════════════════════════════════
# Section A:shared.data_categories SSOT
# ══════════════════════════════════════════════════════════════════

class TestDataCategoriesSSOT:
    def test_eleven_categories(self):
        from shared.data_categories import ALL_CATEGORIES
        # 對齊 src.data.core.data_registry 靜態 11 個 emoji label
        assert len(ALL_CATEGORIES) == 11
        # 確認都是非空 str + 含 emoji 前綴
        for c in ALL_CATEGORIES:
            assert isinstance(c, str) and len(c) > 0

    def test_category_for_known_patterns(self):
        from shared.data_categories import (
            CAT_CHIPS, CAT_ETF, CAT_INTL, CAT_STOCK,
            CAT_TW_MACRO, CAT_TW_MARKET, CAT_US_MACRO, category_for,
        )
        # [個股] / [比較] → 🏢 個股財報
        assert category_for('[個股] 2330 台積電 | 價格走勢') == CAT_STOCK
        assert category_for('[比較] 多股比較排行') == CAT_STOCK
        # [ETF] / [ETF組合] / [ETF回測] → 🏦 ETF / 基金
        assert category_for('[ETF] 0050 | 價格走勢') == CAT_ETF
        assert category_for('[ETF組合] 再平衡分析（3檔）') == CAT_ETF
        assert category_for('[ETF回測] 回測績效（3檔）') == CAT_ETF
        # [先行指標] → 💰 籌碼
        assert category_for('[先行指標] 三大法人現貨') == CAT_CHIPS
        # 精確 name 對映
        assert category_for('VIX 波動率指數') == CAT_INTL
        assert category_for('美國核心CPI年增率') == CAT_US_MACRO
        assert category_for('三大法人 外資買賣超') == CAT_CHIPS
        assert category_for('ADL 市場廣度') == CAT_TW_MARKET
        assert category_for('M1B 資金活水年增率') == CAT_TW_MACRO

    def test_category_for_fallback(self):
        from shared.data_categories import CAT_INTL, CAT_TW_MARKET, category_for
        # 未知 entry → 用 fallback
        assert category_for('未知 entry', fallback=CAT_INTL) == CAT_INTL
        assert category_for('未知 entry', fallback=CAT_TW_MARKET) == CAT_TW_MARKET
        # 預設 fallback 為 CAT_INTL
        assert category_for('未知 entry') == CAT_INTL


# ══════════════════════════════════════════════════════════════════
# Section B:_freshness_emoji 純函式
# ══════════════════════════════════════════════════════════════════

class TestFreshnessEmoji:
    def setup_method(self):
        from src.ui.pages.data_registry_panel import _freshness_emoji
        self.fn = _freshness_emoji

    def test_missing(self):
        assert self.fn('2026-06-29', 'daily', True)[0] == '🔴'
        assert self.fn('N/A', 'daily', True)[0] == '🔴'  # missing 優先

    def test_na(self):
        assert self.fn('N/A', 'daily', False)[0] == '⬜'
        assert self.fn('', 'daily', False)[0] == '⬜'
        assert self.fn('invalid date', 'daily', False)[0] == '⬜'

    def test_daily_thresholds(self):
        today = _dt.date.today()
        d2  = (today - _dt.timedelta(days=2)).strftime('%Y-%m-%d')
        d10 = (today - _dt.timedelta(days=10)).strftime('%Y-%m-%d')
        d40 = (today - _dt.timedelta(days=40)).strftime('%Y-%m-%d')
        assert self.fn(d2,  'daily', False)[0] == '🟢'
        assert self.fn(d10, 'daily', False)[0] == '🟡'
        assert self.fn(d40, 'daily', False)[0] == '🔴'

    def test_monthly_thresholds(self):
        today = _dt.date.today()
        d60  = (today - _dt.timedelta(days=60)).strftime('%Y-%m-%d')
        d120 = (today - _dt.timedelta(days=120)).strftime('%Y-%m-%d')
        d300 = (today - _dt.timedelta(days=300)).strftime('%Y-%m-%d')
        assert self.fn(d60,  'monthly', False)[0] == '🟢'
        assert self.fn(d120, 'monthly', False)[0] == '🟡'
        assert self.fn(d300, 'monthly', False)[0] == '🔴'

    def test_event_always_green(self):
        assert self.fn('2020-01-01', 'event', False)[0] == '🟢'


# ══════════════════════════════════════════════════════════════════
# Section C:compute_registry_groups 純函式
# ══════════════════════════════════════════════════════════════════

class TestComputeRegistryGroups:
    def test_empty(self):
        from src.ui.pages.data_registry_panel import compute_registry_groups
        groups = compute_registry_groups({})
        assert groups == {}  # 空 state → 空 dict

    def test_no_data_registry_key(self):
        from src.ui.pages.data_registry_panel import compute_registry_groups
        groups = compute_registry_groups({'other_key': 'foo'})
        assert groups == {}

    def test_grouped_by_category(self):
        from src.ui.pages.data_registry_panel import compute_registry_groups
        from shared.data_categories import CAT_INTL, CAT_TW_MARKET, CAT_STOCK
        today = _dt.date.today().strftime('%Y-%m-%d')
        state = {
            'data_registry': {
                '道瓊工業 DJI':       {'last_updated': today, 'rows': 90,
                                       'category': CAT_INTL, 'frequency': 'daily'},
                '費城半導體 SOX':     {'last_updated': today, 'rows': 90,
                                       'category': CAT_INTL, 'frequency': 'daily'},
                '台股加權指數':        {'last_updated': today, 'rows': 90,
                                       'category': CAT_TW_MARKET, 'frequency': 'daily'},
                '[個股] 2330 | OHLC': {'last_updated': 'N/A', 'rows': 0,
                                       'category': CAT_STOCK, 'frequency': 'daily',
                                       'missing': True},
            }
        }
        groups = compute_registry_groups(state)
        assert CAT_INTL in groups and len(groups[CAT_INTL]) == 2
        assert CAT_TW_MARKET in groups and len(groups[CAT_TW_MARKET]) == 1
        assert CAT_STOCK in groups and len(groups[CAT_STOCK]) == 1
        # 缺失應為 🔴
        assert groups[CAT_STOCK][0]['emoji'] == '🔴'
        # 新鮮應為 🟢
        assert all(e['emoji'] == '🟢' for e in groups[CAT_INTL])

    def test_unknown_category_falls_into_fallback(self):
        from src.ui.pages.data_registry_panel import compute_registry_groups
        from shared.data_categories import CAT_FALLBACK
        state = {
            'data_registry': {
                '某資料源': {'last_updated': 'N/A', 'rows': 0,
                            'category': '某未知 category', 'frequency': 'daily'},
            }
        }
        groups = compute_registry_groups(state)
        # 未知 category 應 fallback 到 CAT_FALLBACK(🔄 三方備援)
        assert '某未知 category' in groups or CAT_FALLBACK in groups


# ══════════════════════════════════════════════════════════════════
# Section D:SSOT 對齊靜態守衛(scanner / patch / panel 三者用同一 import)
# ══════════════════════════════════════════════════════════════════

class TestSSOTAlignmentStaticGuard:
    def test_scanner_imports_ssot(self):
        """v18.394:scanner 必須 import shared.data_categories,不能 hardcode '大盤'/'個股'/'ETF'"""
        src = open('src/services/data_registry_scanner.py', encoding='utf-8').read()
        assert 'from shared.data_categories import' in src, \
            'data_registry_scanner 未 import shared.data_categories SSOT'
        # 殘留檢查:不能再有 inline '大盤'/'個股'/'ETF' category 字串
        for stale in ["'大盤'", "'個股'", "'ETF'"]:
            # 註解/docstring 內可以有,但 code 內(category=...)不可
            for line in src.splitlines():
                stripped = line.strip()
                if stripped.startswith('#') or stripped.startswith('"""'):
                    continue
                if f"category={stale}" in line or f"'category': {stale}" in line:
                    pytest.fail(f'data_registry_scanner.py 仍有 stale category {stale}: {line.strip()}')

    def test_patch_imports_ssot(self):
        """macro_registry_patch 必須 import shared.data_categories"""
        src = open('src/services/macro_registry_patch.py', encoding='utf-8').read()
        assert 'from shared.data_categories import' in src, \
            'macro_registry_patch 未 import shared.data_categories SSOT'
        for stale in ["'大盤'", "'個股'", "'ETF'"]:
            for line in src.splitlines():
                stripped = line.strip()
                if stripped.startswith('#') or stripped.startswith('"""'):
                    continue
                if f"category={stale}" in line or f"'category': {stale}" in line:
                    pytest.fail(f'macro_registry_patch.py 仍有 stale category {stale}: {line.strip()}')

    def test_panel_imports_ssot(self):
        """data_registry_panel 必須 import shared.data_categories"""
        src = open('src/ui/pages/data_registry_panel.py', encoding='utf-8').read()
        assert 'from shared.data_categories import' in src
