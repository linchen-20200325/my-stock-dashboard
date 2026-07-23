"""src/data/stock/quarterly_financials_fetcher.py — 缺貨選股用季度財報 L1 fetcher（v19.65）。

一次抓齊「缺貨評分」所需的季度序列，對齊成單一 frame：
  • 損益表 TaiwanStockFinancialStatements → 營業收入 / 毛利 / 營業成本
  • 資產負債表 TaiwanStockBalanceSheet     → 合約負債 / 存貨

回傳「由近到遠」的季度 list[dict]，直接餵給 L2 `shortage_screener.score_shortage`。

§8.2 layer:L1 Data — 只抓取 + 解析,無評分邏輯(評分在 L2)。
§8.2.A EX-CACHE-1:條件 import streamlit,僅 @st.cache_data,無真 UI 呼叫。
§2.2 / S-PROV-1:provenance 注入(此函式回 list 而非 DataFrame,provenance 由 caller
  service 記於掃描 meta)。
§1 fail-loud:缺科目/缺季 → 該欄 None(下游標「資料不足/無科目」),**不補 0 造假**;
  抓取失敗回空 list,不拋。

FinMind TaiwanStockFinancialStatements 的季度值本專案一律視為「單季」(與
tab_stock_picker `_check_three_rate_growth` / `_check_pe_zone` TTM 加總同一假設),
故 caller 可安全對其做「近 4 季加總」年化。
"""
from __future__ import annotations

import datetime as _dt
import os

import pandas as pd

try:
    import streamlit as st
