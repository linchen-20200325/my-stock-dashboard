"""B4-b 產業熱力圖稽核回歸測試（H-1 / H-2 / H-3 / H-4 / H-7 / H-9）。

⚠️ **本檔刻意「不寫原始碼掃描式守衛」**。本 session 已被字串掃描守衛的假紅燈擋了 6 次，
教訓是：守衛照抄實作字面，所以它永遠不會發現實作有問題。本檔一律**呼叫函式驗結果**。
唯二對「產出物」的字面斷言是 Plotly figure 的 `hovertemplate` / `customdata` ——
那是使用者滑鼠移過去真正會看到的東西（圖的規格本身），不是原始碼文字。

覆蓋的缺陷：

| 編號 | 缺陷 | 本檔對應測試 |
|---|---|---|
| H-1 | 「1日」實際算 ≈4 個交易日（基期取整個下載窗的第一根） | `TestPeriodContract` / `TestFetchSectorReturns` |
| H-2 | 台股「類股」實為單一權值股、且 3008/2409 重複計數 | `TestTwSectorDisclosure` |
| H-3 | 缺資料格子 hover 出「+0.00%」、且面積比真實類股還大 | `TestMissingValueNeverFakesZero` / `TestTreemap` |
| H-4 | 同一列 `%` 欄說 N/A、方向欄說「持平」；N/A 當 0 插進排序中間 | `TestMissingValueNeverFakesZero` |
| H-7 | 覆蓋率只數母層 | `TestTwSectorDisclosure::test_sub_members_are_counted_separately` |
| H-9 | 全 0 時 `max()` 空序列 ValueError | `TestColorSpan` / `TestTreemap::test_all_missing_does_not_raise` |
"""
from __future__ import annotations

import math

import pandas as pd
import pytest

from shared import sector_heatmap as sh


# ══════════════════════════════════════════════════════════════
# H-1 — 區間口徑：標籤 ↔ 交易日根數必須 1:1
# ══════════════════════════════════════════════════════════════
class TestPeriodContract:

    def test_labels_map_to_declared_trading_days(self):
        """§4.1：區間一律以交易日計。1日=1 / 5日=5 / 1月=21 / 3月=63 根 bar。"""
        assert sh.lookback_trading_days('1日') == 1
        assert sh.lookback_trading_days('5日') == 5
        assert sh.lookback_trading_days('1月') == 21   # 252/12，非 30 個日曆日
        assert sh.lookback_trading_days('3月') == 63   # 252/4，非 90 個日曆日

    def test_labels_are_strictly_increasing(self):
        bars = [sh.lookback_trading_days(p) for p in sh.SECTOR_PERIOD_LABELS]
        assert bars == sorted(bars), '區間選項順序應由短到長'
        assert len(set(bars)) == len(bars), '不同標籤不可對到同一個 bar 數'

    @pytest.mark.parametrize('bad', ['5d', '1mo', '3mo', '1天', '', 'Ｎ日', None])
    def test_unknown_label_fails_loud(self, bad):
        """§1：未知標籤一律 raise，不可猜預設值。

        特別是 `'5d' / '1mo' / '3mo'` —— 那是**下載窗**字串。舊實作正是把下載窗
        當計算區間傳進來，所以這裡必須擋死，避免有人改回去。
        """
        with pytest.raises(ValueError) as ei:
            sh.lookback_trading_days(bad)
        assert '1日' in str(ei.value), '錯誤訊息應列出合法值，方便現場除錯'

    def test_download_window_has_enough_bars_for_lookback(self):
        """下載窗必須夠寬：至少 n+1 根 bar，否則連基期都取不到。

        （測試端自備一張「窗 → 約略 bar 數」對照表，不引用實作的表，
        才有機會抓到「有人把窗改小」的回歸。）
        """
        approx_bars = {'5d': 3, '1mo': 21, '2mo': 42, '3mo': 63, '6mo': 126, '1y': 252}
        for label in sh.SECTOR_PERIOD_LABELS:
            win = sh.yf_download_window(label)
            need = sh.lookback_trading_days(label) + 1
            assert win in approx_bars, f'未知下載窗 {win!r}，請同步更新本測試的對照表'
            assert approx_bars[win] >= need, (
                f'{label}：下載窗 {win}(≈{approx_bars[win]} bars) 不足以取 {need} 根 bar')

    def test_window_is_not_the_lookback(self):
        """下載窗與計算區間是兩件事 —— 這正是 H-1 的根因，必須保持分離。"""
        for label in sh.SECTOR_PERIOD_LABELS:
            assert sh.yf_download_window(label) != label


