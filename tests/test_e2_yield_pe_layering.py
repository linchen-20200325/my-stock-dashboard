"""tests/test_e2_yield_pe_layering.py — E2:三個 yield/PE fetcher 下沉 L1(解 C3-d)。

搬遷內容
────────
`fetch_twse_yield_pe` / `fetch_tpex_yield_pe` / `fetch_pe_name_maps`
  from `src/ui/tabs/yield_screener.py`(L5 UI Tab,module-level 無條件 import streamlit)
  to   `src/data/stock/yield_pe_fetcher.py`(L1,EX-CACHE-1 條件 import streamlit)

為什麼這件事重要(不是潔癖,是資料完整性)
──────────────────────────────────────
四個 caller 有兩個是 headless cron。`scripts/update_forward_test_freeze.py` 每月凍結
**前進式驗證**清單 —— 本專案唯一零 lookahead、零存活者偏誤的績效量測。它走 L5 import
就等於把整條 streamlit UI 依賴鏈綁進 cron;鏈一斷,紀錄**靜默停止累積**(§1 最忌)。

測試策略(§6)
─────────────
以**行為斷言為主**:真的在「沒有 streamlit」的環境下 import + 呼叫,而不是掃字串猜。
只有兩處必須看原始碼(「頂層有沒有無條件 import」/「cron 有沒有 import UI」),那兩處
一律用 **AST**(自動排除 docstring / 註解 —— 本 repo 的 docstring 大量出現
`from src.data...` 之類字樣,字串掃描必假紅燈),失敗訊息印出**該行原文 + 行號**。
兩個 AST 守衛各自附「守衛的守衛」:對合成原始碼證明它抓得到 / 不誤殺,
避免出現一個永遠不會 fire 的假綠燈守衛。
"""
from __future__ import annotations

import ast
import contextlib
import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

_L1_MOD = "src.data.stock.yield_pe_fetcher"
_L1_PATH = REPO_ROOT / "src" / "data" / "stock" / "yield_pe_fetcher.py"
_L5_PATH = REPO_ROOT / "src" / "ui" / "tabs" / "yield_screener.py"
_CRON_PATHS = (
    REPO_ROOT / "scripts" / "push_daily_signals.py",
    REPO_ROOT / "scripts" / "update_forward_test_freeze.py",
)


# ════════════════════════════════════════════════════════════════════
# 共用工具
# ════════════════════════════════════════════════════════════════════
def _resp(payload, status: int = 200):
    """假 requests-like response(.status_code + .json())。"""
    _r = MagicMock()
    _r.status_code = status
    _r.json.return_value = payload
    return _r


def _clear_l1_caches() -> None:
    """清 @st.cache_data(無 streamlit 時 decorator 退化 no-op,沒有 .clear())。"""
    from src.data.stock import yield_pe_fetcher as ypf
    for _fn in ("fetch_twse_yield_pe", "fetch_tpex_yield_pe"):
        try:
            getattr(ypf, _fn).clear()
        except Exception:
            pass


@pytest.fixture(autouse=True)
def _isolate_pe_caches():
    _clear_l1_caches()
    yield
    _clear_l1_caches()


# 2026-08-05 BWIBBU_d 實際回應形狀:未配息 → DividendYield 空字串,PE 照給。
_TWSE_RAW = [
    {"Code": "1102", "Name": "亞泥", "DividendYield": "7.06",
     "PEratio": "10.94", "PBratio": "0.65"},
    {"Code": "2514", "Name": "龍邦", "DividendYield": "",
     "PEratio": "7.07", "PBratio": "0.35"},        # 未配息但 PE 最便宜
    {"Code": "1101", "Name": "台泥", "DividendYield": "3.33",
     "PEratio": "", "PBratio": "0.77"},            # 有配息但無 PE
    {"Code": "   ", "Name": "空代碼", "DividendYield": "1.0",
     "PEratio": "5.00", "PBratio": "1.0"},         # 代碼空白 → 整列丟
]

