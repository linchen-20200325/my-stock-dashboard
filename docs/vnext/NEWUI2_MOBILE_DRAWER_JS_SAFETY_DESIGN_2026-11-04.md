# New UI2 手機抽屜：JavaScript 安全設計文件（治理採用版）— 2026-11-04

> **治理採用的施工規格（單組撰寫＋獨立 QA）；正式 JS 未核准；本批不授權施工；非客戶視覺驗收。**
> ⛔ **此 JS 僅為設計附件，禁止執行、禁止加入正式程式。** 原型只在暫存目錄（研究組 scratchpad，不在 repo）驗證過；**正式核准前，不得進 repo 的任何可執行檔**（`.py`／`.js`／`.html`／workflow）。本檔把它寫在 markdown code block 內只為審查與日後雜湊釘住。
> 配套：統一施工規格 `NEWUI2_MOBILE_DRAWER_UNIFIED_BUILD_SPEC_2026-11-04.md`；測試與驗收規格 `NEWUI2_MOBILE_DRAWER_TEST_AND_ACCEPTANCE_SPEC_2026-11-04.md`。
> 誠實揭露：候選 JS、DOM 範圍、API 白名單、31 種變異全紅、所有瀏覽器行為，都是**研究組單組**在 Chromium headless（Playwright 1.64／Chromium 153）× Streamlit 1.56.0／1.59.2 的結果，**本檔撰寫者未重跑**，且**無第二組獨立複驗**。iOS Safari、Android 真機、Streamlit Cloud／Manage app／CSP、VoiceOver／TalkBack、Firefox／WebKit **未驗**。

## 0. 狀態與核准流程

- BACKLOG `NUI2-DRAWER-NEW-JS-GATE`：**維持 open**（blocked-on-governance）。本檔只是把候選全文與安全設計入庫，**不等於核准**。
- 本輪治理方向（來源＝ChatGPT／客戶側治理方向，非使用者親自視覺驗收，DEC 尚未落盤）：C+JS 為**首選施工候選**；背景採**精準作用範圍 inert**；點目前所在頁也收合。
- New UI2 目前**零 JS 先例**；此為首次引入 `unsafe_allow_javascript=True`。repo 另有一處既有例外（EX-OAUTH-1，見 §5）。

## 1. 候選 JS_V3 全文（逐字）

### 1.1 完整性事實（已核對）

| 項目 | 值 |
|---|---|
| 釘住對象 | `DRAWER_JS_HTML`＝**含 `<script>…</script>` 包裝的整個常數字串**（`"<script>\n" + JS 主體 + "\n</script>"`） |
| 規範化 | CRLF／CR → LF；去頭尾換行；**其餘一字不動**（含註解、空白） |
| **sha256（規範化後）** | `24050f1b81c4fed6441d8dad082c90ab0b94ce10d032f42ce36524842e606cd3` |
| 長度 | 規範化後 3158 字元（研究組 `js/v3.js` 主體 46 行／3592 bytes〔UTF-8，含中文註解〕） |
| 本檔撰寫者核對 | 以研究組 `guard/drawer_js.py` 的 `DRAWER_JS_HTML` 計算規範化 sha256＝`24050f1b…606cd3`（與研究組報告一致）；並確認該常數＝`"<script>\n" + js/v3.js 去頭尾換行 + "\n</script>"`（逐字相等）。本檔下方 code block 的內容由同一常數檔機械嵌入，並於撰寫後**再自本檔取出重算 sha256**（見 §1.3） |
| ⚠️ 兩個雜湊勿混 | `js/v3.js` **檔案位元組**的 sha256 是 `9ce5c99ef308143406f4e733579b871d78e1d2f833f3e5368a71e5fb98e7e83c`（不含 `<script>` 包裝、含檔尾換行處理差異）。**那不是釘住值**。釘住值只有上表 `24050f1b…`（對含包裝的規範化常數）。兩者不一致是**預期**，非錯誤 |

### 1.2 全文（`DRAWER_JS_HTML` 規範化常數，逐字）

```html
<script>
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
</script>
```

### 1.3 如何自本檔復核雜湊

