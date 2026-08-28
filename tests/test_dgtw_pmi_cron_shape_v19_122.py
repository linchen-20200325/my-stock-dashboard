# -*- coding: utf-8 -*-
"""v19.122 — dgtw 6100 shape 修正的 **cron 端**補齊（`result.distribution[]`）。

═══ 這守的是什麼 ══════════════════════════════════════════════════
v19.120 修好的是 **runtime** 那一條（`macro_core._pmi_src_dgtw`，畫面上的
台灣 PMI 卡片）。但 6100 這個來源在本 repo 有**兩條**互相獨立的取數路徑：

    runtime  src/data/macro/macro_core.py::_pmi_src_dgtw        → 畫面卡片
    cron     scripts/update_macro_history.py::fetch_tw_pmi_history
             → 寫 data_cache/tw_pmi.parquet + data_cache/metadata.json

v19.120 只改了前者，**後者的 shape 候選鏈當時沒跟上** —— 仍只有
`result.resources` / `resources` / `data.resources` 三種舊 shape，而探針
run 33101596383 實測 6100 的 v2 API **只有 `result.distribution` 有東西**
（另三個皆 None）→ `_res` 恆空 → 靜默 continue。

實證（修正前的 `data_cache/metadata.json`，非推論）::

    "tw_pmi": {"last_updated": null, "row_count": 0,
               "last_error": "抓取結果為空"}

也就是說：畫面已經修好、**存檔那條路徑還是空的**。這正是「同一個 bug 修一半」
最典型的樣子 —— 表面看起來已修復，實際上一半的產出仍是壞的。

⚠️ 本測試鎖的是 **shape 相容性**，不是網路存活。全部走假 response、零外部
I/O，不會因為 data.gov.tw 當天慢或掛掉而紅燈。

三個最容易讓這段程式出錯的輸入（§6）:
1. metadata **只有** `result.distribution[]`，item 用 `resourceDownloadUrl` /
   `resourceFormat`（**不是** `url` / `format`）—— 真實 shape，舊碼全對不上
2. 同一份 distribution 有多個 resource，CSV 那個**不在第一個** —— 舊碼只看
   `format`（恆空）→ CSV 排不到前面 → 白跑一輪非 CSV 資源
3. 舊 shape `result.resources[]` + `url`/`format` —— 不可為了修新 shape 而
   把舊的弄壞（向後相容）
"""
from __future__ import annotations

import ast
import datetime as _dt
import pathlib

import pytest

from scripts import update_macro_history as umh

_REPO = pathlib.Path(__file__).resolve().parents[1]

# ── 探針 run 33101596383 實測的真實 CSV 尾段（與 test_dgtw_pmi_shape_v19_120 同源）──
_REAL_CSV = "Date,PMI,NMI\n" + "\n".join(
    f"2025{m:02d},{50 + m * 0.1:.1f},-" for m in range(1, 13)
) + ("\n202601,58.0,-\n202602,58.5,-\n202603,59.0,-\n202604,61.4,-\n"
     "202605,61.4,58.2\n202606,60.7,59.9\n202607,61.5,57.3\n")

_CSV_URL = ('https://ws.ndc.gov.tw/Download.ashx?u='
            'LzAwMS9hZG1pbmlzdHJhdG9yLzEwL3JlbGZpbGUvNTc4MS82MzkxL2JmOGE0ZW')

#: 探針實測的 distribution item key 集合（逐字取自 run 33101596383 的輸出）。
#: ⚠️ 注意它**沒有** `url`、也**沒有** `format` —— 這正是舊碼兩個 key 都撲空的原因。
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

#: 取數區間寫死，不用 date.today() —— 否則本測試會在未來某天自己爛掉，
#: 而那是「區間過期」不是「shape 壞掉」，兩者必須分得開（§5 可重現性）。
_START = _dt.date(2025, 1, 1)
_END = _dt.date(2026, 12, 31)


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
    """假 _fetch_url_via_proxy：v2 metadata 回指定 payload，Download.ashx 回真實 CSV。

    v1 / page 兩個變體回 None（＝ 實測的 404 / 無回應），確保本測試真的是在
    驗 v2 那條路徑，而不是靠別的 URL 僥倖救回來。
    """
    def _fetch(url, params=None, timeout=25):
        if calls is not None:
            calls.append(url)
        if 'rest/dataset/6100' in url and '/v2/' in url:
            return _Resp(payload=meta_payload, text='{}')
        if 'Download.ashx' in url:
            return _Resp(text=csv)
        if url.endswith('.json'):
            return _Resp(text='{"not": "csv"}')
        return None
    return _fetch


