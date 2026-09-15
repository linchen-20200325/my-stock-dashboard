# 【S1-4 元件狀態矩陣】獨立紅隊稽核報告

> **稽核組**：狀態矩陣紅隊組（QA/Audit），唯讀。
> **對象**：`scratchpad/S1-4_STATE_MATRIX.md`（1,088 行，交付日 2026-09-14）
> **依據**：`CLAUDE.md §-1.5` 第一條 3「實作與稽核嚴格分離」＋ §-2 規則 3/4/6
> **repo 變更**：**零**。本組未修改 repo 任何檔案、未執行任何 git 寫入。
> **方法聲明**：下列每一條都**重新回到 code 查證**，不接受「那份文件說…」當證據。
> 本組**未**跑起 Streamlit、**未**看過實際畫面；全部結論來自讀 code 與 grep。

**一句話總評**：**七條承重宣稱有六條成立（一條部分成立），line:符號 引用的準確度高得罕見**
—— 這份規格的**事實層是可信的**。問題全部出在**從事實推導出來的矩陣本身**：
§3 的六張表裡，本組找到 **5 處會在實作當天就 `raise` 或不可執行**、
**4 處缺格**、**3 處規格自己違反自己寫的鐵律**。
**最嚴重的一條**：§3.1 大卡片表十行裡有**五行**要求把 `—` / `N/A` 放進大字數值區，
而該表自己在兩節前引用的 `Card.__post_init__`（`tab_today.py:237-240`）**會對這五行直接 `raise ValueError`**
—— 照著寫的結果，正是這份文件自己列為 R-12(b) 的「整頁未捕捉例外、半截死頁」。

---

## §1. 七條承重宣稱的重驗結果

| # | 宣稱 | 結論 | 本組查到的證據（`file:line` + 原文） |
|---|---|---|---|
| **1** | 基金站狀態模型檔頭自稱「顏色五態 SSOT」，不是三態 | ✅ **成立** | `/home/user/linchen-20200325/my-fund-dashboard/ui/helpers/render_state.py:1`：`"""顏色五態 SSOT —— 「系統真紅燈」與「業務紅燈」嚴格分離。`　`:3`：`客戶 2026-08-28 拍板（線框 ... §03「顏色：三態統一規則」）`　`:19-27` 是一張**五列**的「五態對照」表。四個 helper 錨點也全對：`NOT_APPLICABLE_MARK` `:104`、`not_ready()` `:112`、`system_error()` `:134`、`business_alert()` `:216`、破壞性提醒走 `st.warning()`（`:26` 表列，無 helper）。**「條款叫三態、模型是五態」的區分是對的。** 附帶佐證：`grep -rn BUSINESS_ALERT` 在台股 repo **0 命中** → §1.4「台股站無對應」成立 |
| **2** | 值級語彙有兩套；漏了翻譯表 `out_of_range` / `no_extraction` 永不升紅；us10y 真實事故 | ✅ **兩半都成立** | (a) `shared/station_specs.py` `MISS_NO_INPUT:457` `MISS_FETCH_FAILED:458` `MISS_NOT_ENOUGH:459` `MISS_NOT_APPLICABLE:471` `MISS_CONTRACT_DRIFT:477` `MISS_NO_VARIATION:495`（6 種，行號**逐一對上**）；`shared/macro_buckets.py` `MISSING_NOT_LOADED:241` `MISSING_NO_VALUE:244` `MISSING_OUT_OF_RANGE:247` `MISSING_NOT_WIRED:253` `MISSING_NO_EXTRACTION:256`（5 種，**全對**）。(b) `page_today.py:388-394` `READINESS_REASON_TO_MISS` 五條對映與規格 §1.3(b) 表**逐格相同**；`shared/ui_state.py:130` `FAILED_REASONS = frozenset({MISS_FETCH_FAILED, MISS_CONTRACT_DRIFT})`，`:208` `return UI_FAILED if reason in FAILED_REASONS else UI_EMPTY` —— 把生語彙 `"out_of_range"` 直接餵進去，**必然落到 `UI_EMPTY`（灰）**。翻譯確實有接上：`page_today.py:877` `reason=READINESS_REASON_TO_MISS.get(_reason, "")`。(c) us10y 事故：`macro_buckets.py:256-262` 原文「`us10y` 自 v18.286 註冊、到 v19.175 才接線,中間 4 個版本永久灰燈,而上游 `fetch_us10y_block` 全程抓取成功 —— 沒有任何生產端能回報這種病」✅ |
| **3** | 同名 `fmt_value` 有兩支，缺值分別回 `—` 與 `無資料` | ✅ **成立，但嚴重低估規模** | `shared/macro_buckets.py:686-689`：`def fmt_value(value, spec)` → `if value is None: return "—"`；`src/ui/render/macro_v2_cards.py:260-262`：`def fmt_value(value, unit, decimals)` → `if value is None: return "無資料"`，且 `.replace("-", "−")`。`page_today.py:226` 匯入的是**前者** ✅（規格寫的 `:214` 不是匯入行，:214 是 `from shared.macro_buckets import (` 的區塊起點，屬小誤）。**但缺值符號的分歧不是兩支，至少九支** —— 見 §2.3 |
| **4** | `fetched_at` ≠ 歸屬日；顯式 `as_of` 全 `src/data/` 只有一個模組有 | ⚠️ **部分成立（前半成立，後半不成立）** | **前半 ✅**：`src/data/macro/leading_indicators.py:1119,1700` `df["fetched_at"] = pd.Timestamp.now('UTC').isoformat()`；`tw_macro.py:852,947,1033,1135` 同形。獨立複驗覆蓋率：`grep -rln fetched_at src/data/`（排除 `__pycache__`）＝ **18 個 `.py`**，`find src/data -name "*.py"` ＝ **53**，「18/53」✅。**後半 ❌**：本組用規格**自己標為盲點**的別名再掃一次，命中 —— `src/data/etf/etf_fetch.py:1507` docstring「`dict {'nav'...,'source'[,'data_date']}`」＋ `:1587` `_out['data_date'] = _dd`，那**就是**一個顯式的資料歸屬日欄位；另 `src/data/macro/macro_core.py:345` 明文「`date` (Timestamp):資料歸屬日(observation_date)」。→ 「只有一個模組有」**不成立**，正確說法是「只有一個模組用 `as_of` 這個**字面**」。影響見 §2.9 |
| **5** | `expected_latest_trading_day()` 看似交易日曆，`holidays=` 全 repo 無 caller 注入 | ✅ **成立，且本組補到更強的證據** | `shared/staleness.py:26-52`，docstring `:37`「休市日集合(選填)。台股春節長假等由 caller 注入;**None → 只扣週末**」，`:45` `_hol = holidays or set()`，`:46` 註解「上限 400 次防禦」。**獨立窮舉**：`grep -rn holidays --include=*.py .`（含 `tests/` `scripts/`）＝ **9 命中，全部在 `shared/staleness.py` 自己檔內**（:11,:28,:36,:42,:45,:46,:59,:70,:81），**零外部 caller**。`grep -niE "calendar\|holiday\|market_cal\|exchange" requirements.txt` ＝ **0**。**➕ 規格沒有的第三方佐證**：三支 cron 腳本自己記著同一件事 —— `scripts/push_holdings_daily.py:22` / `push_daily_signals.py:14` / `push_watchlist_signals.py:27`「⚠️ 已知限制:cron 排 Mon-Fri,**未濾 TW 國定假日**（本專案無第三方 trading calendar,見 CLAUDE.md §4.5）」。→ 「本 repo 沒有能力判盤中／盤後」是 repo 三處獨立自陳，**方案甲的裁示有充分實證支撐** |
| **6** | `rp_scalar()` 把 `last_updated` 設成 ≈ 今天（「填今天」反模式的既存實例） | ✅ **成立** | `src/compute/macro/macro_helpers.py:606` `def rp_scalar(val, cat, freq, proxy_date)`，`:609` docstring「有值（非 None）→ rows=1 + **last_updated=proxy_date（呼叫端傳入今天或總經更新時間）**」，`:612` `return {'last_updated': proxy_date, ...}`。旁證 `shared/data_categories.py:117-121`：「`rp_entry` 塞 DataFrame 最後一筆資料日期(as_of),`rp_scalar` 塞呼叫端傳入的 `proxy_date`(**≈ 今天,等於抓取時間**);… 同一欄兩種語意 ⇒ 沒有任何一組門檻對兩者都正確」✅。R-10 的 `'N/A'` 錨點也對：`:563`/`:593`（`rp_ts` 回 `'N/A'`）、`:603`/`:614`（`missing=True` 時 `'last_updated': 'N/A'`） |
| **7a** | 鐵律：`idle` 必須排在 `error` 之前 | ✅ **成立** | `shared/ui_state.py:199-211` 實際順序：`if not wired → UI_UNWIRED` / `if not requested → UI_IDLE`(`:202`) / `if in_flight → UI_LOADING` / `if error → UI_FAILED`(`:206`)。docstring `:176-181` 明文「**為什麼 `idle` 必須排在 `error` 前面（勿再對調）**：Streamlit 每次 rerun 都重跑整頁，session 裡很可能還躺著上一輪的錯誤字串」✅ |
| **7b** | 鐵律：`requested` 禁止由 `bool(data)` 推導 | ✅ **成立，但規格替它加的「結構保證」是錯的** | `:45-50` 原文、`:52-60` 三層守衛、`:134-135` `requested: bool` 為 keyword-only 無預設、`:190-198` 矛盾即 `raise`、`:242-251` `_signature_has_required_requested()` 突變守衛，全部對上 ✅。**但**規格 §1.5 規則 4 末句寫「**結構上的保證**：`classify_ui_state` 在 `requested=False` 時…會直接 `raise ValueError`」—— `page_today.py:66-68`（**規格自稱讀過的 60-100 行區間**）原文：「⚠️ 更強的一道：`requested` 為 False 時**根本不呼叫**五桶計算 —— 沒有輸入就不會有 `state=="ok"` 的紀錄，`classify_ui_state` 那條「沒被叫過卻有值 → `ValueError`」的 fail-loud **在結構上就跑不到**。」→ 規格把一條**已被 code 註記為跑不到**的防線寫成「結構上的保證」。**這是唯一一處我認為規格在事實層說了不成立的話。** |

