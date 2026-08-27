# -*- coding: utf-8 -*-
"""v19.120 — dgtw 6100 metadata **shape** 回歸鎖（`result.distribution[]`）。

═══ 這守的是什麼 ══════════════════════════════════════════════════
2026-08-27 之前,台灣 PMI 卡片長期靠 `data_cache/macro_last_good/tw_pmi.json`
的人工 seed 撐著（60.7 / 2026-06,cached_at 2026-07-01,90 天後靜默過期,
見 `tests/test_macro_last_good_expiry.py`）。表面死因是「8 源並行全失敗」,
但探針 run 33101596383 實測發現 **dgtw 這一源其實一直是活的**:

    metadata `GET /api/v2/rest/dataset/6100` → HTTP 200 + 合法 JSON
      top-level keys  = ['help', 'success', 'result']
      result.resources    → None
      resources           → None
      data.resources      → None
      **result.distribution → list × 1**        ← 只有這個有東西
    → 下載 resourceDownloadUrl(ws.ndc.gov.tw/Download.ashx) → HTTP 200 / 2899 bytes
    → CSV 170 行,末 3 行 = 202605,61.4,58.2 / 202606,60.7,59.9 / **202607,61.5,57.3**
    → `_parse_dgtw_pmi_csv` → {'value': 61.5, 'date': '2026-07-01'}

`_pmi_src_dgtw` 舊碼的 shape 候選清單**沒有 `result.distribution`**（只有
result.resources / resources / data.resources）→ `_res` 為空 → 走一條
**不寫 errs 的 continue** → 整段靜默跳過,log 上只剩 v1/page 的 404,
看起來像「來源死了」,實際上是「我們的 shape 假設過時」。

⚠️ 本測試鎖的是 **shape 相容性**,不是網路存活。它不會因為 data.gov.tw 當天
慢或掛掉而紅燈（全部走假 response,零外部 I/O）。

三個最容易出錯的輸入（§6）:
1. `result.distribution[]` 且 item 用 `resourceDownloadUrl` / `resourceFormat`
   （**不是** `url` / `format`）—— 真實 shape,舊碼兩個 key 都對不上
2. 200 + 合法 JSON 但四種 shape 全空 —— 必須**留痕**,不可靜默 continue
   （這正是本 bug 藏了三輪探針的原因）
3. 舊 shape `result.resources[]` —— 不可為了修新 shape 而把舊的弄壞（向後相容）
"""
from __future__ import annotations

import datetime

import pytest

from src.data.macro import macro_core

# ── 探針 run 33101596383 實測的真實 CSV 尾段（前面補到 >13 個月）──────────
_REAL_CSV = "Date,PMI,NMI\n" + "\n".join(
    f"2025{m:02d},{50 + m * 0.1:.1f},-" for m in range(1, 13)
) + ("\n202601,58.0,-\n202602,58.5,-\n202603,59.0,-\n202604,61.4,-\n"
     "202605,61.4,58.2\n202606,60.7,59.9\n202607,61.5,57.3\n")

_CSV_URL = ('https://ws.ndc.gov.tw/Download.ashx?u='
            'LzAwMS9hZG1pbmlzdHJhdG9yLzEwL3JlbGZpbGUvNTc4MS82MzkxL2JmOGE0ZW')

#: 探針實測的 distribution item key 集合（逐字取自 run 33101596383 的輸出）
_REAL_DISTRIBUTION_ITEM = {
    'resourceDescription': '製造業採購經理人指數',
    'resourceField': 'Date,PMI,NMI',
    'qcLevel': '3',
    'resourceFormat': 'CSV',
    'resourceCharacterEncoding': 'UTF-8',
    'resourceQualityCheckTime': '2026-08-01',
    'resourceDownloadUrl': _CSV_URL,
    'resourceAmount': '170',
    'resourceNotes': '',
    'resourceRequestMethod': 'GET',
    'resourceOasUrl': '',
    'resourceRequestParameters': '',
    'resourcePathParameters': '',
}

_REAL_META = {
    'help': '', 'success': True,
    'result': {
        'datasetId': '6100', 'title': '製造業採購經理人指數',
        'distribution': [_REAL_DISTRIBUTION_ITEM],
    },
}

#: 以 2026-08 為「今天」—— 資料日 2026-07-01 距此 57 天,穩穩落在 max_age_days=90 內。
#: 寫死而非 date.today(),否則本測試會在 2026-09-29 之後自己爛掉（那是資料過期,
#: 不是 shape 壞掉,兩者必須分開;§5 可重現性）。
_TODAY = datetime.date(2026, 8, 27)


class _Resp:
    def __init__(self, payload=None, text='', status=200):
        self._payload = payload
        self.text = text
        self.status_code = status
        self.content = text.encode()

    def json(self):
        if self._payload is None:
            raise ValueError('not json')
        return self._payload