取出上方 code block 的內容（不含 fence 行），套用規範化（CRLF→LF、去頭尾換行），計算 sha256，必須等於 `24050f1b…606cd3`。若不一致，**以研究組檔案為準**並在本檔追加更正註記。

## 2. 行為設計

| 機制 | 設計 | 對應程式 |
|---|---|---|
| 去重 | `window.__ui2drJS3` 旗標；`st.html` 的 script 每次 rerun 都會重跑，沒旗標會使監聽數隨 rerun 線性增加（拔旗標變異實測 keydown 6→35、change 1→30、MutationObserver 1→30） | 首行 `if (window.__ui2drJS3) return` |
| 狀態來源 | ☰ checkbox `.ui2-dr-toggle` 的 `checked` ＋ `matchMedia('(max-width: 768px)')`；`isOpen = checked && mq.matches` | `T()`、`isOpen()` |
| inert 作用範圍 | `hold()`：把 `{.st-key-ui2_nav, ☰ 外層 .ui2-dr-wrap}` 當保留集，往上走到 `.stApp`（含），對沿途每個祖先，把「不在保留集也不是祖先」的 child 設 `inert`。手機實測 10 個元素；☰、抽屜、祖先不被 inert；上界 `.stApp` 所以 body 層 portal 不被碰 | `hold()` |
| 只還原自己設的 | `S.held` 記錄；`release()` 只清自己設的。**原本就 inert 的元素（例如 Streamlit 收合 expander 的 `stExpanderDetails`）不碰、不還原** | `release()` |
| 同步 | `sync()`：開啟且手機寬度 → `hold`；其他一律 `release`；桌機寬度若 checkbox 被勾則取消勾選 | `sync()` |
| focus trap | **不寫 Tab 攔截**；以 inert 讓背景不可聚焦、不在 a11y tree。殘留：`section.stMain` 仍可拿一次焦點（已知缺口） | `hold()` |
| 焦點進入 | `change`（capture）偵測 ☰ 被勾選 → `sync()` → 焦點同步移到當前頁 radio（不靠計時） | `change` 監聽 |
| Esc／方向鍵／Enter／Space | `keydown`（capture）：開啟中按 Esc → `close()`；焦點在 `.st-key-ui2_nav input[type=radio]` 且按 `Arrow*`／`Enter`／`Space` → `close()`。BaseWeb 以內部狀態選取，**不發 click／change**，只攔 click／change 會漏 | `keydown` 監聽 |
| 點當前頁收合 | `click`（**capture**）：開啟中點 `.st-key-ui2_nav label` → `close()`。bubble 階段被 React／BaseWeb stopPropagation 收不到；radio 值不變不 rerun，靠此路徑 | `click` 監聽 |
| 焦點返回 | `close()`：取消勾選、記時間 `S.ret`、`t.focus()`、`sync()`，並 `setTimeout(0)` 再 focus 一次（label 預設動作會把焦點拉走）；MutationObserver 在 rAF 內若 4 秒內且焦點掉到 BODY → 還給 ☰（切頁輪替 hack 重建後） | `close()`、observer |
| 殘留防護 | MutationObserver（`document.body`，`childList+subtree`，rAF 節流）每次 React 重繪後 `sync()`：補 inert、移除殘留；切頁輪替 hack 重建 ☰ 外層→checkbox 變未勾→`release()` | observer |
| 視窗尺寸變更 | `mq.addEventListener('change', sync)`：開啟中拉到桌機寬度 → 取消勾選、inert 歸零；縮回手機寬度 → 抽屜為關閉 | `mq` 監聽 |
| 與輪替 hack | 無衝突。`UI2_HACK=0`（拿掉輪替）時 JS 單獨即可關閉全部路徑；`HACK=1`＋JS 時 JS 先關、輪替後重建，焦點由 observer 補。**建議保留輪替 hack 作 JS 被擋時的降級**（此時無 inert／Esc／焦點管理，僅切頁收合） | — |

**已知限制（設計即如此）**：Enter 不能開 ☰（原生 checkbox 只吃 Space）；`section.stMain` 一次焦點停靠；開啟中新增節點約 1 frame 未保護；不支援 `inert` 的瀏覽器降級為無 trap 但無害；body 層 portal／Manage app 浮層不被 inert。

