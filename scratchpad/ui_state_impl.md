# v3 §02「介面狀態嚴格分離」— L0 模型 + 第 4 類修復（架構與前端組實作記錄）

> 依據規格：`scratchpad/ui_state_separation_spec.md`（唯讀盤點組，2026-08-27）。
> ⚠️ 該規格自陳**全部判定未經第二組驗證**，故本組對**承重宣稱逐一自行複查**，
> 複查結果記於本檔 §1／§3。與規格不符處集中列在 §8。

---

## §1. 複驗盤點組的核心論證：「兩條軸不能互相取代」

**結論：論證成立。而且我找到兩條盤點組沒寫出來、但更硬的理由。**

### 1.1 盤點組給的兩個理由，逐一實測

| 盤點組的主張 | 我的複查 | 判定 |
|---|---|---|
| `classify_state` 的簽名沒有 `requested` 這個輸入，加了態卻沒有資料源 → 呼叫端只能猜 | 實讀 `shared/station_specs.py::classify_state`，簽名為 `(spec: StationSpec, *, has_value: bool, reason: str \| None = None)`。**確實沒有 `requested`**，而且 `reason` 這個參數**在函式體內從頭到尾沒被讀過**（body 只有 4 行 if，全部只碰 `spec.wired` / `has_value` / `spec.discriminative`）。 | ✅ 成立 |
| 塞 `MISS_NOT_REQUESTED` 會讓取最根本原因的函式在混合情境給錯答案 | 該函式**實際叫 `most_fundamental_miss`**（不是規格寫的 `pick_miss_reason`，見 §8）。它是 `min(reasons, key=MISS_PRIORITY.index)`，而 `MISS_PRIORITY` 的排序準則寫在原始碼註解裡：**「解釋力涵蓋範圍」**。 | ✅ 成立，理由見下 |

**`MISS_NOT_REQUESTED` 為什麼無論排在哪一格都是錯的**（這是我補的推導，不是照抄）：
`MISS_PRIORITY` 的排序準則是「**誰的解釋力涵蓋誰**」——「整檔抓取失敗」排第一，是因為它一旦成立，
其他項不可能算得出來，它解釋了全部。而「還沒去拿」與「拿了但失敗」之間**沒有涵蓋關係**：
- 排前面 → `[NOT_REQUESTED, FETCH_FAILED]` 回 `NOT_REQUESTED`，畫面對一個**真故障**說「你還沒點」；
- 排後面 → `[NOT_REQUESTED, NOT_APPLICABLE]` 回 `NOT_REQUESTED`? 不，會回 `NOT_APPLICABLE`，
  畫面對一個**根本沒跑過**的項目說「這類持股不適用這盞燈（不是壞掉）」——同樣是斷言了它不知道的事。

**兩個方向都會產生假斷言，因為排序函式的前提（可比較的涵蓋關係）在這一對上不成立。**
這正是 §-2 規則 6 那次 `MISS_*` 選錯的同一個病：**把不同軸的東西丟進同一個優先序去比大小。**

**第三個致命點（盤點組沒寫）**：`MISS_TEXT` 每一則都是**行動指引**（「可以重跑一次」「等時間累積」
「這是程式要修的訊號，請回報」）。而 `classify_state` **根本不讀 `reason`** → 就算塞進 `MISS_NOT_REQUESTED`，
四態仍然判 `missing`，`STATE_META[missing]` 是 `("無資料", "▨")`。
**畫面會對一個沒人叫過的區塊說「無資料」——那句話本身就是假的**（不是沒有資料，是沒有人去要）。

### 1.2 我補的、比盤點組更硬的理由：`StationSpec` 是**編寫期**的靜態註冊表

`wired` / `discriminative` / `emits_level` 三個旗標**全部住在 `@dataclass(frozen=True) StationSpec` 裡**，
而 `StationSpec` 的實例是 module-level 常數註冊表（`SPECS_BY_KEY`）——它們是**寫程式的人在編寫時
就宣告好的事實**（這盞燈有沒有接線、門檻還準不準），一個 session 內永遠不變。