class TestCronDistributionShape:
    def test_real_shape_yields_rows(self, monkeypatch):
        """真實 shape（**只有** result.distribution）→ cron 端必須取到資料。

        ⛔ 突變靶：把 `fetch_tw_pmi_history` 的 `_res` 候選鏈裡的
        `result.distribution` 拿掉，本條**必須**轉紅。
        """
        monkeypatch.setattr(umh, '_fetch_url_via_proxy', _make_fetch(_REAL_META))
        df = umh.fetch_tw_pmi_history(_START, _END)
        assert not df.empty, (
            'cron 端解不出任何列 —— shape 候選鏈可能又漏了 result.distribution。'
            '這正是 metadata.json 長期 row_count:0 / last_error:"抓取結果為空" 的原因。')
        assert {'date', 'pmi'} <= set(df.columns)
        # 末列 = 202607,61.5（探針實測值）
        assert df['pmi'].iloc[-1] == pytest.approx(61.5)
        assert df['date'].iloc[-1] == _dt.date(2026, 7, 1)

    def test_provenance_is_attached(self, monkeypatch):
        """S-PROV-1：取到資料時必須帶 source / fetched_at（§2.2）。"""
        monkeypatch.setattr(umh, '_fetch_url_via_proxy', _make_fetch(_REAL_META))
        df = umh.fetch_tw_pmi_history(_START, _END)
        assert not df.empty
        assert df['source'].iloc[0] == 'data.gov.tw:dataset:6100'
        assert df['fetched_at'].notna().all()

    def test_csv_is_actually_downloaded(self, monkeypatch):
        """撈到 resource 後必須真的去下載 CSV（防「撈到但沒用」的假修好）。"""
        calls: list = []
        monkeypatch.setattr(umh, '_fetch_url_via_proxy',
                            _make_fetch(_REAL_META, calls=calls))
        umh.fetch_tw_pmi_history(_START, _END)
        assert any('Download.ashx' in u for u in calls), (
            f'從未下載 resource CSV；實際呼叫過的 URL = {calls}')

    def test_resource_format_csv_sorts_first(self, monkeypatch):
        """`resourceFormat: CSV` 必須讓 CSV 排到最前面（本 bug 的第二半）。

        6100 的 distribution item 用 `resourceFormat`，**不是** `format`。
        舊碼只看 `format` → 恆為空字串 → CSV 永遠排不到前面 → 多資源時先白跑
        一輪非 CSV。只影響順序不影響正確性（下載後一律交 parser 靠內容判斷），
        但兩邊行為不一致本身就是下一個 bug 的溫床。

        ⛔ 突變靶：把 `or _it.get("resourceFormat")` 拿掉，本條**必須**轉紅。
        """
        noise = {'resourceFormat': 'JSON',
                 'resourceDownloadUrl': 'https://example.invalid/6100.json'}
        meta = {'result': {'distribution': [noise, _REAL_DISTRIBUTION_ITEM]}}
        calls: list = []
        monkeypatch.setattr(umh, '_fetch_url_via_proxy',
                            _make_fetch(meta, calls=calls))
        umh.fetch_tw_pmi_history(_START, _END)
        downloads = [u for u in calls if 'example.invalid' in u or 'Download.ashx' in u]
        assert downloads and 'Download.ashx' in downloads[0], (
            'CSV 沒有排在最前面 —— `resourceFormat` 可能又只看 `format` 了；'
            f'實際下載順序 = {downloads}')

    def test_legacy_shape_still_works(self, monkeypatch):
        """向後相容：舊 shape `result.resources[]` + `url`/`format` 不可被弄壞。"""
        legacy = {'result': {'resources': [{'format': 'CSV', 'url': _CSV_URL}]}}
        monkeypatch.setattr(umh, '_fetch_url_via_proxy', _make_fetch(legacy))
        df = umh.fetch_tw_pmi_history(_START, _END)
        assert not df.empty and df['pmi'].iloc[-1] == pytest.approx(61.5)

    def test_200_but_no_resource_returns_empty_not_crash(self, monkeypatch):
        """200 + 合法 JSON 但四種 shape 全空 → 誠實回空 DataFrame（§1，不可造假）。"""
        empty = {'help': '', 'success': True, 'result': {'datasetId': '6100'}}
        monkeypatch.setattr(umh, '_fetch_url_via_proxy', _make_fetch(empty))
        df = umh.fetch_tw_pmi_history(_START, _END)
        assert df.empty
        assert list(df.columns) == ['date', 'pmi']


