# 狀態語意複驗（第二組，獨立重跑）

> 唯讀。未參考第一組任何產出。所有判定以 `grep` / AST 列舉 / 實際執行為準，不引用文件轉述。
> repo：`/home/user/my-stock-dashboard`（HEAD `fab88a7`）；另可讀到姊妹 repo
> `/home/user/linchen-20200325/my-fund-dashboard`。

---

## 結論：**部分成立 —— 一半成立、一半的前提是錯的**

### ✅ 成立的那一半：`degraded` 與 `unwired` 確實是兩個東西，不得合併

兩者在 code 裡是**兩個獨立常數、兩組獨立旗標、兩種顏色、兩種使用者動作、兩種分母待遇**。
合併會產生 §1 所禁的假訊息（見下方情境 A）。這一半**完全成立**。

### ❌ 不成立的那一半（三個獨立的問題）

**(i) 宣稱的前提「合併成同一個灰燈」在本 repo 不存在。**
`degraded` **從來不是灰的** —— 實測 `state_meta("degraded")` 回
`('門檻已失準', '🟠', '#eab308')`，`unwired` 才是 `('未接線', '⛔', '#888888')`。
灰色家族只有 `idle / loading / empty / unwired` 四個（`tests/test_ui_state_model.py::
test_grey_states_share_one_hex_and_differ_by_glyph` 釘住）。
**沒有人能把 degraded 合併進灰燈，因為它不在灰燈裡。** 宣稱在防一個不存在的組態。

**(ii) 「Partial」不是狀態實體 —— 而且現行 code 的答案與宣稱相反：partial 已經被刻意灌進 `degraded`。**
用 AST 列舉全 `src/` 的 `classify_ui_state(...)` 呼叫點（**49 處，無 attribute-style 呼叫，故為窮舉**），
其中 `discriminative=` 非預設值的只有 **10 處**，逐一判讀後：

| 餵進 `discriminative=` 的是什麼 | 處數 | 檔案:行 |
|---|---|---|
| **覆蓋率 / 部分取到（＝ partial）** | **5** | `page_today.py:1184`、`page_find.py:1329`、`page_hold.py:2549 / 2632 / 2733` |
| 真的 `spec.discriminative` 旗標 | 3 | `page_today.py:879`、`page_why.py:764`、`page_hold.py:1703`(←`:683`) |
| 來源 provenance | 1 | `tab_today.py:310` |
| 快取過期 staleness | 1 | `page_find.py:1389` |

也就是說：**在 production 裡，「只拿到一部分」現在就是畫成 `🟠 門檻已失準`**，
而且每一處都有明文理由（`page_today.py:1155-1157` 原文：「把『門檻層有沒有真的掃過』
餵給 `discriminative=` —— 語意完全對得上」）。
**宣稱說「因為不等價所以必須分開」，但 repo 已經、且刻意、且有文件地把它們合在一起了。**

**(iii) 宣稱把兩個不同軸的東西寫進同一個括號。**
「**部分通過**」在本 repo 是 **band（🟡 黃燈）**，不是 state ——
`src/compute/screener/shortage_screener.py:361` 回 `SHORTAGE_REV_PARTIAL_SCORE` +
「🟡月營收 YoY 部分達標」。band 與 state 是 `_ui_kit.render_card()` 的**兩個獨立 chip**。
「部分通過」是**可信而且結果普通**；「部分欄位有值」是**不完整**。
兩者連頻道都不同，把它們並列成「Partial」會在下一步製造真正的混淆。

---

## 對那個畫面決定的影響（結論站得住，但理由要換）

「底層維持現有七態不動、母法的『8 種』讀作呈現分類」——**這個結論我獨立支持**，
但**不是**因為宣稱給的理由。正確的理由是：

> 區分 partial 所需要的資訊，**已經由強制的 `Note.why` / `where` / `facts` 承載**；
> 而新增第八態的成本落在 **4 個獨立的狀態判定點 ＋ 3 張獨立的標籤表**上。

同時必須回報一個**宣稱射程之外、但現在就存在的真問題**：