`requested` 是**執行期、每個 session 各不相同、每次 rerun 都可能改變**的狀態。

**把 `requested` 放進 `StationSpec` 是 category error**（frozen dataclass 裝不下 session state）；
放進 `classify_state` 的參數又會讓「一個純規格判定函式」開始吃 session 狀態。
**兩條軸不只是語意上正交，它們的生命週期與擁有者都不同。** 這是我認為建獨立模組**最不可繞過**的理由。

### 1.3 有沒有更簡單而不出錯的做法？

我考慮過三種，全部否決，理由如下（§-1.5 第三條「邏輯審查」要求寫出來）：

1. **不建模組，各處自己 `if requested and not data:`** — 這正是現況（S-4.1~S-4.6 五處各寫各的，
   兩個 repo 還各自獨立長出同一個 bug）。**否決**：沒有 SSOT 就沒有守衛，第三次一定再長出來。
2. **擴充 `classify_state` 加 `requested` 參數** — 技術可行，但會讓 12 個既有 caller
   （`dividend_station` / `station_charts` / `dividend_station_service` / 4 個測試檔）全部要處理一個
   它們根本沒有的輸入，且違反 1.2 的生命週期分離。**否決**。
3. **只改文案不建模型** — 能修掉這五處，但**擋不住下一處**。S-4.6 與 Fund 的 `freshness.py`
   逐字同型、兩 repo 獨立長出，證明它是**模式**不是個案（見 §4）。**否決**。

---

## §2. L0 模型：`shared/ui_state.py`

**位置**：`shared/`（L0 Shared）。純函式、零 I/O、零 streamlit，由測試 `test_l0_purity` 釘住。
**為什麼是這裡而不是 `src/compute/`**：它被 L3 UI 與（未來）L2 同時使用，而 §8.2 規定
L0 是「被全層 import 的基底」。旁邊就有同性質的先例：`shared/station_specs.py`
（四態）、`shared/macro_buckets.py`（chips 三態）。

**七態**：`unwired / idle / loading / failed / empty / degraded / live`
**判定順序**：`unwired → idle → loading → failed → empty(→failed) → degraded → live`
**`idle` 排在 `error` 之前**的理由：Streamlit 每次 rerun 重跑整頁，session 常躺著上一輪的
錯誤字串；先判 error 會讓「已重置、還沒重新載入」的區塊亮紅燈 —— 那正是 v3 §02
前半句要杜絕的假性錯誤。（原始碼順序另有測試 `test_idle_beats_error` 釘住。）

**顏色只新增一個**：`failed` 紅。`idle`/`loading`/`empty`/`unwired` 共用既有
`TRAFFIC_NEUTRAL` 一個灰，靠 glyph 分辨（`test_grey_states_share_one_hex_and_differ_by_glyph`）。

**`FAILED_REASONS = {MISS_FETCH_FAILED, MISS_CONTRACT_DRIFT}`**：只有這兩個缺值原因
會把 `empty` 升級成紅。理由：這兩者的 `MISS_TEXT` 指向「系統壞了、去看錯誤／去修程式」；
其餘四個（`no_input`/`not_enough`/`n/a`/`no_variation`）指向「等一等，這是資料本身的性質」
—— 標紅就變成假性錯誤。缺值語彙**沿用 `station_specs` 的 `MISS_*`，不另立第二套**（§2 SSOT）。

**矛盾即炸**：`requested=False` 卻帶 `has_value` / `error` / `in_flight` → `ValueError`（§1）。

---

## §3. 五處的處置（行號自行重新定位；**S-4.3 我實地追過，它是真的**）