class TestPctChangeOverBars:

    #: 遞增序列：最後一根 104，往前 1 根 103、往前 4 根 100。
    SERIES = [100.0, 101.0, 102.0, 103.0, 104.0]

    def test_one_bar_is_one_bar_not_whole_window(self):
        """H-1 核心回歸：n=1 必須是「相鄰兩根」，不是「整個序列頭尾」。

        舊實作 `iloc[-1]/iloc[0]` 會回 4.00（整段），使用者卻讀到「1日 +4.00%」。
        """
        one = sh.pct_change_over_bars(self.SERIES, 1)
        whole = sh.pct_change_over_bars(self.SERIES, len(self.SERIES) - 1)
        assert one == pytest.approx(0.97, abs=1e-9)     # 104/103 - 1
        assert whole == pytest.approx(4.00, abs=1e-9)   # 104/100 - 1
        assert one != whole, '1 根 bar 的報酬不可等於整個下載窗的報酬'

    def test_multi_bar_base_is_positional(self):
        # 104/102 - 1 = 1.9608% → 1.96 ；104/101 - 1 = 2.9703% → 2.97
        assert sh.pct_change_over_bars(self.SERIES, 2) == pytest.approx(1.96, abs=1e-9)
        assert sh.pct_change_over_bars(self.SERIES, 3) == pytest.approx(2.97, abs=1e-9)

    def test_insufficient_bars_returns_none_not_zero(self):
        """§1：樣本不足要留缺，**不可**回 0（0 會被畫成「持平」）。"""
        assert sh.pct_change_over_bars([100.0, 101.0], 5) is None
        assert sh.pct_change_over_bars([], 1) is None
        assert sh.pct_change_over_bars([100.0], 1) is None

    def test_flat_series_returns_real_zero(self):
        """真正的持平要回 0.0（不是 None）—— 才能跟「無資料」區分開。"""
        assert sh.pct_change_over_bars([100.0, 100.0], 1) == 0.0

    @pytest.mark.parametrize('bad_series', [
        [float('nan'), 100.0],
        [0.0, 100.0],            # 基期為 0 → 除以 0
        [-5.0, 100.0],           # 基期為負 → 無意義
        [100.0, float('inf')],
    ])
    def test_non_finite_or_nonpositive_base_returns_none(self, bad_series):
        assert sh.pct_change_over_bars(bad_series, 1) is None

    def test_n_bars_below_one_is_caller_bug(self):
        with pytest.raises(ValueError):
            sh.pct_change_over_bars([1.0, 2.0], 0)


# ══════════════════════════════════════════════════════════════
# H-3 / H-4 — 缺值永遠不可偽裝成 0.00% / 持平
# ══════════════════════════════════════════════════════════════
class TestMissingValueNeverFakesZero:

    def test_hover_text_missing_vs_real_zero(self):
        """H-3：缺值 hover 必須是「無資料」，不可與真實 0.00% 同字面。"""
        assert sh.hover_value_text(None) == sh.HEATMAP_MISSING_TEXT
        assert sh.hover_value_text(0.0) == '+0.00%'
        assert sh.hover_value_text(None) != sh.hover_value_text(0.0)

    def test_hover_text_signs(self):
        assert sh.hover_value_text(1.25) == '+1.25%'
        assert sh.hover_value_text(-1.25) == '-1.25%'
        assert sh.hover_value_text(13.3) == '+13.30%'

    def test_direction_missing_is_not_flat(self):
        """H-4：`ret is None` 落到「持平」是同列自相矛盾（%欄說沒資料）。"""
        missing = sh.direction_label(None)
        assert sh.HEATMAP_MISSING_TEXT in missing
        assert '持平' not in missing
        assert missing != sh.direction_label(0.0)

    def test_direction_real_values(self):
        assert '上漲' in sh.direction_label(0.01)
        assert '下跌' in sh.direction_label(-0.01)
        assert '持平' in sh.direction_label(0.0)

    def test_direction_does_not_use_truthiness(self):
        """舊寫法 `ret and ret > 0` 對 `0.0` 與 `None` 都是 falsy → 兩者同輸出。"""
        assert sh.direction_label(0.0) != sh.direction_label(None)

    def test_missing_sorts_last_not_middle(self):
        """H-4：N/A 原本被當 0.00% 插進真實報酬中間。"""
        rets = [2.0, None, -3.0, 0.0, None, 1.0]
        ordered = sorted(rets, key=sh.sort_key_desc, reverse=True)
        assert ordered[:4] == [2.0, 1.0, 0.0, -3.0]
        assert ordered[4] is None and ordered[5] is None, '缺值必須全部排在最後'

    def test_missing_area_strictly_smaller_than_any_real_node(self):
        """H-3：原本缺值母層給 1.0，比一檔真實 ±0.5% 的類股還大 —— 缺值不該霸佔版面。"""
        for is_parent in (True, False):
            missing = sh.node_area(None, is_parent=is_parent)
            for real in (0.0, 0.01, 0.5, -0.5, 3.0):
                assert missing < sh.node_area(real, is_parent=is_parent), (
                    f'缺值面積 {missing} 不應 >= 真實 {real}% 的面積 '
                    f'(is_parent={is_parent})')

    def test_area_is_symmetric_in_magnitude(self):
        assert sh.node_area(3.0, is_parent=True) == sh.node_area(-3.0, is_parent=True)