**§1 小結**：7 條裡 **5 條全成立、1 條成立且被本組補強（#5）、1 條部分成立（#4 後半不成立）**，
另在 #7b 抓到一句「結構保證」不成立。
規格的 `file:line` 引用準確度本組抽驗約 45 個錨點，**只有 3 個不準**（§0.2(3) 的 `:214`、
§3.3/§3.5 的 `page_hold.py:3646`、§3.3 的「13 處」）—— 詳見 §2.10。

---

## §2. 它漏掉的 / 它自己違反自己的

> 排序 = 嚴重度。**2.1 ~ 2.4 是「照著寫會當場壞掉」**，2.5 ~ 2.8 是「照著寫會寫出它自己禁止的畫面」，
> 2.9 ~ 2.11 是精確度問題。

### 2.1 🔴 **§3.1 大卡片表有五行會直接 `raise ValueError`（規格違反自己的 C-4）**

**規格怎麼寫的**（§3.1 表，「大字數值區」欄）：

| 行 | 規格要求大字數值區放什麼 |
|---|---|
| Empty | **`—`**（灰 ＋ ⚠︎） |
| Missing | **`—`**（灰 ＋ ⚠︎） |
| N/A（unwired） | **`N/A`**（灰，不加 ⚠︎） |
| N/A（值級 `MISS_NOT_APPLICABLE`） | **`N/A`** |
| Error | **`—`**（灰 ＋ ⚠︎） |

**code 怎麼寫的**（`src/ui/tabs/tab_today.py:229-240`，逐字）：

```
229:     #: 正常態才准有的結論文字。非 `live` 一律為空。
230:     value: str = ""
...
237:         if self.state != UI_LIVE and self.value:
238:             raise ValueError(
239:                 f"卡 {self.key!r} 不是正常態卻帶了結論文字 {self.value!r} —— "
240:                 "只有 live 能給結論（線框 §02：只有這一態能給結論文字）")
```

而 `src/ui/views/_ui_kit.py:292-294` 的大字數值區就是從 `card.value` 畫出來的：
`f'<div style="font-size:24px;font-weight:700;...">{_html.escape(card.value)}</div>' if card.value else ""`。

**判定**：`"—"` 與 `"N/A"` 都是 truthy 字串，`if self.value:` 一律成立 →
上表五行**每一行**在建構 `Card` 的當下就 `raise ValueError`。

**為什麼這是最嚴重的一條**：
1. 規格**自己**在兩節前把這條守衛列為 **鐵律 C-4**，引用的還是**同一段行號**（`tab_today.py:232–243`）。
   → **規格違反自己寫的鐵律，而且是在同一份文件裡隔 1.5 頁。**
2. 規格**有一格做對了**：Partial-B 那行寫「值掛 `facts` 的「現值」列，**大字區留空**（C-4 規定非 live 不得帶結論文字）」
   —— 證明作者知道這條規則存在，只是**只在 `degraded` 一格套用，漏了其餘五格**。
3. 後果不是「畫得不好看」：`Card` 建構期拋出的 `ValueError` 會一路穿上去，
   正是規格自己在 **R-12(b)** 寫的「**把一張該畫出來的紅卡變成整頁未捕捉例外**」。
   **照著 §3.1 寫，會重現 §5 R-12。**