| 代號 | 位置（檔案::符號） | 實況複查 | 處置 |
|---|---|---|---|
| **S-4.1** | `macro/handlers.py::_render_traffic_light` 的 `_blocked` 分支 | ✅ 確認。走到這裡的前提是 `tl is not None` = 燈號已算過 = 使用者按過了。原本無條件印藍字「👉 請點上方『🚀 一鍵更新全部數據』…」 | 加 `requested` 參數（`None` → 讀 `chips_loaded`/`cl_ts` gate 旗標）。已請求 → **紅字 + 「重按更新對這個原因無效」** 反轉指引；未請求 → 灰色閒置文案。**沒有增刪任何視覺元件**，紅色本來就已存在於本卡（缺項列 + 信心%） |
| **S-4.2** | `macro/section_long.py` 全球資金流向 | ✅ 確認。分流是對的（吃 `_load_heavy`），真失敗那一支用 `st.info`（藍底） | 改走 `classify_ui_state`；idle → `st.caption` 灰；failed → `st.warning` 橘。**刻意不用紅**：yfinance 限流是暫時性、稍後重試真的會好，紅色在本站語意是「重試無效」 |
| **S-4.3** | `macro/section_state.py::render_section_state` 的 `elif not cd:` | ✅ **存在，而且可達 —— 我把踩點組標為「推導、未實測」的那條路徑追出來了**，證據見下方 §3.1 | 加 `requested`（同 gate 旗標）；已請求 → `st.error('🔴 大盤資料取得失敗…')` + `MISS_FETCH_FAILED`；未請求 → 灰 caption |
| **S-4.4** | `tabs/hot_money.py::render_hot_money_section` | ✅ 確認。文案自白「caller **應該**已抓」= 它自己承認分不出來 | 簽名加 `requested` / `fx_error`，由 caller 帶下來。三分支：idle 灰／contract-drift 紅／其餘橘。唯一 production caller 是 `section_state.py`（我的檔），已同步傳入 |
| **S-4.6** | `pages/sidebar_health.py::render_sidebar_data_health` | ✅ 確認。`if not _lines:` 無條件說「尚未載入」 | 兩個 domain 各自從 **session key 的存在**取 `requested`；有 failed → 紅、有 tried → ▨、都沒有 → 灰**且措辭保留歧義**（見 §4） |

### 3.1 S-4.3 的可達性證明（踩點組沒做這一步，我做了）

`tab_macro.py` 的實際寫入順序：

1. `if do_refresh:` → **第一時間**就 `st.session_state['chips_loaded'] = True`
   **並且** `st.session_state.pop('cl_data', None)`（先設旗標、先清舊值）；
2. 接著呼叫 `fetch_macro_bundle(...)` —— **該呼叫沒有 try/except 包住**
   （實測：從 `if do_refresh:` 到寫回 `cl_data` 之間，唯一的 `with` 是 `st.spinner`）；
3. 它一旦拋例外 → `st.session_state['cl_data'] = dict(...)` 這一行永遠跑不到；
4. 下一次 rerun：`do_refresh` 已是 False，但 `chips_loaded` 仍是 True →
   `_load_heavy = bool(do_refresh) or bool(chips_loaded)` 為 True →
   **通過閘門、卻整段跳過抓取區塊** → `cd = st.session_state.get('cl_data', {})` 是空的；
5. `mkt_info` 也在 `_macro_session_reset()` 被 pop → `_mkt_info` 為假；
6. → 落進 `elif not cd:` → 畫面說「**請點擊載入**」。

**使用者按了、炸了，畫面叫他再按一次。** 這條路徑是真的。

---

## §4. 怎麼讓 S-4.6 那個模式**不會第三次長出來**

S-4.6 與 Fund 端 `ui/helpers/io/freshness.py` 逐字同型、兩個 repo 獨立長出。
會重複發生，是因為「**蒐集成 list → 用 list 空不空當狀態**」是寫聚合器時**最自然的寫法**：
`if not <蒐集到的東西>:` 天生分不出「沒去蒐集」與「蒐集了但一無所獲」。
**光把這一處的文案改對，擋不住第三次。** 所以防線放在三個層次：

1. **結構層（拿不到狀態，除非先回答）** —— `classify_ui_state` 的 `requested` 是
   **必填的 keyword-only 參數、沒有預設值**。沒有任何簽名可以只餵資料就拿到狀態。
   守衛：`_signature_has_required_requested()` + `test_requested_is_required_keyword_only`。