class TestColorSpan:
    """H-9：`max(abs(c) for c in colors if c != 0) or 5` 在空序列時炸整頁。"""

    @pytest.mark.parametrize('colors', [
        [],
        [0.0, 0.0, 0.0],
        [None, None],
        [None, 0.0, None],
        [float('nan')],
    ])
    def test_degenerate_inputs_do_not_raise(self, colors):
        span = sh.color_span_pct(colors)
        assert span == sh.HEATMAP_DEFAULT_COLOR_SPAN_PCT
        assert span > 0, 'cmin/cmax 跨度必須為正，否則色階退化'

    def test_span_is_max_absolute(self):
        assert sh.color_span_pct([1.0, -7.5, None, 0.0, 2.0]) == 7.5


# ══════════════════════════════════════════════════════════════
# H-2 — 台股「類股」其實是單一代表股：必須揭露 + 不可重複計數
# ══════════════════════════════════════════════════════════════
class TestTwSectorDisclosure:

    def test_proxy_label_carries_the_representative_code(self):
        got = sh.sector_display_name('半導體', '2330.TW', single_stock_proxy=True)
        assert '半導體' in got and '2330' in got
        assert '.TW' not in got, '畫面標籤不該露出 yfinance 後綴'

    def test_non_proxy_label_is_untouched(self):
        """美股走真 GICS 類股 ETF，不該被加註「代表股」。"""
        assert sh.sector_display_name('科技', 'XLK', single_stock_proxy=False) == '科技'

    def test_proxy_and_non_proxy_labels_differ(self):
        a = sh.sector_display_name('金融', '2882.TW', single_stock_proxy=True)
        b = sh.sector_display_name('金融', '2882.TW', single_stock_proxy=False)
        assert a != b, '揭露開關必須真的改變畫面文字'

    def test_disclosure_text_is_plain(self):
        """揭露文案同時進 `_colored_box`(unsafe_allow_html) 與 AI prompt，
        因此必須是純文字：markdown `**` 在 HTML 框裡會原樣露出、HTML tag 進
        prompt 又是雜訊。"""
        txt = sh.TW_SINGLE_STOCK_PROXY_DISCLOSURE
        assert '**' not in txt
        assert '<' not in txt and '>' not in txt
        assert '不是類股指數' in txt and '單一代表' in txt

    def test_tw_sectors_have_no_duplicate_tickers(self):
        """H-2 重複計數：`3008.TW` 曾同時是「光電」母層與「電子製造」子成分；
        `2409.TW` 曾同時掛「電信」與「光電」。"""
        from src.ui.render import etf_render as render
        self._assert_no_duplicates(render._TW_SECTORS, '台股')

    def test_us_sectors_have_no_duplicate_tickers(self):
        from src.ui.render import etf_render as render
        self._assert_no_duplicates(render._US_SECTORS, '美股')

    @staticmethod
    def _assert_no_duplicates(sectors: dict, market: str):
        seen: dict[str, list[str]] = {}
        for parent, meta in sectors.items():
            seen.setdefault(parent, []).append(f'{meta["name"]}(母層)')
            for sub in meta.get('sub', []):
                seen.setdefault(sub, []).append(f'{meta["name"]}(子成分)')
        dupes = {t: where for t, where in seen.items() if len(where) > 1}
        assert not dupes, (
            f'{market}熱力圖有標的被重複計數（同一檔股票的漲跌被算進兩個類股）：{dupes}')

    def test_tw_market_is_flagged_as_single_stock_proxy(self):
        """台股側只要還是用個股近似，揭露開關就必須是 True（否則 UI 不會揭露）。"""
        from src.ui.render import etf_render as render
        assert render._TW_SECTOR_SINGLE_STOCK_PROXY is True
        assert render._US_SECTOR_SINGLE_STOCK_PROXY is False
        # 台股表的 key 全是 4 碼台股代號（= 個股），不是指數/ETF 代號
        for ticker in render._TW_SECTORS:
            assert ticker.endswith('.TW'), ticker

    def test_sub_members_are_counted_separately(self):
        """H-7：覆蓋率若只數母層，55 檔子成分全缺也會顯示「✅ 全部完整」。

        這裡驗證「母層數」與「子成分數」是兩個不同的量 —— 只要子成分存在，
        就不能用母層數代表整體覆蓋率。
        """
        from src.ui.render import etf_render as render
        for name, sectors in (('台股', render._TW_SECTORS), ('美股', render._US_SECTORS)):
            subs = [s for meta in sectors.values() for s in meta.get('sub', [])]
            assert len(subs) > len(sectors), (
                f'{name}：子成分 {len(subs)} 檔遠多於母層 {len(sectors)} 檔，'
                f'覆蓋率不可只數母層')