**規格沒有回答、但實作當天一定要有答案的問題**：`—` 與 `N/A` 到底放哪裡？
（候選：`facts` 的某一列／`Note.now`／放寬 `Card.value` 的守衛／新增 `Card.placeholder` 欄位）
—— **這四條路的分層後果完全不同**（最後兩條會動到 L5 既有 dataclass 契約，須走 §8.1 架構踩點）。
**規格對此一字未提。**

### 2.2 🔴 **§3.7 主 CTA 的九行裡有六行違反它自己的規則 3，而且會 `raise`**

**規格 §3.7 規則 3**：「按鈕文字走 `shared/ia_nav.py:103` `action_label()`，**禁止手抄**」。
**規格 §3.7 表**要求九種狀態各自的按鈕文字：「重新更新」/「更新中…」/「🚀 一鍵更新全部數據」/
「換個條件再試」/「再抓一次」/「補抓缺漏的 M−N 筆」/「再試一次」。

**實測 `shared/ia_nav.py:80-85`**：

```
80: ACTION_UPDATE_TODAY: str = "update_today"
82: ACTION_LABELS: dict[str, str] = {
83:     ACTION_UPDATE_TODAY: "🚀 更新今日戰情",
84: }
```

`action_label()`（`:103-108`）對未知 id **fail loud**：
`raise ValueError(f"未知的動作 id {action!r}；合法值：{sorted(ACTION_LABELS)}")`。

**三個獨立問題**：
1. SSOT 裡**只有一個 label**，規格要七個 → 照規則 3 走，六行 `raise`。
2. 規格舉的兩個「例」（「重新更新」「🚀 一鍵更新全部數據」）**都不是** SSOT 裡那一個字串（「🚀 更新今日戰情」）
   —— 規格在示範「手抄」，而它自己剛禁止手抄。
3. **「停用」做不到**：`_ui_kit.py:378-420` `single_submit_form()` 的簽名裡**沒有 `disabled` 參數**，
   `:412` 是 `st.form_submit_button(submit_label, type="primary")`，**無條件可按**。
   而規格表兩行要求停用（Loading、Error+contract_drift），§3.7 規則 4 更把停用做成 `reason` 的函式。
   → **規格 §3.7 的核心機制在現行唯一表單入口上不存在**，卻寫成「現行實作：`_ui_kit.py:378`」。

**這一條要的不是改文案，是改 L0 `ia_nav.ACTION_LABELS` ＋ 改 `_ui_kit` 的函式簽名。**
規格把它呈現成「照著填表」，實作組會在第一天撞牆。

### 2.3 🟠 **缺值符號的分歧不是「兩支 `fmt_value`」，至少九支；其中一支會印出字面 `"None"`**

規格 §5 R-11 把這件事描述為「**兩支**同名 `fmt_value`」，並在 §2.3 B 下結論「新頁一律走 `macro_buckets.fmt_value`」。
**本組獨立掃描 `src/ui/views/` + `src/ui/render/`**，同一個「缺值怎麼印」的決定散在至少九處：

| 位置 | 缺值時回什麼 |
|---|---|
| `shared/macro_buckets.py:689` | `"—"` |
| `src/ui/render/macro_v2_cards.py:261` | `"無資料"` |
| `src/ui/views/page_find.py:1163` | `"—"` |
| `src/ui/views/page_hold.py:1361` | `"—"` |
| `src/ui/views/page_hold.py:3719` | `"—"` |
| `src/ui/views/page_inspect.py:1562` | `"—"` |
| `src/ui/views/page_inspect.py:1567` | `"—"` |
| `src/ui/views/page_inspect.py:1835` | `"—"` |
| `src/ui/render/unified_verdict_render.py:38` | 🔴 **沒有 None 分支** |

最後一支值得單獨講：

```
38: def _fmt_value(val) -> str:
39:     """軸原值格式化:float→2 位、其餘→str(grade/int 原樣)。"""
40:     if isinstance(val, float):
41:         return f'{val:.2f}'
42:     return str(val)
```

`val is None` 時走 `str(None)` → 畫面上會出現**字面的 `None` 四個字元**。
而同檔 `:31` 註解自陳「軸沒有值時 `axis['state']` 是 None」——**軸可以沒有值**。
⚠️【本組未複驗】`a["value"]` 是否真的會是 `None` 我**沒有追到上游**，
故只能說「這支缺 None 分支」，不能說「production 會印出 None」。

**對規格的影響**：§2.3 B 的規則「新頁一律用 `macro_buckets.fmt_value`」**不可執行** ——
它的簽名是 `fmt_value(value, spec: DangerSpec)`，而 `DangerSpec`（`macro_buckets.py:~195-233`）
是**五桶總經危險門檻註冊表**專屬的 dataclass（帶 `yellow_lo` / `red_lo` / `valid_min` / `wired` /
`discriminative` 等總經欄位）。**§3.3 的持股／個股資料表、§3.5 的清單列，沒有也不該有 `DangerSpec`。**
→ 規格在「缺值符號最容易漂移的兩個元件」上，給了一條它們用不了的規則。
**真正該做的是抽一支不綁 spec 的 L0 格式化函式**，規格對此未提。

### 2.4 🟠 **Loading：六張表都有一行，但 `UI_LOADING` 在 `src/` 是零 production 使用**

**實測**：`grep -rn --include=*.py "UI_LOADING\|in_flight" src/ app.py` →
**唯一命中是 `src/ui/views/_ui_kit.py:10` 的 docstring 列舉**。
`grep -rn "st.spinner" src/ui/views/` → **1 處**（`page_find.py:1628`）。
即：**沒有任何 production 路徑會產生 `UI_LOADING`，也沒有任何 caller 傳 `in_flight=True`。**

規格卻在 §3.1 / §3.2 / §3.3.2 / §3.3.3 / §3.4 / §3.5 / §3.6 / §3.7 **八個地方**各給了一行 Loading，
且寫得很具體（「骨架列（固定列高，避免版面跳動）」「3 張骨架卡（固定高）」「固定高骨架框 `CHART_HEIGHT=210`」
「留空（**不留上一輪殘值**）」），**全部未標為新建**。

對照：規格對「表格轉卡片流」**有**誠實標記（§3.3.3「🧠【判斷】…**這是要新寫的東西**，下列為規格，不是現況描述」）。
→ **標記標準不一致**：最小的新建項標了，最大的新建項（跨八個元件的 loading 骨架系統）沒標。

