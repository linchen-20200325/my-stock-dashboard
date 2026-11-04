"""New UI2 手機抽屜 JS（JS_V4）：固定常數＋唯一一處 `st.html(..., unsafe_allow_javascript=True)`。

DEC-137（使用者 2026-11-04 授權受控施工）。JS 安全設計：`docs/vnext/NEWUI2_MOBILE_DRAWER_JS_SAFETY_DESIGN_2026-11-04.md`
（§15 JS_V4：相對 JS_V3 只多「☰ 上按 Enter → `click()`」兩行）。

⛔ 本檔是 New UI2 唯一允許 `unsafe_allow_javascript=True` 的模組（守衛 `tests/test_ui2_drawer_js_guard.py`）：
- `DRAWER_JS_HTML` 為模組層**固定字串常數**、零插值（⛔ f-string／`+`／`%`／`.format`／`.join`／再賦值）。
- 常數規範化後的 sha256 釘在測試檔；**任何改動（含空白、註解）都會紅 → 必須重過 JS Gate**。
- JS 只用 API 白名單（查詢＋`inert`／`checked=false`／`focus()`／`click()` 四種寫入），⛔ 網路／儲存／DOM 建立／屬性寫入。
- 不讀任何資料、不讀 `ui2_account`／`query_params`；不新增 session key。
"""
from __future__ import annotations

import streamlit as st

DRAWER_JS_HTML = """<script>
(function () {
  if (window.__ui2drJS3) { return; }                         // 去重旗標：st.html 的 script 每次 rerun 都會重跑
  const S = window.__ui2drJS3 = { held: [], ret: 0, q: false };
  const mq = window.matchMedia('(max-width: 768px)');        // 與 CSS 抽屜斷點一致；桌機寬度不得殘留 inert
  const $ = (q) => document.querySelector(q);                // 唯讀查詢（只用本檔列舉的自家 selector 與 .stApp）
  const T = () => $('.ui2-dr-toggle');                       // ☰ checkbox（開關狀態唯一來源）
  const isOpen = () => { const t = T(); return !!(t && t.checked && mq.matches); };
  function release() { S.held.forEach((e) => { e.inert = false; }); S.held = []; }   // 只還原自己設過的元素
  function hold() {                                          // 從 ☰ 外層與抽屜往上走到 .stApp，把「不在路徑上」的 sibling 設 inert
    const t = T(), n = $('.st-key-ui2_nav'), root = $('.stApp');
    const w = t && t.closest('.ui2-dr-wrap');                // ☰ + 遮罩所在外層
    if (!n || !w || !root) { return; }
    const keep = new Set([n, w]), anc = new Set();
    keep.forEach((k) => { for (let p = k.parentElement; p && p !== root.parentElement; p = p.parentElement) { anc.add(p); } });
    anc.forEach((p) => { for (const c of p.children) { if (!keep.has(c) && !anc.has(c) && !c.inert) { c.inert = true; S.held.push(c); } } });
  }
  function sync() {                                          // 開啟且為手機寬度 → hold；其他一律 release
    const t = T(); if (t && t.checked && !mq.matches) { t.checked = false; }
    if (isOpen()) { hold(); } else { release(); }
  }
  function close() {                                         // 關閉並把焦點還給 ☰
    const t = T(); if (!t || !t.checked) { return; }
    t.checked = false; S.ret = Date.now(); t.focus(); sync();
    setTimeout(() => { const u = T(); if (u) { u.focus(); } }, 0);   // 點 label 的預設動作會把焦點拉走，下一個 task 再還給 ☰
  }
  document.addEventListener('keydown', (e) => {             // Esc，或在抽屜 radio 上按方向鍵/Enter/Space（BaseWeb 以內部狀態選取，不發 click/change）→ 收合
    const t = T();                                           // V4：焦點在 ☰ 時按 Enter → 走與 Space 相同的原生切換路徑（click → change）
    if (e.key === 'Enter' && t && e.target === t) { t.click(); return; }
    if (isOpen() && (e.key === 'Escape' || (/^(Arrow|Enter$| $)/.test(e.key) && e.target.matches && e.target.matches('.st-key-ui2_nav input[type=radio]')))) { close(); }
  }, true);
  document.addEventListener('change', (e) => {
    if (e.target.matches && e.target.matches('.ui2-dr-toggle')) {   // ☰ 被勾選（點擊/Space）→ 設 inert、焦點進當前頁 radio
      sync(); const r = e.target.checked && $('.st-key-ui2_nav input[type=radio]:checked'); if (r) { r.focus(); }
    }
  }, true);
  document.addEventListener('click', (e) => {                // 點抽屜內任一頁（含目前頁；radio 值不變時不會 rerun）→ 收合
    if (isOpen() && e.target.closest && e.target.closest('.st-key-ui2_nav label')) { close(); }
  }, true);                                                  // capture：React/BaseWeb 可能 stopPropagation，bubble 收不到
  mq.addEventListener('change', sync);
  new MutationObserver(() => {                               // React 重繪後：補 inert / 移除殘留 / 焦點掉到 BODY 時還給 ☰
    if (S.q) { return; } S.q = true;
    requestAnimationFrame(() => {
      S.q = false; sync();
      if (S.ret && Date.now() - S.ret < 4000 && document.activeElement === document.body && T()) { T().focus(); }
    });
  }).observe(document.body, { childList: true, subtree: true });
  sync();
})();
</script>"""


def render_drawer_script() -> None:
    """抽屜行為 JS（Esc／焦點進出／背景 inert／點當前頁收合／Enter）。JS 被擋時，殼的換標籤 hack 仍會在切頁後收合（降級）。"""
    st.html(DRAWER_JS_HTML, unsafe_allow_javascript=True)