## 3. DOM API 與事件（逐一列出）

| 類別 | API |
|---|---|
| 查詢（唯讀） | `document.querySelector`、`Element.closest`、`Element.matches`、`Element.parentElement`、`Element.children`、`document.activeElement`、`document.body` |
| 寫入（**只有 3 種**） | ① `HTMLElement.inert = true/false`（只對 `hold()` 算出的元素）；② `input.checked = false`（只對 `.ui2-dr-toggle`）；③ `HTMLElement.focus()`（只對 ☰ 與當前頁 radio） |
| 事件監聽（4＋1） | `document` 上 **capture**：`keydown`、`change`、`click`；`MediaQueryList` 的 `change`；`MutationObserver`（`document.body`，`childList+subtree`，callback 內只 `requestAnimationFrame(sync)`） |
| 其他 | `window.matchMedia('(max-width: 768px)')`、`requestAnimationFrame`、`setTimeout(fn, 0)`（函式參數，非字串）、`Date.now`、`Set`、`Array#forEach/push`、`RegExp#test`（單一字面 `/^(Arrow\|Enter$\| $)/`；`\|` 僅為 markdown 表格跳脫，實際字面見 §1.2）、全域旗標 `window.__ui2drJS3` |

## 4. 可操作的 DOM 範圍（只准碰這些 selector）

| selector | 用途 | 讀／寫 |
|---|---|---|
| `.ui2-dr-toggle` | ☰ checkbox，開關狀態唯一來源 | 讀 `checked`；寫 `checked=false`、`focus()` |
| `.ui2-dr-wrap` | ☰＋遮罩外層（保持不 inert 的錨點） | 只讀（`closest`） |
| `.st-key-ui2_nav` | 抽屜 container（保持不 inert 的錨點） | 只讀 |
| `.st-key-ui2_nav input[type=radio]`／`:checked` | 當前頁 radio | `focus()`；`matches` 判斷方向鍵目標 |
| `.st-key-ui2_nav label` | 點擊委派判斷 | 只讀（`closest`） |
| `.stApp` | inert 作用範圍上界（只往上走到它，不碰它的外面） | 只讀 |
| 自己算出的「祖先路徑上不在路徑內的 sibling」 | inert 目標 | 寫 `inert`（先記進 `S.held`） |

不依賴任何 Streamlit 內部 testid，只用 `.stApp`（兩版都存在）＋自家 class。

## 5. 禁止清單與 API 白名單

### 5.1 明確禁止清單（守衛 `FORBIDDEN_TOKENS`）

`fetch`／`XMLHttpRequest`／`WebSocket`／`EventSource`／`sendBeacon`／`localStorage`／`sessionStorage`／`indexedDB`／`document.cookie`／`eval`／`Function`／`import(`／`importScripts`／`window.open`／`postMessage`／`innerHTML`／`outerHTML`／`insertAdjacentHTML`／`document.write`／`createElement`／`setAttribute`／`appendChild`／`removeAttribute`／`dispatchEvent`／`classList`／`style.`／`location`／`navigator`／`Worker`／`parent.`／`top.`／`frames`／`opener`／`clipboard`／`history`／`srcdoc`／`javascript:`；另禁**反引號樣板字串、反斜線（unicode 跳脫）、計算式成員存取 `x[..]`**（擋 `window['fe'+'tch']` 類繞法）。

### 5.2 API 白名單（安全守衛主依據）

- **全域識別字**：`window document Set Date MutationObserver requestAnimationFrame setTimeout RegExp`。
  - 註：白名單列了 `RegExp`，但 JS 只使用正則**字面值**（`/^(Arrow|Enter$| $)/`），未使用 `new RegExp`；多列無害。白名單不因此改動，雜湊與 JS 全文不變。
- **成員名**：`matchMedia matches querySelector closest parentElement children checked focus inert held ret q forEach push now add has addEventListener observe activeElement body key target test __ui2drJS3`。
- **事件名**：`keydown change click`（＋ MutationObserver）。
- **字串字面值**：僅限上述事件名、`Escape`、`childList`、`subtree`、`(max-width: 768px)` 與 §4 白名單 selector。
- **規則**：不在白名單 ⇒ 紅燈；白名單變更＝「改 JS」，須走 JS Gate（雜湊也會變）。

