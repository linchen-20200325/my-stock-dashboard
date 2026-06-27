"""
test_app_step4.py — Step 4 引擎整合結構性驗證

由於 app.py 體積過大且強耦合 streamlit,無法在 pytest 環境直接 import。
本測試以「原始碼掃描」方式驗證:
1. ADL 備援區塊已切走 tw_macro.fetch_twse_breadth(不再 inline 直連 MI_INDEX)。
2. _job_m1b 區塊已切走 tw_macro.fetch_cbc_m1b_m2(不再內嵌三層 CBC 備援)。
3. 主要決策渲染區塊不再殘留 `requests.get('https://www.twse.com.tw/.../MI_INDEX'`
   或 `cbc.gov.tw` 等字樣。

註: proxy_helper.py / tw_macro.py / macro_core.py 是底層,允許含上述 URL,
    本測試僅針對 app.py 業務層。
"""
from __future__ import annotations

import re
from pathlib import Path

APP_PATH = Path(__file__).parent / "app.py"
APP_SRC  = APP_PATH.read_text(encoding="utf-8")

# v18.33x 三層重排:ADL/M1B 的 tw_macro 委派由 app.py(L6)下沉至 tab_macro.py(L5 UI Tab),
# 符合 §8.2「L6 App 不直接持有 L1 fetcher」。委派「存在性」斷言改掃 tab_macro.py;
# app.py 端仍保「不得 inline 直連 MI_INDEX / cbc.gov.tw」的負向守衛(下方 test 不變)。
TAB_MACRO_PATH = Path(__file__).parent / "tab_macro.py"
TAB_MACRO_SRC  = TAB_MACRO_PATH.read_text(encoding="utf-8")


# ══════════════════════════════════════════════════════════════
# Step 4-1: ADL 備援區塊已委派
# ══════════════════════════════════════════════════════════════

def test_adl_fallback_uses_tw_macro_breadth():
    """ADL 備援區塊應 import tw_macro.fetch_twse_breadth(現於 tab_macro.py)。"""
    assert "from tw_macro import fetch_twse_breadth" in TAB_MACRO_SRC, \
        "tab_macro.py ADL 備援區塊未委派 tw_macro.fetch_twse_breadth"


def test_app_no_inline_mi_index_get():
    """app.py 不應再 inline 對 MI_INDEX 端點 requests.get。"""
    pattern = re.compile(r"\.get\(\s*['\"]https://www\.twse\.com\.tw[^'\"]*MI_INDEX")
    matches = pattern.findall(APP_SRC)
    assert not matches, f"app.py 殘留 MI_INDEX 直連: {matches}"


# ══════════════════════════════════════════════════════════════
# Step 4-3: _job_m1b CBC 三層備援已委派(此測試在 4-3 完成後才會通過)
# ══════════════════════════════════════════════════════════════

def test_app_no_inline_cbc_url():
    """app.py 不應再 inline 直連 cbc.gov.tw(三層備援應交給 tw_macro)。"""
    matches = re.findall(r"['\"]https?://[^'\"]*cbc\.gov\.tw[^'\"]*['\"]", APP_SRC)
    assert not matches, f"app.py 殘留 cbc.gov.tw 直連: {matches[:3]}"


def test_app_uses_tw_macro_m1b_m2():
    """M1B 區塊應委派 tw_macro.fetch_cbc_m1b_m2(現於 tab_macro.py)。"""
    assert "fetch_cbc_m1b_m2" in TAB_MACRO_SRC, \
        "tab_macro.py 未引用 tw_macro.fetch_cbc_m1b_m2"