# ══════════════════════════════════════════════════════════════
# H-1 端到端：L1 fetcher 的標籤 → bar 數 → 報酬 接線
# ══════════════════════════════════════════════════════════════
def _raw_fetch():
    """取未經 `@st.cache_data` 包裝的原函式，避免跨測試 cache 污染。"""
    from src.data.etf import etf_fetch
    fn = etf_fetch._fetch_sector_returns
    return getattr(fn, '__wrapped__', fn)


def _clear_sector_cache():
    """雙保險：萬一 streamlit 版本沒有 `__wrapped__`，至少把 cache 清掉。"""
    from src.data.etf import etf_fetch
    clear = getattr(etf_fetch._fetch_sector_returns, 'clear', None)
    if callable(clear):
        try:
            clear()
        except Exception:  # noqa: BLE001 — 測試輔助，清不掉不該中斷測試
            pass


class _FakeYF:
    """只實作 `download()` 的 yfinance 替身，順便記錄呼叫參數。"""

    def __init__(self, frame):
        self._frame = frame
        self.calls: list[dict] = []

    def download(self, tickers, **kwargs):
        self.calls.append({'tickers': tuple(tickers), **kwargs})
        return self._frame


def _make_close_frame(series_by_ticker: dict[str, list]) -> pd.DataFrame:
    """組出 yf.download 多 ticker 的 MultiIndex(['Close','Open'] × tickers) 形狀。"""
    n = max(len(v) for v in series_by_ticker.values())
    idx = pd.date_range('2026-01-05', periods=n, freq='B')
    tickers = list(series_by_ticker)
    cols = pd.MultiIndex.from_product([['Close', 'Open'], tickers])
    df = pd.DataFrame(index=idx, columns=cols, dtype=float)
    for t, vals in series_by_ticker.items():
        padded = [float('nan')] * (n - len(vals)) + [float(v) for v in vals]
        df[('Close', t)] = padded
        df[('Open', t)] = padded
    return df


#: AAA 一路上漲（每根 bar 都不同 → 1 根 vs 5 根的報酬差很多）
#: BBB 最後兩根停牌（NaN）—— 舊實作 ffill 後 1 日報酬會變成 0.00%
#: CCC 新上市，只有 2 根 bar —— 「5日」應該直接缺，不可硬算
_FIXTURE = {
    'AAA': [50, 60, 70, 80, 90, 100, 100, 110],
    'BBB': [200, 200, 200, 200, 200, 220, float('nan'), float('nan')],
    'CCC': [float('nan')] * 6 + [300, 303],
}


