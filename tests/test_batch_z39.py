"""批 Z39：板塊資金泡泡圖缺值不再補 0、TPEx 診斷與「目前僅含上市資料」資料驅動提示。

客戶裁示（2026-10-11 已核准）：
  · **Q-z26 = A**：未取得／未觀測 → NaN；真實 0 → 0；有效正負值 → 原值。Z38 的
    `_get_t86_day` 找不到外資欄回 NaN，不得在後段彙總被 fillna(0) 抵銷；缺值板塊顯示「未取得」。
  · **Q-z28 = A**：TPEx 未正式恢復前，泡泡圖以灰字逐字顯示「目前僅含上市資料」；
    TPEx 恢復且整個窗口驗證成功後自動移除（資料驅動）。
  · 診斷：TPEx 失敗 log 印 body 前 500 字（洗秘密）；metadata 記 TWSE／TPEx 各自成敗；
    source 只列實際成功的市場；invariant：預期有 TPEx 但 0 筆／parser failure → 不得標 TPEx success。

突變：每一條核心修正都有一支「把修正換回修前寫法 → 斷言轉紅」的測試（`_mutant()` 以原始碼
逐字置換、在獨立模組物件中執行，不影響本尊）。L1 兩檔另有 `Z39_REVERT_PAIRS`（修後逐字 →
基底 `299c50ec` 逐字，sha256 自證）用來證明 L1 診斷**零行為變更**（回傳值與快取語意同基底）。
"""
from __future__ import annotations

import functools
import hashlib
import importlib.util
import json
import math
import pathlib
import sys
from contextlib import contextmanager

import numpy as np
import pandas as pd
import pytest

import scripts.update_sector_flow as U
import src.data.core.data_loader_inst_fetchers as ifx
import src.data.stock.market_close_fetcher as mcf
from shared.sector_flow_thresholds import (
    QUADRANT_INSUFFICIENT,
    QUADRANT_UNAVAILABLE,
    SECTOR_FLOW_TWSE_ONLY_NOTE,
    format_unavailable_caption,
)
from shared.ui_state import UI_EMPTY, UI_LIVE
from src.compute.sector_flow import compute_bubble, compute_sector_daily_net

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_L2 = "src/compute/sector_flow.py"
_SCRIPT = "scripts/update_sector_flow.py"
_RENDER = "src/ui/render/sector_flow_render.py"
_TAB = "src/ui/tabs/tab_sector_flow.py"
_READER = "src/data/sector_flow/reader.py"
_PF = "src/ui/views/page_find.py"
_DIAG = "shared/http_diag.py"
_INST = "src/data/core/data_loader_inst_fetchers.py"
_CLOSE = "src/data/stock/market_close_fetcher.py"


# ══════════════════════════════════════════════════════════════════════════
# 0. 突變 / 還原 infra
# ══════════════════════════════════════════════════════════════════════════
_MUT_SEQ = [0]


def _mutant(rel: str, pairs, tag: str = "m"):
    """現行檔逐字置換 `pairs`（修後 → 修前）後，在獨立模組物件中執行（不影響本尊）。"""
    path = _ROOT / rel
    code = path.read_text(encoding="utf-8")
    for new, old in pairs:
        assert code.count(new) == 1, f"{rel} 替換點不唯一或已不存在：{new!r}"
        code = code.replace(new, old)
    _MUT_SEQ[0] += 1
    name = f"_z39_{tag}_{_MUT_SEQ[0]}"
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    m.__file__ = str(path)
    sys.modules[name] = m
    exec(compile(code, str(path), "exec"), m.__dict__)
    return m