_TPEX_RAW = [
    {"SecuritiesCompanyCode": "5483", "CompanyName": "中美晶",
     "PriceEarningRatio": "12.50", "YieldRatio": "3.20", "PriceBookRatio": "1.80"},
    {"SecuritiesCompanyCode": "6488", "CompanyName": "環球晶",
     "PriceEarningRatio": "-", "YieldRatio": "-", "PriceBookRatio": "-"},
]


# ════════════════════════════════════════════════════════════════════
# ① 行為:L1 模組在「沒有 streamlit」的環境仍可 import + 可用
#    —— 這就是整個搬遷要保護的東西(headless cron)。
# ════════════════════════════════════════════════════════════════════
@contextlib.contextmanager
def _l1_module_without_streamlit():
    """把 streamlit 從 sys.modules 擋掉,重新 import 一份 L1 模組。

    `sys.modules[name] = None` 會讓 `import name` 丟 ImportError —— 正好走到
    EX-CACHE-1 標準寫法的 `except ImportError` 分支。

    ⚠️ 收尾必須把 streamlit **與** L1 模組(sys.modules + parent package 屬性)
    全部還原,否則會污染 `tests/test_zz_streamlit_pollution_lock.py` 與其他測試。
    """
    import src.data.stock as _pkg

    _saved_st = {k: v for k, v in sys.modules.items()
                 if k == "streamlit" or k.startswith("streamlit.")}
    _saved_mod = sys.modules.get(_L1_MOD)
    _saved_attr = getattr(_pkg, "yield_pe_fetcher", None)
    try:
        for _k in _saved_st:
            sys.modules[_k] = None
        sys.modules["streamlit"] = None
        sys.modules.pop(_L1_MOD, None)
        yield importlib.import_module(_L1_MOD)
    finally:
        for _k in [k for k in sys.modules
                   if k == "streamlit" or k.startswith("streamlit.")]:
            if _k in _saved_st:
                sys.modules[_k] = _saved_st[_k]
            else:
                del sys.modules[_k]
        if _saved_mod is not None:
            sys.modules[_L1_MOD] = _saved_mod
        else:
            sys.modules.pop(_L1_MOD, None)
        if _saved_attr is not None:
            setattr(_pkg, "yield_pe_fetcher", _saved_attr)
        else:
            with contextlib.suppress(AttributeError):
                delattr(_pkg, "yield_pe_fetcher")


def test_l1_module_imports_and_works_without_streamlit():
    """核心行為:模擬無 streamlit 環境 → import 得動,三個 fetcher 照樣算得出結果。

    搬遷前 caller 走 `src/ui/tabs/yield_screener.py`,該檔 module-level 無條件
    `import streamlit as st` → 同樣情境會直接 ImportError,cron 整支掛掉。
    """
    _st_before = sys.modules.get("streamlit")
    with _l1_module_without_streamlit() as _mod:
        # 沒有真 streamlit 被載進來(證明走的是 _NoOpST 分支,不是偷偷 import 成功)
        assert sys.modules.get("streamlit") is None

        with patch.object(_mod, "proxy_fetch_url",
                          return_value=_resp(_TWSE_RAW)) as _http:
            _df = _mod.fetch_twse_yield_pe()
            assert _http.call_count == 1, "無 streamlit 環境下 HTTP 出口沒被走到"
        assert not _df.empty
        assert set(_df["代碼"]) == {"1102", "2514", "1101"}

        with patch.object(_mod, "fetch_twse_yield_pe", return_value=_df), \
             patch.object(_mod, "fetch_tpex_yield_pe", return_value=pd.DataFrame()):
            _pe, _name = _mod.fetch_pe_name_maps()
        assert _pe["2514"] == pytest.approx(7.07)
        assert _name["1102"] == "亞泥"

    # 收尾檢查:streamlit 還原成**進場前的同一個物件**(用身分比對,不假設它一定裝了)。
    # 沒還原乾淨會拖垮字母序在後的整批測試 + tests/test_zz_streamlit_pollution_lock.py。
    assert sys.modules.get("streamlit") is _st_before, (
        "streamlit 沒有還原成進場前的物件 —— _l1_module_without_streamlit 的 finally 有漏"
    )
    assert sys.modules.get(_L1_MOD) is not None, "L1 模組沒還原回 sys.modules"