> **⚠️ 那 5 處 partial 卡片的狀態 chip 印的是「🟠 門檻已失準」，而它們的門檻並沒有失準。**
> 例：`page_find` 熱力圖只抓到 18/29 個類股 → chip「🟠 門檻已失準」，
> 而同一張卡的 `why` 寫的是「這一輪只抓到 類股層 18/29」。
> **chip 與 why 在講兩件不同的事**，chip 那句是假的（§1）。
> `page_today` ④ 更明顯：chip「門檻已失準」／`why`「**門檻層本輪未評估**」——
> 「失準」與「沒跑」是兩個相反的診斷。
>
> ⭐ **最便宜的誠實修法不是加第八態，是改 `UI_STATE_META[UI_DEGRADED]` 的標籤**
> （改成因果中性的說法，例如「打折的數字／別當結論讀」），
> 一行 SSOT 就同時修好 5 處，且四張表都不用動。

---

## 證據（10 條，皆為本組實測）

1. `shared/ui_state.py:93-113` — 七態常數逐行：`UI_IDLE/LOADING/FAILED/EMPTY/DEGRADED/UNWIRED/LIVE`。
   **沒有 `UI_PARTIAL`**；全檔 grep `partial` → 0 命中。
2. `shared/ui_state.py:118-119` —
   `UI_DEGRADED: ("門檻已失準", "🟠", TRAFFIC_YELLOW)` / `UI_UNWIRED: ("未接線", "⛔", TRAFFIC_NEUTRAL)`。
   實跑 `state_meta()`：degraded `#eab308`（橘）、unwired `#888888`（灰）→ **兩者不同色**。
3. `shared/station_specs.py:457-495` — `MISS_*` **共 6 個**：
   `no_input` / `fetch_failed` / `not_enough` / `n/a` / `contract_drift` / `no_variation`。
   **沒有 partial**。`MISS_PRIORITY`（:527）是「解釋力涵蓋範圍」排序；
   `shared/ui_state.py:22-38` 明文說明**跨軸的東西不得塞進同一個 priority**。
4. `shared/macro_buckets.py:214` / `:232` — `unwired_reason`（`wired=False` 時必填）與
   `degraded_reason`（`discriminative=False` 時必填）是 `DangerSpec` 的**兩組獨立欄位**，
   **編寫期靜態宣告**；生產者＝L0 註冊表，消費者＝`station_specs.classify_state()`
   ＋ `tab_macro_v2.py:429-436`（**刻意複製判定順序**的第二處）＋
   `page_today.py:995-1013`（各自印 `spec.degraded_reason` / `spec.unwired_reason`）。
5. `src/ui/views/page_today.py:1180-1185` — `discriminative=threshold_scanned`，
   docstring `:1155-1157` 自陳「把『門檻層有沒有真的掃過』餵給 `discriminative=`」。
   → **partial 直接被當成 degraded 用。**
6. `src/ui/views/page_find.py:1322-1329` — `discriminative=hm.complete`；
   `:1312` docstring 原文「**只抓到一部分 → degraded** ／ 全抓到 → live」。
7. `src/ui/views/page_hold.py:2729-2733` ＋ `_cash_degraded_bits()`（`:2673` 起）——
   判準只有一條 `full_coverage=False`（＝只涵蓋一部分持股）→ `UI_DEGRADED`。
   同檔 `:2545` / `:2632` 的 `_degraded_bits()` 另含 `no_price`（幾檔抓不到價格序列）→ 同樣 degraded。
8. `src/ui/views/_ui_kit.py:278-279` — `_name, _glyph, _hex = state_meta(card.state)` →
   `_chip(f"{_glyph} {_name}", _hex)`。**狀態 chip 的字就是 `UI_STATE_META` 的標籤**，
   所以第 5~7 條那 5 張卡在畫面上印的就是「🟠 門檻已失準」。
   同檔 `:12` 明文禁止 render 層「**不加第八態**」。
9. `src/compute/etf/dividend_station.py:856` ＋ **實跑驗證**：
   `light_235(vix=None, weekly_close=None, …, z=0.1)` → `axes_used=('boll',)`、
   `classify_state(...)` → **`state='live'`（🟢 運作中）**，
   與三軸齊備的 `axes_used=('vix','weekly','boll')` **狀態 token 完全相同**；
   唯一差別在 `reasons` 文字「布林 均未觸發（缺 VIX/週線 依據,1/3 個依據可用）」。
   → **現行最嚴重的 partial 混淆是 partial→live，不是 partial→degraded/unwired。**