def _make_fetch(meta_payload, *, csv=_REAL_CSV, calls=None):
    """假 fetch_url:metadata 回指定 payload,CSV URL 回真實 CSV,其餘 None。"""
    def _fetch(url, **kw):
        if calls is not None:
            calls.append(url)
        if 'rest/dataset/6100' in url and '/v2/' in url:
            return _Resp(payload=meta_payload, text='{}')
        if 'Download.ashx' in url:
            return _Resp(text=csv)
        return None          # v1 / page 變體:同實測的 404→無回應
    return _fetch


class TestDistributionShape:
    def test_real_shape_yields_july_value(self, monkeypatch):
        """真實 shape（result.distribution + resourceDownloadUrl）→ 拿到 61.5。

        ⛔ 這條就是突變測試的靶:把 `_pmi_src_dgtw` 的 shape 候選清單裡的
        `result.distribution` 拿掉,本條**必須**轉紅。
        """
        monkeypatch.setattr(macro_core, 'fetch_url', _make_fetch(_REAL_META))
        errs: list = []
        out = macro_core._pmi_src_dgtw(_TODAY, 90, errs)
        assert out is not None, (
            '真實 shape 解不出值 —— shape 候選清單可能又漏了 result.distribution;'
            f'errs={errs}')
        assert out['value'] == pytest.approx(61.5)
        assert out['date'] == '2026-07-01'
        assert out['source'] == 'data.gov.tw/6100'

    def test_csv_is_actually_downloaded(self, monkeypatch):
        """撈到 resource 後必須真的去下載 CSV（防「撈到但沒用」的假修好）。"""
        calls: list = []
        monkeypatch.setattr(macro_core, 'fetch_url',
                            _make_fetch(_REAL_META, calls=calls))
        macro_core._pmi_src_dgtw(_TODAY, 90, errs=[])
        assert any('Download.ashx' in u for u in calls), (
            f'從未下載 resource CSV;實際呼叫過的 URL = {calls}')

    def test_legacy_shape_still_works(self, monkeypatch):
        """向後相容:舊 shape `result.resources[]` + `url`/`format` 不可被弄壞。"""
        legacy = {'result': {'resources': [{'format': 'CSV', 'url': _CSV_URL}]}}
        monkeypatch.setattr(macro_core, 'fetch_url', _make_fetch(legacy))
        out = macro_core._pmi_src_dgtw(_TODAY, 90, errs=[])
        assert out is not None and out['value'] == pytest.approx(61.5)


class TestNoSilentSkip:
    def test_200_but_no_resource_leaves_a_trace(self, monkeypatch):
        """200 + 合法 JSON 但四種 shape 全空 → **必須寫 errs**,不可靜默 continue。

        這是讓上一個 bug 藏了三輪探針的那條路徑:log 上只看得到 v1/page 的 404,
        於是所有人都以為 v2 也連不上,沒有人去看 v2 其實回了 200。
        ⛔ 突變靶:把那句 `errs.append(...)` 拿掉,本條必須轉紅。
        """
        empty = {'help': '', 'success': True, 'result': {'datasetId': '6100'}}
        monkeypatch.setattr(macro_core, 'fetch_url', _make_fetch(empty))
        errs: list = []
        out = macro_core._pmi_src_dgtw(_TODAY, 90, errs)
        assert out is None
        assert any('resource' in e for e in errs), (
            f'200 但撈不到 resource 卻沒留痕 —— 這正是原 bug 的藏身處;errs={errs}')

    def test_v1_and_v2_are_distinguishable_in_errs(self, monkeypatch):
        """errs 標籤必須分得出 v1 / v2 / page。

        原碼用 `_meta_url[-18:]`,而 v1 與 v2 的尾 18 字**同為
        '/rest/dataset/6100'** → log 上兩者字面撞在一起。
        ⛔ 突變靶:標籤改回 `_meta_url[-18:]`,本條必須轉紅。
        """
        def _all_dead(url, **kw):
            return None
        monkeypatch.setattr(macro_core, 'fetch_url', _all_dead)
        errs: list = []
        macro_core._pmi_src_dgtw(_TODAY, 90, errs)
        assert len(errs) == 3, f'3 個 meta URL 應各留一筆痕,實得 {errs}'
        assert len(set(errs)) == 3, (
            f'errs 標籤撞在一起,無法分辨是哪個 endpoint 失敗:{errs}')


class TestParserOnRealCsv:
    def test_real_csv_tail_gives_july(self):
        """直接對真實 CSV 尾段跑 parser（與 shape 無關的獨立鎖）。"""
        got = macro_core._parse_dgtw_pmi_csv(
            _REAL_CSV, today=_TODAY, max_age_days=90)
        assert got == {'value': 61.5, 'date': '2026-07-01'}

    def test_stale_data_is_rejected_not_faked(self):
        """資料太舊 → 誠實回 None（§1:不可拿過期值冒充當期）。"""
        assert macro_core._parse_dgtw_pmi_csv(
            _REAL_CSV, today=datetime.date(2027, 1, 1), max_age_days=90) is None
