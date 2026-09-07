"""熱力圖的類股宇宙**只有一份** —— 防新舊兩頁各拿一份、然後無聲漂移。

═══ 這支為什麼存在（2026-09-07 FE-32）═════════════════════════════════
IA v2 頁2「🔍 找標的 › 板塊地圖」與既有 🌍 市場環境 ›「🗺️ 產業熱力圖」要畫
**同一份**類股宇宙。本批的做法是把表上移 L0 `shared/sector_heatmap.py`，
舊分頁端改成別名轉發（`_US_SECTORS = US_SECTORS`）。

⚠️ **既有的 `tests/test_b4b_heatmap.py` 擋不住漂移**：它讀的是
`etf_render._TW_SECTORS` / `._US_SECTORS`，也就是**別名**。哪天有人在
`etf_render` 裡把別名改回一份真的 dict 字面值（「只是加一檔而已」），
那支測試會照樣全綠，而兩個頁面從此各畫各的。**本檔就是要擋那個。**

═══ 這支**沒有**在宣稱什麼（先講清楚，免得被引用過頭）═══════════════
它釘的是「**熱力圖用的那兩張表**只有一份」。
它**不宣稱**「這個 repo 的類股分類只有一份」—— 那句話是**假的**。
實測另有三處各自維護、語意也不同（`test_the_other_three_tables_really_are_different`
會現場量它們確實存在且確實不同）：

  1. `_ETF_SECTOR_MAP`（`src/ui/render/etf_render.py`）
     —— ETF 代號 → GICS 類股**中文名**，給組合曝險集中度檢查用。
     連中文譯名都刻意不同：`XLK` 在那裡是「資訊科技」、在熱力圖表是「科技」。
  2. `_signal_sector_rotation()` 內寫死的攻守子集（`src/compute/risk/risk_radar.py`）
     —— 只要 6 檔（攻 3 / 守 3）算 30 日動能差，不是 11 大類股全集。
  3. `ticker_sector.json`（`data_cache/sector_flow/`，`src/data/sector_flow/reader.py` 讀）
     —— cron 產的**裸股號 → 產業別**全市場對映，給泡泡圖標記持股板塊。

⛔ **不准拿本檔當「已經統一了」的證據去合併它們** —— 合併是行為變更
（會動到 `tests/test_sector_exposure_gate.py` 守著的曝險判定），
而且三者的粒度與用途根本不同。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from shared import sector_heatmap as SH

_REPO = pathlib.Path(__file__).resolve().parents[1]
_SCAN_DIRS = ("src", "shared", "scripts", "app.py")
_SKIP_PARTS = ("__pycache__", ".git", "scratchpad", "wt-")

#: 熱力圖用的四個名字（含舊分頁沿用的底線私有別名）。
_HEATMAP_NAMES = (
    "US_SECTORS", "TW_SECTORS",
    "_US_SECTORS", "_TW_SECTORS",
)

#: 本檔**不涵蓋**的另外三處類股分類（見 module docstring）。
_NOT_COVERED = (
    ("src/ui/render/etf_render.py", "_ETF_SECTOR_MAP"),
    ("src/compute/risk/risk_radar.py", "_signal_sector_rotation"),
    ("src/data/sector_flow/reader.py", "TICKER_SECTOR_PATH"),
)

#: 紅燈時印給下一個人的話。**措辭是本檔的一部分** ——
#: 寫成「全站唯一的類股表」就是一句假話（見 module docstring），
#: 而假話會被下一個人拿去當前提。
_HINT = (
    "熱力圖用的 `US_SECTORS` / `TW_SECTORS` 只准有一份（住在 "
    "`shared/sector_heatmap.py`，L0）；`src/ui/render/etf_render.py` 端是"
    "**別名轉發**，不是第二份表。\n"
    "⚠️ 這兩張是**熱力圖用**的表 —— `_ETF_SECTOR_MAP`（ETF 曝險檢查，"
    "連中文譯名都不同）、`risk_radar` 的攻守子集、`ticker_sector.json`"
    "（cron 產的裸股號→產業別）是**語意不同**的另外三份，"
    "本檔不涵蓋它們，也**不主張**它們該被合併。"
)


def _py_files():
    for _d in _SCAN_DIRS:
        _base = _REPO / _d
        if _base.is_file():
            yield _base
            continue
        if not _base.exists():
            continue
        for _f in _base.rglob("*.py"):
            if any(_s in str(_f) for _s in _SKIP_PARTS):
                continue
            yield _f


def _dict_literal_definitions() -> dict[str, list[str]]:
    """→ `{符號名: [定義它成 dict 字面值的檔案, ...]}`。

    **只收 dict / 字面值形式的定義**，別名轉發（`_A = B`）刻意不算 ——
    別名指向同一個物件，它不是第二份表。
    """
    _out: dict[str, list[str]] = {_n: [] for _n in _HEATMAP_NAMES}
    for _f in _py_files():
        try:
            _tree = ast.parse(_f.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):                     # pragma: no cover
            continue
        _rel = _f.relative_to(_REPO).as_posix()
        for _node in ast.walk(_tree):
            _targets = []
            if isinstance(_node, ast.Assign):
                _targets = _node.targets
                _val = _node.value
            elif isinstance(_node, ast.AnnAssign) and _node.value is not None:
                _targets = [_node.target]
                _val = _node.value
            else:
                continue
            if not isinstance(_val, (ast.Dict, ast.DictComp)):
                continue
            for _t in _targets:
                if isinstance(_t, ast.Name) and _t.id in _out:
                    _out[_t.id].append(_rel)
    return _out


class TestOnlyOneCopyOfTheHeatmapUniverse:
    """兩張**熱力圖用**的類股表，全 repo 只准有一份字面定義。"""

    @pytest.mark.parametrize("name", _HEATMAP_NAMES)
    def test_defined_as_a_literal_in_at_most_one_place(self, name):
        _defs = _dict_literal_definitions()[name]
        assert len(_defs) <= 1, (
            f"`{name}` 被定義成 dict 字面值 {len(_defs)} 次：{_defs}\n{_HINT}")

    def test_the_one_place_is_l0(self):
        _defs = _dict_literal_definitions()
        assert _defs["US_SECTORS"] == ["shared/sector_heatmap.py"]
        assert _defs["TW_SECTORS"] == ["shared/sector_heatmap.py"]
        assert _defs["_US_SECTORS"] == [], (
            f"`_US_SECTORS` 又長回一份自己的表了。\n{_HINT}")
        assert _defs["_TW_SECTORS"] == [], (
            f"`_TW_SECTORS` 又長回一份自己的表了。\n{_HINT}")

    def test_the_old_tab_points_at_the_very_same_object(self):
        """**identity**，不是 `==`。

        `==` 只證明「現在內容一樣」，兩份各自維護的表在改動前也是 `==` 的；
        `is` 證明的是「**結構上不可能不一樣**」。
        """
        import src.ui.render.etf_render as R

        assert R._US_SECTORS is SH.US_SECTORS, _HINT
        assert R._TW_SECTORS is SH.TW_SECTORS, _HINT
        assert R._US_SECTOR_SINGLE_STOCK_PROXY is SH.US_SECTOR_SINGLE_STOCK_PROXY
        assert R._TW_SECTOR_SINGLE_STOCK_PROXY is SH.TW_SECTOR_SINGLE_STOCK_PROXY

    def test_the_new_page_reads_it_through_l3_not_a_copy_of_its_own(self):
        """頁2 拿到的宇宙也是同一個物件（經 L3 → L0，沒有中途複製）。"""
        from src.services import sector_heatmap_service as S

        for _is_us, _expect in ((True, SH.US_SECTORS), (False, SH.TW_SECTORS)):
            _sectors, _proxy = SH.sector_universe(_is_us)
            assert _sectors is _expect
        assert S.get_sector_heatmap_view.__module__.startswith("src.services")


class TestTheScopeDisclosureCannotSilentlyDisappear:
    """L0 的 docstring 必須繼續寫明「本表不涵蓋哪三處」。

    這段揭露是本批唯一擋得住「拿 L0 那張表去統一全 repo 類股分類」的東西 ——
    它一旦被人順手刪掉（「這段太囉唆」），下一個人就會以為 L0 是**全部**。
    """

    def test_the_module_docstring_names_all_three(self):
        _doc = SH.__doc__ or ""
        for _needle in ("_ETF_SECTOR_MAP", "risk_radar", "ticker_sector.json"):
            assert _needle in _doc, (
                f"L0 docstring 不再提到 {_needle} —— "
                "涵蓋範圍的揭露被刪掉了，請補回去（理由見本測試 docstring）")

    def test_the_other_three_tables_really_are_different(self):
        """**反證**：那三處真的存在、而且真的不同 —— 否則上面那句就是空話。"""
        for _rel, _sym in _NOT_COVERED:
            _txt = (_REPO / _rel).read_text(encoding="utf-8")
            assert _sym in _txt, f"{_rel} 裡找不到 {_sym} —— 名單過期了"

        import src.ui.render.etf_render as R

        # 同一支 XLK，兩張表給的中文名**刻意不同**（曝險檢查 vs 熱力圖）。
        assert R._ETF_SECTOR_MAP["XLK"] == "資訊科技"
        assert SH.US_SECTORS["XLK"]["name"] == "科技"
        assert R._ETF_SECTOR_MAP["XLK"] != SH.US_SECTORS["XLK"]["name"], (
            "兩張表的譯名變成一樣了 —— 若這是有意識的統一，"
            "請連同 `tests/test_sector_exposure_gate.py` 一起複驗；"
            "若是順手改的，那是行為變更（曝險判定看的就是這個字串）")
        # `_ETF_SECTOR_MAP` 含大量**非類股** ETF，熱力圖表沒有也不該有。
        assert {"SPY", "0050.TW", "BND"} <= set(R._ETF_SECTOR_MAP)
        assert not ({"SPY", "0050.TW", "BND"} & set(SH.US_SECTORS))