### 5.3 誠實限制

- 白名單掃描是 **regex，不是 JavaScript parser**，**不是**健全的靜態分析。
- **完整性的最後防線是雜湊釘住原文**；白名單讓「這次改了什麼」可機械審查、並擋掉最常見的有害加法。
- 兩層互補：白名單抓「有害加法」且給可讀訊息；雜湊抓「任何改動，含無害外觀的功能性退化」（例如拔掉去重旗標——白名單看不出，雜湊紅）。

## 6. Python 端 AST 判準（`check_st_html_js_calls`，純函式吃原始碼字串）

1. 全檔帶 `unsafe_allow_javascript` 關鍵字的呼叫**恰 1**；函式是 `st.html`；該關鍵字值為**字面 `True`**；只有 1 個位置參數＋該 kw。
2. 第一參數必須是**裸 `Name`** 且名稱＝`DRAWER_JS_HTML`（擋 `JoinedStr`／`BinOp`〔`+`、`%`〕／`Call`〔`.format`／`.join`〕／別名 `h = st.html`）。
3. 該 Name 在模組內**恰一次賦值**（`Assign`／`AugAssign`／`AnnAssign`／`global` 皆計），且為**模組層** `NAME = <Constant(str)>`（擋 `BinOp` 拼接、再賦值、`+=`、global 改寫）。
4. 常數恰一個 `<script>…</script>`；再套 §5 白名單掃描。
5. 唯一模組建議為 `src/ui2/shell/drawer_js.py`，內含 `DRAWER_JS_HTML` 常數與 `render_drawer_script()`（內含唯一 `st.html(DRAWER_JS_HTML, unsafe_allow_javascript=True)`）。

## 7. 全域掃描規則（**兩個範圍**）

| 範圍 | 規則 |
|---|---|
| **New UI2**：`src/ui2/**`、`shared/ui2_contract/**`、`src/services/ui2/**`、`app_ui2.py` | `unsafe_allow_javascript`、`<script` **只准** `drawer_js.py` 單模組；`streamlit.components`／`components.v1`／`components.v2`、`on*=` 屬性、`javascript:`、`<iframe`、`srcdoc` **全禁**。研究組實測：目前副本 0 違規 |
| **`src/**` 全域** | 同樣 pattern；**allowlist ＝ `drawer_js.py` ＋ 既有 `src/data/portfolio/oauth_state.py`**（EX-OAUTH-1：`st.html(_silent_redirect_script(_url), …)`，**動態字串**；不得因本批被當成可效仿的樣板）。**計數不得增加**（實測：不加 oauth 例外會 2 命中，加了 0） |

- **pattern 要用 `streamlit\.components`／`st\.components`／`components\.v1|v2`**，不可用寬鬆的 `components\.html`：repo 自己有 `src.ui2.components.html` 模組，會誤判（研究組已修並測）。
- 檢查器吃**字串**、回違規清單 ⇒ 同一支掃真檔也掃注入的假檔（各 pattern 注入皆紅；baseline `views/market.py` 為空）。
- 掃描副檔名只應涵蓋 `.py`／`.js`／`.html`／`.css`；**不得掃 `docs/**`**（本檔 code block 內含 `<script>` 屬設計附件）。

## 8. 雜湊釘住與「雜湊紅＝必須重過 JS Gate」流程

1. 釘住值寫在**測試檔內**（`sha256(normalize(DRAWER_JS_HTML)) == PINNED`）；**pin 與常數任一變更都紅**。
2. 改 JS ⇒ 雜湊測試紅，訊息明寫：`JS changed → must re-pass JS Gate and update pin`。
3. 重過 JS Gate 時，PR **必附**：(a) 新**白名單差異**（新增／刪除了哪些 API、selector、事件、字串）；(b) Playwright **行為矩陣**（本檔 §2＋測試規格 §3）在 **1.56＋1.59** 全綠；(c) **殘留測試**（rerun／30 次切頁／連點 9 次／重載／開啟中改 1440 再縮回）；(d) **獨立 QA** 結論；(e) 治理核准記錄（雜湊值＋日期）寫進 PR。
4. 更新 pin 與（如有）白名單檔須**同 PR**；**不得只更新 pin**（白名單測試仍須綠）。