⚠️ 另有一個 Streamlit 模型層面的問題規格沒回答：
Streamlit 一次 rerun 從頭跑到尾、畫面只在結束時刷新，**阻塞取數期間留在螢幕上的是上一幀**。
規格 §3.1 Loading 行寫「大字數值區**留空**（不留上一輪殘值）」——
**沒有 placeholder／`st.empty()` 機制的話，這句話在 Streamlit 上做不到。**
規格全篇 `grep` 無 `st.empty` / placeholder / fragment 字樣。

### 2.5 🟠 **§3.4 的矩陣讓「契約漂移」掉進 📭 灰態的縫裡 —— 規格自己的 E-9 / R-14 抓不到它**

規格 §3.4.1 把整張圖的分支寫成：「`miss_fn(series)` 回**非空 `MISS_*`** → 不畫圖，印原因收工」，
然後 §3.4 表把 Empty／Missing 配成 `st.info(miss_text, icon="📭")`（灰），
**Error 行只寫「不畫圖，印「這張圖畫不出來（`<ExcType>`）」」**。

**實測 `src/ui/render/station_charts.py:329-352`**：

```
337:     _r = miss_fn(series)
338:     if _r:
339:         st.info(miss_text_for(_r), icon="📭")
340:         return
...
350:     except Exception as e:
352:         st.caption(f"這張圖畫不出來（{type(e).__name__}）—— 不以空圖或合成序列充數。")
```

而 `weekly_ma_miss_reason()`（`:334-348`）**會回 `SS.MISS_CONTRACT_DRIFT`**：
`:337` `if not _payload_ok(series): return SS.MISS_CONTRACT_DRIFT`，
`:346-348` 「`miss_reason` 為空 = L3 宣稱有序列。此時週收卻是空的 → **契約漂移**，不是缺資料。」

→ **契約漂移在圖表上走的是 `st.info(📭)` 這條灰路**，不是 Error 那條紅路。
而規格自己在 **E-9**（「畫成一般灰態 ⇒ 實例是 `us10y` 永久灰燈」）和 **R-14**（「最毒的一種」）
兩處把這件事定為必須升紅。
**§3.4 的八行表裡，沒有任何一行告訴實作者「`miss_fn` 回 `contract_drift` 時要升紅」** ——
Error 行講的是 `except`，Empty/Missing 行講的是灰。**這是一個真正的缺格，而且缺在規格自己最在意的那一格上。**

### 2.6 🟠 **§3.2 燈號徽章：把四種不同的東西畫成同一個「空格＋虛線框」**

規格 §3.2 表給 **Empty / Missing / Error** 三行都配「**空格 ＋ 虛線框**」。
而 `src/ui/render/station_cards.py:122-131` 的 `LEVEL_STYLES` 裡，
**`dashed=True` 只有一個鍵**：`LEVEL_UNJUDGED`（空字串 `""`）。
同檔 `:216-218` 明文：

> 「無資料」= 這輪沒取到值(等 / 重跑就會有);
> 「未判定」= L2 從來沒有為這盞燈判過等級(**重跑一百次也不會有等級**)。

→ 照 §3.2 實作，**Empty（等一等就有）／Missing（重抓就有）／Error（程式要修）／未判定（永遠不會有）
四件處置完全不同的事，在格子牆上長得一模一樣**。
規格自己在**同一節下方兩段**把那條「無資料 ≠ 未判定」原文引了出來，
卻沒發現自己上方那張表把它們合成了一個畫法。

另外 `station_cards.py:552-557` 對不認得的 level **fail loud**
（`if cell.level not in LEVEL_STYLES: raise ...「新增判定符號時必須同時決定它怎麼畫」`）
→ §3.2 的 Loading／未載入／N/A 三行若要各自不同的畫法，**必須先擴 `LEVEL_STYLES`**，規格未提。

**另一個自我衝突**：§3.0 前言寫「在讀下面任何一張表之前，先讀這五條…**每一格都受這五條拘束**」，
C-3 是「訊號頻道**只出中文、禁出 emoji**」；§3.2 Normal 行卻寫「判定符號原樣搬運（🔴／🟡／🟢／⚪／💰／✅／❌／❔）」。
實測 `_ui_kit.py:112-116`：`_BANNED_SIGNAL_GLYPHS = 狀態 glyph ∪ LEVEL_EMOJI.values()`，
而 `macro_buckets.py:40` `LEVEL_EMOJI = {"green":"🟢","yellow":"🟡","red":"🔴","gray":"⬜"}`
→ §3.2 Normal 行要輸出的符號裡有**三個在禁用集合內**。
code 層面兩者不衝突（C-3 的射程其實只有 `render_card(signal_text=)` 這一條字串通道，
格子牆走的是另一條 `LEVEL_STYLES` 路徑），**但規格把 C-3 的射程寫成「每一格」，就製造了一個假衝突**。
→ **C-3 缺一句 scope 限定**，實作組會在這裡吵一輪。

### 2.7 🟠 **`N/A` 這四個字元在 L3 與呈現層語意相反 —— 而規格引用的正是那一段 code**

規格 §2.1 / §2.2 把 `N/A` 釘死為「**本來就不該存在**」（結構上不適用，使用者什麼都不用做）。
規格 §3.3.1 又引用 `page_inspect.py:1149-1152` 當作「一格壞不染整表」的既有裁定。

**但那段 code 裡的 `N/A` 是反過來的意思。** 實測 `src/ui/views/page_inspect.py:1058-1060`：

```
1058: #: L3 用來表達「這一格算不出來」的字面。`"N/A"` 是 L3 明文寫的
1059: #: （`Status: "N/A" if _bad_om else ...`）；`""` / `None` 是欄位根本不存在。
1060: _MISSING_STATUSES: frozenset[str] = frozenset({"", "N/A", "None", "none"})
```

以及 `:1152` 的邊界 (d)：「**某一格的 Status 是 `N/A`** → **只有那一格** `empty`」。

→ L3 的 `"N/A"` ＝「**算不出來**」，被歸成 `empty`，也就是規格 §2.2 的 **`—` 那一桶**。
若實作者照 §2.2 決策樹，看到 L3 回 `Status="N/A"` 就印成灰字 `N/A`、**不加 ⚠︎**，
使用者得到的訊息是「這個概念本來就不該有」——
**那正是規格 §2.1 自己寫的「把 `—` 寫成 `N/A` ⇒ 使用者以為這是設計如此，永遠不會去修」。**

**規格照抄了那段 code 的結論（逐格獨立判態），卻沒有攔下那段 code 裡的字面陷阱。**
§2 需要補一條：**「上游回傳的字串 `"N/A"` 不得直接當呈現層的 `N/A`」**，
並指名 `_MISSING_STATUSES` 這個既有落點。

### 2.8 🟡 **J-3（琥珀色用 `TRAFFIC_YELLOW`）有三個問題**

