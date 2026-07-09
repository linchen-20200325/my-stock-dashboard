"""tests/test_shortage_cli.py — 缺貨 CLI（scripts/shortage_cli.py）測試（v19.67）。

驗報告格式化 + 單股輸入組裝 + main 流程（monkeypatch，不觸網）。計分本身由
test_shortage_screener.py 覆蓋，本檔只驗 CLI 這層薄殼。
"""
from __future__ import annotations

import importlib.util
import json
import os

import pandas as pd
import pytest

from src.compute.screener.shortage_screener import ShortageScore

# 以檔案路徑載入 scripts/shortage_cli.py（scripts 非 package）
_CLI_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                         "scripts", "shortage_cli.py")
_spec = importlib.util.spec_from_file_location("shortage_cli", _CLI_PATH)
cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli)


def _strong_score():
    return ShortageScore(
        stock_id="2330", name="台積電", total=100.0, tier="強缺貨", tier_icon="🟥",
        c1_contract_liab=35, c2_gross_margin=25, c3_inventory_days=20, c4_revenue_yoy=20,
        cl_na=False, reasons=["🟢合約負債YoY+33%", "🟢毛利率60.0%（雙升）"],
        metrics={"cl_yoy": 33.3, "cl_qoq": 25.0, "gm_t": 60.0, "gm_t1": 55.0,
                 "gm_t4": 50.0, "dio_t": 68.0, "dio_t1": 80.0, "dio_t4": 91.0,
                 "rev_yoy_last3": [16.0, 18.0, 22.0], "n_quarters": 8})


def _na_score():
    return ShortageScore(
        stock_id="2801", name="", total=0.0, tier="不適用", tier_icon="🚫",
        c1_contract_liab=0, c2_gross_margin=0, c3_inventory_days=0, c4_revenue_yoy=0,
        cl_na=False, reasons=["金融股不適用缺貨模型（毛利率/存貨/合約負債概念不通用）"],
        metrics={})


def test_format_strong_report_has_all_sections():
    txt = cli.format_score_report(_strong_score())
    assert "2330 台積電" in txt
    assert "綜合總分：100 / 100" in txt and "強缺貨" in txt
    assert "① 合約負債" in txt and "YoY +33.3%" in txt and "QoQ +25.0%" in txt
    assert "② 毛利率" in txt and "60.0%" in txt
    assert "③ 存貨天數" in txt and "68天" in txt
    assert "④ 月營收" in txt and "16.0" in txt


def test_format_na_report_short():
    txt = cli.format_score_report(_na_score())
    assert "2801" in txt and "不適用" in txt
    assert "金融股" in txt
    assert "① 合約負債" not in txt          # NA 不印明細


def test_format_report_json_roundtrip():
    out = cli.format_report([_strong_score()], as_json=True)
    data = json.loads(out)
    assert data[0]["stock_id"] == "2330"
    assert data[0]["total"] == 100.0
    assert data[0]["metrics"]["cl_yoy"] == 33.3


def test_build_stock_input_assembles(monkeypatch):
    _frame = [{"label": "2025Q1", "revenue": 1000, "gross_profit": 600,
               "cogs": 400, "contract_liab": 200, "inventory": 300}]
    _mrev = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=18, freq="MS"),
        "revenue": [100 + i * 8 for i in range(18)],
    })
    monkeypatch.setattr(cli, "fetch_quarterly_shortage_frame", lambda sid, months=12: _frame)
    monkeypatch.setattr(cli, "fetch_monthly_revenue", lambda sid, months=18: _mrev)

    d = cli.build_stock_input("2330")
    assert d["stock_id"] == "2330"
    assert d["is_finance"] is False
    assert d["quarters"] == _frame
    assert len(d["revenue_yoy_last3"]) == 3       # compute_yoy_mom 真算


def test_build_stock_input_finance_flag(monkeypatch):
    monkeypatch.setattr(cli, "fetch_quarterly_shortage_frame", lambda sid, months=12: [])
    monkeypatch.setattr(cli, "fetch_monthly_revenue", lambda sid, months=18: pd.DataFrame())
    assert cli.build_stock_input("2801")["is_finance"] is True


def test_load_ids_dedup(tmp_path):
    f = tmp_path / "wl.txt"
    f.write_text("2330\n# comment\n2317\n2330\n", encoding="utf-8")
    args = cli.main.__globals__  # noqa — 直接建 Namespace 較清楚
    import argparse
    ns = argparse.Namespace(stock_ids=["2330", "1590"], file=str(f), json=False)
    assert cli._load_ids(ns) == ["2330", "1590", "2317"]   # 去重保序


def test_main_no_token_returns_2(monkeypatch, capsys):
    monkeypatch.delenv("FINMIND_TOKEN", raising=False)
    monkeypatch.delenv("FM_TOKEN", raising=False)
    assert cli.main(["2330"]) == 2


def test_main_no_ids_returns_2(monkeypatch):
    monkeypatch.setenv("FINMIND_TOKEN", "dummy")
    assert cli.main([]) == 2


def test_main_end_to_end(monkeypatch, capsys):
    monkeypatch.setenv("FINMIND_TOKEN", "dummy")
    monkeypatch.setattr(cli, "build_stock_input", lambda sid: {
        "stock_id": sid, "name": "", "is_finance": False,
        "quarters": [
            {"label": "Q", "revenue": 1000, "gross_profit": 600, "cogs": 400,
             "contract_liab": 200, "inventory": 300},
            {"label": "Q", "revenue": 1000, "gross_profit": 550, "cogs": 400,
             "contract_liab": 160, "inventory": 350},
            {"label": "Q", "revenue": 1000, "gross_profit": 540, "cogs": 400,
             "contract_liab": 150, "inventory": 360},
            {"label": "Q", "revenue": 1000, "gross_profit": 530, "cogs": 400,
             "contract_liab": 150, "inventory": 380},
            {"label": "Q", "revenue": 1000, "gross_profit": 500, "cogs": 400,
             "contract_liab": 150, "inventory": 400},
            {"label": "Q", "revenue": 1000, "gross_profit": 500, "cogs": 400,
             "contract_liab": 140, "inventory": 400},
            {"label": "Q", "revenue": 1000, "gross_profit": 500, "cogs": 400,
             "contract_liab": 140, "inventory": 400},
            {"label": "Q", "revenue": 1000, "gross_profit": 500, "cogs": 400,
             "contract_liab": 140, "inventory": 400},
        ],
        "revenue_yoy_last3": [16.0, 18.0, 22.0],
    })
    rc = cli.main(["2330", "--json"])
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data[0]["stock_id"] == "2330"
    assert data[0]["tier"] == "強缺貨"
