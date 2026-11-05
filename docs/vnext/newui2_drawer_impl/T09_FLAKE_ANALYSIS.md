# T09 flake 分析（`test_t09_thirty_page_switches_leave_no_inert`）— 2026-11-05

> 單組分析（實作組）。環境：Chromium 153／Playwright 1.64.1、4 vCPU 沙箱；Streamlit 1.59.2（系統）與 1.56.0（/tmp/v156）。
> 原始輸出（精簡到斷言／診斷行）在 `t09_logs/`；重複執行 harness＝`t09_logs/t09_repeat_harness.py.txt`（參數化重複同一測試本體＋失敗時輸出 DOM 診斷與截圖，只加在測試側，**未改 JS／產品碼**）。

## 結論（根因）
**測試等待條件過寬（rerun 與殼重建的競態），不是產品 JS 競態。** 沒有任何一次失敗涉及 inert 殘留：所有失敗診斷的 `inert=[]`（或僅 Streamlit 原生 `stExpanderDetails`，測試本來就排除）。

換頁時殼用「外層標籤輪替 hack」（`div/section/article/aside` 依頁序）讓 React 重建 ☰ 外層（降級機制，spec 保留）。Streamlit 由上而下串流 script 元素：**頁面標題（內容）比導覽殼更早到**。舊 `wait_closed()` 只等 `toggle.checked == false`（JS 在點 label 當下就已取消勾選，並不代表 rerun 完成），所以下一輪 `open_tap()` 可能發生在殼重建中：
1. `.ui2-dr-toggle` 暫時 **2 個**（新舊外層並存）→ `Locator.tap: strict mode violation`；
2. `.ui2-dr-toggle` 暫時 **0 個** → 測試自己的 `wait_for_function` 述詞 `…querySelector('.ui2-dr-toggle').checked` 丟 TypeError（被 Playwright 當 pageerror 收進 `mob.errs`，來源是測試述詞，不是 `drawer_js.py`）；
3. tap 落在即將被替換的舊 toggle 上 → 開啟狀態隨舊元素消失 → 抽屜沒開 → `Locator.click: Timeout 8000ms`（診斷：`checked=False, vis=hidden, page=舊頁`）。

低負載下 server rerun 很快，競態窗口小 → 平常綠；高負載或 `-x` 整檔連續執行時窗口變大 → 偶發紅（與 QA 觀察一致）。

## 重現
- 條件：同時 12 個 busy-loop（4 vCPU）。指令：`REPS=20 UI2_EXPECT_STREAMLIT=<v> UI2_BROWSER_LANE=required <python> -m pytest -v -m ui2_browser tests/test_zz_t09_scratch.py -s`（兩版本同時跑）。
- 修前（`t09_logs/*_BEFORE.txt`）：1.59.2 **19／20 失敗**、1.56.0 **20／20 失敗**。失敗型態：strict-mode 違規 11、`click` 逾時 6、述詞 TypeError 2（1.59 一組樣本）。
- 4 個 busy-loop、1.59.2、10 次：10／10 通過（未達觸發窗口）。

## 修正（只改等待條件；無 retry／skip／xfail／放寬計數）
`tests/test_ui2_drawer_browser.py`：新增 `Ui.wait_settled(page_id)`，`wait_closed(page_id)` 與 `open_tap()` 都先呼叫。條件＝恰 1 個 `.ui2-dr-wrap`＋1 個 `.ui2-dr-toggle`、未勾選，且（指定頁時）標題 `data-ui2-page`＝目標頁、**外層標籤＝該頁的輪替標籤**（殼已更新的決定性訊號）、存在 checked radio。T09／T08 迴圈傳入目標頁 id。
- 第一版只等「標題＝目標頁＋單一 toggle」：12 負載下 20 次各剩 1 次失敗（`t09_logs/*_FIX1.txt`，仍是 strict-mode，因標題先於殼到）→ 第二版加入輪替標籤判定。

## 修後穩定性
| 條件 | Streamlit 1.59.2 | 1.56.0 |
|---|---|---|
| 12 busy-loop 壓力、單測重複 | **30／30 通過** | **30／30 通過** |
| 整個 ui2_browser lane（52 測試，含 T09，無額外壓力） | 52 passed | 52 passed |
| 單測重複 10 次（無壓力） | 10／10 通過 | 10／10 通過 |

穩定性判斷：壓力下各 30 次連續通過、修前同條件 19～20／20 失敗，**可稱此競態已由等待條件修正**。限制：樣本 30 次不是證明；4 vCPU 沙箱；未在 GitHub runner 以壓力驗證。真產品面的對應現象（使用者在 rerun 尚未落定時就點 ☰，開啟狀態可能因舊外層被替換而遺失）是**既有輪替 hack 的固有特性**，不是 JS_V4 引入；未改產品碼，已記錄為限制（BACKLOG `NUI2-DRAWER-TAP-DURING-RERUN`）。