1. **一色兩義**：`shared/ui_state.py:118` `UI_DEGRADED: ("門檻已失準", "🟠", TRAFFIC_YELLOW)`
   —— `TRAFFIC_YELLOW`（`shared/colors.py:22` `#eab308`）**已經是 Partial-B 的狀態色**。
   J-3 要把同一個 hex 再指派給「缺漏警示圖示」。
   → 畫面上「黃 ＝ 門檻失準」與「黃 ＝ 這格缺資料」同時成立，
   這正是規格 §5 **R-11** 的鏡像（R-11 是一個概念兩種符號；這是一個符號兩種概念，**同樣讓規則失去資訊量**）。
2. **違反自己的 C-2**：§3.0 C-2 寫「**glyph / 中文 / 色碼一律取自 L0 `state_meta(state)`，元件不配色**」。
   `empty` / `failed` 的 `state_meta` 色是 `TRAFFIC_NEUTRAL` / `TRAFFIC_RED`，
   J-3 卻叫元件在這兩態下額外塗一個 `TRAFFIC_YELLOW`。**元件配色 = C-2 明文禁止。**
3. **「新增 L0 常數」這條退路在本 repo 走不通**：`shared/colors.py:1-2` 逐字 ——

   ```
   1: # ⚠️  AUTO-SYNCED FROM my-fund-dashboard/shared/ — DO NOT EDIT HERE.
   2: #    Edit fund repo's shared/colors.py, then run scripts/sync_to_stock.sh.
   ```

   且 `scripts/sync_to_stock.sh` **不在本 repo**（只存在於 `my-fund-dashboard/scripts/`）。
   → 在台股站「新增一個琥珀色票」是**跨 repo 的寫入動作**，
   對照 `CLAUDE.md §-1.5.E` **B5** 的明文警告（「不得拿姊妹 repo 的字串來統一本檔 —— 那會是一次沒有 user 裁示的跨 repo 覆寫」），
   這不是實作組可以自決的事。**規格把它寫成一個括號註記。**

   🧠【本組建議】既然 `⚠︎` 的功能只是「和 `N/A` 區分」，**不必是琥珀**：
   直接用**符號本身**做區分（`—` 帶符號、`N/A` 不帶），顏色沿用 `state_meta` 的灰即可 ——
   §2.3 C 自己就說「靠**圖示**分辨」是唯一視覺差。**零新色票、零跨 repo 動作、零 C-2 違反。**

### 2.9 🟡 **四處真正的缺格（矩陣少了本來該有的列）**

| 缺在哪 | 少了什麼 | 為什麼不是「不可能的格子」 |
|---|---|---|
| **§3.2 燈號徽章** | **沒有 Partial-A 行**（其他六張表都有） | 一盞燈的等級由多個子項彙總（3-3-3 三子項、健檢多因）；部分子項缺 = Partial-A，徽章怎麼畫沒被規範 |
| **§3.3.2 整表級** | **沒有 Partial-B 行** | 🔴 **repo 今天就有這個畫面**：`page_hold.py:3646-3653` 的門檻對照表有一欄 `"判別力": ("已失準（別照門檻讀）" if not _r.discriminative else "正常")` —— 表格裡的 degraded 不是假想 |
| **§3.3.3 手機卡片流 / §3.5 清單列** | 同上，**皆無 Partial-B 行** | 同上；且清單列是**逐列判態**，一列 degraded 另一列 live 是常態 |
| **§3.8 全域揭露列** | 表頭寫「頁面整體狀態」，只列 Normal/Loading/未載入/混合/部分不明/全部不明/Error —— **沒有 Empty / Missing / N/A / Partial 的格** | §3.8 自稱「**橫跨全部 8 種狀態的一行**」，卻只規範了其中 4 種 ＋ 3 種自創分類。**自我矛盾**：要嘛它不是橫跨 8 種，要嘛缺 4 格 |

### 2.10 🟡 **`unwired` 先於 `idle` 的優先序，全篇沒有寫**

`shared/ui_state.py:199-202` 的實際順序是 **`wired` 檢查在最前面**：

```
199:     if not wired:
200:         return UI_UNWIRED
201:     if not requested:
202:         return UI_IDLE
```

→ **一盞 `wired=False` 的燈，在冷啟動（`requested=False`）時顯示的是 ⛔ 未接線，不是 ⬜ 尚未載入。**

規格 §1.2 把「未載入」與「N/A」列成兩個平行的呈現格，§1.5 花一整節講兩者的文案必須不同，
**卻從未說明兩者同時成立時誰贏**。這在情境 (a)（冷啟動）會**立刻**發生（見 §3.1），
而一個實作者很可能直覺地寫「冷啟動 → 全部 ⬜」——那會蓋掉所有 unwired 燈的真相。
（順帶：這也是 J-1 的一個實質論據，見 §4。）

### 2.11 🟡 **三個量測數字不準（§8.2.A.0 規則 4 那一類問題）**

| 規格寫的 | 實測 | 影響 |
|---|---|---|
| §3.3「`st.dataframe(...)`（實測 `src/ui/views/` 共 **13 處**）」 | `grep -c` 的是**行數**，其中 6 行是 docstring 提及。**實際呼叫 7 處**（`page_find:1596`、`page_hold:3646,3704`、`page_why:2050,2062,2141`、`page_inspect:2492`） | 低 |
| §3.3 / §3.5「可下鑽者用 `on_select`…（`page_hold.py:3646`；另 `tab_macro_v2.py:1271`、`etf_tab_dividend_station.py:493`）」「**實測 3 處**」 | 🔴 **`page_hold.py:3646` 沒有 `on_select`**（它是門檻對照表）。全 repo `on_select` **只有 2 處**：`tab_macro_v2.py:1271`、`etf_tab_dividend_station.py:493`，而 `etf_tab_dividend_station.py:446` 自陳「**全 repo 目前只有那一處與本處用 `on_select`**」 | **中** |
| —— 由此推出的一條規格沒講的事 —— | **`src/ui/views/` 裡目前一個 `on_select` 都沒有**。§3.5 整節寫成「**現行實作模式**」，實際上在 View 層是**全新建置** | **中**：§3.5 與 §3.3.3 性質相同，但只有 §3.3.3 被誠實標為新建 |

### 2.12 🟡 **`render_note` 的固定字串會在兩種情況下說假話**

`src/ui/views/_ui_kit.py:169-173`：

```
169:     st.markdown(
170:         f"{note.now}\n\n"
171:         f"　**為什麼沒有**：{note.why}\n\n"
172:         f"　**去哪補**：{note.where}"
173:     )
```

標籤**寫死**成「為什麼沒有」。但規格：
- §3.1 **Partial-B** 行要求 `Note.why` 讀 `degraded_reason` —— 那張卡**有值**，
  畫面會印「**為什麼沒有**：這條門檻在 2020 年後已無判別力…」→ 對一張有值的卡說「沒有」。