class TestFetchSectorReturns:

    @pytest.fixture(autouse=True)
    def _isolate_cache(self):
        _clear_sector_cache()
        yield
        _clear_sector_cache()

    @pytest.fixture
    def fake_yf(self, monkeypatch):
        from src.data.etf import etf_fetch
        fake = _FakeYF(_make_close_frame(_FIXTURE))
        monkeypatch.setattr(etf_fetch, 'yf', fake)
        return fake

    def test_one_day_label_uses_one_bar(self, fake_yf):
        """H-1 端到端：選「1日」就必須是 1 根 bar 的報酬。

        AAA 最後兩根 100 → 110 ⇒ +10.00%。
        舊實作會拿整個下載窗第一根 50 當基期 ⇒ +120.00%（差 12 倍）。
        """
        got = _raw_fetch()(('AAA', 'BBB', 'CCC'), '1日')
        assert got['AAA'] == pytest.approx(10.0, abs=1e-9)
        assert got['AAA'] != pytest.approx(120.0, abs=1e-6), \
            '不可退化成「整個下載窗頭尾」的報酬'

    def test_five_day_label_uses_five_bars(self, fake_yf):
        """同一份資料換標籤，數字必須跟著換 —— 證明標籤真的接到 bar 數。"""
        one = _raw_fetch()(('AAA',), '1日')
        five = _raw_fetch()(('AAA',), '5日')
        assert one['AAA'] == pytest.approx(10.0, abs=1e-9)      # 110/100
        assert five['AAA'] == pytest.approx(57.14, abs=0.01)    # 110/70
        assert one['AAA'] != five['AAA']

    def test_no_ffill_so_halted_stock_is_not_reported_as_flat(self, fake_yf):
        """§4.6：停牌不可 ffill。BBB 尾端兩根 NaN，ffill 後 1 日報酬會變 0.00%
        —— 把「沒有交易」偽裝成「持平」。"""
        got = _raw_fetch()(('BBB',), '1日')
        assert got['BBB'] == pytest.approx(10.0, abs=1e-9)  # 220/200，取自己最後兩根真實 bar
        assert got['BBB'] != 0.0

    def test_insufficient_history_is_absent_not_zero(self, fake_yf):
        """§1：CCC 只有 2 根 bar，算不出「5日」→ 不入 dict（UI 顯示無資料）。"""
        got = _raw_fetch()(('AAA', 'BBB', 'CCC'), '5日')
        assert 'CCC' not in got, 'bar 數不足時應留缺，不可填 0'
        # 但「1日」只需 2 根，CCC 應該算得出來
        got1 = _raw_fetch()(('AAA', 'BBB', 'CCC'), '1日')
        assert got1['CCC'] == pytest.approx(1.0, abs=1e-9)  # 303/300

    def test_unknown_ticker_is_absent_not_zero(self, fake_yf):
        got = _raw_fetch()(('AAA', 'ZZZ'), '1日')
        assert 'ZZZ' not in got

    def test_raw_yfinance_window_string_is_rejected(self, fake_yf):
        """回歸守衛：舊實作把 `'5d'/'1mo'/'3mo'` 這種**下載窗**傳進來當區間。
        現在契約改成傳標籤，傳窗字串必須當場炸（§1），而且**不可**先發出請求。"""
        for bad in ('5d', '1mo', '3mo', '6mo'):
            with pytest.raises(ValueError):
                _raw_fetch()(('AAA',), bad)
        assert fake_yf.calls == [], '參數不合法時不該浪費一次外部請求'

    def test_download_window_is_wider_than_the_label(self, fake_yf):
        """下載窗要放大以吸收連假；否則連假後連「1日」都算不出來。"""
        _raw_fetch()(('AAA',), '1日')
        assert fake_yf.calls, '應實際呼叫 yf.download'
        assert fake_yf.calls[0]['period'] == sh.yf_download_window('1日')
        assert fake_yf.calls[0]['period'] != '1日'
        assert fake_yf.calls[0]['auto_adjust'] is True, '§4.6 跨年除權息須用還原價'

    def test_empty_download_returns_empty_dict(self, monkeypatch):
        from src.data.etf import etf_fetch
        monkeypatch.setattr(etf_fetch, 'yf', _FakeYF(pd.DataFrame()))
        assert _raw_fetch()(('AAA',), '1日') == {}

    def test_download_exception_degrades_to_empty_not_zeros(self, monkeypatch):
        """§1：外部失敗要留缺，不可回一堆 0（0 會被畫成「全市場持平」）。"""
        from src.data.etf import etf_fetch

        class _Boom:
            def download(self, *a, **k):
                raise RuntimeError('yfinance rate limited')

        monkeypatch.setattr(etf_fetch, 'yf', _Boom())
        got = _raw_fetch()(('AAA', 'BBB'), '1日')
        assert got == {}


# ══════════════════════════════════════════════════════════════
# H-3 / H-9 — Treemap 產出物（使用者真正看到的圖規格）
# ══════════════════════════════════════════════════════════════
_TOY_SECTORS = {
    '2330.TW': {'name': '半導體', 'sub': ['2303.TW', '2454.TW']},
    '2882.TW': {'name': '金融',   'sub': ['2881.TW']},
}