#: L1 兩檔：修後逐字 → 基底 `299c50ec` 逐字（difflib 由實檔產生、round-trip 驗過）。
Z39_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {
    _INST: (
        ('\nfrom shared.http_diag import scrubbed_body_head\n',
         '\n'),
        ('_TPEX_FAIL_TS: dict = {}   # {日期字串: 失敗時間 epoch};TTL_15MIN 內不重打\n# 批 Z39(客戶 Q-z28 診斷;零行為變更):每次**實際打出請求**後記錄該日的結果狀態,\n# 供 cron 區分「TPEx 假日回空」與「交易日 TPEx 失敗」。回傳值與快取語意一字不變。\n#   ok             JSON 有 aaData 且欄位驗證(buy-sell≈net)通過\n#   empty          JSON 正常但 aaData 空(假日或 TPEx 交易日回空,需由 caller 對照 TWSE 判定)\n#   http_none      fetch_url 回 None(網路/proxy/非 2xx)\n#   json_error     回應不是 JSON(例:改版或擋爬回 HTML)\n#   col_unverified 欄位驗證 for/else 失敗(仍沿用預設索引回資料,但不得當成成功)\n#   exception      其他例外\n# 快取命中 / 負快取命中不重設狀態(沿用上一次實際請求的結果)。\n_TPEX_DAY_DIAG: dict[str, str] = {}\nTPEX_DAY_STATUS_OK: str = "ok"\n\n\ndef get_tpex_day_status(ds: str) -> str | None:\n    """`_get_tpex_day(ds)` 最近一次實際請求的狀態(見 `_TPEX_DAY_DIAG`);從未請求 → None。"""\n    return _TPEX_DAY_DIAG.get(ds)\n\n\ndef _log_tpex_body(ds: str, status: str, r) -> None:\n    """批 Z39:失敗分支印 response body 前 500 字(先洗秘密;只印 body,不印 headers/proxy/token)。"""\n    print(f\'[TPEx] {ds} status={status} body[:500]={scrubbed_body_head(r)!r}\')\n',
         '_TPEX_FAIL_TS: dict = {}   # {日期字串: 失敗時間 epoch};TTL_15MIN 內不重打\n'),
        ("           'Referer': 'https://www.tpex.org.tw/'}\n    r = None   # 批 Z39:例外分支印 body 用(請求前就炸 → 無 body 可印)\n",
         "           'Referer': 'https://www.tpex.org.tw/'}\n"),
        ("        if r is None:\n            _TPEX_DAY_DIAG[ds] = 'http_none'\n",
         '        if r is None:\n'),
        ("            return {}\n        try:\n            j = r.json()\n        except ValueError as e:\n            # 批 Z39:非 JSON(改版/擋爬 HTML)單獨記狀態 + 印 body;回傳與負快取同原 except 分支\n            _TPEX_DAY_DIAG[ds] = 'json_error'\n            _log_tpex_body(ds, 'json_error', r)\n            print(f'[TPEx] {ds} 失敗: {e}')\n            _TPEX_FAIL_TS[ds] = _t_tp.time()\n            return {}\n",
         '            return {}\n        j = r.json()\n'),
        ("        if not rows_data:\n            _TPEX_DAY_DIAG[ds] = 'empty'\n            _log_tpex_body(ds, 'empty', r)\n",
         '        if not rows_data:\n'),
        ('        f_idx, t_idx, d_idx = 4, 7, 10  # 預設索引\n        _status = TPEX_DAY_STATUS_OK   # 批 Z39:for/else 失敗 → col_unverified\n',
         '        f_idx, t_idx, d_idx = 4, 7, 10  # 預設索引\n'),
        ("            print(f'[TPEx] {ds} 欄位驗證失敗，row長度={len(rows_data[0]) if rows_data else 0}，使用預設索引')\n            _status = 'col_unverified'\n            _log_tpex_body(ds, _status, r)\n",
         "            print(f'[TPEx] {ds} 欄位驗證失敗，row長度={len(rows_data[0]) if rows_data else 0}，使用預設索引')\n"),
        ('        _TPEX_DAY_CACHE[ds] = day_data\n        _TPEX_DAY_DIAG[ds] = _status\n',
         '        _TPEX_DAY_CACHE[ds] = day_data\n'),
        ("        print(f'[TPEx] {ds} 失敗: {e}')\n        _TPEX_DAY_DIAG[ds] = 'exception'\n        if r is not None:\n            _log_tpex_body(ds, 'exception', r)\n",
         "        print(f'[TPEx] {ds} 失敗: {e}')\n"),
    ),
    _CLOSE: (
        ('\nfrom shared.http_diag import scrubbed_body_head\n',
         '\n'),
        ('\n#: 批 Z39(客戶 Q-z28 診斷;零行為變更):`fetch_tpex_close_day(ds)` 最近一次呼叫的結果狀態。\n#:   ok / empty(aaData 空)/ parse_zero(有列但解析 0 筆)/ http_none(None)/\n#:   http_error(非 200)/ json_error(非 JSON)/ exception。回傳值一字不變。\n_TPEX_CLOSE_DIAG: dict[str, str] = {}\n\n\ndef get_tpex_close_status(ds: str) -> str | None:\n    """`fetch_tpex_close_day(ds)` 最近一次呼叫的狀態;從未呼叫 → None。"""\n    return _TPEX_CLOSE_DIAG.get(ds)\n\n\n',
         '\n'),
        ('    假日/無資料 → aaData 空 → 回 {}(§1 自然排除)。\n    批 Z39:各分支記 `_TPEX_CLOSE_DIAG[ds]`;「解析 0 筆」與例外分支印洗過的 body 前 500 字。\n',
         '    假日/無資料 → aaData 空 → 回 {}(§1 自然排除)。\n'),
        ('    """\n    r = None\n',
         '    """\n'),
        ('        if r is None or getattr(r, "status_code", 0) != 200:\n            _TPEX_CLOSE_DIAG[ds] = "http_none" if r is None else "http_error"\n',
         '        if r is None or getattr(r, "status_code", 0) != 200:\n'),
        ('            return {}\n        try:\n            j = r.json()\n        except ValueError as e:\n            # 批 Z39:非 JSON 單獨記狀態;回傳 / log 前綴同原 except 分支\n            _TPEX_CLOSE_DIAG[ds] = "json_error"\n            print(f"[TPEX close] {ds} 失敗: {type(e).__name__}: {e} "\n                  f"body[:500]={scrubbed_body_head(r)!r}")\n            return {}\n',
         '            return {}\n        j = r.json()\n'),
        ('        if not out:\n            _TPEX_CLOSE_DIAG[ds] = "parse_zero" if rows else "empty"\n            print(f"[TPEX close] {ds} ({roc_date}) 解析 0 筆 "\n                  f"body[:500]={scrubbed_body_head(r)!r}")\n',
         '        if not out:\n            print(f"[TPEX close] {ds} ({roc_date}) 解析 0 筆")\n'),
        ('        else:\n            _TPEX_CLOSE_DIAG[ds] = "ok"\n',
         '        else:\n'),
        ('    except Exception as e:\n        _TPEX_CLOSE_DIAG[ds] = "exception"\n        _body = f" body[:500]={scrubbed_body_head(r)!r}" if r is not None else ""\n        print(f"[TPEX close] {ds} 失敗: {type(e).__name__}: {e}{_body}")\n',
         '    except Exception as e:\n        print(f"[TPEX close] {ds} 失敗: {type(e).__name__}: {e}")\n'),
    ),
}
#: 基底 `299c50ec` 原始檔 sha256（`git show 299c50ec:<檔> | sha256sum` 實算）
Z39_BASE_SHA = {
    _INST: "1cb7c8e624ed6cf28f543aef6541a916631dd13055b4d484ea06aae998ff7b52",
    _CLOSE: "e24b0de830a747eb9c253c81f4931208f0098d3ee29cf8e4a7bd738fe277b5d6",
}


def z39_revert(rel: str, code: str) -> str:
    for new, old in Z39_REVERT_PAIRS[rel]:
        assert code.count(new) == 1, f"{rel} 替換點不唯一或已不存在：{new!r}"
        code = code.replace(new, old)
    return code


@functools.lru_cache(maxsize=None)
def z39_pre_module(rel: str):
    return _mutant(rel, Z39_REVERT_PAIRS[rel], tag="pre")


@pytest.mark.parametrize("rel", [_INST, _CLOSE])
def test_reverted_source_equals_base_file(rel):
    """還原體逐字 ＝ 基底檔 ⇒ 下方「零行為變更」比對跑的是真修前碼。"""
    code = z39_revert(rel, (_ROOT / rel).read_text(encoding="utf-8"))
    assert hashlib.sha256(code.encode("utf-8")).hexdigest() == Z39_BASE_SHA[rel]


# ══════════════════════════════════════════════════════════════════════════
# 1. 合成世界（逐日：T86 / TPEx 法人、TWSE / TPEx 收盤、TPEx 狀態）
# ══════════════════════════════════════════════════════════════════════════
_DAYS = [d.date() for d in pd.bdate_range(end="2026-10-09", periods=20)]
_DS = [d.strftime("%Y%m%d") for d in _DAYS]
IMAP = {"2330": "半導體業", "2317": "其他電子業", "6488": "半導體業", "8069": "上櫃光電"}


def _v(f, t, d):
    return {"外資": f, "投信": t, "自營商": d}


def _day_ok(i: int = 0) -> dict:
    return dict(
        t86={"2330": _v(100.0 + i, -10.0, 5.0), "2317": _v(-50.0, 0.0, 0.0)},
        tpex={"6488": _v(20.0, 1.0, -1.0), "8069": _v(-3.0, 0.0, 0.0)},
        tpex_status="ok",
        twse_close={"2330": 1000.0, "2317": 100.0},
        tpex_close={"6488": 500.0, "8069": 50.0},
        tpex_close_status="ok")


def _install(monkeypatch, mod, spec: dict) -> None:
    def g(k, default):
        return lambda ds: spec.get(ds, {}).get(k, default)
    monkeypatch.setattr(mod, "_get_t86_day", g("t86", {}))
    monkeypatch.setattr(mod, "_get_tpex_day", g("tpex", {}))
    monkeypatch.setattr(mod, "get_tpex_day_status", g("tpex_status", None))
    monkeypatch.setattr(mod, "fetch_twse_close_day", g("twse_close", {}))
    monkeypatch.setattr(mod, "fetch_tpex_close_day", g("tpex_close", {}))
    monkeypatch.setattr(mod, "get_tpex_close_status", g("tpex_close_status", None))