- §3.0 **C-5**「只要有 `Note` 就畫」＋ §3.1 Normal 行「`Note` 可省；**若有則必畫**」
  → 一張 `live` 的卡帶 Note 時，同樣印「為什麼沒有」。

⚠️【本組判斷】這不是致命錯，但它是**規格層面就能避免**的文案說謊：
要嘛 §3.1 規定 degraded / live 不得帶 `Note`（與 C-5 衝突），
要嘛 `render_note` 的標籤要隨狀態變（**動到 L5 kit，須登記**）。
**規格兩條路都沒選，兩條路的成本也沒揭露。**

### 2.13 🟢 一條規格**沒寫、但值得補**的結構風險（本組新發現）

`page_today.py:877` 用的是 `READINESS_REASON_TO_MISS.get(_reason, "")` ——
**預設值是空字串**。空字串不在 `FAILED_REASONS` 裡（`ui_state.py:130`），
→ **任何未登記的 `MISSING_*` 新常數，會靜默落成灰色 `UI_EMPTY`。**

這與 `us10y` 事故**是同一個形狀**：新增一個 spec、忘了接一條線，畫面永久灰燈、沒有生產端能回報。
規格 §1.3(c) 處理了「**文案**該說什麼」（`UNKNOWN_REASON_WHY`），
但**沒有處理「狀態該是什麼」** —— 未登記原因目前一律不升紅。

🧠【本組建議】§1.3 補一條給實作組與 CI：
**「新增 `MISSING_*` 常數時必須同步 `READINESS_REASON_TO_MISS`，否則 CI 紅燈」**
（對照 `macro_buckets.py:262` 自陳 `tests/test_decision_readiness.py` 已有「新增 spec 忘了接取值即 CI 紅燈」的同族守衛 —— 這裡缺的是**翻譯表**那一半）。
⚠️【本組未複驗】我**沒有**去讀 `tests/test_decision_readiness.py`，
不知道它是否已經順帶守住翻譯表的完整性。**這條只能當待驗建議。**

---

## §3. 三個真實情境的壓力測試

> 走法：拿規格當唯一說明書，逐塊問「這一塊現在是什麼狀態、畫面上出現哪些字」。
> **答不出來的地方就是規格缺口**，逐項標出來。

### 3.1 情境 (a)｜剛打開 App，什麼都沒點，網路是通的

| 畫面區塊 | 規格能推出的狀態 | 應顯示的字 | 規格答得出來嗎 |
|---|---|---|---|
| 主 CTA 按鈕 | 「未載入(idle)」行 → `type="primary"`、全頁最醒目 | 規格例句「🚀 一鍵更新全部數據」 | ⚠️ **字錯了**。SSOT 只有「🚀 更新今日戰情」（`ia_nav.py:83`），照規則 3 走就不是那句（§2.2） |
| 全域資料時點列 | §3.8「未載入」行 | 「資料時點：**尚未載入，本頁沒有任何本輪資料**」 | ✅ **答得出來，而且答得好** |
| KPI 卡（已接線的燈） | `UI_IDLE` | chip 「⬜ 尚未載入」；`why`＝`IDLE_LIGHT_WHY`（`page_today.py:494`）；`where`＝`indicator_exit(key)`（`:499`）指向按鈕 | ✅ **答得出來**，且有既有實作可抄 |
| KPI 卡（`wired=False` 的燈） | 🔴 **規格答不出來** | 規格 §1.2 有「未載入」與「N/A」兩格，**沒說哪個贏**。code 是 `unwired` 贏（`ui_state.py:199-202`）→ 應顯示 ⛔ 未接線 ＋ `unwired_reason` ＋「永遠不會亮」 | ❌ **缺口（§2.10）**。一個沒讀過 code 的實作者會全畫成 ⬜，**把「刻意沒接」說成「還沒載入」** —— 那是 R-2 的變體 |
| KPI 卡的大字數值區 | 應留空 | — | ✅ 留空不觸發 `Card.value` 守衛 |
| KPI 卡的 `facts` 中繼列 | §3.6 硬規則 1：任何狀態都要給 | 門檻帶／出處（「這盞燈本來長什麼樣」） | ✅ 有 `_ui_kit.py:265-266` 原文撐 |
| 燈號徽章牆 | §3.2「未載入」行 → 空框、不填色 | — | ⚠️ 需要一個 `LEVEL_STYLES` 裡沒有的畫法（現行只有 `LEVEL_UNJUDGED` 的虛線）→ **要先擴 L4 常數**（§2.6） |
| 資料表／清單列 | §3.3.2「未載入」→ 不畫表頭，改畫 `Note` | Note 三要素 | ✅ |
| 圖表 | §3.4「未載入」→ 不畫圖框，畫 `Note` | Note 三要素 | ✅ |
| 展開佐證 | §3.6「未載入」→ **仍可點**，展開講「這一輪還沒有人去取」＋ 門檻帶 | ✅ | ✅ **這一格設計得很好**，是全篇少數把「缺資料時佐證更重要」講清楚的地方 |

**情境 (a) 結論**：**一個缺口（unwired vs idle 優先序）＋ 一個文案錯（CTA 字串）＋ 一個要先擴 L0/L4 的前置（徽章空框）。**
其餘答得出來。

### 3.2 情境 (b)｜點了載入，總經拿到了、個股那段 API 逾時

| 畫面區塊 | 狀態 | 應顯示的字 | 規格答得出來嗎 |
|---|---|---|---|
| 全域時點列 | §3.8「**混合**」行（總經有、個股沒有） | 「資料時點：最舊 `<日>` ～ 最新 `<日>`（逐塊不同，展開看）」 | ⚠️ **半個缺口**：個股那半**根本沒有日期**，不是「比較舊」。規格 §3.8 另有「部分源時點不明」行 —— **兩行同時成立**，規格沒說怎麼合併。實作者要自己決定 |
| 總經 KPI 卡 | `UI_LIVE` | 值 ＋ 🟢 運作中 | ✅ |
| 個股 KPI 卡 | 逾時 → `error` 有值 → `UI_FAILED` | chip「🔴 取得失敗」；`why`＝`upstream_error_why(e)`（`tab_today.py:177`，先過 `scrub_state_glyphs`）；`where`＝`EXIT_RETRY_HERE`（`page_today.py:437`） | ⚠️ **大字區規格說要印 `—`＋⚠︎ → 會 `raise`（§2.1）**。其餘 ✅ |
| 個股清單列 | §3.5「Error（整檔抓取失敗）」→ **列保留**、各格 `—`、列首標紅、整列同一個 `fetch_failed` | ✅ 這一節（「失敗的列不得從清單裡消失」）是全篇最有價值的規則之一 | ✅ |
| 個股資料表（整表逾時） | §3.3.2「Error」→ **不畫表**、紅框 ＋ 例外可展開 | ✅ | ⚠️ 與上一列**打架**：同一批個股資料，§3.3 說「不畫表」、§3.5 說「列保留」。規格沒給「什麼時候算整表失敗、什麼時候算逐列失敗」的判準 → **缺口** |
| 個股圖表 | 逾時是**例外**（不是 `miss_fn`）→ 走 `station_charts.py:350-352` | 「這張圖畫不出來（`ReadTimeout`）—— 不以空圖或合成序列充數。」 | ✅ **答得出來**，且 code 已實作 |
| 主 CTA | §3.7 Error 行「再試一次」（逾時 = `fetch_failed`，**可按**） | ⚠️ 字串不在 SSOT（§2.2）；但「逾時可按、契約漂移停用」的判準 ✅ **是對的** | ⚠️ |
| 燈號徽章（個股那幾盞） | §3.2 Error → 空格＋虛線框、徽章格不填紅 | ⚠️ 與 Empty / Missing / 未判定 **畫成同一個東西**（§2.6） | ❌ |