except ImportError:
    class _NoOpST:
        @staticmethod
        def cache_data(*args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            return lambda f: f
        cache_resource = cache_data
        secrets: dict = {}
    st = _NoOpST()  # noqa

from shared.ttls import TTL_1DAY
from src.data.core.finmind_client import finmind_get

# ── 會計科目別名（英文 IFRS code + 中文 origin_name 混合，比照 data_loader 既有慣例）──
# B4(SSOT-H1):FinMind FS 欄碼別名搬至 shared/finmind_subject_aliases.py,import 回原名。
from shared.finmind_subject_aliases import (
    FINMIND_FS_REVENUE_KEYS as _REVENUE_KEYS,
    FINMIND_FS_GROSS_KEYS as _GROSS_KEYS,
    FINMIND_FS_COGS_KEYS as _COGS_KEYS,
    FINMIND_FS_INV_KEYS as _INV_KEYS,
)
_CL_SUBSTR = "合約負債"   # str.contains 主路徑（涵蓋 流動/非流動 各種 dash 變體）
_CL_ENG_KEYS = ("ContractLiabilities", "CurrentContractLiabilities",
                "NonCurrentContractLiabilities", "ContractLiabilitiesCurrent",
                "ContractLiabilitiesNonCurrent", "契約負債", "預收款項")


def _get_token() -> str:
    return (os.environ.get("FINMIND_TOKEN", "") or os.environ.get("FM_TOKEN", ""))


def _num(v) -> float | None:
    try:
        f = float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def _first_hit(slot: dict, keys) -> float | None:
    """slot={key: value}，回第一個非零命中的 |value|（缺 → None，§1 顯式旗標）。"""
    for k in keys:
        if k in slot:
            v = _num(slot[k])
            if v is not None and v != 0:
                return abs(v)
    return None


def _index_rows(rows: list) -> dict:
    """FinMind long rows → {date: {type/origin_name: value}}（type 與 origin_name 皆索引）。"""
    out: dict[str, dict] = {}
    for r in rows:
        d = r.get("date", "")
        if not d:
            continue
        slot = out.setdefault(d, {})
        _t = r.get("type", "")
        _o = r.get("origin_name", "")
        if _t:
            slot[_t] = r.get("value", 0)
        if _o:
            slot[_o] = r.get("value", 0)
    return out


def _sum_contract_liab(rows: list) -> dict:
    """{date: 合約負債合計}。主路徑 str.contains('合約負債') 加總（流動+非流動），
    備援英文 key。缺 → 不建 key（下游 None → cl_na）。"""
    if not rows:
        return {}
    df = pd.DataFrame(rows)
    out: dict[str, float] = {}
    if not df.empty and {"date", "value"}.issubset(df.columns):
        _typ = df["type"].astype(str) if "type" in df.columns else pd.Series([""] * len(df))
        _org = df["origin_name"].astype(str) if "origin_name" in df.columns else pd.Series([""] * len(df))
        _mask = _typ.str.contains(_CL_SUBSTR, na=False) | _org.str.contains(_CL_SUBSTR, na=False)
        _hit = df[_mask]
        for _d, _grp in _hit.groupby("date"):
            _vals = pd.to_numeric(
                _grp["value"].astype(str).str.replace(",", "", regex=False),
                errors="coerce").abs()
            _vals = _vals[_vals > 0]
            if len(_vals) > 0:
                out[str(_d)] = float(_vals.sum())
    # 英文 key 備援（僅補未命中的季）
    _idx = _index_rows(rows)
    for _d, _slot in _idx.items():
        if _d in out:
            continue
        _v = _first_hit(_slot, _CL_ENG_KEYS)
        if _v is not None:
            out[_d] = _v
    return out


def _finmind_rows_first(datasets: tuple, stock_id: str, start: str, tok: str) -> list:
    """依序試多個 dataset 名,回第一個非空的 rows(list[dict])。全空/全失敗回 []。

    用於相容 FinMind 免費/付費版 dataset 命名差異(如財報 無s/有s)。
    """
    for _ds in datasets:
        try:
            _df = finmind_get(_ds, data_id=stock_id, start_date=start, token=tok, timeout=25)
        except Exception as _e:  # noqa: BLE001 — 換下一個 dataset 名
            print(f"[qtr-shortage] {stock_id} {_ds} 失敗: {type(_e).__name__}: {_e}")
            continue
        if isinstance(_df, pd.DataFrame) and not _df.empty:
            return _df.to_dict("records")
    return []


@st.cache_data(ttl=TTL_1DAY, show_spinner=False)
def fetch_quarterly_shortage_frame(stock_id: str, quarters: int = 12) -> list[dict]:
    """抓齊缺貨評分所需的季度序列，回「由近到遠」list[dict]。

    Args:
        stock_id: 純台股代碼如 '2330'
        quarters: 最多回傳季數（預設 12）

    Returns:
        list[dict]（近→遠）每季:
          {label, date, revenue, gross_profit, cogs, contract_liab, inventory}
        缺科目該欄為 None;抓取失敗回 []。
    """
    _tok = _get_token()
    if not _tok:
        return []
    _start = (_dt.date.today() - _dt.timedelta(days=365 * 3 + 120)).strftime("%Y-%m-%d")

    # 損益表:免費版 dataset 名 `TaiwanStockFinancialStatement`(無 s),付費版有 s → 兩個都試
    # (對齊 data_loader.get_quarterly_data:1068 既有慣例;缺這步 → 免費方案每檔 0 季→全「資料不足」)
    _is_rows = _finmind_rows_first(
        ("TaiwanStockFinancialStatement", "TaiwanStockFinancialStatements"),
        stock_id, _start, _tok)
    _bs_rows = _finmind_rows_first(("TaiwanStockBalanceSheet",), stock_id, _start, _tok)
    if not _is_rows and not _bs_rows:
        print(f"[qtr-shortage] {stock_id}: 損益表+資產負債表皆無資料(方案權限/配額/停牌?)")
        return []

    _is_idx = _index_rows(_is_rows)
    _bs_idx = _index_rows(_bs_rows)
    _cl_map = _sum_contract_liab(_bs_rows)

    _all_dates = sorted(set(_is_idx) | set(_bs_idx), reverse=True)  # 近→遠
    _out: list[dict] = []
    for _d in _all_dates[:quarters]:
        try:
            _ts = pd.Timestamp(_d)
            _label = f"{_ts.year}Q{((_ts.month - 1) // 3) + 1}"
        except Exception:
            continue
        _is_slot = _is_idx.get(_d, {})
        _bs_slot = _bs_idx.get(_d, {})
        _rev = _first_hit(_is_slot, _REVENUE_KEYS)
        _gp = _first_hit(_is_slot, _GROSS_KEYS)
        _cogs = _first_hit(_is_slot, _COGS_KEYS)
        # 毛利缺但營收/成本齊 → 用定義補算(gp = 營收 − 成本;同 data_loader.py:2106,非造假)
        if _gp is None and _rev is not None and _cogs is not None:
            _gp = _rev - _cogs
        _out.append({
            "label": _label,
            "date": _d,
            "revenue": _rev,
            "gross_profit": _gp,
            "cogs": _cogs,
            "contract_liab": _cl_map.get(_d),
            "inventory": _first_hit(_bs_slot, _INV_KEYS),
        })
    return _out