10. `src/ui/render/station_cards.py:474-476` — 「給得出判定」的分子是**白名單**
    `c.state in (STATE_LIVE, STATE_DEGRADED)`，刻意 fail-closed（`:472` 註解：
    「新增第五態時要 fail-closed」）。→ 上一條那盞 1/3 依據的燈，**在可信度分子裡算一整盞**。

---

## 三個是非題（逐題附證據）

**(a) 「Partial」在現行 code 有沒有實體？**
> **有實體，但不是狀態常數；而且是**三個互不相干、住在不同軸上的執行期旗標**。

| 何處 | 是什麼 | 畫成什麼 |
|---|---|---|
| `src/services/macro_refresh_service.py:298`（`SourceContent.partial`）＋`:480`（`report.partials`） | 一輪更新裡某桶 `0 < filled < total` | `page_today.py:1732` → `st.warning` ⚠️、`_event_icon`（`:1652`）給 `⚠️`，**且 `partial` 必須排在 `ok` 前面**（`:1646` 註解） |
| `src/services/portfolio_deep_service.py:490/637/879`（`partial` property） | `valued_n < held_n` | 經 `_degraded_bits` → **`UI_DEGRADED`** |
| `src/ui/views/page_today.py:465` `EXIT_ALERTS_PARTIAL` | **出口**只有一半在射程內 | 第四種 `where` 文案（刻意不併進 (a)/(c)，`:459-464` 寫明理由） |

→ 三個 partial **連軸都不同**（更新輪次覆蓋率／持股估值覆蓋率／出口可達性）。
把它們收斂成一個「Partial 態」本身就需要先證明它們是同一件事，**而它們不是**。

**(b) `degraded` 與 `unwired` 在現行 code 是不是兩個不同的東西？**
> **是，而且是四個層面上的不同**（證據 2 / 4）：
> ① 常數不同；② 顏色不同（橘 vs 灰）；③ 旗標來源不同
> （`discriminative` vs `wired`，`DangerSpec` 上兩組獨立必填 reason）；
> ④ **分母待遇不同** —— `macro_buckets.py:253-254` 說 `not_wired`「**不計入分母**」，
> 而 `page_today.py:721-724` 的 `Coverage` 說 unwired **在分母裡**（16 是總數）。
> ⚠️ **這兩句互相矛盾，是本組順手查出的第二個獨立問題**（見「我沒查到的」第 4 點）。

**(c) 有沒有現存路徑讓「degraded / unwired」與「部分欄位有值」長成同一個樣子？**
> **有，而且比宣稱描述的更廣 —— 但方向不同：**
> · **partial → degraded：5 處**（證據 5/6/7），畫面完全同形（同一顆 🟠 chip、同一句標籤）。
>   宣稱說「不能合併」，但**已經合併了**，且是 2026-09-07/09 那幾批刻意做的。
> · **partial → live：1 處且更危險**（證據 9），1/3 依據的 235 燈與 3/3 **同為 🟢 運作中**，
>   且在可信度分子裡算一整盞（證據 10）。
> · **partial → unwired：0 處**（`wired=False` 只出現在 `page_hold.py:1428` /
>   `page_inspect.py:2197` 兩個真未接線建構器，皆 `has_value=False`）。

**→ 宣稱的方向性描述不準：**真正發生的不是「partial 被畫成灰燈」，
而是「partial 借用了 degraded 的 token，而那個 token 的標籤是一句關於門檻的假話」。

---

## 具體畫面情境（§1 假訊息會長什麼樣）

**情境 A（合併 degraded / unwired 會壞 —— 支持宣稱）**
`foreign_net`（外資現貨淨買賣）在 L0 標 `wired=False`＋`unwired_reason`；
`margin`（融資餘額）標 `discriminative=False`＋`degraded_reason`。
若合併成一格：畫面對 `foreign_net` 說「改看它相對自身區間的方向」——
**那格永遠不會有值，沒有任何區間可看**；對 `margin` 說「重按一百次也一樣」——
**它其實有值、按了會更新**。**兩句話各自對另一格是假的。** → 必須分開，宣稱這一半成立。