2. **執行期（矛盾即炸，§1 Fail Loud）** —— `requested=False` 卻帶著值／錯誤／in_flight
   → `ValueError`，訊息直接點名兩個常見成因（把上輪殘留當本輪事實／`requested` 從資料反推）。
3. **CI 守衛（把鐵律編碼成可執行檢查）** —— `TestNoDerivedRequested` 用 AST 掃**全 repo**：
   - 每個 `classify_ui_state(` 呼叫**必須**傳 `requested=`；
   - `requested=` 綁的運算式**不得與 `has_value=` 綁的相同** ——
     那個簽名（同一個運算式同時當「有沒有被叫過」與「有沒有值」）**正是 S-4.6 的本體**。
   - 另釘 production 呼叫點 `>= 5`，避免有人把接線默默拆掉。

⚠️ **誠實揭露第 3 條的極限**：它比對 AST 結構是否相同，抓得到
`requested=bool(x), has_value=bool(x)` 這種直接同源，**抓不到**語意等價但寫法不同的
（`requested=len(x)>0` 配 `has_value=bool(x)`）。**它是護欄不是證明。**

**另外**：S-4.6 修完後的「三個 domain 都沒留下請求痕跡」那一支，措辭**刻意保留歧義**。
理由：個股那條路徑若在寫 `t2_data` 之前就拋例外，`sidebar_health` 從外面看起來
與「從沒載過」**一模一樣，本函式無法分辨**。與其斷言一個查不到的事實，
不如講一句在兩種情況下都為真的話，並指出去哪裡確認（§1：錯的敘述比沒有敘述更危險）。
`_macro_compass_cache` 那一格則**沒有這個歧義** —— `render_macro_compass._do_fetch()`
在 try/except **之後**無條件寫入該 key（成功寫 `data`、失敗寫 `_err`），
所以 key 存在 = 按鈕按過了。兩格的訊號品質不同，文案就據實寫成不同。

---

## §5. 突變測試（原始輸出見交付報告）

| 突變 | 做法 | 結果 |
|---|---|---|
| (a) 拿掉 `requested` 參數 | 從簽名移除，改由 `has_value or error or in_flight` 推導 | **15 failed / 15 passed** |
| (b) `idle` 改由 `if not data:` 推導 | 簽名保留 `requested`，把第 2 順位換成 `if not has_value and not error:` | **9 failed / 21 passed** |
| (c) S-4.1 錯誤指引放回去 | 把紅字換回「👉 請點上方…載入完整資料後，燈號才會顯示」 | **1 failed / 29 passed** |

三次都在還原後回到 **30 passed**。

---

## §6. 明確**沒有**做的事

- **W1~W5 五項需線框的一律沒碰**：冷啟動置底常駐灰條（S-1b.1）、Fund Tab4 空狀態卡、
  **總經 v2 狀態欄加紅色態（W3）**、全站 `st.info` 改自繪灰卡、標題狀態徽章。
  ⚠️ **W3 完全沒碰** —— 它會動到 user 2026-08-26「燈欄維持純文字、視覺重心留給核心結論」
  的裁示，`macro_v2_cards.py` / `tab_macro_v2.py` / `station_cards.py` **一個字都沒改**。
- **基金端一個字都沒改。** 模型先在 stock 驗證過再移植。
- **沒有改任何門檻數值、沒有刪任何檔案。**
- **第 3 類（S-3.1~S-3.5）一處都沒動** —— 本次任務範圍是第 4 類。

---

## §7. 順帶發現、但**刻意沒修**的東西（§-1.5.3 C 禁止夾帶）

寫進報告當資訊，不夾帶進本次改動：

1. `src/ui/tabs/macro/section_long.py` 的 OTC 區塊有一處 `except Exception: pass`
   —— 憲法 §3.3「`except: pass` 一律違憲」。**在我的檔案裡，但不在我的任務範圍**，未動。