def test_noop_cache_decorator_accepts_both_call_styles():
    """EX-CACHE-1 範本的 `_NoOpST.cache_data` 必須同時吃
    `@st.cache_data` 與 `@st.cache_data(ttl=...)` 兩種寫法。

    本模組用的是後者;若哪天有人改壞前者,無 streamlit 環境會在 import 期就炸。
    """
    with _l1_module_without_streamlit() as _mod:
        _cache = _mod.st.cache_data
        _bare = _cache(lambda: "bare")
        _parametrised = _cache(ttl=123, show_spinner=False)(lambda: "parametrised")
        assert _bare() == "bare"
        assert _parametrised() == "parametrised"


# ════════════════════════════════════════════════════════════════════
# ② 原始碼守衛(AST):L1 頂層不得有「無條件」streamlit import
#    行為測試已經涵蓋 99%;這條擋的是「加了無條件 import 但 CI 剛好有裝
#    streamlit 所以行為測試看不出來」的回歸。
# ════════════════════════════════════════════════════════════════════
def _targets_streamlit(node: ast.stmt) -> bool:
    if isinstance(node, ast.Import):
        return any(a.name == "streamlit" or a.name.startswith("streamlit.")
                   for a in node.names)
    if isinstance(node, ast.ImportFrom):
        _m = node.module or ""
        return _m == "streamlit" or _m.startswith("streamlit.")
    return False


def _unconditional_streamlit_imports(src_text: str) -> list[tuple[int, str]]:
    """module **頂層**(不在 try/except、不在函式內)的 streamlit import。

    只看 `tree.body` —— 包在 `try: ... except ImportError:` 內的會是 `ast.Try`
    節點,不會被列入,正是 EX-CACHE-1 允許的寫法。
    docstring / 註解天生不會變成 Import 節點,故不需要額外排除。
    """
    _tree = ast.parse(src_text)
    _lines = src_text.splitlines()
    return [(_s.lineno, _lines[_s.lineno - 1].strip())
            for _s in _tree.body if _targets_streamlit(_s)]


def test_l1_has_no_unconditional_streamlit_import():
    _hits = _unconditional_streamlit_imports(_L1_PATH.read_text(encoding="utf-8"))
    assert not _hits, (
        f"\n❌ {_L1_MOD}(L1)頂層出現無條件 streamlit import:\n"
        + "\n".join(f"    {_L1_PATH.name}:{ln}: {txt}" for ln, txt in _hits)
        + "\n\n   L1 必須用 CLAUDE.md §8.2.A.1 的 EX-CACHE-1 條件 import 寫法"
          "(try: import streamlit / except ImportError: _NoOpST),"
          "否則 headless cron / MCP server 會被迫拉 streamlit。\n"
    )


def test_unconditional_import_guard_actually_fires():
    """守衛的守衛:證明上面那條會抓、且不誤殺條件 import。

    一個永遠不會 fire 的守衛 = 假綠燈,比沒有守衛更糟。
    """
    _bad = "import pandas as pd\nimport streamlit as st\n"
    _bad_from = "from streamlit.runtime import x\n"
    _good = ("try:\n"
             "    import streamlit as st\n"
             "except ImportError:\n"
             "    st = None\n")
    _good_lazy = "def f():\n    import streamlit as st\n    return st\n"
    assert len(_unconditional_streamlit_imports(_bad)) == 1
    assert len(_unconditional_streamlit_imports(_bad_from)) == 1
    assert _unconditional_streamlit_imports(_good) == []
    assert _unconditional_streamlit_imports(_good_lazy) == []


