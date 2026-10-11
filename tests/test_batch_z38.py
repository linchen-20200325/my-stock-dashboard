"""批 Z38：個股法人 T86 外資欄名對映修正（治理規則 Level 1：mapping／欄名對映錯誤）。

Bug：`data_loader_inst_fetchers._get_t86_day` 挑外資欄的舊條件
「含『外』、含『買賣超』、不含『自營』」—— TWSE T86 現行欄名
「外陸資買賣超股數(不含外資自營商)」括號內含「自營」→ 被排除 → f_idx=None →
`_pn` 回 0.0 → 每檔每天外資＝0.0（假零）。

production 證據（sector_flow cron log 原文）：
  fields=['證券代號','證券名稱','外陸資買進股數(不含外資自營商)',
          '外陸資賣出股數(不含外資自營商)','外陸資買賣超股數(不含外資自營商)']
  f_idx=None t_idx=10 d_idx=14

修法：先挑「含外陸資且含買賣超」（現行格式只命中第 4 欄）；舊格式「外資買賣超股數」
保留原判斷作備援；找不到外資欄 → NaN（缺值），不回 0.0 假零。
口徑不變（外資及陸資、不含外資自營商，同 BFI82U）。
"""
from __future__ import annotations

import datetime as _dt
import math

import pandas as pd
import pytest

import src.data.core.data_loader_inst_fetchers as ifx

# TWSE T86 現行 19 欄欄位表（前 5 欄＝production log 原文逐字）
FIELDS_NOW = [
    "證券代號", "證券名稱",
    "外陸資買進股數(不含外資自營商)", "外陸資賣出股數(不含外資自營商)",
    "外陸資買賣超股數(不含外資自營商)",                       # 4 ← 外資
    "外資自營商買進股數", "外資自營商賣出股數", "外資自營商買賣超股數",  # 7 ← 不得被選
    "投信買進股數", "投信賣出股數", "投信買賣超股數",               # 10 ← 投信
    "自營商買賣超股數",                                         # 11
    "自營商買進股數(自行買賣)", "自營商賣出股數(自行買賣)",
    "自營商買賣超股數(自行買賣)",                               # 14 ← 自營商（既有）
    "自營商買進股數(避險)", "自營商賣出股數(避險)", "自營商買賣超股數(避險)",
    "三大法人買賣超股數",
]
PROD_LOG_FIRST5 = ['證券代號', '證券名稱', '外陸資買進股數(不含外資自營商)',
                   '外陸資賣出股數(不含外資自營商)', '外陸資買賣超股數(不含外資自營商)']

# 2017-12 前舊格式 16 欄（外資欄名「外資買賣超股數」）
FIELDS_OLD = [
    "證券代號", "證券名稱",
    "外資買進股數", "外資賣出股數", "外資買賣超股數",               # 4 ← 外資
    "投信買進股數", "投信賣出股數", "投信買賣超股數",               # 7
    "自營商買賣超股數",
    "自營商買進股數(自行買賣)", "自營商賣出股數(自行買賣)",
    "自營商買賣超股數(自行買賣)",                               # 11
    "自營商買進股數(避險)", "自營商賣出股數(避險)", "自營商買賣超股數(避險)",
    "三大法人買賣超股數",
]


def _row_now(code, foreign, f_dealer=10_000, trust=-200_000, d_self=50_000, d_hedge=-20_000):
    """股數 → T86 字串列（含千分位）。"""
    fmt = lambda n: f"{n:,}"
    d_total = d_self + d_hedge
    return [code, "測試",
            "0", "0", fmt(foreign),
            "0", "0", fmt(f_dealer),
            "0", "0", fmt(trust),
            fmt(d_total),
            "0", "0", fmt(d_self),
            "0", "0", fmt(d_hedge),
            fmt(foreign + f_dealer + trust + d_total)]


def _row_old(code, foreign, trust=-200_000, d_self=50_000, d_hedge=-20_000):
    fmt = lambda n: f"{n:,}"
    return [code, "測試", "0", "0", fmt(foreign), "0", "0", fmt(trust),
            fmt(d_self + d_hedge), "0", "0", fmt(d_self), "0", "0", fmt(d_hedge),
            fmt(foreign + trust + d_self + d_hedge)]


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


@pytest.fixture
def t86_env(monkeypatch):
    """隔離進程快取，並讓 _fetch_url_dl 回指定 payload。"""
    monkeypatch.setattr(ifx, "_T86_DAY_CACHE", {})
    monkeypatch.setattr(ifx, "_T86_FAIL_TS", {})

    def _set(fields, rows):
        payload = {"stat": "OK", "fields": list(fields), "data": [list(r) for r in rows]}
        monkeypatch.setattr(ifx, "_fetch_url_dl", lambda *a, **k: _Resp(payload))
    return _set


