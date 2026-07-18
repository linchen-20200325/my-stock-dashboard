# -*- coding: utf-8 -*-
"""v19.117 — 出口卡片改「直連海關 opendata」繞過 data.gov.tw catalog metadata 脆弱環。

決定性背景(探針 run 29223581269,雲端 US IP + NAS):
- 同一 run 內,deep-dump 打 data.gov.tw/api/v2/rest/dataset/6100 metadata **成功**、
  production `_pmi_src_dgtw` 秒級後打「同一 URL」卻「無回應」→ catalog metadata hop
  從雲端 IP 不穩,且 v19.116 timeout 已放寬至 25s 仍無效(實證)。
- 但資源 CSV **直連 opendata.customs.gov.tw/data/6053/csv.csv** 於兩 run
  (29186611230 + 29223581269)皆穩定 200。海關 opendata 才是實際 T1 源,
  data.gov.tw 僅為 catalog 指標 → 出口改先直打海關直連,失敗才回退 catalog。

三個最容易出錯的輸入(§6):
1. 直連 URL 打不通(None/非200)→ 不得 crash,須落回退 metadata(且記診斷 token,非裸 pass)
2. 直連成功但 CSV 解析失敗 → 落回退,不得回捏造值
3. 直連成功且解析成功 → 直接回傳,**不應再打 data.gov.tw catalog**
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent

# 重用 v19.114/115 回歸鎖的真實海關出口 CSV 樣本(民國年、降序)
from tests.test_dgtw_recovery_v19_114_115 import _export_csv  # noqa: E402


class _FakeResp:
    def __init__(self, content: bytes, status: int = 200):
        self.content = content
        self.status_code = status


def test_direct_customs_url_present_and_first():
    """海關直連 URL 存在且排在 data.gov.tw catalog metadata 之前(direct-first)。"""
    ms = (REPO / 'src/data/macro/macro_snapshot.py').read_text(encoding='utf-8')
    direct = 'https://opendata.customs.gov.tw/data/6053/csv.csv'
    meta = 'https://data.gov.tw/api/v2/rest/dataset/6053'
    assert direct in ms, '出口須有海關 opendata 直連 URL'
    assert meta in ms, '回退 catalog metadata URL 仍保留'
    assert ms.index(direct) < ms.index(meta), (
        '海關直連須排在 data.gov.tw catalog metadata 之前(繞過脆弱環)')


def test_direct_except_logs_not_bare_pass():
    """直連失敗 except 不得裸 pass(§1 Fail Loud)— 須記 customs-direct 診斷 token。"""
    ms = (REPO / 'src/data/macro/macro_snapshot.py').read_text(encoding='utf-8')
    assert 'except Exception as _e_direct:' in ms
    assert 'customs-direct/6053:' in ms, '直連失敗須記診斷 token,非裸 pass'


def test_direct_url_short_circuits_catalog():
    """直連海關成功 → 回傳直連來源,且**不再打 data.gov.tw catalog metadata**。"""
    # 安全 patch:走 proxy_helper.fetch_url(非 patch 套件本身,避開 PEP 562 forwarding 地雷)
    from src.data.proxy import proxy_helper as _ph
    import src.data.macro.macro_snapshot as ms

    calls: list[str] = []
    csv_bytes = _export_csv().encode('utf-8')

    def _fake(url, *a, **k):
        calls.append(url)
        if 'opendata.customs.gov.tw' in url:
            return _FakeResp(csv_bytes, 200)
        return None  # 其他源(stat.gov.tw / catalog metadata / FRED / MOF)全 None

    ms.fetch_export_block.clear()   # 清 _cache_success_only 快取,避免跨測試 bleed
    with patch.object(_ph, 'fetch_url', side_effect=_fake):
        out = ms.fetch_export_block(fred_api_key='', finmind_token='')

    assert out.get('tw_export') is not None, f'直連應命中;out={out}'
    assert '直連' in out['tw_export']['source'], out['tw_export']['source']
    assert out['tw_export']['ccy'] == 'TWD'
    assert not any('data.gov.tw' in u for u in calls), (
        f'直連成功後不應再打 catalog metadata;calls={calls}')


def test_gov_mof_ckan_sorts_before_iloc():
    """v19.133 資料穩健:GOV-MOF CKAN 泛用 CSV 路徑取 iloc[-1]/[-13] 前須 sort_values。

    此路徑用泛用 read_csv + 欄位比對(非走 _parse_customs_export_csv),CKAN 列序不保證
    (常降序)。未 sort → iloc[-1] 取到最舊列 → YoY 算反(§1 錯值比沒值更糟)。防回退。
    """
    ms = (REPO / 'src/data/macro/macro_snapshot.py').read_text(encoding='utf-8')
    _idx_block = ms.find("'source': 'MOF-CSV'")
    assert _idx_block != -1, 'GOV-MOF CKAN 區塊(source=MOF-CSV)應存在'
    # 該 source 標記前方同段 _df_ex 處理須含 sort_values(_dt_k)
    _seg = ms[max(0, _idx_block - 900):_idx_block]
    assert 'sort_values(_dt_k)' in _seg, (
        'GOV-MOF CKAN CSV 取 iloc 前須 sort_values(_dt_k)(源可能降序 → YoY 算反)')


def test_direct_fail_falls_back_and_logs():
    """直連非200 → 落回退(catalog 也 None)→ 最終回 _err_export,且含 customs-direct token。"""
    from src.data.proxy import proxy_helper as _ph
    import src.data.macro.macro_snapshot as ms

    def _fake(url, *a, **k):
        if 'opendata.customs.gov.tw' in url:
            return _FakeResp(b'', 503)   # 直連壞掉
        return None                      # 其餘全 None

    ms.fetch_export_block.clear()   # 清 _cache_success_only 快取,避免跨測試 bleed
    with patch.object(_ph, 'fetch_url', side_effect=_fake):
        out = ms.fetch_export_block(fred_api_key='', finmind_token='')

    # 全敗 → 不捏造,回診斷 token(§1)
    assert out.get('tw_export') is None
    assert '_err_export' in out