# ════════════════════════════════════════════════════════════════════
# ③ 兩支 cron 不再 import src.ui.*(AST 走訪全樹 —— late import 也算)
# ════════════════════════════════════════════════════════════════════
def _ui_imports(src_text: str) -> list[tuple[int, str]]:
    """全樹(含函式內 late import)掃 `src.ui` / `src.ui.*` 的 import。"""
    _tree = ast.parse(src_text)
    _lines = src_text.splitlines()
    _hits: list[tuple[int, str]] = []
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.Import):
            if any(a.name == "src.ui" or a.name.startswith("src.ui.")
                   for a in _n.names):
                _hits.append((_n.lineno, _lines[_n.lineno - 1].strip()))
        elif isinstance(_n, ast.ImportFrom):
            _m = _n.module or ""
            if _m == "src.ui" or _m.startswith("src.ui."):
                _hits.append((_n.lineno, _lines[_n.lineno - 1].strip()))
    return _hits


@pytest.mark.parametrize("path", _CRON_PATHS, ids=lambda p: p.name)
def test_cron_scripts_do_not_import_ui_layer(path: Path):
    """headless cron 不得 import 任何 L5 UI 模組。

    §8.2 C3-d 的根因就在這:cron 為了拿 PE / 名稱 map 而 import
    `src.ui.tabs.yield_screener`,把整條 streamlit 依賴鏈拉進無頭環境。
    orchestrator 身分允許**往下**跨層(L2/L3),不涵蓋往 UI 層取數。
    """
    _hits = _ui_imports(path.read_text(encoding="utf-8"))
    assert not _hits, (
        f"\n❌ cron `{path.name}` 又 import 了 L5 UI 模組:\n"
        + "\n".join(f"    {path.name}:{ln}: {txt}" for ln, txt in _hits)
        + "\n\n   資料要從 L1(src/data/**)或 L3(src/services/**)取,不要走 UI。\n"
    )


def test_ui_import_guard_actually_fires():
    """守衛的守衛:late import(函式內)也必須被抓到 —— 原本的違憲正是 late import。"""
    _late = ("def f():\n"
             "    from src.ui.tabs.yield_screener import fetch_pe_name_maps\n"
             "    return fetch_pe_name_maps()\n")
    _top = "import src.ui.tabs as t\n"
    _ok = ("def f():\n"
           "    from src.data.stock.yield_pe_fetcher import fetch_pe_name_maps\n"
           "    return fetch_pe_name_maps()\n")
    assert len(_ui_imports(_late)) == 1
    assert len(_ui_imports(_top)) == 1
    assert _ui_imports(_ok) == []


@pytest.mark.parametrize(
    "mod_name",
    ["scripts.push_daily_signals", "scripts.update_forward_test_freeze"],
)
def test_cron_pe_map_helper_resolves_to_l1(mod_name: str):
    """行為證明(比原始碼掃描強):cron 的 `_build_pe_name_maps` 真的呼叫到 L1 那支。

    patch L1 → mock 必須被走到。若哪天有人把 import 改回 L5 re-export,
    這條會因為 mock 沒被呼叫而紅。
    """
    _cron = importlib.import_module(mod_name)
    _sentinel = ({"9999": 4.2}, {"9999": "測試"})
    with patch(f"{_L1_MOD}.fetch_pe_name_maps", return_value=_sentinel) as _m:
        _pe, _name = _cron._build_pe_name_maps()
    assert _m.call_count == 1, (
        f"{mod_name}._build_pe_name_maps 沒有呼叫到 L1 的 fetch_pe_name_maps —— "
        "import 路徑可能又被改回 src.ui.tabs.yield_screener"
    )
    assert _pe == {"9999": 4.2} and _name == {"9999": "測試"}


