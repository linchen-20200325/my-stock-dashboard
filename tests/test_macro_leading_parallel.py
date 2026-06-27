"""v18.331 PR-2C 守衛：先行指標 build_leading_fast 併入平行池。

原 leading 在主流程序列呼叫（v8 因 Colab worker thread requests 受阻而移出池），
拖慢總經更新 ~15-55s。2-C 改：import/reload 留主執行緒，worker thread 只跑純抓取，
作為 job 'li' 併入既有 _exc 平行池；結果以 _results.get('li') 收回。失敗時下游既有
fallback 保留舊 li_latest（不致崩潰）。
"""
from __future__ import annotations

import re


def _src(p="tab_macro.py"):
    return open(p, encoding="utf-8").read()


class TestLeadingInPool:
    def test_li_job_registered_in_pool(self):
        src = _src()
        assert "def _job_li()" in src, "缺 _job_li"
        assert "'li':           _job_li" in src, "li 未併入 _jobs 平行池"
        assert re.search(r"'li':\s*80", src), "li timeout 未設"

    def test_import_reload_on_main_thread(self):
        src = _src()
        # reload 非 thread-safe → 須在主執行緒（job 外）取得函式參考
        assert "_li_build_fn = _li_mod.build_leading_fast" in src
        # _job_li 內只呼叫純抓取，不做 import/reload
        m = re.search(r"def _job_li\(\):(.*?)\n\n", _src(), re.S)
        assert m, "_job_li 區塊解析失敗"
        body = m.group(1)
        assert "importlib" not in body and "reload" not in body, "_job_li 內不得 reload"
        assert "build_leading_fast" not in body or "_li_build_fn" in body

    def test_serial_leading_block_removed(self):
        src = _src()
        # 舊序列版本的 UI 進度元件不得殘留
        assert "_li_ph" not in src, "舊 _li_ph 序列進度殘留"
        assert "_li_log" not in src, "舊 _li_log 殘留"
        # 結果改從 pool 收回
        assert "df_li_a = _results.get('li')" in src

    def test_result_handling_preserved(self):
        """下游 li_latest fallback 仍在（失敗保留舊快取，不崩潰）。"""
        src = _src()
        assert "st.session_state['li_latest'] = df_li_a" in src