# ══════════════════════════════════════════════════════════════════
# 漂移鎖：runtime 與 cron 的 shape 候選鏈必須逐項一致
# ══════════════════════════════════════════════════════════════════
def _extract_res_chain(path: pathlib.Path, func_name: str) -> list[tuple[str, ...]]:
    """AST 解出指定函式裡 `_res = (a or b or ...)` 的 key 路徑序列。

    為什麼用 AST 而不是 grep：grep 只能證明「某個字串出現過」，證不了
    **順序**，也證不了它出現在**哪個函式**裡。本鎖要抓的正是順序分岔。

    回傳例：[('result','resources'), ('resources',),
             ('result','distribution'), ('data','resources')]
    """
    tree = ast.parse(path.read_text(encoding='utf-8'))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and n.name == func_name), None)
    assert fn is not None, f'{path.name} 找不到函式 {func_name}'

    assigns = [n for n in ast.walk(fn)
               if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == '_res' for t in n.targets)]
    assert len(assigns) == 1, (
        f'{path.name}::{func_name} 的 `_res` 賦值有 {len(assigns)} 處，預期剛好 1 處'
        '（多處代表這個鎖的抓取目標已經不明確，請先釐清再改本測試）')

    node = assigns[0].value
    assert isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or), (
        f'{path.name}::{func_name} 的 `_res` 不再是 `or` 鏈，本鎖需同步更新')

    chain: list[tuple[str, ...]] = []
    for operand in node.values:
        keys: list[str] = []
        cur = operand
        # 由外而內剝 `.get('k', ...)`，最後反轉成由外而內的 key 路徑
        while (isinstance(cur, ast.Call)
               and isinstance(cur.func, ast.Attribute)
               and cur.func.attr == 'get'
               and cur.args
               and isinstance(cur.args[0], ast.Constant)):
            keys.append(cur.args[0].value)
            cur = cur.func.value
        if keys:
            chain.append(tuple(reversed(keys)))
    return chain


class TestShapeChainParity:
    """runtime 與 cron 的 dgtw shape 候選鏈必須**逐項且同序**一致。

    為什麼要鎖：`or` 鏈是**短路取第一個非空**。若兩邊涵蓋的 key 不同，
    就是這次要修的 bug（一邊接得到、一邊接不到）；若涵蓋相同但**順序**
    不同，則同一份 metadata 若同時帶兩種 shape，runtime 與 cron 會挑到
    **不同的 resource 清單** —— 畫面對、存檔錯，是最難查的那種分岔。

    ⛔ 突變靶：把任一邊的 `result.distribution` 拿掉、或調換順序，本類必須轉紅。
    """

    RUNTIME = (_REPO / 'src/data/macro/macro_core.py', '_pmi_src_dgtw')
    CRON = (_REPO / 'scripts/update_macro_history.py', 'fetch_tw_pmi_history')

    def test_chains_cover_the_same_key_paths(self):
        runtime = _extract_res_chain(*self.RUNTIME)
        cron = _extract_res_chain(*self.CRON)
        assert set(runtime) == set(cron), (
            'runtime 與 cron 的 dgtw shape 候選鏈涵蓋的 key 路徑分岔了。\n'
            f'  runtime({self.RUNTIME[1]}) = {runtime}\n'
            f'  cron   ({self.CRON[1]}) = {cron}\n'
            f'  只有 runtime 有：{sorted(set(runtime) - set(cron))}\n'
            f'  只有 cron 有   ：{sorted(set(cron) - set(runtime))}\n'
            '兩條路徑打同一個 endpoint，shape 假設必須同步（v19.120/v19.122）。')

    def test_chains_are_in_the_same_order(self):
        runtime = _extract_res_chain(*self.RUNTIME)
        cron = _extract_res_chain(*self.CRON)
        assert runtime == cron, (
            'runtime 與 cron 的 shape 候選**順序**不一致 —— `or` 鏈短路取第一個非空，'
            '順序不同會讓兩邊在「同時有多種 shape」的 metadata 上挑到不同 resource。\n'
            f'  runtime = {runtime}\n  cron    = {cron}')

    def test_distribution_is_actually_in_both(self):
        """正面斷言：兩邊都必須含 result.distribution（防兩邊「一起漏」而 parity 仍綠）。"""
        for path, fn in (self.RUNTIME, self.CRON):
            chain = _extract_res_chain(path, fn)
            assert ('result', 'distribution') in chain, (
                f'{path.name}::{fn} 的候選鏈缺 result.distribution —— '
                f'那是 6100 v2 API 唯一有東西的 shape；實得 {chain}')