def _patch_paths(monkeypatch, mod, tmp_path, days) -> None:
    monkeypatch.setattr(mod, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(mod, "PARQUET_PATH", tmp_path / "daily_net.parquet")
    monkeypatch.setattr(mod, "BUBBLE_PATH", tmp_path / "bubble_latest.json")
    monkeypatch.setattr(mod, "META_PATH", tmp_path / "metadata.json")
    monkeypatch.setattr(mod, "TICKER_SECTOR_PATH", tmp_path / "ticker_sector.json")
    monkeypatch.setattr(mod, "_candidate_trading_days", lambda *a, **k: list(days))
    monkeypatch.setattr(mod, "fetch_industry_map_bulk", lambda: dict(IMAP))


def _pipeline(mod, days):
    inst, price, diag = mod._collect_days(days)
    sd, cov = compute_sector_daily_net(inst, price, IMAP)
    return inst, price, diag, sd, cov


def _by(df, **kw):
    m = pd.Series(True, index=df.index)
    for k, v in kw.items():
        m &= df[k] == v
    return df[m]


def _no_nan_token(text: str) -> None:
    def _bad(tok):
        raise AssertionError(f"JSON 出現非標準 token {tok}")
    json.loads(text, parse_constant=_bad)
    for tok in ("NaN", "Infinity"):
        assert tok not in text


# ══════════════════════════════════════════════════════════════════════════
# 2. 外資 NaN 一路到 net_amt / groupby / pivot / bubble =「未取得」
# ══════════════════════════════════════════════════════════════════════════
class TestNaNEndToEnd:
    def _spec(self):
        spec = {ds: _day_ok(i) for i, ds in enumerate(_DS)}
        # 第 18 日:T86 找不到外資欄(Z38 → NaN);第 19 日:TPEx 列缺「外資」鍵
        spec[_DS[17]]["t86"] = {"2330": _v(float("nan"), -10.0, 5.0),
                                "2317": _v(-50.0, 0.0, 0.0)}
        spec[_DS[18]]["tpex"] = {"6488": {"投信": 1.0, "自營商": -1.0},
                                 "8069": _v(-3.0, 0.0, 0.0)}
        return spec

    def test_nan_reaches_bubble_as_unavailable(self, monkeypatch):
        _install(monkeypatch, U, self._spec())
        inst, _p, _d, sd, cov = _pipeline(U, _DAYS)
        d17, d18 = pd.Timestamp(_DAYS[17]), pd.Timestamp(_DAYS[18])
        # _collect_days:缺值 NaN(不是 0)
        assert math.isnan(_by(inst, date=_DAYS[17], stock_id="2330")["foreign_lots"].iloc[0])
        assert math.isnan(_by(inst, date=_DAYS[18], stock_id="6488")["foreign_lots"].iloc[0])
        assert cov["n_missing_foreign_stock_days"] == 2
        # groupby:半導體業兩天外資 / 淨額 NaN(O1);其他電子業不受影響
        semi17 = _by(sd, date=d17, sector="半導體業").iloc[0]
        assert math.isnan(semi17["foreign_yi"]) and math.isnan(semi17["net_amt_yi"])
        assert semi17["trust_yi"] == pytest.approx((-10.0 * 1000 + 1.0 * 500) * 1000 / 1e8)
        assert math.isnan(_by(sd, date=d18, sector="半導體業").iloc[0]["foreign_yi"])
        ele = _by(sd, date=d17, sector="其他電子業").iloc[0]
        assert ele["foreign_yi"] == pytest.approx(-50.0 * 1000 * 100 / 1e8)
        # bubble:半導體業 → 未取得;其他板塊正常
        b, meta = compute_bubble(sd)
        semi = b[b["sector"] == "半導體業"].iloc[0]
        assert bool(semi["unavailable"]) and semi["quadrant"] == QUADRANT_UNAVAILABLE
        assert semi["n_missing_days"] == 2
        assert math.isnan(semi["x_yi"]) and math.isnan(semi["size_yi"])
        assert meta["n_missing_value_cells"] == 2 and meta["n_absent_cells"] == 0
        assert not b[b["sector"] != "半導體業"]["unavailable"].any()

    def test_mutant_collect_days_zero_default_fakes_zero(self, monkeypatch):
        """突變:`_collect_days` 缺鍵預設換回 0.0 → 第 19 日 6488 外資變假 0。"""
        M = _mutant(_SCRIPT, [('"foreign_lots": v.get("外資", _nan),',
                               '"foreign_lots": v.get("外資", 0.0),')])
        _install(monkeypatch, M, self._spec())
        inst, *_ = M._collect_days(_DAYS)
        assert _by(inst, date=_DAYS[18], stock_id="6488")["foreign_lots"].iloc[0] == 0.0

    def test_mutant_l2_fillna_zero_hides_missing(self, monkeypatch):
        """突變:L2 換回 `fillna(0.0)` → 半導體業不再未取得(把 Z38 的 NaN 抵銷成假 0)。"""
        M = _mutant(_L2, [("        inst[c] = _finite_or_nan(inst[c])\n",
                           "        inst[c] = _finite_or_nan(inst[c]).fillna(0.0)\n")])
        _install(monkeypatch, U, self._spec())
        inst, price, _d = U._collect_days(_DAYS)
        sd, _ = M.compute_sector_daily_net(inst, price, IMAP)
        b, _ = M.compute_bubble(sd)
        assert not bool(b[b["sector"] == "半導體業"].iloc[0]["unavailable"])


# ══════════════════════════════════════════════════════════════════════════
# 3. golden:真 0 仍為 0、有效正負值原值
# ══════════════════════════════════════════════════════════════════════════
class TestGolden:
    def test_true_zero_and_signed_values(self):
        day = pd.Timestamp("2026-10-09")
        inst = pd.DataFrame([
            {"date": day, "stock_id": "A1", "foreign_lots": 0.0, "trust_lots": 0.0, "dealer_lots": 0.0},
            {"date": day, "stock_id": "A2", "foreign_lots": 10.0, "trust_lots": -5.0, "dealer_lots": 0.0},
            {"date": day, "stock_id": "B1", "foreign_lots": 0.0, "trust_lots": 0.0, "dealer_lots": 0.0},
        ])
        price = pd.DataFrame([{"date": day, "stock_id": s, "close": 100.0} for s in ("A1", "A2", "B1")])
        sd, cov = compute_sector_daily_net(inst, price, {"A1": "A", "A2": "A", "B1": "B"})
        a = sd[sd["sector"] == "A"].iloc[0]
        b = sd[sd["sector"] == "B"].iloc[0]
        assert a["foreign_yi"] == pytest.approx(0.01, abs=1e-12)
        assert a["trust_yi"] == pytest.approx(-0.005, abs=1e-12)
        assert a["net_amt_yi"] == pytest.approx(0.005, abs=1e-12)
        for c in ("net_amt_yi", "foreign_yi", "trust_yi", "dealer_yi"):
            assert b[c] == 0.0 and not math.isnan(b[c])     # 真 0 → 0,不是 NaN
        assert list(sd.columns) == ["date", "sector", "net_amt_yi", "foreign_yi",
                                    "trust_yi", "dealer_yi", "n_stocks"]
        assert cov["n_missing_foreign_stock_days"] == 0

    def test_bubble_golden_with_true_zero_day(self):
        dates = list(pd.bdate_range(end="2026-10-09", periods=10))
        vals = [1.0, -2.0, 0.0, 3.0, 0.0, 4.0, -1.0, 0.0, 2.0, 5.0]
        sd = pd.DataFrame({"date": dates, "sector": "A", "net_amt_yi": vals})
        b, meta = compute_bubble(sd)
        r = b.iloc[0]
        assert not bool(r["unavailable"]) and r["n_missing_days"] == 0
        assert r["x_yi"] == pytest.approx(4.0 - 1.0 + 0.0 + 2.0 + 5.0)
        assert r["size_yi"] == pytest.approx(abs(sum(vals)))
        assert r["y_yi"] == pytest.approx(np.mean(vals[5:]) - np.mean(vals[:5]))
        assert meta["n_absent_cells"] == 0 and meta["n_missing_value_cells"] == 0

    def test_insufficient_priority_not_overwritten(self):
        dates = list(pd.bdate_range(end="2026-10-09", periods=6))
        sd = pd.concat([
            pd.DataFrame({"date": dates, "sector": "A", "net_amt_yi": [1.0] * 6}),
            pd.DataFrame({"date": dates[-2:], "sector": "B", "net_amt_yi": [1.0, 1.0]}),
        ])
        b, _ = compute_bubble(sd)
        rb = b[b["sector"] == "B"].iloc[0]
        assert rb["quadrant"] == QUADRANT_INSUFFICIENT and bool(rb["insufficient"])
        assert bool(rb["unavailable"])       # 資料真相仍記
        ra = b[b["sector"] == "A"].iloc[0]
        assert ra["quadrant"] == QUADRANT_INSUFFICIENT and not bool(ra["unavailable"])


# ══════════════════════════════════════════════════════════════════════════
# 4. O1:板塊內任一成分股該類別缺 → 板塊該日該類別 NaN(其他類別照算)
# ══════════════════════════════════════════════════════════════════════════
def _o1_inputs():
    day = pd.Timestamp("2026-10-09")
    inst = pd.DataFrame([
        {"date": day, "stock_id": "1", "foreign_lots": np.nan, "trust_lots": 2.0, "dealer_lots": 1.0},
        {"date": day, "stock_id": "2", "foreign_lots": 5.0, "trust_lots": 3.0, "dealer_lots": 1.0},
    ])
    price = pd.DataFrame([{"date": day, "stock_id": s, "close": 100.0} for s in ("1", "2")])
    return inst, price, {"1": "S", "2": "S"}


class TestO1Mask:
    def test_partial_missing_masks_only_that_category(self):
        sd, _ = compute_sector_daily_net(*_o1_inputs())
        r = sd.iloc[0]
        assert math.isnan(r["foreign_yi"]) and math.isnan(r["net_amt_yi"])
        assert r["trust_yi"] == pytest.approx(0.005) and r["dealer_yi"] == pytest.approx(0.002)
        assert r["n_stocks"] == 2

    def test_mutant_without_o1_mask_sums_half(self):
        M = _mutant(_L2, [('        agg[c] = agg[c].where(agg[f"_na_{c}"] == 0)\n',
                           '        pass\n')])
        r = M.compute_sector_daily_net(*_o1_inputs())[0].iloc[0]
        assert r["foreign_yi"] == pytest.approx(0.005)     # 半套當完整 = 修前錯誤

    def test_mutant_without_min_count_net_fakes(self):
        M = _mutant(_L2, [("        axis=1, min_count=len(_LOT_COLS))\n", "        axis=1)\n")])
        day = pd.Timestamp("2026-10-09")
        inst = pd.DataFrame([{"date": day, "stock_id": "1", "foreign_lots": np.nan,
                              "trust_lots": 2.0, "dealer_lots": 1.0}])
        price = pd.DataFrame([{"date": day, "stock_id": "1", "close": 100.0}])
        assert math.isnan(compute_sector_daily_net(inst, price, {"1": "S"})[0].iloc[0]["net_amt_yi"])
        # 無 min_count:per-stock 淨額 = 投+自(把缺的外資當 0)→ 板塊淨額變假值
        sd_m = M.compute_sector_daily_net(inst, price, {"1": "S"})[0]
        assert sd_m.iloc[0]["net_amt_yi"] == pytest.approx(0.003)


# ══════════════════════════════════════════════════════════════════════════
# 5. 整列缺席 → NaN(不是 0)、n_absent_cells 計數
# ══════════════════════════════════════════════════════════════════════════
def _absent_sd():
    dates = list(pd.bdate_range(end="2026-10-09", periods=20))
    return pd.concat([
        pd.DataFrame({"date": dates, "sector": "A", "net_amt_yi": [1.0] * 20}),
        pd.DataFrame({"date": dates[:-1], "sector": "B", "net_amt_yi": [2.0] * 19}),
    ], ignore_index=True)


class TestAbsentCells:
    def test_absent_cell_is_nan_and_counted(self):
        b, meta = compute_bubble(_absent_sd())
        assert meta["n_absent_cells"] == 1 and meta["n_missing_value_cells"] == 0
        rb = b[b["sector"] == "B"].iloc[0]
        assert bool(rb["unavailable"]) and rb["n_missing_days"] == 1
        assert rb["quadrant"] == QUADRANT_UNAVAILABLE
        assert b.iloc[-1]["sector"] == "B"           # NaN size 排最後

    def test_duplicate_date_sector_raises(self):
        sd = _absent_sd()
        with pytest.raises(ValueError):
            compute_bubble(pd.concat([sd, sd.iloc[:1]], ignore_index=True))

    def test_mutant_fillna_zero_back(self):
        M = _mutant(_L2, [("    _absent = present.isna()\n",
                           "    _absent = present.isna()\n    pv = pv.fillna(0.0)\n")])
        rb = M.compute_bubble(_absent_sd())[0]
        rb = rb[rb["sector"] == "B"].iloc[0]
        assert not bool(rb["unavailable"]) and rb["size_yi"] == pytest.approx(38.0)


# ══════════════════════════════════════════════════════════════════════════
# 6. render:None / NaN 不畫在 x=0、不當最小泡泡
# ══════════════════════════════════════════════════════════════════════════
_RSECT = [
    {"sector": "好", "x_yi": 3.0, "y_yi": 1.0, "size_yi": 9.0, "quadrant": "漲潮",
     "n_days": 20, "insufficient": False, "unavailable": False, "n_missing_days": 0},
    {"sector": "缺旗標", "x_yi": None, "y_yi": None, "size_yi": None, "quadrant": "未取得",
     "n_days": 20, "insufficient": False, "unavailable": True, "n_missing_days": 2},
    {"sector": "舊檔NaN", "x_yi": float("nan"), "y_yi": 1.0, "size_yi": 4.0, "quadrant": "漲潮",
     "n_days": 20, "insufficient": False},
    {"sector": "size缺", "x_yi": 2.0, "y_yi": 1.0, "size_yi": None, "quadrant": "漲潮",
     "n_days": 20, "insufficient": False},
    {"sector": "x缺", "x_yi": None, "y_yi": 1.0, "size_yi": 5.0, "quadrant": "漲潮",
     "n_days": 20, "insufficient": False},
]


def _plotted(fig):
    out = []
    for tr in fig.data:
        if tr.name and "持股" in tr.name:
            continue
        out.extend(zip(tr.x or (), tr.text or ()))
    return out


class TestRender:
    def test_missing_not_drawn_at_zero(self):
        from src.ui.render.sector_flow_render import build_sector_flow_figure
        fig = build_sector_flow_figure(_RSECT, highlight_sectors={"缺旗標", "好"})
        pts = _plotted(fig)
        assert pts == [(3.0, "好")]
        for tr in fig.data:
            for x in (tr.x or ()):
                assert x is not None and math.isfinite(x)
        # 「交易日不足」註解不得把未取得算進去
        assert not any("交易日不足" in str(a.text) for a in fig.layout.annotations)

    def test_mutant_or_zero_back_draws_at_zero(self):
        M = _mutant(_RENDER, [
            ("            if not r.get(\"insufficient\") and not is_unavailable(r)\n",
             "            if not r.get(\"insufficient\")\n"),
            ('            x=[float(r.get("x_yi")) for r in _pts],\n',
             '            x=[float(r.get("x_yi") or 0.0) for r in _pts],\n'),
            ('            customdata=[[float(r.get("size_yi")),',
             '            customdata=[[float(r.get("size_yi") or 0.0),'),
            ('    _max_abs = max((abs(float(r.get("size_yi"))) for r in plot), default=0.0)',
             '    _max_abs = max((abs(float(r.get("size_yi") or 0.0)) for r in plot), default=0.0)'),
            ('    s = abs(float(size_yi))', '    s = abs(float(size_yi or 0.0))'),
        ])
        fig = M.build_sector_flow_figure([r for r in _RSECT if r["sector"] != "舊檔NaN"])
        pts = _plotted(fig)
        assert (0.0, "x缺") in pts                        # None 畫在 x=0 = 修前錯誤
        assert "size缺" in [t for _x, t in pts]           # None size 畫成最小泡泡


# ══════════════════════════════════════════════════════════════════════════
# 7. cron 逐日分市場判定(TPEx invariant / unresolved / source)
# ══════════════════════════════════════════════════════════════════════════
def _one(monkeypatch, mod, day: dict):
    _install(monkeypatch, mod, {_DS[0]: day})
    return mod._collect_days([_DAYS[0]])


class TestMarketJudgement:
    @pytest.mark.parametrize("name,patch", [
        ("tpex_empty_on_trading_day", dict(tpex={}, tpex_status="empty")),
        ("tpex_col_unverified", dict(tpex_status="col_unverified")),
        ("tpex_json_error", dict(tpex={}, tpex_status="json_error")),
        ("tpex_close_empty", dict(tpex_close={}, tpex_close_status="empty")),
        ("tpex_intersection_zero", dict(tpex_close={"9999": 1.0})),
    ])
    def test_tpex_failure_is_not_success(self, monkeypatch, name, patch):
        inst, price, diag = _one(monkeypatch, U, {**_day_ok(), **patch})
        day = diag["per_day"][_DS[0]]
        assert day["twse_ok"] is True and day["tpex_ok"] is False and day["written"] is True
        assert set(inst["stock_id"]) == {"2330", "2317"}          # 當日 TPEx 法人列不入彙總
        assert set(price["stock_id"]) == {"2330", "2317"}
        assert diag["unresolved_days"] == []
        assert U._day_flags_frame(diag)["source"].tolist() == ["TWSE:T86+MI_INDEX"]

    def test_all_ok_includes_tpex(self, monkeypatch):
        inst, _p, diag = _one(monkeypatch, U, _day_ok())
        assert diag["per_day"][_DS[0]]["tpex_ok"] is True
        assert set(inst["stock_id"]) == set(IMAP)
        assert U._day_flags_frame(diag)["source"].tolist() == [
            "TWSE:T86+MI_INDEX / TPEX:3itrade+otc_quotes"]

    def test_twse_fail_tpex_only_is_unresolved(self, monkeypatch):
        inst, _p, diag = _one(monkeypatch, U, {**_day_ok(), "t86": {}})
        assert inst.empty and diag["unresolved_days"] == [_DS[0]]
        day = diag["per_day"][_DS[0]]
        assert day["holiday"] is False and day["written"] is False and day["tpex_ok"] is True

    def test_both_empty_is_holiday(self, monkeypatch):
        inst, _p, diag = _one(monkeypatch, U, {"tpex_status": "empty"})
        assert inst.empty and diag["unresolved_days"] == []
        assert diag["per_day"][_DS[0]]["holiday"] is True and diag["days_holiday_or_empty"] == 1

    def test_mutant_status_check_removed_marks_success(self, monkeypatch):
        M = _mutant(_SCRIPT, [('_day["tpex_inst_status"] == TPEX_DAY_STATUS_OK', "True")])
        _inst, _p, diag = _one(monkeypatch, M, {**_day_ok(), "tpex_status": "col_unverified"})
        assert diag["per_day"][_DS[0]]["tpex_ok"] is True

    def test_mutant_failed_tpex_rows_back_in(self, monkeypatch):
        M = _mutant(_SCRIPT, [("        _inst = {**tpex, **t86} if tpex_ok else dict(t86)\n",
                               "        _inst = {**tpex, **t86}\n")])
        inst, _p, _d = _one(monkeypatch, M, {**_day_ok(), "tpex_status": "col_unverified"})
        assert "6488" in set(inst["stock_id"])


# ══════════════════════════════════════════════════════════════════════════
# 8. main() 端到端:parquet / bubble_latest.json / metadata
# ══════════════════════════════════════════════════════════════════════════
def _e2e_spec():
    spec = {ds: _day_ok(i) for i, ds in enumerate(_DS[:12])}
    spec[_DS[10]]["tpex_status"] = "col_unverified"      # TPEx 失敗日 → 只含上市
    spec[_DS[11]]["t86"] = {}                            # TWSE 失敗 → unresolved
    return spec


class TestMainEndToEnd:
    def test_parquet_json_metadata(self, monkeypatch, tmp_path):
        _install(monkeypatch, U, _e2e_spec())
        _patch_paths(monkeypatch, U, tmp_path, _DAYS[:12])
        assert U.main([]) == 0
        pq = pd.read_parquet(tmp_path / "daily_net.parquet")
        assert pq["date"].nunique() == 11                # TWSE 失敗日未寫入
        d10 = pq[pq["date"] == pd.Timestamp(_DAYS[10])]
        assert set(d10["source"]) == {"TWSE:T86+MI_INDEX"}
        assert not d10["tpex_ok"].any() and d10["twse_ok"].all()
        assert "上櫃光電" not in set(d10["sector"])
        d0 = pq[pq["date"] == pd.Timestamp(_DAYS[0])]
        assert set(d0["source"]) == {"TWSE:T86+MI_INDEX / TPEX:3itrade+otc_quotes"}

        text = (tmp_path / "bubble_latest.json").read_text(encoding="utf-8")
        _no_nan_token(text)
        bj = json.loads(text)
        assert bj["tpex_complete"] is False and bj["n_days_tpex_ok"] == 10
        assert bj["n_absent_cells"] == 1
        opt = next(s for s in bj["sectors"] if s["sector"] == "上櫃光電")
        assert opt["unavailable"] is True and opt["n_missing_days"] == 1
        assert opt["x_yi"] is None and opt["size_yi"] is None

        meta = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
        assert meta["last_error"] is None and meta["warnings"]
        assert meta["unresolved_days"] == [_DS[11]]
        assert _DS[10] in meta["markets_summary"]["TPEx"]["fail_dates"]
        assert meta["markets_summary"]["TWSE"]["fail_dates"] == [_DS[11]]
        assert meta["per_day"][_DS[10]]["tpex_inst_status"] == "col_unverified"
        assert any("僅含上市" in w for w in meta["warnings"])

    def test_mutant_json_nan_token(self, monkeypatch, tmp_path):
        M = _mutant(_SCRIPT, [("    payload = _json_safe({\n        \"updated_at\": pd.Timestamp",
                               "    payload = ({\n        \"updated_at\": pd.Timestamp"),
                              ("    BUBBLE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2,\n"
                               "                                      allow_nan=False) + \"\\n\",",
                               "    BUBBLE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + \"\\n\",")])
        _install(monkeypatch, M, _e2e_spec())
        _patch_paths(monkeypatch, M, tmp_path, _DAYS[:12])
        M.main([])
        with pytest.raises(AssertionError):
            _no_nan_token((tmp_path / "bubble_latest.json").read_text(encoding="utf-8"))


# ══════════════════════════════════════════════════════════════════════════
# 9. tpex_complete 真值表 + reader 透傳 + 兩處 UI caption
# ══════════════════════════════════════════════════════════════════════════
def _full(tpex_flags):
    dates = list(pd.bdate_range(end="2026-10-09", periods=len(tpex_flags)))
    df = pd.DataFrame({"date": dates, "sector": "A", "net_amt_yi": 1.0})
    if tpex_flags is not None and any(f != "absent" for f in tpex_flags):
        df["tpex_ok"] = [None if f == "absent" else f for f in tpex_flags]
    return df


class TestTpexComplete:
    @pytest.mark.parametrize("flags,expect", [
        ([True] * 12, True),
        ([True] * 11 + [False], False),
        ([None] + [True] * 11, False),                   # 舊列(未知)≠ True
        (["absent"] * 12, False),                        # 舊 parquet 無欄
    ])
    def test_truth_table(self, monkeypatch, tmp_path, flags, expect):
        monkeypatch.setattr(U, "BUBBLE_PATH", tmp_path / "b.json")
        meta = U._write_bubble_json(_full(flags))
        assert meta["tpex_complete"] is expect
        bj = json.loads((tmp_path / "b.json").read_text(encoding="utf-8"))
        assert bj["tpex_complete"] is expect

    def test_more_than_window_only_window_counts(self, monkeypatch, tmp_path):
        monkeypatch.setattr(U, "BUBBLE_PATH", tmp_path / "b.json")
        # 舊的 5 天 TPEx 失敗,但窗口(近 20)只含最近 20 天且全成功 → True(恢復後自動移除)
        assert U._write_bubble_json(_full([False] * 5 + [True] * 20))["tpex_complete"] is True

    def test_mutant_complete_rule(self, monkeypatch, tmp_path):
        M = _mutant(_SCRIPT, [("_n_tp is not None and _n_used > 0 and _n_tp == _n_used",
                               "_n_used > 0")])
        monkeypatch.setattr(M, "BUBBLE_PATH", tmp_path / "b.json")
        assert M._write_bubble_json(_full([True] * 11 + [False]))["tpex_complete"] is True

    @pytest.mark.parametrize("payload_extra,expect", [
        ({}, None), ({"tpex_complete": True}, True), ({"tpex_complete": False}, False)])
    def test_reader_passthrough(self, monkeypatch, tmp_path, payload_extra, expect):
        import src.data.sector_flow.reader as R
        bp = tmp_path / "bubble_latest.json"
        bp.write_text(json.dumps({"sectors": [], **payload_extra}), encoding="utf-8")
        monkeypatch.setattr(R, "BUBBLE_PATH", bp)
        monkeypatch.setattr(R, "META_PATH", tmp_path / "m.json")
        monkeypatch.setattr(R, "TICKER_SECTOR_PATH", tmp_path / "t.json")
        v = R.read_sector_flow_cache()
        assert v["tpex_complete"] is expect and "n_absent_cells" in v

    def test_mutant_reader_constant_true(self, monkeypatch, tmp_path):
        M = _mutant(_READER, [('        "tpex_complete": bubble.get("tpex_complete"),\n',
                               '        "tpex_complete": True,\n')])
        bp = tmp_path / "bubble_latest.json"
        bp.write_text(json.dumps({"sectors": []}), encoding="utf-8")
        monkeypatch.setattr(M, "BUBBLE_PATH", bp)
        monkeypatch.setattr(M, "META_PATH", tmp_path / "m.json")
        monkeypatch.setattr(M, "TICKER_SECTOR_PATH", tmp_path / "t.json")
        assert M.read_sector_flow_cache()["tpex_complete"] is True   # 舊 JSON 被冒充完整


class _FakeSt:
    """記錄 caption 等呼叫的極簡 streamlit 替身(函式層測 UI,不起 AppTest)。"""

    def __init__(self):
        self.captions: list[str] = []
        self.errors: list[str] = []
        self.charts = 0
        self.session_state: dict = {}

    def caption(self, t, *a, **k):
        self.captions.append(str(t))

    def plotly_chart(self, *a, **k):
        self.charts += 1

    def error(self, t, *a, **k):
        self.errors.append(str(t))

    def button(self, *a, **k):
        return False

    @contextmanager
    def spinner(self, *a, **k):
        yield

    def __getattr__(self, name):           # markdown / info / warning … → no-op
        return lambda *a, **k: None


_VIEW_SECTORS = [
    {"sector": "好", "x_yi": 3.0, "y_yi": 1.0, "size_yi": 9.0, "quadrant": "漲潮",
     "n_days": 20, "insufficient": False, "unavailable": False, "n_missing_days": 0},
    {"sector": "上櫃光電", "x_yi": None, "y_yi": None, "size_yi": None, "quadrant": "未取得",
     "n_days": 20, "insufficient": False, "unavailable": True, "n_missing_days": 3},
]
_UNAV_CAP = "⬜ 未取得：上櫃光電（缺 3 日）"


def _view(tpex_complete="absent", sectors=_VIEW_SECTORS):
    v = {"ok": True, "sectors": [dict(s) for s in sectors], "updated_at": "x",
         "n_trading_days_used": 20, "is_stale": False, "highlight_sectors": set(),
         "holding_sectors": {}, "window_size": 20}
    if tpex_complete != "absent":
        v["tpex_complete"] = tpex_complete
    return v


def _run_tab(monkeypatch, tab_mod, view):
    import src.services.sector_flow_service as svc
    fake = _FakeSt()
    monkeypatch.setattr(tab_mod, "st", fake)
    monkeypatch.setattr(svc, "get_sector_flow_view", lambda **k: view)
    tab_mod.render_tab_sector_flow()
    return fake


class TestTabCaptions:
    @pytest.mark.parametrize("tpc,shown", [("absent", True), (None, True), (False, True),
                                           (True, False)])
    def test_twse_only_note(self, monkeypatch, tpc, shown):
        import src.ui.tabs.tab_sector_flow as T
        fake = _run_tab(monkeypatch, T, _view(tpc))
        assert (SECTOR_FLOW_TWSE_ONLY_NOTE in fake.captions) is shown
        assert SECTOR_FLOW_TWSE_ONLY_NOTE == "目前僅含上市資料"
        assert _UNAV_CAP in fake.captions

    def test_no_unavailable_no_caption(self, monkeypatch):
        import src.ui.tabs.tab_sector_flow as T
        fake = _run_tab(monkeypatch, T, _view(True, _VIEW_SECTORS[:1]))
        assert not any(c.startswith("⬜ 未取得") for c in fake.captions)

    def test_mutant_condition_inverted(self, monkeypatch):
        M = _mutant(_TAB, [('    if view.get("tpex_complete") is not True:\n',
                            '    if view.get("tpex_complete") is False:\n')])
        fake = _run_tab(monkeypatch, M, _view("absent"))
        assert SECTOR_FLOW_TWSE_ONLY_NOTE not in fake.captions   # 舊 JSON 時提示消失 = bug


def _run_leaf(monkeypatch, P, readout):
    fake = _FakeSt()
    monkeypatch.setattr(P, "st", fake)
    monkeypatch.setattr(P, "section_header", lambda *a, **k: None)
    monkeypatch.setattr(P, "grid", lambda *a, **k: iter(()))
    monkeypatch.setattr(P, "_render_one", lambda *a, **k: None)
    monkeypatch.setattr(P, "map_requested", lambda s: True)
    monkeypatch.setattr(P, "load_heatmap", lambda requested: P.HeatmapReadout(requested=False))
    monkeypatch.setattr(P, "load_sector_flow", lambda session, requested: readout)
    P._render_map_leaf({})
    return fake


class TestPageFind:
    def _readout(self, monkeypatch, view):
        import src.services.sector_flow_service as svc
        import src.ui.views.page_find as P
        monkeypatch.setattr(svc, "get_sector_flow_view", lambda **k: view)
        return P.load_sector_flow({}, requested=True)

    @pytest.mark.parametrize("tpc,shown", [("absent", True), (False, True), (True, False)])
    def test_leaf_captions(self, monkeypatch, tpc, shown):
        import src.ui.views.page_find as P
        ro = self._readout(monkeypatch, _view(tpc))
        assert ro.unavailable == ("上櫃光電",)
        assert ro.tpex_complete is (None if tpc == "absent" else tpc)
        fake = _run_leaf(monkeypatch, P, ro)
        assert fake.charts == 1 and not fake.errors
        assert (SECTOR_FLOW_TWSE_ONLY_NOTE in fake.captions) is shown
        assert _UNAV_CAP in fake.captions

    def test_card_counts_plottable(self, monkeypatch):
        import src.ui.views.page_find as P
        card, _f = P.build_sector_flow_card(self._readout(monkeypatch, _view(True)))
        assert card.state == UI_LIVE and card.value == "1 個板塊"

    def test_all_unavailable_is_grey_not_cache_missing(self, monkeypatch):
        import src.ui.views.page_find as P
        ro = self._readout(monkeypatch, _view(True, _VIEW_SECTORS[1:]))
        card, _f = P.build_sector_flow_card(ro)
        assert card.state == UI_EMPTY
        assert card.note.now == P.FLOW_ALL_UNAVAILABLE_NOW != P.FLOW_EMPTY_NOW
        assert "1 個板塊" in card.note.why
        assert P.v2_card_html(card, _f)                  # 短句表有登記、畫得出卡

    def test_mutant_has_value_counts_all(self, monkeypatch):
        ro = self._readout(monkeypatch, _view(True, _VIEW_SECTORS[1:]))
        M = _mutant(_PF, [("        has_value=flow.n_plottable > 0,",
                           "        has_value=bool(flow.sectors),")])
        card, _ = M.build_sector_flow_card(M.SectorFlowReadout(**{
            k: getattr(ro, k) for k in ro.__dataclass_fields__}))
        assert card.state == UI_LIVE                    # 全未取得仍標 live「1 個板塊」= bug

    def test_mutant_leaf_condition(self, monkeypatch):
        ro = self._readout(monkeypatch, _view("absent"))
        M = _mutant(_PF, [("        if _flow.tpex_complete is not True:\n",
                           "        if _flow.tpex_complete is False:\n")])
        fake = _run_leaf(monkeypatch, M, M.SectorFlowReadout(**{
            k: getattr(ro, k) for k in ro.__dataclass_fields__}))
        assert SECTOR_FLOW_TWSE_ONLY_NOTE not in fake.captions

    def test_caption_formatter(self):
        assert format_unavailable_caption(_VIEW_SECTORS) == _UNAV_CAP
        assert format_unavailable_caption(_VIEW_SECTORS[:1]) is None
        assert format_unavailable_caption([{**_VIEW_SECTORS[1], "insufficient": True}]) is None


# ══════════════════════════════════════════════════════════════════════════
# 10. L1 診斷:狀態、500 字洗過的 body、零行為變更(對照基底)
# ══════════════════════════════════════════════════════════════════════════
_SECRET = "SECRETTOKEN0123456789abcdef"
_PROXY = "http://naspxy:S3cretPw@10.0.0.9:3128"
_BODY = (f"<html>token={_SECRET} proxy={_PROXY} Authorization: Bearer {_SECRET} "
         + "x" * 2000 + "</html>")


class _Resp:
    def __init__(self, payload=None, *, raise_json=False, text=_BODY, status=200):
        self._p, self._raise = payload, raise_json
        self.text, self.status_code = text, status
        self.headers = {"Authorization": f"Bearer {_SECRET}", "Proxy-Authorization": _PROXY,
                        "X-Hdr-Only": "HEADERONLYVALUE"}

    def json(self):
        if self._raise:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._p


def _tp_row(code, fb=5000, fs=1000, tb=300, ts=100, db=20, dss=10, ok=True):
    fmt = lambda n: f"{n:,}"
    fnet = fb - fs if ok else fb - fs + 99_999
    return [code, "名", fmt(fb), fmt(fs), fmt(fnet), fmt(tb), fmt(ts), fmt(tb - ts),
            fmt(db), fmt(dss), fmt(db - dss), "0", "0", "0", "0"]


_TPEX_CASES = {
    "ok": lambda: _Resp({"aaData": [_tp_row("6488"), _tp_row("8069")]}),
    "empty": lambda: _Resp({"aaData": []}),
    "http_none": lambda: None,
    "json_error": lambda: _Resp(raise_json=True),
    "col_unverified": lambda: _Resp({"aaData": [_tp_row("6488", ok=False)]}),
    "exception": lambda: _Resp(["not", "a", "dict"]),
}


def _fresh_inst(monkeypatch, mod, resp):
    monkeypatch.setattr(mod, "_TPEX_DAY_CACHE", {})
    monkeypatch.setattr(mod, "_TPEX_FAIL_TS", {})
    if hasattr(mod, "_TPEX_DAY_DIAG"):
        monkeypatch.setattr(mod, "_TPEX_DAY_DIAG", {})
    monkeypatch.setattr(mod, "_fetch_url_dl", lambda *a, **k: resp)


def _assert_body_log_clean(out: str) -> None:
    lines = [ln for ln in out.splitlines() if "body[:500]=" in ln]
    assert lines, "失敗分支沒有印 body"
    for ln in lines:
        body = ln.split("body[:500]=", 1)[1]
        assert len(eval(body)) <= 500                                   # noqa: S307 — repr 字串
        assert _SECRET not in ln and "S3cretPw" not in ln
        assert "HEADERONLYVALUE" not in ln and "Proxy-Authorization" not in ln


class TestL1TpexDayDiag:
    @pytest.mark.parametrize("status", list(_TPEX_CASES))
    def test_status_and_zero_behavior_change(self, monkeypatch, capsys, status):
        base = z39_pre_module(_INST)
        got = {}
        for name, mod in (("now", ifx), ("base", base)):
            _fresh_inst(monkeypatch, mod, _TPEX_CASES[status]())
            ret = mod._get_tpex_day(_DS[0])
            got[name] = (ret, dict(mod._TPEX_DAY_CACHE), set(mod._TPEX_FAIL_TS))
            if name == "now":
                assert ifx.get_tpex_day_status(_DS[0]) == status
                out = capsys.readouterr().out
                if status not in ("ok", "http_none"):
                    _assert_body_log_clean(out)
                else:
                    assert "body[:500]=" not in out
        assert got["now"] == got["base"]            # 回傳值 / 永久快取 / 負快取 同基底

    def test_cache_hit_keeps_status(self, monkeypatch):
        _fresh_inst(monkeypatch, ifx, _TPEX_CASES["empty"]())
        ifx._get_tpex_day(_DS[0])
        monkeypatch.setattr(ifx, "_fetch_url_dl", lambda *a, **k: _TPEX_CASES["ok"]())
        assert ifx._get_tpex_day(_DS[0]) == {}       # 永久快取 {} 語意不變
        assert ifx.get_tpex_day_status(_DS[0]) == "empty"
        assert ifx.get_tpex_day_status("19990101") is None

    def test_mutant_empty_reported_ok(self, monkeypatch):
        M = _mutant(_INST, [("            _TPEX_DAY_DIAG[ds] = 'empty'\n",
                             "            _TPEX_DAY_DIAG[ds] = 'ok'\n")])
        _fresh_inst(monkeypatch, M, _TPEX_CASES["empty"]())
        M._get_tpex_day(_DS[0])
        assert M.get_tpex_day_status(_DS[0]) == "ok"

    def test_mutant_col_unverified_reported_ok(self, monkeypatch):
        M = _mutant(_INST, [("            _status = 'col_unverified'\n", "            pass\n")])
        _fresh_inst(monkeypatch, M, _TPEX_CASES["col_unverified"]())
        M._get_tpex_day(_DS[0])
        assert M.get_tpex_day_status(_DS[0]) == "ok"

    def test_mutant_unscrubbed_leaks(self, monkeypatch, capsys):
        D = _mutant(_DIAG, [("    return scrub_secrets(str(_text)[:_SCRUB_WINDOW_CHARS])[:LOG_BODY_HEAD_CHARS]",
                             "    return str(_text)[:_SCRUB_WINDOW_CHARS][:LOG_BODY_HEAD_CHARS]")])
        _fresh_inst(monkeypatch, ifx, _TPEX_CASES["json_error"]())
        monkeypatch.setattr(ifx, "scrubbed_body_head", D.scrubbed_body_head)
        ifx._get_tpex_day(_DS[0])
        with pytest.raises(AssertionError):
            _assert_body_log_clean(capsys.readouterr().out)


_CLOSE_CASES = {
    "ok": lambda: _Resp({"aaData": [["6488", "名", "512.0"], ["8069", "名", "50.5"]]}),
    "empty": lambda: _Resp({"aaData": []}),
    "parse_zero": lambda: _Resp({"aaData": [["6488", "名", "--", "--", "--", "--"]]}),
    "http_none": lambda: None,
    "http_error": lambda: _Resp({}, status=500),
    "json_error": lambda: _Resp(raise_json=True),
    "exception": lambda: _Resp(["x"]),
}


class TestL1TpexCloseDiag:
    @pytest.mark.parametrize("status", list(_CLOSE_CASES))
    def test_status_and_zero_behavior_change(self, monkeypatch, capsys, status):
        base = z39_pre_module(_CLOSE)
        rets = {}
        for name, mod in (("now", mcf), ("base", base)):
            monkeypatch.setattr(mod, "_fetch", lambda *a, **k: _CLOSE_CASES[status]())
            rets[name] = mod.fetch_tpex_close_day(_DS[0])
            if name == "now":
                assert mcf.get_tpex_close_status(_DS[0]) == status
                out = capsys.readouterr().out
                if status in ("empty", "parse_zero", "json_error", "exception"):
                    _assert_body_log_clean(out)
        assert rets["now"] == rets["base"]


# ══════════════════════════════════════════════════════════════════════════
# 11. 輸入含 "None" / "<NA>" / "NaN" / "+inf" / "-inf" / 空值:不炸、不變 0
# ══════════════════════════════════════════════════════════════════════════
_JUNK = ["None", "<NA>", "NaN", "+inf", "-inf", "", None, "abc", pd.NA, float("inf")]


class TestJunkInputs:
    @pytest.mark.parametrize("junk", _JUNK, ids=[repr(j) for j in _JUNK])
    def test_l2_junk_is_nan_not_zero(self, junk):
        day = pd.Timestamp("2026-10-09")
        inst = pd.DataFrame([{"date": day, "stock_id": "1", "foreign_lots": junk,
                              "trust_lots": junk, "dealer_lots": 1.0}], dtype=object)
        price = pd.DataFrame([{"date": day, "stock_id": "1", "close": 100.0}])
        sd, cov = compute_sector_daily_net(inst, price, {"1": "S"})
        r = sd.iloc[0]
        assert math.isnan(r["foreign_yi"]) and math.isnan(r["trust_yi"])
        assert math.isnan(r["net_amt_yi"]) and r["dealer_yi"] == pytest.approx(0.001)
        assert cov["n_missing_foreign_stock_days"] == 1

    @pytest.mark.parametrize("junk", ["+inf", "-inf", "None", "NaN", None])
    def test_l2_junk_close_dropped(self, junk):
        day = pd.Timestamp("2026-10-09")
        inst = pd.DataFrame([{"date": day, "stock_id": "1", "foreign_lots": 1.0,
                              "trust_lots": 0.0, "dealer_lots": 0.0}])
        price = pd.DataFrame([{"date": day, "stock_id": "1", "close": junk}], dtype=object)
        sd, cov = compute_sector_daily_net(inst, price, {"1": "S"})
        assert sd.empty and cov["n_dropped_missing_price"] == 1

    def test_collect_days_none_values(self, monkeypatch):
        day = _day_ok()
        day["t86"] = {"2330": _v(None, "NaN", "+inf"), "2317": _v(-50.0, 0.0, 0.0)}
        inst, price, _d = _one(monkeypatch, U, day)
        sd, _ = compute_sector_daily_net(inst, price, IMAP)
        semi = sd[sd["sector"] == "半導體業"].iloc[0]
        assert math.isnan(semi["foreign_yi"]) and math.isnan(semi["dealer_yi"])
        assert not (sd[["foreign_yi", "trust_yi", "dealer_yi"]] == 0.0).loc[
            sd["sector"] == "半導體業"].any().any()

    def test_mutant_inf_kept(self):
        M = _mutant(_L2, [("    return out.where(np.isfinite(out))\n", "    return out\n")])
        day = pd.Timestamp("2026-10-09")
        inst = pd.DataFrame([{"date": day, "stock_id": "1", "foreign_lots": "+inf",
                              "trust_lots": 0.0, "dealer_lots": 0.0}], dtype=object)
        price = pd.DataFrame([{"date": day, "stock_id": "1", "close": 100.0}])
        assert math.isinf(M.compute_sector_daily_net(inst, price, {"1": "S"})[0].iloc[0]["foreign_yi"])


def test_json_safe_helper():
    assert U._json_safe({"a": float("nan"), "b": [np.float64("inf"), np.int64(3)], "c": True}) \
        == {"a": None, "b": [None, 3], "c": True}
