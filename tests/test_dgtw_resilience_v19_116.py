# -*- coding: utf-8 -*-
"""v19.116 — dgtw 慢站 timeout 放寬 + Cnyes None-summary crash 修復回歸鎖。

背景(user 部署後回報出口/PMI 仍待取得,且證明 NAS 正常):
- production smoke(run 29220720874)實錘 data.gov.tw 慢速政府 API,
  原 timeout=10/attempts=1 在「慢但活」時被殺 → 探針(20s/2)成功但 production
  失敗的根因。放寬至 25s/2。
- 同 smoke 實錘 `_pmi_src_cnyes` crash:`can only concatenate str (not
  "NoneType") to str` — `it.get('summary','')` 對「鍵存在但值=None」不套
  default,None 進字串串接 → 整個 Cnyes 源在第一篇 null summary 就崩(即使
  後面有 PMI 命中也拿不到)。

三個最容易出錯的輸入(§6):
1. Cnyes JSON 某篇 summary=None(非缺鍵)→ 不得 crash,續掃後面篇
2. Cnyes summary=None 但 title 含 PMI → 仍要命中(不因 None 中斷)
3. dgtw 慢站 → timeout 須足夠長(25s),不得回退 10s
"""
from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent


class _FakeResp:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class TestCnyesNoneSummary:
    def _run(self, items):
        import src.data.macro.macro_core as mc
        errs: list = []
        with patch.object(mc, 'fetch_url',
                          return_value=_FakeResp({'items': {'data': items}})):
            return mc._pmi_src_cnyes(datetime.date(2026, 7, 13), 90, errs), errs

    def test_none_summary_does_not_crash(self):
        # summary=None(鍵存在但值 None)+ 一篇無關 → 不得 TypeError
        items = [{'title': '大盤收紅', 'summary': None},
                 {'title': '外資動向', 'summary': None}]
        out, errs = self._run(items)
        assert out is None
        assert not any('TypeError' in e for e in errs), (
            f'None summary 不得再 crash;errs={errs}')

    def test_none_summary_still_matches_pmi_in_title(self):
        # 第一篇 summary=None(舊版會在此崩)、第二篇 title 帶 PMI → 須命中
        items = [
            {'title': '無關新聞', 'summary': None},
            {'title': '2026 年 6 月台灣製造業 PMI 為 60.7', 'summary': None},
        ]
        out, errs = self._run(items)
        assert out is not None, f'None summary 崩潰修好後應命中第二篇;errs={errs}'
        assert out['value'] == 60.7 and out['date'] == '2026-06-01'

    def test_missing_summary_key_also_ok(self):
        items = [{'title': '2026 年 6 月台灣 PMI 60.7'}]   # 完全無 summary 鍵
        out, _ = self._run(items)
        assert out is not None and out['value'] == 60.7


def test_dgtw_timeouts_fit_orchestrator_budget():
    """v19.116→v19.119 修訂:PMI dgtw 仍 25s(由外層 45s race deadline 兜底,見
    test_pmi_bounded_race_v19_119);出口 dgtw **收窄** fit macro_trio 70s inner budget
    (v19.116 的 25s×2 撐爆 budget → export block 被 cancel → 待取得,已由 v19.119 修)。"""
    mc = (REPO / 'src/data/macro/macro_core.py').read_text(encoding='utf-8')
    ms = (REPO / 'src/data/macro/macro_snapshot.py').read_text(encoding='utf-8')
    # PMI:metadata + CSV 仍 25s/2(慢站放寬;外層 race deadline 保證整體準時回)
    assert 'fetch_url(_meta_url, timeout=25, attempts=2' in mc
    assert 'fetch_url(_u2, timeout=25, attempts=2' in mc
    # 出口:v19.119 收窄 — customs-direct 15/1、metadata 10/1、CSV 12/1
    assert 'timeout=15, attempts=1)' in ms                       # customs-direct
    assert '_fu_ex(_meta_url_ex, timeout=10, attempts=1' in ms
    assert '_fu_ex(_csv_url_ex, timeout=12, attempts=1' in ms
    # 不得殘留 v19.116 的出口 25s×2(撐爆 orchestrator budget 根因)
    assert '_fu_ex(_meta_url_ex, timeout=25, attempts=2' not in ms
    assert '_fu_ex(_csv_url_ex, timeout=25, attempts=2' not in ms
    # PMI 不得殘留舊 10s/1(v19.116 慢站被殺根因;PMI 這條未動)
    assert 'fetch_url(_meta_url, timeout=10, attempts=1' not in mc