## 9. 與 CSS 斷點的交叉比對（測試要求）

JS 的 `(max-width: 768px)` 與 CSS 的 `@media (max-width:768px)` 是**兩處相同數字**。施工須加一條測試：從 `src/ui2/shell/css.py` 解析抽屜斷點，與 JS 常數內的 `(max-width: NNNpx)` 比對，不相等＝紅（避免斷點漂移導致桌機殘留 inert 或手機 inert 不生效）。

## 10. 變異測試清單（拔掉修復邏輯必須轉紅；`CLAUDE.md` v3 §03-1 第四項）

**研究組結果（單組、未重跑）**：守衛原型 31 種變異、基準 0 違規、全部紅、未抓到 0。分層歸因：

| 層 | 抓到什麼 |
|---|---|
| 僅「白名單／AST」層 | 加入 `fetch`／`localStorage`／`eval`／`new Function`／`innerHTML`／`window.open`／`postMessage`／`document.cookie`／未列選擇器／未列事件／未列成員 `.value`／`window['fe'+'tch']`／樣板字串／unicode 跳脫／計算式存取；全部 py 端變異（f-string、`+`、`.format`、`%`、`join`、再賦值、`+=`、`global`、第二個呼叫、變數取代、旗標非字面 True、別名呼叫、兩個 script） |
| 僅「雜湊」層 | 空白＋1、只改註解、**拔掉去重旗標**；以及所有 JS 內容變異 |

**行為層變異（Playwright；施工測試必含，皆須轉紅）**：

| 變異 | 預期紅燈證據（研究組實測值） |
|---|---|
| 拔掉去重旗標 | keydown 6→35、change 1→30、MutationObserver 1→30（click 2→61） |
| `release()` 改空函式 | Esc 後殘留 inert 11、整頁卡死（`.st-key-ui2_dev_surface` 在 inert 內） |
| `sync()` 拿掉桌機 release 分支 | 1440 殘留 inert 11 |
| 拿掉 inert 本身 | Tab 穿到背景 9 次、a11y 背景具名節點 13 |
| 拿掉 focus-return（`t.focus()`） | 焦點不回 ☰（待施工時寫成測試） |
| 拿掉 `click` capture（改 bubble） | 點當前頁不收合（待施工時寫成測試） |

研究組附有變異檔：`v3_noinert.js`、`v3_noflag.js`、`v3_norelease.js`、`v3_nodesktoprelease.js`、`v3_focusin.js`（在研究組 scratchpad，不在 repo）。

## 11. 殘留與重繪實測（研究組單組結果）

| 項目 | 結果 |
|---|---|
| 開著抽屜按 `r` 觸發 rerun | 1.59、1.56：inert 12/12 保留（React 不洗掉未知屬性），`held` 12，抽屜仍開 |
| 開啟中 React 新增元素（JS 注入 sibling 模擬） | 下一個 rAF 補上 inert（1.56 實測）；**約 1 frame 未保護**；關閉後還原 |
| 切頁（輪替 hack 重建 ☰ 外層） | observer→`sync()`→`release()`，inert 0（1.59 連 30 次、1.56 連 10 次，每次先開抽屜） |
| 快速連點 ☰ ×9／Esc ×5 | 奇數次開、Esc 後 0 inert、無例外 |
| 頁面重載（開啟中） | inert 0（狀態不持久） |
| 開啟中視窗改 1440 | toggle 取消勾選、inert 0、背景可互動；縮回 390 抽屜為關閉 |
| pageerror | 全程 0 |

> 註：被 inert 的元素數在研究組報告中有 10（手機基準，§4）、11–13（開啟開發面 `?ui2_dev=1` 時）與 12（rerun 測試）等不同數字，**口徑不同（推測為是否含開發面或 rerun 後狀態，研究組報告未逐項說明），數值待施工測試釘死**。

## 12. 行為矩陣（1.56／1.59 結果相同；研究組單組）

