⚠️ **本檔為提案，尚未經客戶核准範圍；依 `CLAUDE.md` §8.4 step 4，重構範圍須客戶拍板。**

# `src/ui_v2/markup.py` 解綁 `page_today` — 選項 2 重構提案

> 量測日 **2026-09-22**，分支 `ui-v2` @ `2ac951c`。⛔ 全檔不寫行號（§8.2.A.0 規則 1），一律用符號名定位。
> 本輪**只寫提案、⛔ 未動 `src/`**。全稱句已逐條標「單組結論，未經第二組驗」。

## §1 現況 — markup 綁死 `page_today` 的逐點清單

檔頭 `from src.ui_v2 import components, page_today, tokens` 是**無條件 import**，綁死分兩層：**(A) 模組層級**（import 時就算完，⛔ 參數救不了）、**(B) 函式層級**。

**(A) 模組層級常數 —— 實測 4 個（⚠️ 非 3 個）**，全部由 `_grid_rules` / `_card_rules` / `_breakpoint_rules` 取用：

| 常數 | 由哪個符號算出 | 實測值 |
|---|---|---|
| `_BLOCK_COLS_USED` | `page_today.BLOCK_COLS.values()` | `((1,1,1),(3,2,1))` |
| `_LAYER_COLS_USED` | `page_today.LAYER_GRID_COLS.values()` | `((3,2,1),)` |
| `_TIERS_ON_PAGE` | `page_today.tier_for_block` × `BLOCK_COLS` | `('t1','t2','t3','t4')` |
| `_TIERS_WITH_LAYER_GRID` | `components.tier_for_layer` × `LAYER_GRID_COLS` | `('t2',)` |

⇒ `page_css()` 產出的 class 集合**在 import 時就被今天頁凍結**。換頁時**不會炸**，只會**少產 class** —— 正是 §1 最怕的靜默走樣（畫面出得來、版面是錯的）。**這是本重構最難的一塊。**

**(B) 五個公開函式**

| 函式 | 卡在哪個符號 | 非今天頁輸入的實測結果 |
|---|---|---|
| `page_css(mode)` | `BADGES_ON_PAGE`（經 `_badge_rules`）＋ 上表 4 常數 | **不炸**，少產 class（靜默） |
| `badge_html(n,*,size=None)` | **不碰 `page_today`**（走 `components.badge`） | 見下方缺陷 |
| `card_html(*,block,…)` | `tier_for_block` / `BADGES_NOT_ON_PAGE` / `card_value_text` / `card_level_text` | `KeyError 未知的 block：'why.edu.lights'` |
| `grid_html(*,block,cards)` | `BLOCK_COLS[block]` ＋ `tier_for_block` | `KeyError: 'why.edu.lights'` |
| `layer_html(*,layer,block_htmls)` | `LAYER_GRID_COLS` | `KeyError 第 5 層沒有登記層級網格` |

**⚠️ 一個必須先釐清的非綁死項**：`components.tier_for_layer(5)` → `ValueError 只有 0 與 1~4`，是 **`components` 的設計上限（任何頁都只有四層）**，⛔ **不是** `page_today` 綁死 ⇒ **本重構不動它**。

**🔴 必須一併解掉的既有缺陷（客戶已裁示本輪不修、登記待修）**：`badge_html(10)` **不 raise**，但 `.bdg-10` **不在 `page_css()` 輸出**（`_badge_rules` 只跑 `BADGES_ON_PAGE`，實測 `{1..9}`；`BADGES_NOT_ON_PAGE={10}`）⇒ 畫出一顆**無配色徽章、不變紅**。
⚠️ 重構後 `BADGES_ON_PAGE` 隨 page 走，此洞會**從一頁擴散到每一頁** ⇒ ⛔ 不得延後，須在介面改的同一輪收掉（作法：`badge_html` 吃 `page=` 並對未登記編號 fail loud）。

## §2 方案 — 兩案比較

**方案 (a) 參數注入**：五個函式多吃 `page=`（預設 `page_today`）。
- **向後相容** ✅ 既有 caller（`render.py` 全部呼叫點）**0 改**；**代價**：預設值會讓「忘了傳 `page=`」**靜默畫成今天頁**（§1 失效模式）。
- **模組常數怎麼辦** ⚠️ **參數救不了** —— 四個常數 import 時就綁死。**必須**把它們從 `Final` 常數改成**吃 `page` 的內部 helper**（`_block_cols_used(page)` 等），由 `page_css(mode,*,page=…)` 呼叫時現算。這是 (a)(b) **共同的必做項，⛔ 不是二選一**。

**方案 (b) Protocol 介面**：定義 `PageLayout` 協定，`page_today` / 未來 `page_why` 各自實作，`page` **必填**。
- **向後相容** ❌ 五函式全變必填參數 ⇒ `render.py` 所有呼叫點 ＋ `test_markup.py` 178 條全要改；**好處**：杜絕靜默預設，`page_why` 缺符號時在守衛測試就紅燈，而非畫面走樣。
- **模組常數怎麼辦**：**與 (a) 完全相同**（同樣得轉 helper）—— Protocol 只解決「**page 長什麼樣**」，⛔ **不解決**「**markup 怎麼拿到 page**」⇒ **(b) 不是 (a) 的替代品，是它的型別補強。**