**情境 B（現在就在發生的假話 —— 宣稱沒抓到）**
使用者按「🗺️ 載入板塊地圖」，29 個類股只回 18 個。畫面：

```
🟠 門檻已失準     產業漲跌熱力圖
                 有幾格沒有資料，圖照畫但缺格是留白的
                 這一輪只抓到 類股層 18/29 ——（略）
```

chip 說「門檻失準」＝「這張圖的判讀標準壞了，別照門檻讀」；
實際上**門檻好好的，是資料只來了 62%**。使用者依 chip 會去懷疑門檻設定，
而真正該做的是「稍後重載」（那句寫在 `where` 裡，但 chip 已經先把他帶偏）。

**情境 C（最危險的一個，不在宣稱射程內）**
一檔新上市 ETF，VIX 這輪沒抓到、週線長度不足，只剩布林 z 算得出來且 z=0.1。
畫面：**`⚪ 巡航：維持定期定額`＋狀態 `🟢 運作中`**，
可信度列把它算成一盞「給得出判定」的燈。
與「三個依據都同意現在很平靜」**完全同形**，
差別只在一行小字「（缺 VIX/週線 依據,1/3 個依據可用）」。
**這才是宣稱應該去防的那個坑，而它現在是綠的。**

---

## 反向理由（認真找「不必分開」的理由 —— 找到 5 條，其中 3 條我認為成立）

**R1（成立，最強）：狀態 token 實際上只 gate 一個二元問題，而 partial 與 degraded 對它的答案相同。**
`Card.__post_init__` 規定**非 live 不得帶 `value`**（`page_today.py:993` 註解、
`page_hold.py:265-267` 同語）。也就是狀態 token 唯一真正決定的事是
「**這個數字可不可以放在結論位置**」。partial 與 degraded 的答案都是「不可以」。
**答案相同的兩件事共用一個 token，不是說謊，是正確的抽象。**

**R2（成立）：使用者的應對動作根本不住在 token 裡，而且三個 partial 的動作各不相同。**
`page_hold` partial → 「去 📁 組合管理補張數／均價」；
`page_today` ④ partial → 「**沒有出口**，門檻層本頁摸不到」；
`page_find` partial → 「稍後重新載入多半會補齊」。
**三個 partial 三種動作。** 加一個 `UI_PARTIAL` token **一個都承載不了** ——
動作永遠只能寫在 `where` 裡。**新 token 買不到任何東西。**
（而且 `_degraded_note()`（`page_hold.py:2437-2445`）在 bits 為空時**直接 raise**——
「判成 degraded 卻說不出哪裡失準」已經是 fail-loud 的，不會出現空洞的橘燈。）

**R3（成立）：第八態的成本是可列舉的，而且會落在四個獨立的判定點與三張標籤表上。**
狀態判定目前有 **4 處**：`ui_state.classify_ui_state`（7 態）、
`station_specs.classify_state`（4 態）、`tab_macro_v2.py:429-436`（**刻意 inline 複製**）、
以及 `station_cards._judged_ratio` 的白名單。標籤表有 **3 張**：
`ui_state.UI_STATE_META`（7）、`station_specs.STATE_META`（4）、`macro_v2_cards.STATE_META`（4）。
`_ui_kit.py:12` 還明文禁止 render 層加第八態。
**新增一態 = 同時改 7 個地方，且 `station_cards` 的 fail-closed 白名單會讓新態
靜默掉出可信度分子（分數下修，是行為變更）。**

