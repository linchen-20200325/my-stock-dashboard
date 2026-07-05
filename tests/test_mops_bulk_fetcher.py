"""MOPS 全市場彙總 bulk fetcher 解析層測試(不觸網,純解析)。

驗證 _parse_mops_aggregate 能：
  1. 從多張產業別表格抽出每檔一列(stock_id + 標準欄)
  2. 缺欄容錯:金融業表無「營業收入/營業毛利」→ 該欄 NaN,但 net_income/eps 仍抓到
  3. 濾掉非股號列(合計/總計)
  4. 資產負債表欄位映射正確
"""
import math

import pandas as pd

from src.data.stock.mops_bulk_fetcher import (
    _BS_FIELD_MAP,
    _IS_FIELD_MAP,
    _parse_mops_aggregate,
)

# 一般業損益表(有營收/毛利)+ 金融業損益表(無營收/毛利,有利息淨收益)+ 合計列
_IS_HTML = """
<html><body>
<table>
<tr><th>公司代號</th><th>公司名稱</th><th>營業收入</th><th>營業成本</th>
    <th>營業毛利（毛損）</th><th>營業利益</th><th>本期淨利（淨損）</th><th>基本每股盈餘（元）</th></tr>
<tr><td>2330</td><td>台積電</td><td>2,000,000</td><td>800,000</td>
    <td>1,200,000</td><td>900,000</td><td>800,000</td><td>32.50</td></tr>
<tr><td>合計</td><td>-</td><td>2,000,000</td><td>800,000</td>
    <td>1,200,000</td><td>900,000</td><td>800,000</td><td>-</td></tr>
</table>
<table>
<tr><th>公司代號</th><th>公司名稱</th><th>利息淨收益</th>
    <th>營業利益</th><th>本期淨利（淨損）</th><th>基本每股盈餘（元）</th></tr>
<tr><td>2891</td><td>中信金</td><td>50,000</td>
    <td>60,000</td><td>45,000</td><td>1.80</td></tr>
</table>
</body></html>
"""

_BS_HTML = """
<html><body>
<table>
<tr><th>公司代號</th><th>公司名稱</th><th>流動資產</th>
    <th>資產總計</th><th>負債總計</th><th>權益總計</th></tr>
<tr><td>2330</td><td>台積電</td><td>1,500,000</td>
    <td>5,000,000</td><td>1,000,000</td><td>4,000,000</td></tr>
</table>
</body></html>
"""


def test_income_parse_two_industries():
    df = _parse_mops_aggregate(_IS_HTML, _IS_FIELD_MAP)
    assert not df.empty
    # 合計列被濾掉,只剩 2 檔
    assert set(df["stock_id"]) == {"2330", "2891"}, df["stock_id"].tolist()

    tsmc = df[df["stock_id"] == "2330"].iloc[0]
    assert tsmc["revenue"] == 2_000_000
    assert tsmc["gross_profit"] == 1_200_000
    assert tsmc["net_income"] == 800_000
    assert math.isclose(float(tsmc["eps"]), 32.50)

    # 金融業:無營收/毛利 → NaN;但淨利/EPS 有
    bank = df[df["stock_id"] == "2891"].iloc[0]
    assert pd.isna(bank["revenue"]), "金融業表不應有營收(欄不存在→NaN)"
    assert pd.isna(bank["gross_profit"])
    assert bank["net_income"] == 45_000
    assert math.isclose(float(bank["eps"]), 1.80)


def test_balance_parse_fields():
    df = _parse_mops_aggregate(_BS_HTML, _BS_FIELD_MAP)
    assert not df.empty
    row = df[df["stock_id"] == "2330"].iloc[0]
    assert row["total_assets"] == 5_000_000
    assert row["total_liab"] == 1_000_000
    assert row["current_assets"] == 1_500_000
    assert row["total_equity"] == 4_000_000
    # 負債比可由此算 = 1,000,000 / 5,000,000 = 0.2
    assert math.isclose(row["total_liab"] / row["total_assets"], 0.2)


def test_empty_html_returns_empty():
    assert _parse_mops_aggregate("<html><body>no table</body></html>", _IS_FIELD_MAP).empty
    assert _parse_mops_aggregate("", _IS_FIELD_MAP).empty


def test_no_code_column_skipped():
    html = "<html><body><table><tr><th>名稱</th></tr><tr><td>台積電</td></tr></table></body></html>"
    assert _parse_mops_aggregate(html, _IS_FIELD_MAP).empty


# ── 重試 / 退避(_fetch_bulk)───────────────────────────────────────────
import src.data.stock.mops_bulk_fetcher as _mbf  # noqa: E402


class _Resp:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


class _FakeRequests:
    """依 script 逐次回傳:值為 int→拋 Timeout;為 _Resp→回該 response。"""

    def __init__(self, script):
        self._script = list(script)
        self.calls = 0

    def post(self, *a, **k):
        item = self._script[self.calls]
        self.calls += 1
        if isinstance(item, _Resp):
            return item
        raise TimeoutError("connect timeout")  # 模擬 ConnectTimeout


def _run(monkeypatch, script):
    fake = _FakeRequests(script)
    monkeypatch.setattr(_mbf, "requests", fake)
    slept: list = []
    html = _mbf._fetch_bulk("ajax_t163sb04", "sii", 115, 1,
                            _sleep=lambda s: slept.append(s))
    return html, fake, slept


def test_retry_recovers_after_transient_timeout(monkeypatch):
    # 前兩次 timeout,第 3 次成功 → 應回 HTML、共打 3 次、退避 2 次(8、16 秒)
    html, fake, slept = _run(monkeypatch, [0, 0, _Resp(200, "<ok/>")])
    assert html == "<ok/>"
    assert fake.calls == 3
    assert slept == [8, 16]


def test_retry_exhausts_all_attempts(monkeypatch):
    # 全 timeout → 回 None、共打 _MAX_RETRIES 次、退避 (_MAX_RETRIES-1) 次
    html, fake, slept = _run(monkeypatch, [0] * _mbf._MAX_RETRIES)
    assert html is None
    assert fake.calls == _mbf._MAX_RETRIES
    assert len(slept) == _mbf._MAX_RETRIES - 1


def test_permanent_4xx_not_retried(monkeypatch):
    # 400 屬永久錯誤 → 立刻放棄,不重試、不退避
    html, fake, slept = _run(monkeypatch, [_Resp(400, "bad")])
    assert html is None
    assert fake.calls == 1
    assert slept == []


def test_5xx_is_retried(monkeypatch):
    # 503 屬暫時性 → 重試;第 2 次 200 成功
    html, fake, slept = _run(monkeypatch, [_Resp(503), _Resp(200, "<ok/>")])
    assert html == "<ok/>"
    assert fake.calls == 2
    assert slept == [8]
