"""src/ui/render/print_css.py — L4 全域列印樣式(只有 `@media print`)。

## 這個檔在解什麼 bug

使用者用瀏覽器列印(Ctrl+P → 另存 PDF)輸出任一分頁時,內容**切在第一頁**。

根因不是版面太長,是 **Streamlit 的捲動不在 document 上**:`<html>` / `<body>`
永遠只有一個視窗高,所有內容都在 `section.stMain` **內部**捲。瀏覽器分頁時
只看得到 document 流裡的內容,捲動容器裡溢出的部分不會被分到第 2 頁。

Streamlit 自己有一段 `@media print`,但**只還原了一半**。下表逐條比對自
`streamlit/static/static/js/index.*.js`(emotion 產生的 styled component,
括號內是它的 `target` 指紋)——

| 元素(emotion target)                  | 常態                                    | Streamlit 的 `@media print`                     |
|---|---|---|
| `stApp` (`e1vju3fw0`)                  | `position:absolute; inset:0; overflow:hidden` | ✅ `position:static` + `height:100%` + `overflow:visible` |
| `stAppViewContainer` (`e15ve43o0`)     | `position:absolute; inset:0; overflow:hidden` | ⚠️ **只有** `overflow:visible`                  |
| 其下一層 wrapper (`e15ve43o10`)         | `height:100dvh`                          | ❌ **完全沒有**                                  |
| `section.stMain` (`e15ve43o1`)         | `height:100dvh; overflow:auto`           | ⚠️ **只有** `overflow:visible`                  |

⇒ 只要有一層還鎖著 `100dvh` / `position:absolute`,內容就仍然被關在一個
視窗高的盒子裡。本檔補上缺的那一半。

**不是版本退化**:同樣的比對也在 `streamlit==1.59.0`(`requirements.txt`
允許範圍內的上緣)做過,四條**完全相同** —— 這是長期行為,不是某一版改壞的。

## ⚠️ 這些 `data-testid` 是 Streamlit 的內部實作細節,不是公開 API

驗證版本:**1.61.1**(開發沙箱實裝)+ **1.59.0**(比對用)。Streamlit 沒有
保證 testid 穩定。若上游改名:

  · 本檔全部規則都在 `@media print{}` 內 ⇒ **螢幕版面完全不受影響**,
    壞掉的只有列印(退回現在這個「切在第一頁」的狀態),不會把畫面弄壞。
  · `tests/test_print_layout.py::TestPrintCssIsPrintOnly` 釘住「不得有任何
    規則洩漏到 `@media print` 之外」,漏一個大括號就紅燈。

## ⚠️ 一個已知脆弱的位置選擇器

`[data-testid="stAppViewContainer"]>div` —— 那一層 wrapper(emotion target
`e15ve43o10`,`height:100dvh`)在 Streamlit 1.61.1 的 DOM 裡**既沒有
`data-testid` 也沒有 class**(渲染處是 `s(Db,{children:[...]})`,一個裸 div),
所以除了「位置」之外沒有別的把手可抓。**沒有更穩的寫法。**

它同時也會命中側邊欄那一層(側邊欄也是 `stAppViewContainer` 的直接子元素)——
無害:規則只設 `height:auto`,而側邊欄本來就被 Streamlit 的 print 規則設成
`height:auto!important`,且本檔下面直接把它 `display:none`。

**下一個人要重驗什麼**:升級 Streamlit 後,若列印又被切斷,先確認
`stAppViewContainer` 的直接子元素是否仍是那個 `height:100dvh` 的裸 div
(DevTools 選它 → Computed → height)。

## 兩個刻意的取捨(不是漏寫)

1. **不強制展開 `stExpanderDetails`。** 收合的 expander 內容其實在 DOM 裡,
   CSS 撐開它做得到。**但不做** —— 列印應該印「螢幕上看得到的東西」,
   使用者收起來的區塊(例如存股戰情室 `expanded=False` 的組合深度分析)
   是他決定不看的,替他印出一大片他沒打算印的內容不是幫忙。想印就先展開,
   那是一次點擊的事,而且是**他的**決定。

2. **不動 `stMainBlockContainer` 的 `max-width` / `padding-top`。**
   本 app 是 `layout='wide'`,Streamlit 在 wide 模式下已把 `max-width` 設成
   `initial`;`padding-top` 它自己的 print 規則也已收成 `2.25rem`。再寫一次
   等於放一條看起來有在做事、實際是 no-op 的規則,反而誤導下一個讀的人。
"""
from __future__ import annotations

#: 全域列印樣式。**整段只有一個 `@media print` 區塊** —— 任何規則跑到區塊外
#: 就會影響螢幕顯示,測試 `TestPrintCssIsPrintOnly` 會擋下。
PRINT_CSS = """<style>
@media print{
  /* ① 還原三層捲動容器 —— 讓內容真的回到 document 流,瀏覽器才分得了頁 */
  [data-testid="stApp"]{position:static!important;height:auto!important;overflow:visible!important;}
  [data-testid="stAppViewContainer"]{position:static!important;height:auto!important;overflow:visible!important;}
  /* ⚠️ 位置選擇器,見 module docstring「一個已知脆弱的位置選擇器」 */
  [data-testid="stAppViewContainer"]>div{height:auto!important;}
  /* stMain 在有 chat input 的頁面會換成 stAppScrollToBottomContainer,
     但兩者的 class 都是 `stMain` —— 兩個選擇器一起寫,少一邊改名還有另一邊 */
  section[data-testid="stMain"],section.stMain{height:auto!important;overflow:visible!important;}
  /* ② 操作介面不入紙。Streamlit 自己只把 header 的子元素藏起來(留 st.logo),
     側邊欄則是「展開著就印出來」—— 對一份要拿去看的報表來說,側邊欄是控制項
     不是內容,整條印在第一頁只是浪費紙。本 app 未使用 st.logo,故整個 header
     一併收掉(若日後加了 st.logo,列印時也不會出現 —— 這是已知代價) */
  [data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stSidebar"]{display:none!important;}
}
</style>"""
