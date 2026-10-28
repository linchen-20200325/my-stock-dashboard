"""xview V2：側欄「🔄 強制刷新數據」說明文字須據實（只改文字，按鈕行為不變）。

按鈕實際只做 `st.cache_data.clear(); st.rerun()`；總經戰情快照（session）、
macro_core 模組層暫存（VIX／FRED）、籌碼本機 pkl、proxy 原始回應暫存、失敗冷卻都不清。
原 help「清除所有快取並重新抓取最新資料」不實。
"""
from __future__ import annotations

import ast
import pathlib

_APP = pathlib.Path(__file__).resolve().parents[1] / "app.py"


def _button_call():
    tree = ast.parse(_APP.read_text(encoding="utf-8"))
    hits = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "button":
            kws = {k.arg: k.value for k in n.keywords}
            key = kws.get("key")
            if isinstance(key, ast.Constant) and key.value == "_sb_force_refresh":
                hits.append((n, kws))
    assert len(hits) == 1
    return hits[0]


def _help_text() -> str:
    _, kws = _button_call()
    return ast.literal_eval(kws["help"])


def test_help_no_longer_claims_all_caches():
    h = _help_text()
    assert "所有快取" not in h
    assert "清除所有" not in h


def test_help_names_what_is_not_cleared():
    # XV-H2-EXT／XV-M1（客戶 2026-10-28 裁示）：VIX／匯率／FRED 改為會清 ⇒ 從「不在此列」移到前段；
    # ~~"台灣與美國總經"~~ 不再列為不清項目。
    # QA 回修 #4：會清＝各頁資料暫存＋VIX 與美國 FRED；~~匯率~~ 不在會清之列（日線匯率 pkl 與 tw_macro 快取沒清）。
    h = _help_text()
    head, tail = h.split("不在此列", 1)
    for frag in ("各頁的資料暫存", "VIX", "FRED"):
        assert frag in head, frag
    assert "匯率" not in head and "台灣" not in head
    for frag in ("總經戰情快照", "個股股價", "籌碼", "日線指數與匯率的本機暫存（約 30 分）",
                 "台灣總經數據", "多檔批次結果", "原始回應（約 5 分）", "等待重試"):
        assert frag in tail, frag


def test_help_says_list_is_not_exhaustive():
    """QA 回修：列舉不得讀成完整清單 —— 以「等各模組自有的暫存」收尾。"""
    assert _help_text().endswith("等各模組自有的暫存。")


def test_label_and_key_unchanged():
    n, kws = _button_call()
    assert ast.literal_eval(n.args[0]) == "🔄 強制刷新數據"
    assert ast.literal_eval(kws["use_container_width"]) is True


def test_button_behavior():
    """XV-H2-EXT／XV-M1（客戶 2026-10-28 裁示，取代 xview V2「行為不變」）：按下做
    st.cache_data.clear() → L3 force_refresh_service → L1 macro_core.clear_success_caches()（只清成功快取）→ st.rerun()。"""
    src = _APP.read_text(encoding="utf-8")
    i = src.index("key='_sb_force_refresh'")
    body = src[i:i + 2000]
    j = body.index("):\n")
    after = [ln.strip() for ln in body[j + 3:].splitlines()[:4]]
    assert after == ["st.cache_data.clear()",
                     "from src.services.force_refresh_service import clear_module_success_caches as _mc_clear_ok",
                     "_mc_clear_ok()",
                     "st.rerun()"]
