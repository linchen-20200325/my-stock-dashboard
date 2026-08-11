"""板塊資金泡泡圖 Stage 2(UI)測試 — reader / L4 render / L3 service。

涵蓋:
- reader(L1):正常 / 缺檔 / 過期 / 缺 metadata 四情境(合成 JSON,不碰真實 cache)。
- render(L4):真 committed bubble_latest.json + highlight + 空 + insufficient(不丟例外)。
- service(L3):.TW/.TWO 正規化 + 板塊對映 + 未分類不 highlight + reader 缺檔透傳。
- AppTest(slow):真實 mount 分頁,配 committed 真資料,斷言無 uncaught exception。

§1:缺料/過期走 sentinel/旗標,不炸;§3.3:staleness 門檻走 L0 SSOT 常數。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from shared.sector_flow_thresholds import (
    SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS,
    QUADRANT_RISING,
    QUADRANT_EBBING,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_REAL_BUBBLE = _REPO_ROOT / "data_cache" / "sector_flow" / "bubble_latest.json"


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _sample_sectors():
    return [
        {"sector": "半導體業", "x_yi": 136.7, "y_yi": -21.4, "size_yi": 413.6,
         "quadrant": QUADRANT_EBBING, "n_days": 20, "insufficient": False},
        {"sector": "電子工業", "x_yi": 331.5, "y_yi": 14.2, "size_yi": 839.9,
         "quadrant": QUADRANT_RISING, "n_days": 20, "insufficient": False},
        {"sector": "新上市板塊", "x_yi": 1.0, "y_yi": None, "size_yi": 2.0,
         "quadrant": "資料不足", "n_days": 3, "insufficient": True},
    ]


# ═══════════════════════════════════════════════════════════════════════
# reader(L1)
# ═══════════════════════════════════════════════════════════════════════
def _point_reader(monkeypatch, tmp_path):
    """把 reader 的三個路徑常數指到 tmp,隔離真實 cache。"""
    from src.data.sector_flow import reader as R
    monkeypatch.setattr(R, "BUBBLE_PATH", tmp_path / "bubble_latest.json")
    monkeypatch.setattr(R, "META_PATH", tmp_path / "metadata.json")
    monkeypatch.setattr(R, "TICKER_SECTOR_PATH", tmp_path / "ticker_sector.json")
    return R


def test_reader_normal(monkeypatch, tmp_path):
    R = _point_reader(monkeypatch, tmp_path)
    (tmp_path / "bubble_latest.json").write_text(json.dumps({
        "updated_at": "2026-08-10T23:39:52+00:00", "window_size": 20,
        "n_trading_days_used": 20, "sectors": _sample_sectors(),
    }), encoding="utf-8")
    (tmp_path / "metadata.json").write_text(json.dumps({
        "updated_at": _iso(datetime.now(timezone.utc) - timedelta(hours=6)),
    }), encoding="utf-8")
    (tmp_path / "ticker_sector.json").write_text(json.dumps({
        "2330": "半導體業", "2317": "其他電子業",
    }), encoding="utf-8")

    v = R.read_sector_flow_cache()
    assert v["ok"] is True
    assert len(v["sectors"]) == 3
    assert v["is_stale"] is False
    assert v["stale_reason"] is None
    assert v["ticker_sector"]["2330"] == "半導體業"
    assert v["window_size"] == 20


def test_reader_missing_bubble(monkeypatch, tmp_path):
    R = _point_reader(monkeypatch, tmp_path)
    v = R.read_sector_flow_cache()
    assert v["ok"] is False
    assert "reason" in v and v["reason"]


def test_reader_stale(monkeypatch, tmp_path):
    R = _point_reader(monkeypatch, tmp_path)
    (tmp_path / "bubble_latest.json").write_text(json.dumps({
        "updated_at": "2026-01-01T00:00:00+00:00", "window_size": 20,
        "n_trading_days_used": 20, "sectors": _sample_sectors(),
    }), encoding="utf-8")
    # metadata 明顯超過門檻(門檻 + 5 天前)
    old = datetime.now(timezone.utc) - timedelta(
        days=SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS + 5)
    (tmp_path / "metadata.json").write_text(json.dumps({"updated_at": _iso(old)}),
                                            encoding="utf-8")
    v = R.read_sector_flow_cache()
    assert v["ok"] is True          # 仍回資料(過期不等於缺)
    assert v["is_stale"] is True
    assert "門檻" in (v["stale_reason"] or "")


def test_reader_missing_metadata_is_stale(monkeypatch, tmp_path):
    R = _point_reader(monkeypatch, tmp_path)
    (tmp_path / "bubble_latest.json").write_text(json.dumps({
        "updated_at": "2026-08-10T00:00:00+00:00", "window_size": 20,
        "n_trading_days_used": 20, "sectors": _sample_sectors(),
    }), encoding="utf-8")
    # 無 metadata.json → §1 不假設新鮮
    v = R.read_sector_flow_cache()
    assert v["ok"] is True
    assert v["is_stale"] is True
    assert v["ticker_sector"] == {}   # 無 ticker_sector.json → 空 dict(graceful)


def test_reader_corrupt_bubble(monkeypatch, tmp_path):
    R = _point_reader(monkeypatch, tmp_path)
    (tmp_path / "bubble_latest.json").write_text("{not valid json", encoding="utf-8")
    v = R.read_sector_flow_cache()
    assert v["ok"] is False


# ═══════════════════════════════════════════════════════════════════════
# render(L4)— 純繪圖,不需 streamlit
# ═══════════════════════════════════════════════════════════════════════
def test_build_figure_real_committed_data():
    import plotly.graph_objects as go
    from src.ui.render.sector_flow_render import build_sector_flow_figure
    assert _REAL_BUBBLE.exists(), "committed bubble_latest.json 應存在"
    payload = json.loads(_REAL_BUBBLE.read_text(encoding="utf-8"))
    fig = build_sector_flow_figure(payload["sectors"])
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1          # 至少一個象限 trace


def test_build_figure_highlight_trace():
    from src.ui.render.sector_flow_render import build_sector_flow_figure
    fig = build_sector_flow_figure(_sample_sectors(),
                                   highlight_sectors={"半導體業"})
    names = [t.name for t in fig.data]
    assert any("你的持股" in (n or "") for n in names), \
        "highlight 應產生「你的持股」外環 trace"
    # 半導體業(退潮)也應在退潮 trace 內
    assert any("退潮" in (n or "") for n in names)


def test_build_figure_insufficient_not_plotted():
    from src.ui.render.sector_flow_render import build_sector_flow_figure
    fig = build_sector_flow_figure(_sample_sectors())
    plotted = set()
    for t in fig.data:
        for txt in (t.text or []):
            plotted.add(txt)
    # insufficient 板塊不進象限(§1 不硬塞),但正常兩檔要在
    assert "新上市板塊" not in plotted
    assert "半導體業" in plotted and "電子工業" in plotted


def test_build_figure_empty_graceful():
    import plotly.graph_objects as go
    from src.ui.render.sector_flow_render import build_sector_flow_figure
    fig = build_sector_flow_figure([])
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0          # 空圖只有註解,無 trace


# ═══════════════════════════════════════════════════════════════════════
# service(L3)
# ═══════════════════════════════════════════════════════════════════════
def _fake_view():
    return {
        "ok": True,
        "sectors": _sample_sectors(),
        "updated_at": "2026-08-10T23:39:52+00:00",
        "window_size": 20, "n_trading_days_used": 20,
        "ticker_sector": {"2330": "半導體業", "2317": "電子工業", "9999": "未分類"},
        "is_stale": False, "stale_reason": None,
        "meta_updated_at": "2026-08-10T23:39:52+00:00",
    }


def test_service_normalizes_and_maps(monkeypatch):
    from src.data.sector_flow import reader as R
    monkeypatch.setattr(R, "read_sector_flow_cache", lambda: _fake_view())
    from src.services.sector_flow_service import get_sector_flow_view
    # .TW / .TWO 後綴須被剝除才對得上裸碼
    v = get_sector_flow_view(etf_tickers=["2330.TW", "2317.TWO"],
                             include_stock_watchlists=False)
    assert v["highlight_sectors"] == {"半導體業", "電子工業"}


def test_service_unclassified_not_highlighted(monkeypatch):
    from src.data.sector_flow import reader as R
    monkeypatch.setattr(R, "read_sector_flow_cache", lambda: _fake_view())
    from src.services.sector_flow_service import get_sector_flow_view
    v = get_sector_flow_view(etf_tickers=["9999"], include_stock_watchlists=False)
    # 9999 → 未分類:不 highlight(避免亂框)
    assert v["highlight_sectors"] == set()
    assert v["holding_sectors"]["9999"] == "未分類"


def test_service_reader_not_ok_passthrough(monkeypatch):
    from src.data.sector_flow import reader as R
    monkeypatch.setattr(R, "read_sector_flow_cache",
                        lambda: {"ok": False, "reason": "缺快取"})
    from src.services.sector_flow_service import get_sector_flow_view
    v = get_sector_flow_view(etf_tickers=["2330.TW"])
    assert v["ok"] is False
    assert v["highlight_sectors"] == set()
    assert v["holding_sectors"] == {}


# ═══════════════════════════════════════════════════════════════════════
# AppTest smoke(slow)— 真實 mount 分頁
# ═══════════════════════════════════════════════════════════════════════
@pytest.mark.slow
def test_apptest_render_tab_sector_flow_real_data():
    try:
        from streamlit.testing.v1 import AppTest
    except ImportError:
        pytest.skip("streamlit.testing.v1.AppTest 不可用")
    drv = (
        "import sys, os\n"
        "sys.path.insert(0, os.getcwd())\n"
        "import streamlit as st\n"
        "from src.ui.tabs.tab_sector_flow import render_tab_sector_flow\n"
        "render_tab_sector_flow()\n"
    )
    at = AppTest.from_string(drv, default_timeout=90)
    at.run()
    if at.exception:
        msgs = [f"{e.type}: {str(e.value)[:300]}" for e in at.exception]
        pytest.fail("render_tab_sector_flow 有 uncaught exception:\n" + "\n".join(msgs))