def test_cron_pe_map_helper_is_fail_soft():
    """§1 fail-soft 契約不變:PE 抓不到 → 回兩個空 dict(讓 pe_low 因子缺料),不炸。

    (缺料 ≠ 填 0:composite 端會直接不計入該因子。)
    """
    import scripts.update_forward_test_freeze as _cron

    def _boom():
        raise RuntimeError("TWSE down")

    with patch(f"{_L1_MOD}.fetch_pe_name_maps", side_effect=_boom):
        assert _cron._build_pe_name_maps() == ({}, {})


# ════════════════════════════════════════════════════════════════════
# ④ 行為與搬遷前一致 —— 三個 fetcher 的解析 / 缺值 / provenance 契約
# ════════════════════════════════════════════════════════════════════
class TestTwseFetcherParity:
    def test_parses_and_keeps_non_dividend_rows(self):
        """B6-b 修正①(TWSE 移除 `dropna(subset=['殖利率(%)'])`)必須完整帶過來。

        未配息 → 殖利率 NaN,但該列的 PE / 名稱 / PB **保留**。
        (2026-08-05 實測 BWIBBU_d 前 410 檔有 99 檔殖利率為空 ≈ 24%。)
        """
        from src.data.stock import yield_pe_fetcher as ypf
        with patch.object(ypf, "proxy_fetch_url",
                          return_value=_resp(_TWSE_RAW)) as _http:
            _df = ypf.fetch_twse_yield_pe()
            assert _http.call_count == 1
            assert "openapi.twse.com.tw" in str(_http.call_args)
        _row = _df[_df["代碼"] == "2514"].iloc[0]
        assert pd.isna(_row["殖利率(%)"]), "空字串殖利率應為 NaN(不是 0)"
        assert _row["本益比"] == pytest.approx(7.07), "未配息股被連坐丟掉了 PE"
        assert _row["名稱"] == "龍邦"
        assert _row["股價淨值比"] == pytest.approx(0.35)

    def test_blank_code_rows_dropped_and_columns_renamed(self):
        from src.data.stock import yield_pe_fetcher as ypf
        with patch.object(ypf, "proxy_fetch_url", return_value=_resp(_TWSE_RAW)):
            _df = ypf.fetch_twse_yield_pe()
        # ⚠️ 比對**集合**不比順序：欄位順序沿用 TWSE payload 的原始鍵序，不是契約。
        # 所有 consumer（`fetch_pe_name_maps` / `_fetch_pbratio_from_twse`）都以
        # **欄名**取值，沒有任何一處靠位置索引。原本寫死順序（本益比 在 殖利率(%) 前）
        # 與實際相反 → 這條測試在對「上游 JSON 的鍵序」下斷言，那是它管不著也不該管的事。
        assert set(_df.columns[:5]) == {"代碼", "名稱", "本益比", "殖利率(%)", "股價淨值比"}
        assert "" not in set(_df["代碼"]) and "   " not in set(_df["代碼"])
        assert len(_df) == 3

    def test_provenance_attrs_survived_the_move(self):
        """S-PROV-1:DataFrame.attrs 帶 source / fetched_at(§2.2)。"""
        from src.data.stock import yield_pe_fetcher as ypf
        with patch.object(ypf, "proxy_fetch_url", return_value=_resp(_TWSE_RAW)):
            _df = ypf.fetch_twse_yield_pe()
        assert _df.attrs.get("source") == "TWSE:OpenAPI:BWIBBU_d"
        assert _df.attrs.get("fetched_at")

    @pytest.mark.parametrize("payload,status", [
        ([], 200), ({"not": "a list"}, 200), (None, 200), (_TWSE_RAW, 500),
    ])
    def test_bad_payloads_return_empty_not_fabricated(self, payload, status):
        """§1:抓不到就是空 DataFrame,不編造列、不填 0。"""
        from src.data.stock import yield_pe_fetcher as ypf
        _clear_l1_caches()
        with patch.object(ypf, "proxy_fetch_url",
                          return_value=_resp(payload, status)) as _http:
            assert ypf.fetch_twse_yield_pe().empty
            assert _http.call_count == 1