**情境 (b) 結論**：**兩個新缺口** ——
(1) §3.8「混合」與「部分源時點不明」同時成立時怎麼寫；
(2) **§3.3（整表不畫）與 §3.5（逐列保留）的邊界沒有判準**，而 (b) 正好落在邊界上。
加上 §2.1 的 `raise`。

### 3.3 情境 (c)｜週一早上 09:00 打開（盤中），昨天是國定假日，資料停在上週五

| 畫面區塊 | 狀態 | 應顯示的字 | 規格答得出來嗎 |
|---|---|---|---|
| 全域時點列 | 資料歸屬日 = 上週五 | §4.2 → 「資料時點：**09-11 收盤**」 | ✅ **答得出來，而且這正是方案甲最漂亮的地方**：它不需要知道今天開不開市 |
| 每張 KPI 卡的 `facts` 末列 | 同上 | 「09-11 收盤」 | ✅ |
| 「這是不是最新的？」 | 🔴 **規格答不出來** | —— | ❌ **缺口，見下** |
| 圖表 footer | 週數等 | ✅ | ✅ |
| 主 CTA | Normal → 可按 | ⚠️ 字串問題同前 | ⚠️ |

**(c) 暴露出的真正缺口 —— 一條規格自己造成的規則對撞**：

規格 §4.4(b) 把 `staleness_days()` ＋ `gate_for_realtime()` 列為「配套」，
並稱後者是「**§1 fail-safe 的既有落點**」。實測這兩支在情境 (c) 會這樣跑：

1. `expected_latest_trading_day(today=週一)`（`staleness.py:26-52`）——
   `holidays` 沒有 caller 注入（§1 #5 已證），週一 `weekday()==0 < 5` → **回「今天（週一）」**。
2. `staleness_days(資料=上週五)` → `(週一 − 上週五).days = 3`。
3. `gate_for_realtime(3, max_days=1)`（`:101-118`）→
   `(False, "⚠️ 此數據為 3 天前的資料，僅供歷史參考，未納入即時燈號。")`

**兩個獨立的錯**：
- **(i) 國定假日**：若假日落在週五，實際上週四才是最後交易日，資料完全當期，卻被算成落後。
  這是規格**已經識別**的問題（§4.4(d)），但它**只用來論證「不要標盤中/盤後」，沒有用來檢查自己推薦的 `gate_for_realtime`**。
- **(ii) 盤中**：`expected_latest_trading_day` 收的是 `date`，**沒有時刻概念**。
  週一 09:00 台股還沒收盤（TWSE 盤後 ≈14:30，`CLAUDE.md §2.3`），
  **週一的收盤資料在物理上還不存在**，但函式仍把週一當成「預期最新交易日」。
  → **每一個交易日的 09:00–14:30，任何日頻序列都會被多算至少 1 天的落後**，
  於是 `gate_for_realtime(max_days=1)` 在**每個交易日的整個上午**對正常資料發出
  「僅供歷史參考，未納入即時燈號」。

**這就是規則對撞**：
- §4.5 檢查清單明文禁止：「沒有任何地方出現「**盤中 / 已收盤 / 休市中**」這類需要交易日曆才能判的字眼」；
- 而 §4.4(b) 推薦的 `gate_for_realtime` **要算對就必須知道「今天收盤了沒有」**。

**規格同時禁止判斷市場時段、又推薦一個需要市場時段才會正確的閘門，且未揭露這個矛盾。**
後果正是規格自己 §1.A-4 / R-1 在防的東西：**滿版的假警示稀釋真警示**
（每天上午所有卡都掛「僅供歷史參考」，使用者三天後就不看它了）。

🧠【本組建議，非客戶原話】§4 應補一條：
> **「資料時點」只寫歸屬日 ＋ 性質（§4.2），不做「新不新鮮」的判斷。**
> 需要新鮮度時，比較基準用「**資料歸屬日 vs 前一個已知資料歸屬日**」或明確標為
> 「距今 N 個日曆天」，**不得用 `expected_latest_trading_day` 推出的「落後幾個交易日」當使用者可見的警示**
> —— 本 repo 算不出正確的交易日。

---

## §4. 對 J-1 裁定的獨立意見（總管裁定：**不補**第 6 格）

### 4.1 結論

**總管的裁定在實質上是對的，本組不推翻。**
**但「7 種狀態 ＋ 1 條全域時點揭露列」這句替代說法本身不精確，而且它的錯誤方向比 J-1 更危險。**
建議**維持不補、但換一個更精確的說法**。

### 4.2 支持總管的三條理由（其中第三條是本組新找到的）

1. **母法那 8 格是客戶寫的清單，清單的長度是結果不是要求。**
   把 Off-Market 抽掉之後自然剩 7 格；為了維持「8」而填入一個客戶沒放在那個位置的東西，
   會讓後人以為「客戶要求要有一個叫『未載入』的呈現分類」——**製造一個假的來歷**。
   這與 `CLAUDE.md §-1.5.A-8` 標註 (a)/(b)/(c) 處理「政策新增」的做法同源：
   **來歷要誠實保留**，不能讓後人以為原文自帶。
2. **成本幾乎是零。** 規格自己寫了「若客戶本意是…7 種 ＋ 1 條揭露列，請當場推翻本格，
   §3 的矩陣列名跟著改，**但每一格的內容一個字都不用動**（內容綁的是底層七態）」——
   本組複驗這句話**成立**：§3 各表用的列名是「未載入（idle）」這類**綁底層態**的寫法，
   刪掉 §1.2 的編號不影響任何一格的內容。**推翻的代價確實是零。**