2. `src/ui/tabs/hot_money.py` 還有兩處同族的第 4 類：
   `st.info("無法取得外資資料；請確認 FINMIND_TOKEN 與網路。")` 與
   `st.info("外資與匯率資料沒有重疊的交易日（區間太短？）。")`
   —— 都是**真失敗印藍底**，與 S-4.2 同病。**踩點組沒列**，我也沒改（不在指派清單內）。
3. `handlers.py` 的 `tl is None` 分支（S-3.2，「系統正在深度解析…請稍候」＋
   「首次使用請點擊」**自我矛盾**）**未動** —— 那是第 3 類。
4. `tests/test_macro_classroom.py::test_explainer_after_traffic_light_render` 用
   「字元距離 < 500」當版面順序守衛。HEAD 基線 471，我加 ` requested=_requested`
   後為 **493，只剩 7 字元餘裕**。已在 `section_state.py` 就地寫警告註解。
   **我沒有去放寬那條測試的門檻** —— 改測試門檻來讓自己的 diff 過關，
   正是這份憲法要擋的東西。

---

## §8. 與踩點組規格不符之處

| # | 規格寫的 | 實際 | 影響 |
|---|---|---|---|
| 1 | 函式名 `pick_miss_reason` | 實際是 **`most_fundamental_miss`**（`shared/station_specs.py`） | 只是名字錯，**論證本身不受影響**（我按實際實作重新驗過一次，結論相同） |
| 2 | S-4.3「這條路徑我沒有實測到，屬推導」 | **實地追出可達路徑**（§3.1）：`chips_loaded` 先設、`cl_data` 先 pop、`fetch_macro_bundle` 無 try 包 → 例外後下一輪必然落進該分支 | 從「可能不存在」升級為「確定存在」，該修 |
| 3 | 規格未提 `classify_state` 的 `reason` 參數 | `classify_state(spec, *, has_value, reason=None)` 的 **`reason` 從頭到尾沒被讀過**（函式體只碰 `spec.wired`/`has_value`/`spec.discriminative`） | **強化**了「不能塞 `MISS_NOT_REQUESTED`」的論證：就算塞了，四態仍判 `missing`、畫面仍印「無資料」 |
| 4 | 規格未提 `StationSpec` 的性質 | 它是 `@dataclass(frozen=True)` 的 **module-level 靜態註冊表**（編寫期事實），而 `requested` 是**執行期 session 狀態** | 新增一條規格沒有的、更硬的分離理由（生命週期與擁有者都不同） |
| 5 | S-4.1 建議文案「`<缺的來源>` 取得失敗」 | 改寫成「**上列**來源取得失敗」 | 缺項清單就印在同一張卡的正上方，再重複一次來源名會與該列打架；指向「上列」更精準 |
| 6 | 規格說 S-4.2 應改 `st.warning`（橘） | 照做，**但補寫了理由**：限流可自癒 → 標紅會製造 v3 §02 前半句要杜絕的假性錯誤 | 無分歧，只是把理由寫進 code |

---

## §9. 過程中的一個操作失誤（據實揭露）

為了判斷 `hot_money.py` 的 ruff `E402` 是不是我造成的，我用了
`git stash push --keep-index --include-untracked` + `git stash pop` 來取得乾淨樹比對。
**這在「同 repo 另有三組 agent 正在寫入」的情況下是不該做的** ——
那兩秒的窗口內若有別組寫檔，pop 可能撞上衝突。

**實際結果：沒有造成損害**（已查證：`git stash list` 為空、pop 無衝突、
其他組的 11 個修改檔全部在位、我的檔案測試全綠）。
但**方法本身是錯的**，正確做法是 `git show HEAD:<path>` 讀單檔（我在別處都是這樣做的）。
記在這裡是因為「沒出事」不等於「做對了」。

（順帶查證：`E402` 是 **HEAD 就有的**，位置在同一行 import，只是被我新增的 3 行 import
往下推了 3 行。不是我造成的。）