| 操作 | 結果 | 焦點 |
|---|---|---|
| 點 ☰（觸控 tap） | 開、背景 inert | → 當前頁 radio |
| Space（焦點在 ☰） | 開 | → 當前頁 radio |
| **Enter（焦點在 ☰）** | ❌ **不會開**（已知限制） | — |
| Esc | 關 | → ☰ |
| 點「目前頁」label | 關（capture 階段） | → ☰ |
| 點「他頁」label | 立即收合，頁面切換 | → ☰（輪替重建後由 observer 補） |
| 遮罩點擊 | 原生 label 切 checkbox 關 | ☰ |
| 方向鍵（radio 上） | 選取並關 | → ☰ |
| Enter／Space（radio 上） | 關 | → ☰ |

## 13. 與其他文件的關係

- 把 inert 與點當前頁收合寫成**必要行為**的是統一施工規格 §4（R-05／R-07）；本檔只負責「JS 怎麼做、怎麼守」。
- 測試規格 §3 把本檔 §10／§12 轉成逐項測試清單，並規定 CI 必須真的跑瀏覽器（skip≠PASS）。
- `CLAUDE.md` v3 §03-1／§03-2：JS **不屬**「框架與效能優化」的內部自決——首次引入 `unsafe_allow_javascript` 是**安全面變更**，BACKLOG 已將其列為需治理／客戶裁示的 Gate；總管不得以「內部自決」跳過。

## 14. 本檔限制

單組撰寫；未重跑研究組原型；§10 的「31 種變異全紅」「行為矩陣」皆為研究組單組結果，獨立 QA 前只是待驗事項；regex 白名單不是 parser；真機／SR／Cloud／CSP 未驗。


## 15. 實作版本 JS_V4（2026-11-04，DEC-137；只追加，§1～§14 原文不動）

- **V3→V4 diff（唯一改動）**：`keydown` 監聽內、`if (isOpen() && …)` 之前新增兩行——`const t = T();`（含註解）與
  `if (e.key === 'Enter' && t && e.target === t) { t.click(); return; }`。理由：使用者要求 Enter／Space 都須明確驗證，V3 的 Enter 不開 ☰（R-11／L-7）；`click()` 走與 Space 相同的原生 checkbox 切換（click → change），不新增狀態路徑。
- **白名單差異**：成員新增 `click`（寫入類 API 由 3 種變 4 種：`inert`／`checked=false`／`focus()`／`click()`，`click()` 只對 `.ui2-dr-toggle`）；字串字面值新增 `Enter`；其餘（全域、事件、selector、正則）不變。禁用清單不變。
- **規範化 sha256（含 `<script>` 包裝）**：`c84d687fcaa246b7411ce1f1b927efcd230e9863fbaeb132b3fb10cb3702680a`（3350 字元）。JS_V3＝`24050f1b…606cd3`（保留為歷史）。守衛 `tests/test_ui2_drawer_js_guard.py` 釘 V4，並有測試證明「移除這兩行必須逐字回到 V3 雜湊」。
- **模組**：`src/ui2/shell/drawer_js.py`（`DRAWER_JS_HTML` 模組層固定常數＋唯一 `st.html(DRAWER_JS_HTML, unsafe_allow_javascript=True)`）。守衛：AST 判準、白名單（regex，非 parser）、雜湊、New UI2 範圍只准此模組、`src/**` allowlist＝本模組＋EX-OAUTH-1（計數不增）、JS／CSS 斷點交叉比對、殼內 raw 互動 HTML 只准 ☰ toggle、抽屜不讀 `ui2_account`／`query_params`／`ui2_dev`。白名單另有測試要求「白名單成員＝實際使用成員」（防預留）。
- **Enter 實測**：1.56.0／1.59.2 × Chromium，焦點在 ☰ 按 Enter 開啟並使焦點進當前頁 radio；再按 Enter 關閉；拿掉該分支（突變）Enter 不開——測試轉紅。
- **本批仍為單組實作**：獨立 QA 由另一組做；未驗項見 PR 描述（iOS／Android／Cloud CSP／Manage app／VoiceOver／TalkBack／Firefox／WebKit／不支援 inert 瀏覽器）。