3. 🆕 **`UI_IDLE` 在結構上根本不是 8 格裡的一個平等席次，本組實測**：
   `shared/ui_state.py:199-202` —— `if not wired: return UI_UNWIRED` **排在** `if not requested: return UI_IDLE` **前面**。
   也就是說「未載入」**不是一個與 N/A 平行的呈現分類，而是一個被 N/A 攔在前面的閘門**。
   把它排進母法的第 6 格，等於宣稱它與 Normal/Empty/Missing/N/A 是同一層的並列項 —— **它不是**。
   **這條是母法對照表本身沒有能力表達的資訊**（規格 §1.2 也確實沒表達，見 §2.10）。

### 4.3 我認為總管**說法**要修的地方（這是我的挑戰）

**「7 種狀態」這個數字混了兩個層，而且往危險的那一邊混。**

規格 §1.2 自己證明了一件事，而且證得很好：

> **底層七態 → 呈現層是「一對多」，不是雙射。** `UI_EMPTY` 一個態同時供給呈現層第 4、5、7 三格…
> **寫 UI 的人必須把 `reason` 一路帶到卡上**，只帶 `state` 會讓 Empty / Missing / N/A 三格合成一格。

那麼「7 種狀態」這句話會被怎麼讀？
- 若「7」＝**底層七態**（unwired/idle/loading/failed/empty/degraded/live）→ 這句話對，但它**回答的不是母法的問題**，
  而且說出口後，下一個實作者很容易照著做出「畫面有七種樣子」的 UI —— **那正是 Empty/Missing/N/A 合成一格的那個 bug**。
- 若「7」＝**母法 8 格扣掉 Off-Market** → 那麼「未載入」**整個從呈現清單上消失了**，
  因為母法那 7 格裡**沒有**「未載入」（Normal/Loading/Empty/Missing/Partial/N/A/Error）。
  而「未載入」是 v3 §02 的主角、是 `CLAUDE.md §1.A` 第 4 條的主角、
  是規格 §1.5 花一整節在保護的東西。**把它從呈現清單上拿掉，風險遠大於把它多列一格。**

**兩種讀法，一種製造合併風險、一種製造遺漏風險，而句子本身分不出是哪一種。**

### 4.4 本組建議的替代說法（保留總管的判斷，去掉歧義）

> **母法 8 格中，7 格仍是狀態**（Normal / Loading / Empty / Missing / Partial / N/A / Error）；
> **第 6 格 Off-Market 撤下**，改為 **1 條全域「資料時點揭露」列**（不是狀態）。
> **另有 1 個母法沒有、但客戶已口頭認可的呈現分類：「未載入」（＝ 底層 `UI_IDLE`）** ——
> 它**不佔用 Off-Market 空出來的位置**，是新增的第 8 項；
> 且它在判定上**位於 `N/A`（unwired）之後**（`shared/ui_state.py:199-202`：`wired` 先判），
> 兩者同時成立時**顯示 `N/A`**。

這個說法：
- ✅ 守住總管要守的東西：**不把「未載入」冒充成母法第 6 格**，來歷誠實。
- ✅ 避免「7」被讀成「畫面只有七種樣子」而重現 Empty/Missing/N/A 合併。
- ✅ 順手把 §2.10 那個缺口（unwired 先於 idle）補進定義裡。
- ✅ 不需要改 §3 任何一格的內容（同 4.2 第 2 點）。

**如果總管認為「另有 1 個新增分類」這種講法仍然太接近 J-1，那也可以，
但請務必在交付給客戶的文件裡把 7 格逐項列名，不要只寫數字 7。**
本組的實質意見只有一句：**危險的不是數 7 還是 8，是「只給數字不給清單」。**

---

## §5. 我沒查到 / 沒複驗的（依 `CLAUDE.md §-2` 規則 6）

1. ⚠️ **「§3 的矩陣沒有其他缺口」這句話本組不敢講。**
   本組是**逐表對照底層 code 能力**去找缺格的（八個呈現態 × 六個元件＝48 格，抽驗約 30 格），
   **不是窮舉 48 格逐一驗證**。§2.9 列的四處是**本組單組找到的**，未經第二組複驗。
2. ⚠️ **`unified_verdict_render._fmt_value` 印出字面 `"None"` 是否 production 可達，本組未追上游。**
   只證實了「該函式沒有 None 分支」＋「同檔註解自陳軸可以沒有值」。**不得當成已證實的 bug。**
3. ⚠️ **本組未讀 `tests/` 下任何測試的內容**（只 `ls` 過檔名 ＋ `grep` 過 `test_ui_state_model.py` 的 `requested=` 行）。
   §2.13 建議的「翻譯表完整性 CI 守衛」是否已經存在於 `tests/test_decision_readiness.py`，**未查證**。
4. ⚠️ **本組未跑起 Streamlit、未看過任何實際畫面。** §2.4 關於「Streamlit 阻塞期間留上一幀」
   是依執行模型推論，**不是實測**。
5. ⚠️ **`macro_buckets.py:256-262` 自陳的「中間 4 個版本永久灰燈」，數字本身可疑**：
   v18.286 → v19.175 不是 4 個版本增量。規格 §5 R-14 逐字轉錄了它並標 📌 實證。
   **那是 repo 自己的措辭，不是規格的錯**，但引用時請知道這個數字沒有被任何人驗過。
6. ⚠️ **§2.3 那張「九支缺值格式化」表只掃了 `src/ui/views/` 與 `src/ui/render/`**，
   關鍵字為 `return "—"` / `無資料` 的字面。`src/ui/tabs/`、`src/ui/etf/`、`app.py` **沒掃**。
   **實際數量只會更多，不會更少**，但「九支」不是全部。
7. ⚠️ **本組沒有複驗兄弟交付物 S1-1 / S1-2 / S1-3 / S1-5。**
   規格中標為「轉錄自 S1-3、未複驗」的三項（E-4 本益比 ≤0、E-7 匯兌損益、§6.5）**本組同樣未複驗**。
8. ⚠️ **§3 三個情境的走法，是本組拿規格當說明書自己推的**，
   沒有與實作組對過。若實作組對某一格有不同讀法，代表**那一格的規格文字有歧義**，
   那本身就是額外的缺口（本組沒有能力窮舉歧義）。
9. ✅ **明確聲明找不到錯的地方**（避免為了交差硬湊）：
   §1.3 的 `MISS_*` / `MISSING_*` 兩張表、§1.5 的 `UI_IDLE` vs `UI_UNWIRED` 文案四規則、
   §3.4.2 的四條圖表禁令、§3.5 的「失敗的列不得消失」、§3.6 的三條硬規則、
   §5 的 14 個反例本身 —— 本組逐條回 code 比對，**沒有找到錯誤**。
   §4.4(d)（本 repo 沒有能力判盤中/盤後）本組**獨立複驗且另外補到三支 cron 腳本的佐證，結論成立**。
   **這些部分可以直接拿去用。**