class TestTreemap:

    @staticmethod
    def _build(returns, **kw):
        from src.ui.render import etf_render as render
        return render._build_treemap_data(_TOY_SECTORS, returns, '台股類股', **kw)

    def test_missing_node_color_is_none_not_zero(self):
        """H-3：缺值顏色填 0 會被畫成「中性/持平」色，與真實 0.00% 無法區分。"""
        fig = self._build({'2330.TW': 1.5, '2303.TW': 0.0})
        trace = fig.data[0]
        colors = list(trace.marker.colors)
        ids = list(trace.ids)
        i_missing = ids.index('2882.TW')          # 完全沒抓到
        i_real_zero = ids.index('2330.TW/2303.TW')  # 真實 0.00%
        assert colors[i_missing] is None
        assert colors[i_real_zero] == 0.0

    def test_missing_node_hover_says_no_data(self):
        """H-3：使用者滑過缺資料的格子，看到的必須是「無資料」而不是「+0.00%」。"""
        fig = self._build({'2330.TW': 1.5})
        trace = fig.data[0]
        ids = list(trace.ids)
        custom = [c[0] if isinstance(c, (list, tuple)) else c for c in trace.customdata]
        assert custom[ids.index('2882.TW')] == sh.HEATMAP_MISSING_TEXT
        assert custom[ids.index('2330.TW')] == '+1.50%'
        # hover 不可再從 marker.color 取值（那正是 +0.00% 的來源）
        assert 'customdata' in trace.hovertemplate
        assert 'marker.color' not in trace.hovertemplate

    def test_missing_node_area_is_smaller_than_real_node(self):
        """H-3：缺值原本給面積 1（比真實 ±0.5% 的類股還大），等於讓沒資料的搶版面。"""
        fig = self._build({'2330.TW': 0.4})
        trace = fig.data[0]
        ids = list(trace.ids)
        vals = list(trace.values)
        assert vals[ids.index('2882.TW')] < vals[ids.index('2330.TW')]

    def test_all_missing_does_not_raise(self):
        """H-9：`max()` 空序列 → 整頁白掉（此 tab 原本還沒包隔離器）。"""
        fig = self._build({})
        assert fig.data[0].marker.cmax == sh.HEATMAP_DEFAULT_COLOR_SPAN_PCT
        assert fig.data[0].marker.cmin == -sh.HEATMAP_DEFAULT_COLOR_SPAN_PCT

    def test_all_zero_does_not_raise(self):
        """H-9 的另一個觸發路徑：全部真實為 0（例如全市場休市當天）。"""
        fig = self._build({t: 0.0 for t in ['2330.TW', '2303.TW', '2454.TW',
                                            '2882.TW', '2881.TW']})
        assert fig.data[0].marker.cmax == sh.HEATMAP_DEFAULT_COLOR_SPAN_PCT

    def test_color_scale_is_symmetric_around_zero(self):
        fig = self._build({'2330.TW': 3.0, '2882.TW': -1.0})
        m = fig.data[0].marker
        assert m.cmid == 0
        assert math.isclose(m.cmax, 3.0) and math.isclose(m.cmin, -3.0)

    def test_proxy_labels_disclose_representative_stock(self):
        """H-2：台股側每一格都要看得到「這是哪一檔股票」。"""
        fig = self._build({'2330.TW': 1.0}, single_stock_proxy=True)
        labels = ' '.join(fig.data[0].labels)
        assert '2330' in labels and '2882' in labels

    def test_non_proxy_labels_have_no_disclosure_noise(self):
        fig = self._build({'2330.TW': 1.0}, single_stock_proxy=False)
        assert '代表股' not in ' '.join(fig.data[0].labels)

    def test_missing_label_shows_no_data_text(self):
        fig = self._build({'2330.TW': 1.0})
        trace = fig.data[0]
        label = trace.labels[list(trace.ids).index('2882.TW')]
        assert sh.HEATMAP_MISSING_TEXT in label

    def test_hover_prefix_carries_period_label(self):
        """H-1：hover 也要講清楚是哪一段區間，不能只寫「漲跌」。"""
        fig = self._build({'2330.TW': 1.0}, period_label='3月')
        assert '3月' in fig.data[0].hovertemplate

    def test_node_counts_match_config(self):
        fig = self._build({})
        expected = 1 + len(_TOY_SECTORS) + sum(
            len(m['sub']) for m in _TOY_SECTORS.values())
        assert len(fig.data[0].ids) == expected