**✅ 推薦：(a) 為主 ＋ 借 (b) 的 Protocol 當型別標註與守衛。** 理由三條：① `page_why.py` 在 `src/ui_v2/` **尚未存在**（實測 7 檔無此檔），純 (b) 會把一次介面重構變成 575 條測試全面重寫，違 §8.1 step 6「用不到的抽象先不做」；② 相容層讓**今天頁在重構期間全程可用**（§5 風險 3）；③ (a) 的唯一弱點（靜默預設）可用兩道便宜的鎖壓住 —— `render.py` 端**必填**（它是唯一 production caller）＋ Protocol 符合性守衛測試。
⚠️ **未定案項**：兩頁若各自產出同名 class（例 `.g-3-2-1`）而語意不同，單一 `page_css()` 注入會互蓋 ——「一頁一張 sheet」vs「共用 sheet 取聯集」須在第一輪定，⛔ 本提案不預設答案。

## §3 影響範圍（行數／條數為 **2026-09-22 實測**）

| 檔 | 行／條 | 要動什麼 |
|---|---|---|
| `src/ui_v2/markup.py` | 510 | **主改檔**：五函式加 `page=`；4 個模組常數 → helper；`badge_html` 補 fail loud |
| `src/ui_v2/render.py` | 184 | ⚠️ **同病**：`_BLOCK_LAYER` / `_LAYER_ORDER` / `_MAIN_CTA_LAYERS` 同樣由 `page_today.LAYERS` 在 import 時算好；`render_page_today` 簽章不得變 |
| `src/ui_v2/components.py` | 451 | 新增 `PageLayout` Protocol（或另立檔）；⛔ `tier_for_layer` 不動 |
| `src/ui_v2/page_today.py` | 664 | ⛔ 實作不動（實測已具備 Protocol 所需全部符號） |
| `src/ui_v2/__init__.py` | 45 | `__all__` 增列新符號 |
| `src/ui_v2/app_today.py`／`tokens.py` | 38／238 | ⛔ 預期不動 |
| `tests/ui_v2/test_markup.py` | 1649／178 | **最大改動面**：模組常數 `COLS_BLOCKS`／`ALL_BLOCKS`／`ON_PAGE_BADGES`／`LAYER_IDS`／`GRID_LAYERS`／`UNGRIDDED_LAYERS` 全由 `page_today` 導出 → 改 fixture／parametrize 吃 page |
| `tests/ui_v2/test_render.py` | 268／4 | 以 `BLOCK_COLS`／`LAYER_GRID_COLS`／`resolve_badge`／`main_cta_state` 組 view model |
| `tests/ui_v2/test_today_page.py` | 927／156 | 只測 `page_today` 自身契約 → **預期不動**（單組結論，未經第二組驗） |
| `tests/ui_v2/test_components.py` | 606／77 | 僅一處註解字串提及 → **預期不動**（同上） |
| `tests/ui_v2/test_tokens.py` | 976／160 | ⛔ 不受影響 |

`tests/ui_v2` 合計 **575 條**（實測，⚠️ 任務書寫 574）。📌 **命名提醒**：`src/ui/views/page_why.py` **已存在**（舊 IA v2 樹，實測），與本提案要新增的 `src/ui_v2/page_why.py` **是兩個不同的檔** —— ⛔ 不要混淆，也⛔ 不要據此以為已有現成的 page 契約可用。

## §4 工時估算（單位＝**輪**；一輪 ＝ 派工＋複驗＋fast/slow 兩條 lane）

1. `markup` 四個模組常數 → helper ＋ 定案 class 命名策略（§2 未定案項）
2. `markup` 五函式加 `page=` ＋ `badge_html` 補 fail loud（`.bdg-10` 一併收）
3. `test_markup.py` 178 條的模組常數改吃 page
4. `render.py` 三常數解綁 ＋ `test_render.py` 同步
5. `PageLayout` Protocol ＋ 符合性守衛測試
6–7. `page_why.py` 落地（`LAYERS`／`BLOCK_COLS`／`LAYER_GRID_COLS`／`BADGES_*`／`card_*_text`，規格見 `UI_PAGE_WHY.md`）＋ 其新測試

**合計 7 輪** ＝ 介面 2（輪 1–2）＋ 測試 2（輪 3–4）＋ Protocol 1（輪 5）＋ 新頁 2（輪 6–7）。⚠️ **單組估算，未經第二組驗**；輪 1 的未定案項若走「共用 sheet」會再多 1 輪。

## §5 風險與回滾

| # | 風險 | 壓制手段 |
|---|---|---|
| 1 | **575 條 `tests/ui_v2` 大規模改動**（射程內實測 182 條＝`test_markup` 178 ＋ `test_render` 4；其餘 393 條預期不動 —— **單組結論，未經第二組驗**） | 拆輪：介面與測試分輪，每輪兩條 lane 綠燈才進下一輪 |
| 2 | **`render.py` 連動** —— 與 markup 同病，只改 markup 會留下半套解綁 | 輪 4 必做，⛔ 不得省略 |
| 3 | **重構期間今天頁必須維持可用**（`app_today.py` 是 production 進入點） | 方案 (a) 的預設 `page=page_today` 即為此而設；`render_page_today()` 簽章全程不變 |
| 4 | **靜默預設** —— 忘了傳 `page=` 就畫成今天頁，不報錯 | `render.py` 端必填 ＋ Protocol 守衛測試（輪 5） |
| 5 | **class 命名互蓋**（§2 未定案項） | 輪 1 先定案再寫 code |

**回滾**：本重構應**全部落在單一 PR**，回滾 ＝ `git revert` 該 PR 的 merge commit。`markup.py` 至今**僅一個 commit**（`b4cb83e`，實測 `git log --diff-filter=A`）、無交錯歷史 ⇒ revert 乾淨；若逐輪分 PR，則以**輪 1 之前的 commit** 為回滾錨點。
⛔ **不建議 feature flag**：`CLAUDE.md` §-1.2 記載客戶 2026-09-16 已撤銷雙軌（「雙軌是純成本，沒有好處」），且 (a) 的預設參數本身就是相容層，再加 flag 等於第二套開關。