class TestTpexFetcherParity:
    def test_parses_tpex_columns_and_dash_becomes_nan(self):
        from src.data.stock import yield_pe_fetcher as ypf
        with patch.object(ypf, "proxy_fetch_url",
                          return_value=_resp(_TPEX_RAW)) as _http:
            _df = ypf.fetch_tpex_yield_pe()
            assert _http.call_count == 1
            assert "tpex.org.tw" in str(_http.call_args)
        assert _df.attrs.get("source") == "TPEX:OpenAPI:peratio_analysis"
        _ok = _df[_df["代碼"] == "5483"].iloc[0]
        assert _ok["名稱"] == "中美晶"
        assert _ok["本益比"] == pytest.approx(12.5)
        _dash = _df[_df["代碼"] == "6488"].iloc[0]
        assert pd.isna(_dash["本益比"]) and pd.isna(_dash["殖利率(%)"])
        assert _dash["名稱"] == "環球晶", "PE 缺不該連坐丟掉名稱"

    def test_yield_column_name_fallback(self):
        """TPEX 曾用 DividendYield / 現用 YieldRatio,兩種都要解得出。"""
        from src.data.stock import yield_pe_fetcher as ypf
        _rows = [{"SecuritiesCompanyCode": "5483", "CompanyName": "中美晶",
                  "PriceEarningRatio": "12.50", "DividendYield": "3.20",
                  "PriceBookRatio": "1.80"}]
        with patch.object(ypf, "proxy_fetch_url", return_value=_resp(_rows)):
            _df = ypf.fetch_tpex_yield_pe()
        assert _df.iloc[0]["殖利率(%)"] == pytest.approx(3.20)


class TestPeNameMapsParity:
    @staticmethod
    def _maps(twse_df, tpex_df):
        from src.data.stock import yield_pe_fetcher as ypf
        with patch.object(ypf, "fetch_twse_yield_pe", return_value=twse_df) as _a, \
             patch.object(ypf, "fetch_tpex_yield_pe", return_value=tpex_df) as _b:
            _out = ypf.fetch_pe_name_maps()
            assert _a.call_count == 1 and _b.call_count == 1, (
                "patch 沒打到 L1 模組的 globals —— fetch_pe_name_maps 正在呼叫真 fetcher"
            )
        return _out

    def test_nonpositive_pe_treated_as_missing(self):
        """B6-b 修正②:PE ≤ 0 是「無本益比」,不是「全市場最便宜」(§1 不造假)。

        pe_low 因子是「值越小分越高」,讓 0 / 負 PE 進 map 等於把虧損股排到榜首。
        """
        _df = pd.DataFrame({"代碼": ["AAA", "BBB", "CCC", "DDD"],
                            "名稱": ["零PE", "負PE", "正常", "缺PE"],
                            "本益比": [0.0, -3.5, 12.0, float("nan")]})
        _pe, _name = self._maps(_df, pd.DataFrame())
        assert set(_pe) == {"CCC"}, "0 / 負 / NaN 的 PE 不得進 pe_map"
        # 名稱不受 PE 缺值影響(兩者是各自獨立的欄)
        assert set(_name) == {"AAA", "BBB", "CCC", "DDD"}

    def test_listed_and_otc_union_with_listed_winning(self):
        """§2.1:同 T1 官方源,不平均;上市先填(setdefault)贏。"""
        _twse = pd.DataFrame({"代碼": ["2330"], "名稱": ["台積電"], "本益比": [18.0]})
        _tpex = pd.DataFrame({"代碼": ["2330", "5483"], "名稱": ["冒充", "中美晶"],
                              "本益比": [99.0, 12.5]})
        _pe, _name = self._maps(_twse, _tpex)
        assert set(_pe) == {"2330", "5483"}
        assert _pe["2330"] == pytest.approx(18.0)
        assert _name["2330"] == "台積電"

    def test_nan_string_names_filtered(self):
        _df = pd.DataFrame({"代碼": ["9999"], "名稱": ["nan"], "本益比": [10.0]})
        _pe, _name = self._maps(pd.DataFrame(), _df)
        assert "9999" in _pe          # PE 照收
        assert "9999" not in _name    # 但畫面不該顯示 "nan"

    def test_fail_soft_when_one_market_raises(self):
        """單一市場丟例外 → 只少半邊涵蓋,不炸(§1 的例外是:這裡確實只是缺料)。"""
        from src.data.stock import yield_pe_fetcher as ypf
        _tpex = pd.DataFrame({"代碼": ["5483"], "名稱": ["中美晶"], "本益比": [12.5]})
        with patch.object(ypf, "fetch_twse_yield_pe",
                          side_effect=RuntimeError("TWSE down")) as _a, \
             patch.object(ypf, "fetch_tpex_yield_pe", return_value=_tpex) as _b:
            _pe, _name = ypf.fetch_pe_name_maps()
            assert _a.call_count == 1 and _b.call_count == 1
        assert set(_pe) == {"5483"}

    def test_both_markets_empty_returns_empty_maps(self):
        _pe, _name = self._maps(pd.DataFrame(), pd.DataFrame())
        assert _pe == {} and _name == {}