# ══════════════════════════════════════════════════════════════════════
# 1. 欄名對映：現行格式外資取第 4 欄
# ══════════════════════════════════════════════════════════════════════
class TestForeignColumnMapping:
    def test_positive_negative_zero(self, t86_env, capsys):
        t86_env(FIELDS_NOW, [_row_now("2330", 5_000_000),
                             _row_now("2317", -3_456_000),
                             _row_now("1101", 0)])
        d = ifx._get_t86_day("20261009")
        assert d["2330"]["外資"] == 5000.0
        assert d["2317"]["外資"] == -3456.0
        # 真實 0 保留為 0.0（不是 NaN）
        assert d["1101"]["外資"] == 0.0 and not math.isnan(d["1101"]["外資"])
        out = capsys.readouterr().out
        # 批 Z40（Q-z25＝A）：自營商欄由 idx 14「自營商買賣超股數(自行買賣)」改為 idx 11「自營商買賣超股數」（自行＋避險）
        assert "f_idx=4 t_idx=10 d_idx=11" in out

    def test_foreign_dealer_column_not_selected(self, t86_env):
        # 外陸資 +5,000,000；外資自營商 +10,000 → 外資必須是 5000.0 而非 10.0
        t86_env(FIELDS_NOW, [_row_now("2330", 5_000_000, f_dealer=10_000)])
        assert ifx._get_t86_day("20261009")["2330"]["外資"] == 5000.0

    def test_trust_dealer_unchanged(self, t86_env):
        # 投信 idx 10 與修前相同。
        # 批 Z40（客戶 Q-z25＝A）：自營商口徑由 idx 14「只取自行買賣」（50.0）改為 idx 11「自行＋避險」
        #   （50,000 ＋ −20,000 股 ＝ 30.0 張）。
        t86_env(FIELDS_NOW, [_row_now("2330", 5_000_000, trust=-200_000,
                                      d_self=50_000, d_hedge=-20_000)])
        v = ifx._get_t86_day("20261009")["2330"]
        assert v["投信"] == -200.0
        assert v["自營商"] == 30.0

    def test_prod_log_first5_fields_verbatim(self):
        assert FIELDS_NOW[:5] == PROD_LOG_FIRST5

    def test_old_format_still_supported(self, t86_env, capsys):
        t86_env(FIELDS_OLD, [_row_old("2330", 1_234_000)])
        v = ifx._get_t86_day("20170101")["2330"]
        assert v["外資"] == 1234.0
        assert v["投信"] == -200.0
        # 批 Z40（Q-z25＝A）：自營商由 idx 11（自行買賣，50.0）改為 idx 8「自營商買賣超股數」（自行＋避險，30.0）
        assert v["自營商"] == 30.0
        assert "f_idx=4 t_idx=7 d_idx=8" in capsys.readouterr().out


# ══════════════════════════════════════════════════════════════════════
# 2. 找不到外資欄 → 缺值（NaN），不回 0.0 假零
# ══════════════════════════════════════════════════════════════════════
class TestForeignColumnMissing:
    def _fields_without_foreign(self):
        # 拿掉外陸資三欄，只剩「外資自營商」欄 → 外資欄不存在
        return [f for f in FIELDS_NOW if "外陸資" not in f]

    def _row_without_foreign(self, code):
        r = _row_now(code, 5_000_000)
        return r[:2] + r[5:]

    def test_missing_is_nan_not_zero(self, t86_env, capsys):
        t86_env(self._fields_without_foreign(), [self._row_without_foreign("2330")])
        v = ifx._get_t86_day("20261009")["2330"]
        assert isinstance(v["外資"], float) and math.isnan(v["外資"])
        # 外資自營商欄不得被當外資撿走
        assert v["外資"] != 10.0
        # 投信 / 自營商照常（批 Z40 Q-z25＝A：自營商＝自行 50,000 ＋ 避險 −20,000 股 ＝ 30.0，修前只取自行 50.0）
        assert v["投信"] == -200.0 and v["自營商"] == 30.0
        assert "f_idx=None" in capsys.readouterr().out

    def test_fallback_main_total_is_missing_not_fake(self, t86_env):
        """個股頁 TWSE T86 fallback：外資缺 → 主力合計亦缺（NaN），交既有 D2 填補路徑（有 log）。"""
        t86_env(self._fields_without_foreign(), [self._row_without_foreign("2330")])
        base = _dt.date.today()
        df = pd.DataFrame({"date": [base - _dt.timedelta(days=i) for i in range(20)]})
        out = ifx._fetch_twse_inst_fallback("2330", df)
        got = out.dropna(subset=["投信"])
        assert len(got) > 0
        assert got["外資"].isna().all()
        assert got["主力合計"].isna().all()


