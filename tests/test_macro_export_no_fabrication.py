"""v18.330 PR-2B 守衛：總經出口 YoY 全來源失敗時不得捏造靜態值（§1 Fail Loud）。

原 `_fetch_export` 全敗回傳寫死 `{'yoy': 18.9, 'date': '2026-03-01',
'source': '靜態備援'}`，把假出口數據灌進儀表板 / MK 拐點 / AI 摘要。
PR-2B 改回空 dict（不貢獻 tw_export key），下游退「待取得」placeholder。
"""
from __future__ import annotations

import re


def _src(p="src/ui/tabs/tab_macro.py"):
    # P3-D1 v18.389:_fetch_export 下沉 macro_snapshot.fetch_export_block;
    # 守衛斷言改掃合集(主檔仍須無 "靜態備援"/"18.9" — 雙檔同步檢查)。
    base = open(p, encoding="utf-8").read()
    try:
        base += open("src/data/macro/macro_snapshot.py", encoding="utf-8").read()
    except FileNotFoundError:
        pass
    return base


class TestNoStaticExportFallback:
    def test_no_static_fallback_label(self):
        assert "靜態備援" not in _src(), "出口全敗不得回『靜態備援』捏造值（§1）"

    def test_no_fabricated_189_literal(self):
        # 不得再出現寫死的 yoy 18.9 靜態出口值
        assert not re.search(r"'yoy':\s*18\.9", _src()), "出口捏造值 18.9 應已移除"
        assert "'date': '2026-03-01'" not in _src()

    def test_export_total_fail_returns_err_token_not_value(self):
        """全敗 fallback 契約（v19.111 重釘）。

        原鎖 `return {}`；v19.111 起改回 `{'_err_export': ...}` 診斷 token —
        section_mid 錯誤碼面板(v18.194)與 health_inspector 的 `_err_export`
        讀取端原為死鍵（macro_snapshot 從無 setter），出口全敗時 user 看不到
        任何錯誤碼。§1 精神不變：token 僅為診斷字串，**不得**出現 'tw_export'
        數值 key（行為鎖見 tests/test_export_fail_trace_v19_111.py）。"""
        src = _src()
        # 鎖定 fallback 段落：log 行 + 緊接的 return {'_err_export': ...}
        assert "所有方案全失敗" in src
        m = re.search(
            r"所有方案全失敗.*?\n\s*return\s*\{'_err_export':", src, re.S)
        assert m, "全敗 fallback 應回 `{'_err_export': ...}`（診斷 token，不捏造值）"
        # 全敗段不得夾帶 tw_export 數值賦值（防退化回捏造；註解提及不算）
        tail = src[m.start():m.end() + 200]
        assert not re.search(r"'tw_export':\s*\{", tail), (
            "全敗 fallback 不得貢獻 tw_export 值")