# ════════════════════════════════════════════════════════════════════
# ⑤ 相容性:L5 re-export 仍然可用(app.py 與既有測試靠它)
# ════════════════════════════════════════════════════════════════════
def test_l5_reexport_points_at_the_same_l1_objects():
    """`from src.ui.tabs.yield_screener import fetch_pe_name_maps` 仍可用,
    且拿到的就是 L1 那個物件(不是複本 / 不是另一份實作 —— §2.1 SSOT)。"""
    from src.data.stock import yield_pe_fetcher as ypf
    from src.ui.tabs import yield_screener as ys
    for _fn in ("fetch_twse_yield_pe", "fetch_tpex_yield_pe", "fetch_pe_name_maps"):
        assert getattr(ys, _fn) is getattr(ypf, _fn), f"{_fn} re-export 不是同一物件"
    assert ys.TWSE_BWIBBU_URL == ypf.TWSE_BWIBBU_URL
    assert ys.TPEX_PERATIO_URL == ypf.TPEX_PERATIO_URL


def test_section_357_pbratio_reads_l1_fetcher():
    """L5 個股估值 section 的 P/B 取數改吃 L1,且 patch L1 就攔得到(行為證明)。"""
    from src.ui.tabs.stock_sections import section_357_valuation as _sec
    with contextlib.suppress(Exception):
        _sec._fetch_pbratio_from_twse.clear()
    _df = pd.DataFrame({"代碼": ["2330"], "名稱": ["台積電"], "股價淨值比": [5.5]})
    with patch(f"{_L1_MOD}.fetch_twse_yield_pe", return_value=_df) as _m:
        _pb = _sec._fetch_pbratio_from_twse("2330")
    assert _m.call_count == 1, "section_357 沒有走到 L1 fetcher(patch 目標可能過期)"
    assert _pb == pytest.approx(5.5)


def test_l5_shim_has_no_fetcher_implementation_left():
    """L5 只該剩 re-export —— 不得有第二份實作(否則 §2.1 SSOT 破功:
    UI 走一份、cron 走另一份,兩邊數字會漂)。"""
    _tree = ast.parse(_L5_PATH.read_text(encoding="utf-8"))
    _defs = {n.name for n in ast.walk(_tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    _dup = _defs & {"fetch_twse_yield_pe", "fetch_tpex_yield_pe", "fetch_pe_name_maps"}
    assert not _dup, (
        f"{_L5_PATH.name} 又出現 fetcher 實作(非 re-export):{sorted(_dup)} —— "
        "L1 已是 SSOT,L5 重新定義會造成兩份實作漂移"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