# ══════════════════════════════════════════════════════════════════════
# 3. 修前行為重現（還原 pair）：舊條件在 production 欄名下 f_idx=None → 0.0
# ══════════════════════════════════════════════════════════════════════
def _old_pick(fields):
    fi = {n: i for i, n in enumerate(fields)}
    return next((v for k, v in fi.items() if '外' in k and '買賣超' in k and '自營' not in k), None)


def _new_pick(fields):
    fi = {n: i for i, n in enumerate(fields)}
    f = next((v for k, v in fi.items() if '外陸資' in k and '買賣超' in k), None)
    return f if f is not None else _old_pick(fields)


class TestPreFixReproduction:
    def test_old_rule_misses_on_prod_fields(self):
        assert _old_pick(FIELDS_NOW) is None          # 修前：f_idx=None（production log 同）
        assert _new_pick(FIELDS_NOW) == 4             # 修後：第 4 欄

    def test_old_rule_yields_fake_zero(self, t86_env):
        """以修前條件還原後，外資＝0.0（假零）；修後為真值。"""
        t86_env(FIELDS_NOW, [_row_now("2330", 5_000_000)])
        assert ifx._get_t86_day("20261009")["2330"]["外資"] == 5000.0
        # 修前 _pn(row, None) 的行為
        row = _row_now("2330", 5_000_000)
        old_idx = _old_pick(FIELDS_NOW)
        pre = 0.0 if old_idx is None else round(int(row[old_idx].replace(',', '')) / 1000, 1)
        assert pre == 0.0

    def test_both_rules_agree_on_old_format(self):
        assert _old_pick(FIELDS_OLD) == _new_pick(FIELDS_OLD) == 4

    def test_production_code_matches_new_pick(self, t86_env, capsys):
        for fields, rows, exp in ((FIELDS_NOW, [_row_now("2330", 1000)], 4),
                                  (FIELDS_OLD, [_row_old("2330", 1000)], 4)):
            ifx._T86_DAY_CACHE.clear()
            t86_env(fields, rows)
            ifx._get_t86_day("20261009")
            assert f"f_idx={exp} " in capsys.readouterr().out


# ══════════════════════════════════════════════════════════════════════
# 4. 下游：sector_flow 增量 cron 納入外資，net_amt_yi = 外+投+自，schema 不變
# ══════════════════════════════════════════════════════════════════════
class TestSectorFlowDownstream:
    def test_collect_days_and_net_amt_include_foreign(self, t86_env, monkeypatch):
        import scripts.update_sector_flow as U
        from src.compute.sector_flow import compute_sector_daily_net

        t86_env(FIELDS_NOW, [_row_now("2330", 5_000_000, trust=-200_000,
                                      d_self=50_000, d_hedge=-20_000)])
        monkeypatch.setattr(U, "_get_tpex_day", lambda ds: {})
        monkeypatch.setattr(U, "fetch_twse_close_day", lambda ds: {"2330": 1000.0})
        monkeypatch.setattr(U, "fetch_tpex_close_day", lambda ds: {})

        inst, price, diag = U._collect_days([_dt.date(2026, 10, 9)])
        assert list(inst.columns) == ["date", "stock_id", "foreign_lots",
                                      "trust_lots", "dealer_lots"]
        assert inst.loc[0, "foreign_lots"] == 5000.0

        sd, _cov = compute_sector_daily_net(inst, price, {"2330": "半導體業"})
        assert list(sd.columns) == ["date", "sector", "net_amt_yi", "foreign_yi",
                                    "trust_yi", "dealer_yi", "n_stocks"]
        r = sd.iloc[0]
        # 5000 張 × 1000 股 × 1000 元 / 1e8 = 50 億
        assert r["foreign_yi"] == pytest.approx(50.0)
        assert r["trust_yi"] == pytest.approx(-2.0)
        # 批 Z40（客戶 Q-z25＝A，泡泡圖自營商＝自行＋避險）：30 張 × 1000 股 × 1000 元 / 1e8 ＝ 0.3 億
        #   （修前只取自行 50 張 ⇒ 0.5 億）
        assert r["dealer_yi"] == pytest.approx(0.3)
        assert r["net_amt_yi"] == pytest.approx(50.0 - 2.0 + 0.3)
        assert r["foreign_yi"] != 0.0
