"""P3-D(v19.199 對稱性稽核第三輪):health_inspector M1B 假綠燈 + etf_tab_ai None% 修正守衛。"""
from __future__ import annotations

import pathlib

_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _src(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def test_health_inspector_m1b_no_fake_fresh():
    """A(§1):M1B/M2 不再餵 cl_ts(抓取時間)當 as_of → 不假🟢當期;改標「有值·無資料日期」。"""
    s = _src("src/ui/pages/health_inspector.py")
    # M1B 那列不再用 cl_ts 當 date_str,改走 has_value_no_date
    assert "has_value_no_date=(_mi_g.get('m1b_yoy')" in s, "M1B 應改走 has_value_no_date 不餵 cl_ts"
    # _g_add 有第三態(有值但無日期 → 不綠不紅)
    assert "有值·無資料日期" in s
    assert "date_str=(_cl_ts_g if _mi_g.get('m1b_yoy') is not None else None)" not in s, \
        "舊的 cl_ts 假新鮮寫法須移除"


def test_etf_ai_war_row_none_safe():
    """B:war-row 對 present-but-None 的鍵(年輕ETF 的 1年報酬%等)不再輸出字面 'None%' 進 LLM。"""
    s = _src("src/ui/etf/etf_tab_ai.py")
    assert "def _wf(w, k" in s, "應有 None-safe helper"
    # 不再用 w.get(k,'—') 後直接接 %（present-but-None → None%）
    assert 'w.get("1年含息報酬%","—")' not in s
    assert 'w.get("折溢價%","—")' not in s
    assert 'w.get("距月線%","—")' not in s