**R4（部分成立）：姊妹 repo 的獨立答案也是「不新增 token」。**
Fund 端 `ui/helpers/render_state.py` 是**五態顏色模型**（未載入／不適用／業務警訊／
系統真出錯／破壞性操作），**沒有 partial、也沒有 unwired**；
它遇到 partial 的處置是 `ui/views/page_01_macro.py:1475-1497`：
`_partial = 0 < _n_on < _n_all` → **直接不下研判** ＋ 印一句 caption 解釋權重重分配。
**兩個 repo 獨立長出同一個策略：partial 走「撤回結論 ＋ 加說明」，不走「新增狀態」。**
⚠️ 但 Fund 的 `degraded` 是**另一個意思**（`system_error(degraded=True)` ＝
「系統失敗但數字全在，掉的只有一張圖」），**兩 repo 同字不同義**，
引用 Fund 當先例時不得混用字面。

**R5（我認為不成立，但據實列出）：「多一態讓人看不懂」。**
我不接受這條當理由 —— 灰色家族現在就有四個態靠 glyph 分辨，且有測試守著；
**認知負荷不是本 repo 既有做法的否決點**，拿它當理由是事後合理化。

---

## 我沒查到的（依 §-2 規則 6 據實標明）

1. **「partial→degraded 只有 5 處」是本組單組窮舉，未經第二組驗證。**
   方法：AST 列舉 `src/**/*.py` 裡函式名為 `classify_ui_state` 的 `Call` 節點（49 處），
   逐一讀 `discriminative=` 的運算式。
   **結構性盲點**：只抓得到 **bare-name 呼叫**；若日後有人寫
   `ui_state.classify_ui_state(...)` 或用 `getattr` 動態取，本次掃描**掃不到**
   （已另 grep `\.classify_ui_state` → 0 命中，故**就本 HEAD 而言**為窮舉，
   但這條保證不會自動延續到下一個 commit）。
2. **`src/ui/tabs/**` 的舊分頁我沒有逐檔讀。** 只掃了 `classify_ui_state` 的呼叫點
   （`hot_money.py:223`、`macro/handlers.py:165`、`macro/section_long.py:456`、
   `macro/section_state.py:503`、`tab_today.py:306`、`sidebar_health.py:200/205`，
   皆 `discriminative` 預設）。這些檔**是否另有自己手寫的狀態判定**（如
   `tab_macro_v2.py:429` 那種 inline 複製），**我沒有窮舉**。
3. **`station_specs.classify_state()`（4 態）的消費端我只查到 `dividend_station.py:830`。**
   `LightCell.state` 之後流到哪幾個畫面、有沒有第二處 partial 混淆，**未追完**。
4. ⚠️ **順手查出、但未追究的第二個矛盾**：`macro_buckets.py:253-254` 寫
   `not_wired`「**不計入分母**」，`page_today.py:721-724` 的 `Coverage` 寫
   unwired **在分母裡**（`0／16（無資料 15 · 未接線 1）`）。
   **兩句話對同一件事給相反答案。** 我沒有判定哪一句是對的，也沒有查
   `macro_helpers._unwired()`（`:1748`）寫進側車之後實際被誰數進分母。
   **這是獨立的一題，不屬本次射程。**
5. **`SPEC.md` 與 code 已經漂開，我只確認漂了、沒有確認漂了幾處。**
   實測兩處：`SPEC.md:830` 的 P02 四態表**沒有 `UI_DEGRADED` 那一列**，
   而 `page_find.py:1329/1389` 現在會判 degraded；`SPEC.md:1100` 寫 page_hold
   「**唯一**會判 `UI_DEGRADED` 的是 ② 兩套刻度」，而 `page_hold.py:244` 自己的
   docstring 寫「**有三處**」。→ **拿 SPEC.md 當狀態模型真相源會讀到過期資訊。**
6. **Fund repo 只讀了 `ui/helpers/render_state.py` 與 `ui/views/page_01_macro.py` 兩檔。**
   `ui/helpers/ia/empty_state.py` / `io/freshness.py` **沒讀**，
   「Fund 沒有 unwired 態」是 grep `unwired|未接線|not_wired` 的結果（命中皆為註解／文案，
   非狀態常數），**單組、未複驗**。
7. **我沒有實跑任何 Streamlit 畫面。** 情境 B / C 的畫面樣貌是從
   `_ui_kit.render_card()` 的字串組裝 ＋ 實跑 `classify_ui_state` / `light_235` / `classify_state`
   推出來的，**沒有截圖佐證**。沙箱跑不到部署環境。
