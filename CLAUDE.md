# CLAUDE.md — 資料完整性憲法（my-stock-dashboard）

> 本檔為 AI 協作的最高行為準則,目標：確保資料**真實、可追溯、計算正確、可重現**。
> 跨領域不變的原則已寫死；**領域相關**的部分由 §0 Bootstrap 依本專案實況填妥。
> 違反本檔任一條視同 bug,須當場修正。
>
> ⚠️ **流程治理 / state 管理 / PR 規範 / Anti-Loop** 屬另一面向,獨立於本「資料憲法」,
> 請見同目錄 `PROCESS.md`（原 Core Protocol v2.0,2026-06-22 並存策略 B 拆檔保留）。

---

## §-2. AI 總管與執行分工（凌駕本檔其餘各節）

> 2026-08-25 user 指派：**「每一次任務 AI 總管都要安排對應的 AI 去執行，AI 總管是負責監督的人」**

### 角色分工

| 角色 | 負責 | **不**負責 |
|---|---|---|
| **AI 總管**（主對話） | 拆任務、定規格、派工、**複驗回報**、對 user 負責 | 自己動手寫實作 |
| **執行 AI**（subagent） | 依規格調查 / 實作 / 測試 | 決定範圍、直接對 user 交付 |

### 規則

1. **每一次任務都要派工。** 不論大小 —— 調查、實作、測試、稽核，都由對應的 subagent 執行。
2. **總管不自己寫實作。** 總管的產出是：規格、判斷、複驗結論、給 user 的報告。
3. **一定要複驗。** subagent 回報**不等於**完成。總管必須自己查證關鍵宣稱（尤其「零行為變更」「全都查過了」「沒有其他地方受影響」這類全稱句），不可照單全收 —— subagent 也會錯、也會過度自信。
4. **平行派工**（user 2026-08 指示：「因為這樣會漏東西」）：同一件事至少派多組不同角度的 agent，不要單點。調查與稽核尤其要獨立分派，不可由同一組自己查自己。
5. **例外看「產出什麼」，不看「動作多大」。** 免派工的只有一種：**唯讀、不產生 diff、而且不產生會被別人拿去用的結論** —— 查一個事實直接回答 user，就是這種。只要出現下列任一項，**一律派工，不論動作看起來多小**：
   - **會寫入檔案**（改 code、改文件、改本憲法同樣算）
   - **會下判斷或給結論**，尤其是全稱句（「查過了」「只有這一處」「零影響」「沒有其他地方受影響」）
   - **屬於調查 / 稽核**（依規則 4 還要多組獨立派工）

   ⚠️「這件事小到不用派工」這個判斷本身**不是**免派工的理由 —— 它正是實證裡三次都出錯的那一步（理由見下）。把工作**發回原 subagent 續做**仍屬派工，不算總管自己動手。
6. **總管自己的結論也要驗。** 規則 3 管的是 **subagent 的回報**，但總管自己產出的全稱句同樣沒有第二雙眼睛。總管**不得**把未經第二組驗證的全稱句當成事實交付給 user —— 要嘛派一組獨立驗，要嘛**明說「這是我自己看的，沒有第二組驗過」**。

   實證：本 repo commit `db4c139`，訊息宣稱「順帶修掉」235 燈的缺資料偵測，實際上那段是死碼 —— `assess_holding` 開頭已先 `raise` 掉空序列，判斷式 `weekly_close is None` 在 production 路徑恆為 False。那句宣稱是**總管自己寫、自己沒查**，最後由派出去的稽核 agent 抓到（21,168 組真實組合實測 `miss_reason` 從未非空）。**規則 3 擋不住這種錯，因為它不是 subagent 說的。**

### 為什麼要有這條（2026-08-25 實證，非儀式性規定）

同一個 session 內，**總管自己動手寫的東西被派出去的稽核 agent 抓到三次實質錯誤**：

- 宣稱「順帶修掉」的 235 燈缺資料偵測，實測在 production 路徑**永遠不會觸發**
  （`assess_holding` 已先擋掉空序列，判斷式 `weekly_close is None` 恆為 False）——
  也就是 commit message 裡的宣稱**不成立**，而且是自己寫的自己沒查出來。
- 教學卡的門檻帶寫錯方向：寫成 direction bands，卻引用 level bands 的出處。
- 兩個 `MISS_*` 缺值原因常數選錯，導致新上市標的收到「可以重跑一次」這種**錯誤指引**
  （真正原因是歷史長度不足，重跑一百次也一樣）。

三次都發生在「看起來很小、我自己來比較快」的改動上。
**「這件事小到不用派工」這個判斷本身，就是最常出錯的地方。**

⚠️ 對照 §1「錯誤的數字比沒有數字更危險」：**沒查證的宣稱比沒有宣稱更危險**。
一句「已修正」若實際沒生效，會讓下一個人（含未來的 AI）建立在假前提上繼續蓋。

### 與既有條文的關係（2026-08-25 插入時查證）

- **本檔內查無牴觸**：全檔搜尋 `subagent` / 子代理 / 派工 / 平行 / 並行 / agent 後，
  唯一命中的 §0 步驟 1「三組並行 Explore agent 掃描」是**歷史紀錄**而非規則，且與本節規則 4
  同向，不衝突。§6 自審清單 / §8.1 先設計 / §8.5「一次只寫 / 改一個模組」講的是「**怎麼寫**、
  **一次改多少**」，與本節的「**誰動手**、**誰複驗**」正交，兩者並存。
- ⚠️ **`PROCESS.md` §3「規劃與多線程」有兩條較窄的舊規定，已由 §-2 收斂，以 §-2 為準**
  （**2026-08-25 已在 `PROCESS.md` 端同步改完**（user 後續授權擴大至 `PROCESS.md`）。處置方式：
  **舊條文一律保留不刪**，原地加刪除線 + 註明「有意識的政策變更，不是漏刪」+ 標日期與決策者
  + 兩邊理由並陳（舊規則的理由**仍然成立**，只是被權衡掉）。全篇掃過（關鍵字 subagent / 子代理 /
  派工 / 並行 / 平行 / agent / 就地 / 序列化）**只有 §3 這兩條牴觸**，§1 / §2 均與 §-2 正交，
  未動；§4「不准說 Done 就跑」與 §-2 **同向而非正交**（2026-08-25 加規則 6 時複查更正）——
  規則 6 等於把 §4 的「交付前自己驗」推進到「全稱句要嘛有第二組驗、要嘛明說沒驗過」，兩者
  不牴觸，`PROCESS.md` §4 原文同樣未動；§5 卡關救援**無牴觸**，但補了一條 §-2 **連帶造成的
  缺口**（重試計數跨 subagent 累計，見該節）—— 屬補洞，不是收斂）：
  1. §3「**並行處理（限唯讀）**……**寫入（改 code）仍嚴格序列化，一次一檔**」＋「嚴格三步法：
     Explore Agent（唯讀探索環境）-> Plan -> Execute（動手改 code）」—— 舊條把「派 agent」
     限縮在探索 / 稽核（唯讀）階段，Execute 預設總管自己下場；**§-2 規則 1 要求實作也派工**。
     ⚠️ 但**序列化那半句仍然有效**：§-2 管的是「誰動手」，不是「同時開幾隻手改 code」，
     寫入端一次一檔的紀律不變。
     **處置**：`PROCESS.md` §3「嚴格三步法」該句**整條加刪除線保留**，同行補「現行」全文
     （Explore / Execute **兩階段都派 subagent**，user 核准 gate 不變）；「並行處理」條的
     **「（限唯讀）」與「寫入嚴格序列化、一次一檔」原文未動**（正交，見該條 ✅ 註）。
  2. §3「探索 / 稽核階段若牽涉**超過 5 個檔案**，主動拆子任務並行 Explore agent」——
     舊條拿檔案數當派工門檻；**§-2 規則 5 明文否定「這件事小到不用派工」這種判斷**
     （實證見上：三次實質錯誤全出在被判定為小的改動）。**門檻取消，一律派工。**
     **處置**：`PROCESS.md` §3「並行處理」條**僅將「若牽涉超過 5 個檔案，」一段加刪除線**，
     句子其餘部分原文未動；並補註依 §-2 規則 4，調查 / 稽核須多組視角、不可自己查自己。

---

## §-1. 工作準則(凌駕 §0~§8;本節之上另有 §-2)

> 2026-06-24 user 明確要求:**「沒實際 bug / 沒具體需求 → 不要動」**

**AI 提議任何新工作前,必須先驗證**:
1. ❓ 這個項目 user 實際在用嗎?
2. ❓ 是真實 bug 觸發,還是只是 BACKLOG / CLAUDE.md 待議標籤?
3. ❓ ROI 對 user 的工作流程有具體幫助嗎?

**任一答 No → WONTFIX,不該提議**

**禁止的提議模式**:
- ❌ 因為 BACKLOG / CLAUDE.md 寫了就提議
- ❌ 因為「審計清單裡的 TODO」就推
- ❌ 機械式清 TODO list 充數
- ❌ 把「文件待議」當必做項
- ❌ 把「未完成項目?」當作要主動找事做的訊號

**允許動工的觸發**:
- ✅ user 主動要求新功能 / bug fix
- ✅ 跑測試 / 使用時遇到實際錯誤
- ✅ 既有功能維護(security / 依賴升級必要)

**標準 default 回應**:user 沒明確指派時 → **停手等指令**,不主動找事。

---

## §0. 填寫紀錄（首次填寫 2026-06-22；v3 升級 2026-06-22 新增 §8；步驟 4 收尾 2026-06-23）

> Bootstrap 流程全 4 步完成,§0 已從「BOOTSTRAP 紀錄」改名為「填寫紀錄」。
> 完整收尾證據按時序記錄如下。

**步驟 1｜探查專案** — 已完成,三組並行 Explore agent 掃描,涵蓋：
- meta-docs（README/STATE/ARCHITECTURE/SPEC/DATASTATION/STRATEGY_MANUAL/MACRO_CALIBRATION）
- 27 個外部資料來源 endpoint + 單位 + 發布延遲 + 修正風險
- 14 類門檻常數 + 10 大單位陷阱 + TTL 對照表 + 時區/日曆使用

**步驟 2｜填寫待填欄位** — 已完成,以下節次依現有 code 證據填妥（每條附 `file:line`）：
- §2.1 SSOT 5-Tier 27 來源權威分級
- §2.3 Point-in-Time 各源發布延遲 + 修正風險表
- §2.4 Freshness max_age 對照（依 `shared/ttls.py` + macro_core 常數）
- §3.1 Schema 主要 DataFrame 表（待議：是否導入 pandera）
- §3.2 範圍 / 合理性檢查（依 `MACRO_THRESHOLDS` + 領域知識）
- §3.3 反捏造 — 14 類 magic number 盤點（含 SSOT vs inline 標記）
- §3.4 Benford 適用性判斷
- §4.1 8 大單位陷阱
- §4.2 不變量斷言
- §4.4 Welford 適用性判斷
- §4.5 時序對齊（**無**第三方 trading calendar lib）
- §4.6 領域邊界（9 種 TW 股市特有狀態）
- §8 架構先行 — 7 層分層 + 5 條硬規則 + 3 處灰色地帶（v3 增補,evidence: ARCHITECTURE.md §1-§7 + SPEC.md §5）

**步驟 3｜回溯稽核** — 已完成,違憲清單分高/中/低三級;以下 W 系列 + S-H 系列 PR 逐一收斂：
- W1（v18.241 群 A/B/C）：14 處 SSOT 抽出 + EX-CACHE-1/EX-L0-1/EX-AI-1 例外登記（EX-AI-1 v18.399 已退役）
- W3a/W3b（#253）：4 處 inline magic SSOT 抽出 + 收斂 §3.3 表
- W4（#252）：刪死碼 get_nas_proxy 群
- W5-1（#254）：data_loader 5 處 except:pass 收窄 + log
- W5-2（#255）：9 處 except/empty 補 log + 註解
- W5-3（#256）：tw_stock_data_fetcher 加註 §8.2.A EX-CACHE-1+EX-L0-1 例外
- S-H1/H3/H4/H5/H6（#257）：Stock §8.2 5 項違憲全結案
  - S-H4：merrill_clock fetch_pmi_history 下沉 tw_macro（L2→L1 重構）
  - S-H1：data_loader 死碼 safe_fetch_strict 刪除
  - S-H3：etf_fetch 4 處 st.error/warning/session_state → print + module-level dict + accessor
  - S-H5/H6：app.py + etf_dashboard 直呼 L1 → EX-PASSTHRU-1 例外登記（類比 Fund F-H6）

**步驟 4｜收尾** — 已完成。
- §3.3 反捏造 ❌ 0 項（原 14 類 magic number 全 SSOT 化）
- §8.2 高項違憲 0 項（S-H1/H3/H4 真重構；S-H5/H6 EX-PASSTHRU-1 例外登記）
- §8.2.A 例外清單：EX-L0-1 / EX-CACHE-1 / EX-PASSTHRU-1 / EX-OAUTH-1(v18.431 補登)(EX-AI-1 + EX-RENDER-1 已退役)
- 證據：全部 commit history + PR description 保留於 origin/main。

---

## §1. 最高原則：Fail Loud, Never Fake（寧可炸掉,不可造假）

凌駕一切的鐵律。錯誤的數字比沒有數字更危險。

當缺資料、外部呼叫失敗、值異常、或假設無法成立時：

- ✅ **一律 `raise` 並清楚說明**（哪個來源、哪幾筆、為什麼）
- ❌ **禁止**用以下手段讓流程「看起來成功」：
  - `fillna(0)` / 填入任意預設值
  - 無說明的 `ffill` / `bfill`
  - 回傳 dummy / example / 範例資料
  - `except: pass` 或吞掉例外
  - 自行「估一個合理值」當常數
- ⚠️ 任何填補**必須**：(1) 顯式呼叫、(2) 寫入 log、(3) 在輸出帶旗標（如 `is_imputed`）

> **判斷準則**：若你正打算寫一段「讓程式不報錯」的程式碼,先問：
> 「這是在**解決**問題,還是在**掩蓋**問題？」掩蓋 = 違憲。

---

## §2. 資料層（Data Integrity）

### 2.1 SSOT — 單一權威來源

**來源註冊清單 SSOT**：`data_registry.py`（dataset → endpoint → 權威分級對映）+ `macro_core.PMI_SOURCE_REGISTRY`（macro_core.py:1262, v18.240）+ `tw_macro.CBC_MS1_URLS`（tw_macro.py:74）。

**5-Tier 權威分級**（衝突時上層贏,**禁止平均**）：

| Tier | 等級 | 來源範例 | Evidence |
|---|---|---|---|
| **T1** | 官方政府/央行 API | FRED, TWSE OpenAPI, TPEX OpenAPI, TAIFEX, CBC ms1.json, data.gov.tw, MOF, MOPS, BLS, IMF | macro_core.py:51-53, data_registry.py:125-156,228-275 |
| **T2** | 商用聚合 API（帶 API key） | FinMind, DBnomics, Yahoo Finance query1 | data_registry.py:228-275, requirements.txt:16 |
| **T3** | 第三方網站（HTML 抓） | CIER, NDC, StockFeel, MacroMicro, Goodinfo, HiStock/Wearn, MoneyDJ, Cnyes, ISM | macro_core.py:557-558,816,939-1041,1108,1222 |
| **T4** | News RSS（非數值,僅文本） | Google News, Reuters, Bloomberg, CNBC, Yahoo News | data_registry.py:398-425 |
| **T5** | User config / AI | Google Sheets（portfolio）, Gemini API（synthesis only） | gsheet_portfolio.py, ai_engine.py |

**關鍵衝突裁決**：
- **M1B/M2**：CBC（TWD）主、IMF（USD）備 → **禁止跨幣別平均**,IMF 僅作 CBC 全敗 fallback（evidence: data_registry.py:345-350）
- **TW PMI 多源**：依 `PMI_SOURCE_REGISTRY` 順序賽跑,取第一個命中（CIER-EN > data.gov.tw > NDC > CIER首頁 > StockFeel > Cnyes > CIER-cid8 > MoneyDJ,共 8 源）。**不平均**（evidence: macro_core.py PMI_SOURCE_REGISTRY, SPEC.md §4）。⚠️ v19.86 更正：原第 8 順位 FinMind 段（打 dataset `TaiwanEconomicIndicator`）已於 v19.85 拔除 — 該 dataset **不存在於 FinMind**（SDK 2.0.4 枚舉 + 官方文件皆無此名）。FinMind 無 PMI 資料集可替換。⚠️ v19.113 拔除 MacroMicro 段 + CIER cid=21 列表 URL — 探針 run 29182317622（美國 IP + NAS proxy）實錘兩者無回應（macromicro.me host 級攔截、cid21 頁下架）;CIER 段改僅掃首頁。
- **TW NDC 景氣燈號**：FinMind `TaiwanBusinessIndicator`（國發會官方鏡像,含 monitoring 分數 + monitoring_color 燈號 + leading 領先指標）為主 → StockFeel → MacroMicro 備援（v19.85；原「舊源全廢改抓第三方」中的 FinMind 判定為誤診,真名 TaiwanBusinessIndicator 一直可用）
- **US PMI**：FRED（NAPM/ISPMANPMI）> DBnomics（ISM/pmi）> ISM 官網 > MacroMicro（evidence: macro_core.py:557-617）
- **VIX**：Yahoo `^VIX` 主、CBOE CDN 備
- **TW 月營收**：FinMind 主、MOPS 備、Goodinfo 第三（evidence: data_registry.py:276-293）
- **TW 融資餘額**：TWSE 主 → HiStock → Wearn（evidence: data_registry.py:430-449）
- **TW 季報**：FinMind 主、MOPS 備、Goodinfo 第三

### 2.2 Provenance — 血緣追蹤

**目標模型**（template 範例）：
```python
@dataclass(frozen=True)
class DataPoint:
    value: float
    source: str            # 來源識別（e.g. "FRED:CPILFESL", "CBC:ms1.json"）
    fetched_at: datetime   # UTC,抓取當下
    as_of: date            # 資料歸屬日（≠ 抓取日,極重要）
```

**現況**：本專案**尚未**統一以 `DataPoint` 攜帶 provenance,多以 `DataFrame + meta dict / failure token` 方式承載。
- macro 失敗以 token 字串（如 `"FAIL:CIER:timeout"`）回傳供診斷（SPEC.md §4）
- proxy_helper 的 cache layer 攜帶 `X-Cache-*` header 作為來源追蹤
- ✅ **S-PROV-1 v18.246 第 1 階段**:`macro_core.fetch_fred()` 已加 `source` + `fetched_at` 兩欄(schema-additive,既有 caller 無感)。其他 fetcher(`fetch_yf_close` / FinMind / TWSE / CBC 等)後續逐步補上。

### 2.3 Point-in-Time — 防 Lookahead

本專案**無傳統歷史回測**(v18.265 移除 `backtest_engine.py` / `tab_backtest_optimization.py` / `etf_tab_backtest.py` — 因只有現存公司快照 + 短歷史,回頭測必踩 lookahead + 存活者偏誤)。**改採前進式驗證(Forward-test,v19.141~148)**:凍結當下選股 → 事後真實現價對帳 vs 0050(`src/compute/screener/forward_test.py` L2 + `services/forward_test_service.py` L3),**零 lookahead、零存活者偏誤**(都是當下真實決定 + 事後真實現價)。**v19.147 自動化**:`scripts/update_forward_test_freeze.py` + `.github/workflows/update_forward_test.yml` 每月自動凍結(走與選股網畫面同源的 L3 `get_ranked_picks`)→ 落地 git 追蹤 `data_cache/forward_test/picks.parquet`(L1 `forward_test_store.py`);對帳讀「本地 ∪ Google Sheet」去重。解原本「手動 + 只存私人 sheet → 0 樣本」卡關。macro 校準歷史驗算(`scripts/calibrate_macro_traffic.py`,v18.359 F-2 搬入 `scripts/`)仍須遵守 PIT,**禁止 lookahead**。(v19.181 detox：未接線的 `tw_backtest.py` 拐點驗證死碼已移除 —— 前進式驗證 forward_test 才是現行的驗證路徑。)

**各來源發布延遲 + 修正風險**:

| 來源 | 指標 | 發布延遲 | 修正風險 | PIT 對齊鍵 |
|---|---|---|---|---|
| FRED | CPI / NFP | 月後 ~13 天 | **是**(隨後 1-2 月常修) | release_date,**禁止**用 observation_date |
| FinMind | 季財報 | 季後 ~45 天 | **是**(審計修正) | 公告日 |
| FinMind | 月營收 | 月後 ~10 天 | 低 | 公告日 |
| FinMind | 月度 PMI | 月後 ~5-10 天 | 低 | 公告日 |
| CIER / data.gov.tw | TW PMI | 月後第 1 營業日 | 無 | 發布日 |
| CBC | M1B/M2 | 月後 ~5-7 天 | **未明**(待 audit) | 公告日 |
| MOF | 進出口 | 月後 ~8-10 天 | **是**(後續月修 ±5%) | 公告日 |
| TWSE / TPEX | 收盤行情 / 法人 | 同日盤後 ~14:30 TW | 低 | 交易日 + 17:00 後可信 |
| TAIFEX | 期貨 / 選擇權 / PCR | 同日盤後 ~14:00 TW | 無 | 交易日 |
| Yahoo Finance | OHLCV | EOD 16:00 ET ≈ 翌日 04:00 TW | 無 | 交易日(TW 用 T+1 才齊) |
| IMF | M1B 備援 | 月後 1-2 月 | 可能 | 公告日 |

**對齊規則**:
- FRED CPI 用 `release_date` 而非 `observation_date`(修正後值不可回填到過去決策)
- 季財報用「公告日」(45 天後)對齊,**不可**用季末日
- 跨市場 merge_asof 用 backward + tolerance="40d"(macro_core.py:1336)

### 2.4 Freshness — Max Staleness

依 `shared/ttls.py`（SSOT for `@st.cache_data(ttl=N)`）+ macro_core 額外常數：

| TTL 常數 | 數值 | 適用範圍 | Evidence |
|---|---|---|---|
| `TTL_15MIN` | 900 s | Intraday risk metric, optionality PCR | shared/ttls.py:24 |
| `TTL_30MIN` | 1800 s | 三大法人 / 融資 / PCR / 期貨 OI | shared/ttls.py:25, data_config.py:20-21 |
| `TTL_1HOUR` | 3600 s | 報價 / 財報 / macro snapshot | shared/ttls.py:26, data_config.py:22 |
| `TTL_2HOUR` | 7200 s | ETF NAV history | shared/ttls.py:27 |
| `TTL_6HOUR` | 21600 s | 月營收掃描 / 出場訊號 | shared/ttls.py:28 |
| `TTL_1DAY` | 86400 s | 持股 / 評等 / 績效 / 股利歷史 | shared/ttls.py:29, data_config.py:24 |
| `TTL_3DAY` | 259200 s | TW 原始月營收 fetch | shared/ttls.py:30 |
| `TTL_7DAY` | 604800 s | 經理人 / 中文名 | shared/ttls.py:31 |
| `_MACRO_CACHE_TTL_DAYS` | 90 days | PMI / 進出口 fallback 過期快取 | macro_core.py:59 |
| `_FRED_RELEASE_CACHE_TTL_DAYS` | 30 days | FRED 下期發布表 | macro_core.py:63 |
| `_FRED_TTL` | 1800 s | FRED API module-level | macro_core.py:238 |
| `_YF_CLOSE_TTL` | 3600 s | Yahoo Finance close | macro_core.py:302 |

**規則**：超過 TTL 應**重新抓取**;若上游全敗,過期 cache 回傳須帶 `is_stale` 旗標,**禁止**靜默返回。

---

## §3. 驗證層（Validation）

### 3.1 邊界契約（Schema）

**現況**（v19.159 團隊稽核同步）：`pandera>=0.20,<2.0` **已 pin 於 requirements.txt:44**。DataFrame schema SSOT 統一於 `shared/schemas.py`（L0,v19.159 Batch C 併回原 `compute/risk/schemas.py`）：MacroFred / OHLCV / MonthlyRevenue / MacroDF / PMI / ForeignFlow + `validate_in_log_mode`(log-only) / `validate_or_reject`(blocking)。**opt-in**：fetcher 在出口主動呼叫,pandera 缺席時 graceful degrade（不阻斷）。其餘散落 dict / df parse 斷言仍逐步收斂中。

**規範**：新增資料流入 / 流出系統的點,**必須**附等效斷言（即使尚未引入 pandera）：

```python
# price_df (股價 OHLCV) — TWSE / Yahoo / FinMind 共通
{
    "date":   DatetimeIndex, ascending=True, unique=True,
    "open":   float >= 0, non-null,
    "high":   float >= 0, non-null,
    "low":    float >= 0, non-null,
    "close":  float >= 0, non-null,
    "volume": int >= 0,   non-null,
}
# 不變量: low <= open/close <= high, low <= high

# pmi_df (TW / US PMI)
{"date": ..., "pmi": float in [30, 70]}   # v18.359 起改自 shared/signal_thresholds.py:139-143(原 merrill_clock.py:107 已下沉 + 該檔已刪)

# macro_df (FRED / CBC / generic macro)
{"date": ..., "value": float, "source": str, "as_of": date}

# monthly_revenue_df (FinMind / MOPS)
{"date": ..., "revenue_twd": float > 0}

# institutional_flow_df (TWSE 三大法人)
{"date": ..., "foreign_twd": float, "trust_twd": float, "dealer_twd": float}
```

✅ **已定案**（v19.159）：pandera 已 pin + 6 個 schema 落地 `shared/schemas.py`(L0),8 處 L1 fetcher 出口採 opt-in log-mode / blocking 驗證。逐 fetcher 全面強制驗證仍屬漸進（避免一次性破壞既有契約）。

### 3.2 範圍 / 合理性檢查

| 指標 | 合理範圍 | Evidence |
|---|---|---|
| PMI（採購經理指數） | [30, 70] | shared/signal_thresholds.py:139-143(v18.359 merrill_clock.py 已刪,原 inline 已下沉至此) |
| VIX | [5, 100] | macro_core.py:215 thresholds |
| CPI YoY (%) | [-5, 20] | macro_core.py:216 |
| US10Y (%) | [0, 20] | macro_core.py:217 |
| DXY（美元指數） | [70, 130] | macro_core.py:218 |
| HY OAS (%) | [1, 25] | macro_core.py:220 |
| 殖利率差 10Y-2Y / 10Y-3M (%) | [-3, 5] | macro_core.py:221-222 |
| M2 YoY (%) | [-10, 50] | macro_core.py:223 |
| Fed BS YoY (%) | [-30, 30] | macro_core.py:224 |
| 健康評分 | [0, 100] | macro_helpers.py:24-25 |
| RSI | [0, 100] | config.py:52-53 |
| ATR | > 0 | strategy 層必要 |
| 月營收（個股） | > 0 | (停業時應為 NaN 而非 0) |
| 三大法人單日買賣超 | < 該股 30D 均量 × 5 | ✅ helper + wiring 皆已落地(`src/compute/risk/inst_sanity.py`:`is_inst_net_outlier` + `flag_inst_net_outliers_batch` + `flag_latest_inst_outlier_from_df`,SSOT `INST_NET_OUTLIER_VOLUME_RATIO=5.0`,30 測試)。**v19.135 wire 進 `section_chips_20d`**(舊註「現無 fetcher 同時持 inst_net+30D 均量」已過時 — consumer 端 `df2` 本就同時持 `主力合計`+`volume`,同為張免換價),outlier 時顯示徽章 |

**領域不變量**（calculation-side）：
- OHLC: `low ≤ open/close ≤ high`, `volume ≥ 0`
- date 軸單調遞增
- 6-factor 健康評分 ∈ [0, 100]
- 權重和 ≈ 1.0（健康評分、ETF 權重）

### 3.3 反捏造（Anti-Fabrication）

**禁止 inline magic number**,以下常數**必須**從 SSOT 引入,絕不可腦補：

| 常數類別 | 值 | SSOT 位置 / 現況 | 違憲狀態 |
|---|---|---|---|
| `MACRO_THRESHOLDS`（10 項） | 各 zone 邊界 | macro_core.py:214-225 | ✅ SSOT |
| `YIELD_HIGH/MID/LOW` + `_DEC` | 7.0/5.0/3.0% + 0.07/0.05/0.03 | shared/thresholds.py:21-27 | ✅ SSOT |
| `HEALTH_DEFENSE_THRESHOLD` | 35（[20,60] 可調） | macro_helpers.py:24, macro_thresholds.json | ✅ SSOT + config |
| `BULL_MIN_SCORE` | 4/6（[1,6] 可調） | macro_helpers.py:25 | ✅ SSOT + config |
| `HEALTH_GRADE_A/B_MIN` | 80 / 50 | shared/health_thresholds.py:19-20 | ✅ SSOT |
| `RSI_OVERBOUGHT/OVERSOLD` | 70 / 30 | config.py:52-53 | ✅ SSOT |
| `LEEK_HIGH/LOW` | 35 / 10 | config.py:69-70 | ✅ SSOT |
| `BULLRUN_VOL_THRESHOLD` | 1.3× | config.py:73 | ✅ SSOT |
| ~~`_CPI_THRESHOLD` (merrill clock)~~ | ~~2.0%~~ | ~~merrill_clock.py:56~~(v18.359 F-4 已刪) | ⚪ 退役 |
| `ANNUAL_MA` | 240 trading days | config.py:14 | ✅ SSOT |
| `signal_thresholds.*`（76 個語意常數） | 252 / 健康評分加權 / 4 個 TW 麥邊閾值 / VIX/Foreign futures / ATR%/MA20/合約負債/ETF 折溢價 / Recession logit / PMI 有效範圍 / merge_asof 40d / trend lookback 6 / 個股組合操作狀態燈+多因子評級+入選70+利空信心50 / **scoring_engine 全評分曲線+交易濾網斷點(MOM_/RISK_/RS_/SQ_/FGMS_/LEAD_/CL_/BOLL_/FAKEOUT_/RR_/ATR_STOP_/TIME_STOP_/VCP_/SQUEEZE_/POS_ 共 50 個)** 等 | shared/signal_thresholds.py v18.241→v18.324 | ✅ SSOT（v18.322 補 7 個股組合,詳見 SPEC §12；v18.324 補 50 scoring_engine 全抽,前綴分名防同數字不同義耦合,詳見 SPEC §14） |
| `financial_health_thresholds.FH_*`（19 個財報體檢門檻；v19.174 前綴自 `MJ_*` 改名,舊名保留 alias） | 現金 25/10 / DSO 15/90 / 100-100-10 / 負債 40/60/70 / 流動·速動 300/150 / 毛利 40 / 安全邊際 60 / 淨利 10 / ROE 15 / 杜邦槓桿 65 / 盈餘品質 100 等 | shared/financial_health_thresholds.py v18.323 | ✅ SSOT（financial_health_engine 6 個 `_no_ai_*` code 端引入；prompt 端由 golden test 釘一致；含 3 漂移修正,詳見 SPEC §13） |

❌ 標記 **0 項**(原 8 項已全數 W3a/W3b 收斂)。

**其他規則**：
- `fillna` / `ffill` / `dropna` 必須顯式呼叫 + log 受影響筆數
- 測試資料與正式路徑物理隔離（pytest fixtures 不可流入 production fetcher cache）
- `except: pass` 一律違憲;`except Exception as e:` 至少要 log + 往上拋或回傳 fail token

### 3.4 統計異常偵測

- **IQR**（穩健,優先用）：**適用** — VIX / HY spread / 個股 vol 為厚尾資料
- **Z-score**（近常態時）：**部分適用** — CPI、PMI 近常態,適用;個股報酬率非常態,**不適用**
- **Benford's Law**：**不適用** — 本專案資料皆官方/聚合 API（FRED/TWSE/FinMind/CBC etc.）,**無人為申報原始資料**。Benford 適用於財報捏造偵測,本專案下游(MOPS 季報)雖含申報資料但已經官方審核,且當前無此偵測需求

---

## §4. 計算層（Computation Correctness）

### 4.1 量綱 / 單位陷阱

| 陷阱 | 描述 | Evidence |
|---|---|---|
| **百分比 vs 小數** | `YIELD_HIGH=7.0`(%) vs `YIELD_HIGH_DEC=0.07`,呼叫端混用 = 100× 誤差 | shared/thresholds.py:21-27 |
| **元 vs 百萬元 vs 億** | FinMind margin 用「元」,macro signal threshold 3400 用「億」(`/1e8` 轉換) | shared/signal_thresholds.py `MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI=3400` + shared/margin_schema.py（元→億 /1e8）(v19.181 detox 前為 macro_signal_lookback_tw.py) |
| **TWD vs USD** | CBC M1B（TWD）vs IMF M1B（M USD）**禁止平均**,IMF 僅作 fallback | data_registry.py:345-350 |
| **YoY vs MoM** | CPI 用 YoY (%);PMI 用月度 level;merrill_clock 用 CPI YoY | merrill_clock.py:5,133, macro_core.py:216 |
| **名目 vs 實質** | CPI 預設名目;尚未實作實質報酬轉換（待後續需求） | — |
| **交易日 vs 日曆日** | `pct_change(20)` = 20 交易日 ≈ 4 週,**非** 20 日曆日 | shared/signal_thresholds.py `TRADING_DAYS_PER_YEAR=252`（交易日常數；通則）(v19.181 detox 前為 macro_signal_lookback_tw.py) |
| **TW 時區 vs UTC** | Yahoo Finance EOD 為 UTC;TWSE/CBC/TAIFEX 為 TW 時間 (UTC+8) | app.py:47, daily_checklist.py:131 |
| **點數 vs 百分比** | M1B-M2 gap 用「點/月」差分（diff()）,**非** %  | shared/signal_thresholds.py `M1B_M2_GAP_DETERIORATION_THRESHOLD=-2.0`（單位 pts/月）(v19.181 detox 前為 macro_signal_lookback_tw.py) |

**命名規範**：新增變數**必須**編碼單位,例：`rate_pct` / `rate_ratio` / `amount_twd` / `amount_twd_m`（百萬）/ `amount_twd_yi`（億）/ `qty_shares` / `count`。

### 4.2 不變量斷言

```python
# OHLC 鐵則
assert (df["low"] <= df["open"]).all() and (df["low"] <= df["close"]).all()
assert (df["high"] >= df["open"]).all() and (df["high"] >= df["close"]).all()
assert (df["low"] <= df["high"]).all()
assert (df["volume"] >= 0).all()

# 時序
assert df["date"].is_monotonic_increasing, "時序未排序"
assert df["date"].is_unique, "日期重複"

# 健康評分
assert 0 <= health_score <= 100, "score 越界"
assert math.isclose(sum(factor_weights), 1.0, abs_tol=1e-9), "權重未歸一"

# PMI（merrill_clock 已實作）
assert df["pmi"].between(30, 70).all() or df.empty   # evidence: merrill_clock.py:107

# 月營收
assert (df["revenue"] > 0).all() or df["revenue"].isna().all(), "營收應為正或全 NaN"

# 利差合理
assert (us10y_spread.abs() < 5).all(), "10Y-2Y/3M spread 異常"
```

### 4.3 重算對帳（Reconciliation）

**現況雙源備援**已在 §2.1 衝突裁決列明（M1B/M2、PMI、VIX、月營收、融資、季報）。**雙演算法**待落地：
- **健康評分**：目前單一 path（`macro_helpers.compute_macro_health`）,缺對照演算法 → 步驟 3 audit 後補
- **月營收 YoY**：`(本月 / 12 月前) - 1` vs FinMind 預算 YoY 對帳
- **殖利率**：FRED DGS10 vs Yahoo `^TNX` (TNX = 10Y × 10) 對帳

**浮點比較**：**禁止 `==`**,一律：
```python
math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
np.isclose(a, b, rtol=1e-9, atol=1e-12)
```

### 4.4 數值穩定性

- **log 空間連乘**：cumulative return（(1+r1)(1+r2)...）建議改 `exp(sum(log(1+ri)))`,本專案 backtest 路徑須檢查
- **災難性抵消**：yield spread (10Y-2Y) 兩值尺度接近,計算精度要保留 float64
- **Welford 變異數**：**部分適用** — 現用 pandas `rolling().std()`（內部 Welford-friendly 實作）,**單序列**無需顯式;批次處理 N×T 大序列時可考慮顯式 Welford
- **大數除以小數**：估值倍數（PE = price / EPS）當 EPS 接近 0 時須 guard（return NaN 或 inf,不可 silent ÷0）

### 4.5 時序對齊

**日曆 / 時區決策**：
- **不使用**第三方 trading calendar lib（無 pandas_market_calendars / exchange_calendars 在 requirements.txt）
- 用 Python std `datetime.timezone(timedelta(hours=8))` 統一表示 TW 時間（evidence: app.py:47, daily_checklist.py:131, macro_state_locker.py:352, nas_server.py:66,279）
- **本地時區**：Asia/Taipei (UTC+8)
- **存儲規則**：時間戳一律 UTC（或 TZ-aware UTC+8）,顯示時轉本地

**業務時點**：
- TWSE 同日盤後 ≈ 14:30 TW（17:00 後資料完整）
- TAIFEX 同日盤後 ≈ 14:00 TW
- Yahoo Finance EOD ≈ 16:00 ET → 翌日 ~04:00 TW
- CBC ms1 monthly 月後 ~5-7 天
- GitHub Actions cron `update_macro_history.yml:15` 設 UTC 09:00 = TW 17:00（收盤後）✅
- `recalibrate_macro.yml:15` 每季首日 UTC 00:00（1/4/7/10 月）

**resample 安全性**：
- 已用 `"ME"`（月底）/ `"QE"`（季底）/ `"YE"`（年底）/ `"W-SUN"`（週,錨定週日;v18.461 自 `"W"` 改,right-closed 不變）
- 預設 `closed=right, label=right` — 月底資料 label 為 `"YYYY-MM-31"`,**不會**引入未來資料
- audit 須驗證所有 resample 呼叫的 label/closed 是否一致

⚠️ **無業務還原調整**：本專案不涉及匯率轉換 / 股本回填 / 借券稅後還原,直接用源數據（**不適用** §4.5 業務調整子項）。

### 4.6 邊界條件

**通用**：空資料集 / 單筆 / 全空值 / 欄位剛建立。

**TW 股市 / Macro 領域特有**（必測）：
- **新上市股票**：歷史不足 60 天 → 健康評分應降可信度旗標
- **停牌股票**：連續 N 天無價格 → **不可** ffill,旗標 `is_halted=True` 並 raise 或顯式 skip
- **跨年除權息**：價格跳空 → 用還原價（dividend-adjusted）
- **跌停 0 vol**：有 close 但 vol=0 → 視為有效報價(不可丟掉)
- **月營收三態**：剛公布 / 等公布 / 永久缺（已停業）— 三種狀態須區分,不可一律 `fillna(0)`
- **PMI 多源同月不同數**：依 `PMI_SOURCE_REGISTRY` 順序取第一個命中,**禁止平均**（macro_core.py:1262）
- **多市場休市**：US 假日 ≠ TW 假日,`merge_asof` 跨市場時用 `direction="backward"` + `tolerance="40d"` (macro_core.py:1336)
- **FinMind quota 用罄**：fallback 鏈須完整（MOPS → Goodinfo → HiStock → Wearn）
- **proxy 失效 / 直連 / 407**：`proxy_helper.fetch_url` 已實作降級鏈（NAS Squid → 直連 → fail）

---

## §5. 流程層（Process）

- **冪等性**：同輸入重跑得同結果;重抓不產生重複筆。
- **可重現性**：固定隨機種子、pin 套件版本（注意 requirements.txt 多為 floor-only,backtest 場景須補版本 pin）；歷史運算用**凍結快照**(`data_cache/` parquet）而非即時來源。
- **可觀測性**：每次 pipeline 輸出資料品質指標（缺失率、被填補筆數、outlier 數）,異常告警。
- **效能**：向量化運算,避免隱性逐列迴圈；說明複雜度。

---

## §6. AI 自審清單（每寫完一段主動執行,勿等問）

```
□ SSOT；關鍵數值帶 provenance（source / fetched_at / as_of）
□ 無 inline magic number；常數從 shared/* 或 config.py 引入
□ 缺值顯式處理且 log；無 fillna(0) / 沉默 ffill / except:pass
□ 邊界已測：空集 / 單筆 / 全空值 / 新上市 / 停牌 / 跨年除權息 / 跌停 0 vol / PMI 多源 / FinMind quota / proxy 降級
□ 量綱一致：% vs ratio / TWD vs USD / 元 vs 億 / YoY vs MoM / 交易日 vs 日曆日 / TW vs UTC
□ 無 lookahead：FRED CPI 用 release_date 非 observation_date；季財報用公告日
□ 時序對齊：TW 收盤 14:30 / Yahoo EOD 翌日 / merge_asof tolerance="40d" / resample label 右閉
□ 浮點比較用容差（math.isclose / np.isclose）,非 ==
□ 關鍵指標有第二種算法對帳（健康評分 / 月營收 YoY / 殖利率）
□ 不變量斷言（OHLC / date monotonic / 權重和=1 / PMI∈[30,70]）
□ 向量化,無隱性逐列迴圈
```

最後另外提供：**3 個最容易讓這段程式出錯的輸入**,並寫成測試（單元 + property-based + golden test）。

---

## §7. 新功能動工前對齊

我交付新功能時,你**動手寫程式前**先回答：

1. 資料來源是哪個 endpoint？欄位單位是什麼？（對照 §2.1 表格 + §4.1 單位陷阱）
2. 這資料有發布延遲 / 回溯修正嗎？該用哪個「可用日」對齊？（對照 §2.3 表格）
3. 有哪些邊界要處理？（對照 §4.6 + §3.2 範圍表）
4. 計算式先用**數學式**寫給我確認,再寫程式。

先別寫 code,我們先對齊這四點。

---

## §8. 架構先行 — 涉及新模組 / 多檔案 / 改變資料流時

§7 對齊的是「資料」；本節對齊的是「架構」（模組怎麼切、誰依賴誰、資料怎麼流）。

**觸發條件**：新增模組、跨多檔案、或改變資料流。
**不觸發**：單檔小修、純 bug fix、改字串、typo、版本字串 bump — 直接做,避免儀式性開銷。

### 8.1 通則 — 先設計、自評過度設計、經核准才寫

動工前先提交架構規劃（文字 + 簡單流程圖）,**這一步禁止寫 code**：

1. 這個功能 / 模組的**單一職責**一句話講完。
2. 該切成哪幾個模組 / 檔案？各自職責？
3. **資料流向**：從哪進 → 經過哪幾層 → 從哪出。
4. **依賴方向**：誰依賴誰？有無違反分層？
5. **失敗降級**：外部來源失敗時這個架構怎麼辦（fail loud 還是有備援）？
6. **自評過度設計**：對「當前需求的規模」會不會太重？用不到的抽象 / 分層標「**先不做,等真的需要再加**」。給最簡單能滿足需求的版本,不是最完整的。

### 8.2 本專案分層與依賴硬規則（evidence: ARCHITECTURE.md §1-§7 + SPEC.md §5）

**7 層架構**(由低到高)：

> ⚠️ **不寫 LOC / 檔數**(v19.180 稽核修正)。原文寫「~21,323 LOC 跨 19 核心模組」— 該數字沿自
> `ARCHITECTURE.md §1.4`(v7.1 歷史表),實測 repo `**/*.py` 為 **545 檔**(量測日 2026-08-07),
> 差距 28 倍。規模數字每次重構就失真,且沒有任何判斷依賴它 → 一律不寫在憲法裡;
> 需要規模數字時**現場量測**,不引用本檔。下表「代表檔案」只列**判斷分層歸屬時的錨點**,
> 不求窮舉(窮舉必然漏、必然過期;窮舉的工作交給 `tests/test_c3_layering_guard.py`)。

| 層 | 職責 | 代表檔案 |
|---|---|---|
| **L0 Infra** | 常數 / TTL / 門檻 / 全域 config | `src/config/{config,data_config,persona,stock_names}.py`(v18.359 F-6.1 搬入)、`shared/ttls.py`、`shared/thresholds.py`、`shared/health_thresholds.py`、`shared/fred_series.py`、`shared/roc_calendar.py`(民國↔西元 SSOT,B3 v19.152)、`shared/finmind_subject_aliases.py`(FinMind 科目別名 SSOT,B4 v19.152) |
| **L1 Data** | 外部資料抓取 / 快取 / proxy | `data_loader.py`(B8 v19.155-156 拆分 2545→1734:抽出 `financial_statements_fetcher.py`(財報體檢原始數據,B8-a)+ `data_loader_inst_fetchers.py`(TWSE/TPEX 三大法人 fallback,B8-b),皆同 `src/data/core/`,套件 __getattr__ / import-back 轉發介面不變)、`data_registry.py`、`proxy_helper.py`、`scripts/update_macro_history.py`(cron CLI,v18.359 F-2 搬入)、`scripts/update_forward_test_freeze.py`(前進式驗證每月凍結 cron CLI,v19.147)、`tw_macro.py`、`macro_core.py`、`leading_indicators.py`、`etf_fetch.py`(含 `fetch_etf_close_history`,B7-a 從 UI 下沉)、`tw_stock_data_fetcher.py`、`src/data/portfolio/forward_test_store.py`(前進式驗證本地落地 parquet,v19.147) |
| **L2 Compute** | 純函式運算 / 評分 / 策略 / 風控 | `scoring_engine.py`、`v4_strategy_engine.py`、`v5_modules.py`、`macro_helpers.py`、`etf_calc.py`、`etf_quality.py`、`risk_control.py`、`exit_signals.py`(含 `compute_macd` + `weekly_macd_hist` MACD SSOT kernel,B6 v19.153)、`compute/screener/{fundamental_prescreen,shortage_screener,rs_leader_screener,cross_quarter_trends,forward_test}.py`、`compute/risk/{risk_contribution,risk_radar,concentration}.py`(⚠️ `risk_radar` 見 §8.2.A.2 **V-RADAR-1**)(~~`merrill_clock.py`~~ v18.359 F-4 已刪;~~`macro_signal_lookback_tw.py`~~ v19.181 detox 已刪（連同 `macro_validation_tw` / `signal_threshold_optimization` / `multi_factor_optimization` / `tw_backtest` 封閉死簇一併移除）) |
| **L3 Service** | 業務邏輯編排 / AI 整合 / 摘要 | `market_strategy.py`、`ai_structured_summary.py`、`daily_checklist.py`、`macro_state_locker.py`(① 接線 v19.148:`get_macro_state` canonical 總經契約 + `normalize_regime` 中→英)、`services/{fundamental_screener_service,rs_leader_service,shortage_screener_service,forward_test_service}.py`(選股網編排,v19.14x;`fundamental_screener_service.get_ranked_picks` = 畫面/cron 同源排名,v19.147)(~~`ai_engine.py`~~ P5-DEAD-δ 已刪、~~`unified_decision.py`~~ F-4 已刪) |
| **L4 Render** | 圖表生成 / 通用 UI 元件（無 Streamlit container） | `chart_plotter.py`、`etf_render.py`、`ui_widgets.py`、`render/risk_contribution_render.py`(v19.138) |
| **L5 UI Tabs** | Streamlit Tab 級組裝 | `tab_macro.py`、`tab_stock.py`、`tab_stock_grp.py`、`tab_stock_picker.py`、`pattern_targets_ui.py`(型態目標價,`render_pattern_targets_for_ticker` 內嵌 🔬 個股 + 🏆 個股組合;v19.164 組合改**批次表 + 下鑽共用批次 df**,無獨立分頁;v19.174 去識別化改名,舊檔名/函式名為人名羅馬拼音,舊名 alias 過渡中)、`etf_dashboard.py`、`etf_tab_*.py`(含 `etf_tab_smart.py` — ⚠️ L5 自建 cache 層,見 §8.2.A.2 **V-SMART-CACHE-1**)(**~~體檢轉機獨立分頁~~(舊檔名帶人名縮寫,v19.174 不再列出) v19.164 退役真刪**:「找體質差→變好」轉機能力已合併進 🏆 個股組合「📊 財報趨勢×轉機」區塊 — `compute_one_stock_trend` 用同一份季快照附帶算 `diff_verdict`,零額外抓取、去第二輸入框 + 去重複第二張表) |
| **L6 App** | session_state 路由 + 全域編排 | `app.py` — ⚠️ **仍不是純 orchestrator,但 F2(2026-08)已收掉三項**:`_bps()`(→ L1 `proxy_helper.build_unverified_proxy_session`)、`gemini_call()` + 金鑰池(→ L3 `services/app_ai_service.py`)、`_build_llm_context()`(→ 同上)皆已下沉,`_AppProxy` / `sys.modules['app']` 劫持一併刪除。**剩「選股網整段內嵌 UI+編排邏輯(L5)」未修** → 見 §8.2.A.2 **V-APP-1** |

**硬規則（violation = 違憲）**：
- ❌ **L1 Data 不得 import streamlit** — 資料層脫離 UI 框架,可單獨測試
- ❌ **L2 Compute 不得 import** `requests` / `proxy_helper` / `FinMind` SDK / `yfinance` — 純函式,無 I/O
- ❌ **L0 Infra 不得依賴任何 L1+** — 被全層 import,須無迴圈依賴
- ❌ **L5 UI / L6 App 不得直呼 L1 Data fetcher** — 透過 L3 Service 取數（cache 才能集中）
- ❌ **跨層上行 import**：L1 不得 import L2/L3、L2 不得 import L3、L3 不得 import L4/L5

**已落地範例**：ETF dashboard 三層分離(SPEC.md §5,v18.182+ 強制)：
```
etf_fetch.py (L1, I/O) → etf_calc.py (L2, 純函式) → etf_render.py (L4, 圖表) → etf_dashboard.py (L5, Tab)
```

**8.2.A 已知例外清單**（豁免 §8.2 硬規則的特定模式,需明確標註理由）：

---

#### 8.2.A.0 這份清單怎麼維護（v19.180 新增 — 讀者請先看這段）

> **本節存在的理由**:2026-08-07 唯讀稽核發現本清單已嚴重失真 — EX-CACHE-1 寫「已收齊 9 處」實測 24 檔、
> EX-PASSTHRU-1 寫「25+ 處」實測 70+ 處且**行號 100% 過期**(唯一還對的是 `macro/handlers.py:51`)、
> 註 2 宣告「已移出例外」的檔案早被加回、註 1 把違憲寫成合憲。
> 一份**會說謊的憲法比沒有憲法更危險** —— 後續每次 AI 判斷都建立在錯資訊上。故立下列維護規則。

**規則 1｜禁止寫行號。** 例外一律以「**檔案路徑 + 符號名 + 模式描述**」登記。
行號在任何一次重構後就失效,而重構**不會**觸發本清單更新 → 行號是「保證會過期的資訊」。
（本節 v19.180 已把全部既有行號拔除。）

**規則 2｜禁止寫「共 N 處」「已收齊」「全域重盤」等窮舉宣稱。**
窮舉清單只要漏一筆就變成「未登錄軟例外」,而 §8.2.A 自己禁止軟例外 → 清單違反自己。
改寫「**適用模式 + 判定準則**」,讓讀者能自行判斷任一新檔是否落在例外內,不必比對名單。

**規則 3｜清單由測試強制,不由人工維護。**
分層規則的**窮舉**工作屬 `tests/test_c3_layering_guard.py`（C3,另組撰寫中）。該測試應：
- 以 AST 掃描實作 §8.2 五條硬規則(L1↛streamlit / L2↛IO / L0↛L1+ / L5·L6↛L1 / 跨層上行);
- 例外以**測試檔內的白名單常數**表達(檔案+符號,非行號),白名單即 machine-readable SSOT;
- 白名單與本節文字**任一方新增都必須同步另一方**,否則測試紅燈。
→ 本節文字負責「**為什麼**豁免」(人讀),測試白名單負責「**豁免了誰**」(機器讀)。
**C3 落地後,本節的檔案列舉應改為指向測試白名單,不再在 .md 內重複維護。**

**規則 4｜會漂移的量測值一律標日期或不寫。**
LOC / 檔數 / 「N 處」都屬此類。若非寫不可,格式為「〈值〉(量測日 YYYY-MM-DD)」,
讓讀者一眼知道它可能過期;否則直接不寫。

**規則 5｜豁免理由必須是「為什麼這個位置是對的」,不是「它長得像什麼」。**
反例(本節 v19.180 修正的真實錯誤):原註 1 寫
「`render_leading_table` **是 render fn 而非 fetcher**,合 L4 / 略豁」——
但該函式定義在 `src/data/macro/leading_indicators.py`(**L1**)。
「它是 render fn」正是它**不該住在 L1** 的理由,不是豁免理由。**理由倒置 = 把違憲寫成合憲。**
寫豁免理由前先自問:我在解釋這個設計為何正確,還是在替一個已知錯誤找說法?(對照 §1 判斷準則)

---

#### 8.2.A.1 生效中的例外

| ID | 適用範圍（檔案 + 符號,**不寫行號**） | 例外規則 | 理由 |
|---|---|---|---|
| EX-L0-1 | `src/config/config.py` — secrets bootstrap 段條件 `import streamlit as _st` | L0 條件 import streamlit | 限於 `st.secrets` bootstrap 讀 FINMIND_TOKEN；`try/except ImportError` 已護純 .py 環境;**無 UI lifecycle 依賴**(不用 cache_data/session_state)。替代方案(移 L3 + 改函式)會打破所有 caller 介面,ROI 低。v18.241 A1 註記 |
| **EX-CACHE-1** | **依模式判定,不列名單**（v19.180 改）— 適用於 `src/data/**` + `src/compute/**` 任一模組,只要同時滿足下列 3 條：<br>① 以 `try: import streamlit as st / except ImportError: _NoOpST` 條件 import（或等價的 inline `_safe_cache` wrapper,如 `src/data/macro/macro_alert.py`）;<br>② 全檔 streamlit 使用**僅限** `@st.cache_data` / `@st.cache_resource` / `st.secrets`;<br>③ **零** `st.session_state` / `st.error` / `st.warning` / `st.markdown` / `st.rerun` 等真 UI 呼叫。<br>⚠️ 2026-08-07 量測:符合本模式者 **24 檔**(`src/data/**` 21 + `src/compute/**` 3)。原文寫「已收齊 9 處」並逐一列名 → 實際漏登 12 檔(`daily_data_fetchers` / `financial_statements_fetcher` / `macro_snapshot` / `app_stock_fetchers` / `monthly_revenue_fetcher` / `quarterly_financials_fetcher` / `dividend_fetcher` / `share_capital_fetcher` / `fundamentals_snapshot_loader` / `news_fetcher` / `proxy_helper` / `exit_signals`)。**該 12 檔寫法全部合格**,問題純粹是清單沒跟上 → 依 §8.2.A.0 規則 2 改為模式判定,窮舉交 `tests/test_c3_layering_guard.py`。 | **`@st.cache_data` / `@st.cache_resource` / `st.secrets` 條件 import** | Streamlit Cloud cache 是部署架構核心,提供跨 session 共享 + TTL 自動失效,`functools.lru_cache` 不等價(無跨 session、無 TTL)。故允許 L1/L2 條件 import streamlit **僅為取得 cache decorator**。<br>**不適用本例外的情形**(須走真重構或另立例外):任何真 UI 呼叫。歷史案例:`data_loader` 曾同時用 `st.session_state`(S-H1 v18.244 刪死碼後合規)、`etf_fetch` 曾用 `st.error/warning/session_state`(S-H3 v18.244 下沉 print + module-level dict 後合規)。<br>**注意 `src/compute/**` 的額外限制**:L2 用本例外只能為 cache;若同時 import `requests` / `proxy_helper` / `yfinance` / FinMind SDK 則另外違反 §8.2「L2 不得 I/O」,**本例外不涵蓋**（現況見 §8.2.A.2 的 `risk_radar`）。 |
| **EX-OAUTH-1** | `src/data/portfolio/oauth_state.py` — **無條件** `import streamlit as st` + `handle_oauth_callback()` 內用 `st.success` / `st.error` / `st.rerun`(L1 含真 UI 呼叫,超出 EX-CACHE-1 範圍)<br>`src/data/portfolio/gsheet_portfolio.py` — 讀 `st.session_state['gsheet_tokens']` / `['portfolio_sheet_id']`(v19.159 擴充納入) | **L1 Data 含 OAuth callback flash / token 取用** | OAuth `handle_oauth_callback()` 屬 auth callback middleware 本質(URL `?code=` exchange → token → flash 訊息 → rerun),類比 web framework session lifecycle。同 EX-L0-1 將 streamlit lifecycle 視為部署框架特性(非業務 UI)。原位於 `src/ui/pages/oauth_state.py`(命名錯誤,從未渲染 UI),v18.400 D4 為解 `gsheet_portfolio` 的 L1→L5 反向違憲而搬正至 L1。替代方案(把 callback 拆 L5 UI + L1 client / 或抽 framework adapter / caller 注入 token+sheet_id)會打破現有 OAuth 流程 + ROI 低。檔內 docstring 已說明,本例外正式登錄於此(v18.431 補,v19.159 擴充)。**升級觸發條件**:若未來新增多 OAuth provider(Twitter / GitHub 等)→ 升級 L4 framework adapter。 |
| ~~EX-AI-1~~(已退役 v18.399 P5-DEAD-δ) | ~~`ai_engine.py` 全檔 public 函式~~ | ~~LLM 輸出回 **str** 而非 `LLMOutput`~~ | **v18.399 P5-DEAD-δ 整檔真刪**:AST-strict audit 確認 ai_engine.py 5 個 public fn 全 dead(0 production caller / 1 test ref / 1 internal helper 串到另一個 dead fn)。EX-AI-1 例外原文寫「~10+ caller」實際 0 — 例外建立在錯誤前提。真 production AI 走 `app.py:gemini_call` + `ai_fetcher.post_gemini` + `ai_structured_summary.build_structured_summary_prompt` 三條路,本例外正式退役。 |
| **EX-PASSTHRU-1** | **依模式判定,不列名單**（v19.180 改）— L5 UI Tab / L6 App / L4 Render 直接 `from src.data.* import <fetcher>`,只要滿足：<br>① 該 fetcher **無對應 L3 service**,且 caller 端**只是取數**（無多源 fallback、無跨 fetcher TTL 統一、無結果後處理）;<br>② 該 fetcher 在 L1 內已自帶 `@st.cache_data`（即 EX-CACHE-1 已集中緩存）。<br>⚠️ 2026-08-07 量測:符合本模式者 **70+ 處 import 陳述,散佈 `src/ui/**` 約 28 檔 + `app.py`**。原文寫「U3 v18.403 全域重盤收齊 25+ 處」並逐一列行號 → 覆蓋率約 4 成、**行號幾乎全數過期**(逐一比對後唯一仍正確的是 `src/ui/tabs/macro/handlers.py:51`)。依 §8.2.A.0 規則 1+2 改為模式判定。<br>**集中度最高的 caller**（給讀者定位用,非窮舉）:`tab_stock_picker` / `health_inspector` / `etf_tab_single` / `etf_tab_portfolio` / `etf_tab_smart` / `tab_stock` / `tab_stock_grp` / `tab_macro` / `macro/section_*` / `stock_grp_sections/section_*` / `stock_sections/section_*` / `app.py`。<br>**L4 Render lazy fallback**（同屬本例外,理由:fallback 抓比強制 caller pre-fetch 對多檔 dashboard 體驗佳）:`src/ui/render/etf_render.py` → `fetch_etf_holdings`;`src/ui/render/app_render.py` → `fetch_macro_compass`;`src/ui/render/macro_ui_components.py` → `macro_alert.alert_summary`。<br>**⚠️ 明確排除**（**不**適用本例外,見 §8.2.A.2 待修）:`src/ui/tabs/tab_stock_picker.py` 直呼 `src.data.core.data_loader._fm_raw_headers`（**private symbol**,非 public pass-through API,pass-through 前提不成立）。<br>**已解決,移出清單**:<br>- `app.py` → `StockDataLoader`：**已遷** `src/ui/tabs/stock_grp_sections/section_batch_fetcher.py`,`app.py` 不再持有(2026-08-07 複驗)<br>- `src/ui/tabs/yield_screener.py`：**已全部改走** L3 `src/services/yield_screener_service.py`,0 直呼 L1(2026-08-07 複驗)<br>**⚠️ 已解決宣告被推翻,重新納入例外**:`src/ui/etf/etf_tab_grp_compare.py` — 原註 2 宣告「已 R4 升 `etf_grp_compare_service`,移出例外」,但該檔 v18.452 又加回 `from src.data.etf import fetch_etf_zh_name`(另有 `src.data.core.provenance` import)。**升級後又退回 = 例外必須重新登記**,不能靠一次性宣告永久除名 → 正是 §8.2.A.0 規則 3(清單須由測試強制)要防的失效模式。 | L5 UI Tab / L6 App / L4 Render lazy fallback 可直接 import L1 「pass-through 用 + 無 L3 業務值」的 **public** fetcher | §8.2 規則「cache 才能集中」核心理由失效於本場景:L1 模組內已用 `@st.cache_data`(EX-CACHE-1)集中緩存,L3 wrapper 加一層只是 pure pass-through = §8.1 step 6「用不到的抽象」反例。Lazy import 多在 button click / on-demand 場景,延遲 import 避免 module load 時跑全 dependency chain。**升級觸發條件**:若未來新增跨多 fetcher 統一 TTL、多源 fallback chain、或結果後處理 → 升級 L3 service。S-H5/S-H6 v18.244 + P2-EX v18.393 + P5-B2 v18.396 + U3 v18.403 決策沿用,僅登記方式改為模式判定。 |
| ~~EX-RENDER-1~~(已升級退役 v18.396 P5-B1) | ~~`src/ui/render/etf_render.py:11`~~ | ~~L4 Render 直 import L1 Data fetcher~~ | **v18.396 P5-B1 已重構**:L4→L3→L1 走 `src/services/etf_sector_service.py`(L3 wrapper),封裝 `get_sector_returns(*, refresh=False)` + `get_news_for(...)`。L4 anti-pattern `_fetch_sector_returns.clear()` 已下沉至 L3 service。本例外正式退役,不再需要登錄。 |

---

#### 8.2.A.2 待修違憲清單（**不是**例外 — 這些沒有豁免理由,只是還沒修）

> 2026-08-07 唯讀稽核新增。與 §8.2.A.1 的差別:**上表是「這樣寫是對的」,本表是「這樣寫是錯的,待修」**。
> 兩者放在一起是為了避免下一個讀者又把違憲誤當例外(§8.2.A.0 規則 5)。
> **依 §-1**:本表**不構成**主動動工的授權 —— 沒有 user 指派 / 沒有實際 bug 觸發就不要碰。
> 本表的用途是:(a) 動到這些檔案時知道現況、(b) 給 `tests/test_c3_layering_guard.py` 當初始 xfail 清單。

| ID | 位置（檔案 + 符號） | 違反哪條硬規則 | 說明 |
|---|---|---|---|
| **V-RADAR-1** | `src/compute/risk/risk_radar.py` — module-level `from src.data.macro import fetch_fred, fetch_yf_close`;函式內 `from src.data.proxy import fetch_url` + 呼叫 + `pd.read_csv(io.StringIO(r.text))` | L2 不得 import `requests`/`proxy_helper`/yfinance;L2↛L1 | **規則字面點名禁止的 `proxy_helper`**,經 `src.data.proxy` barrel(PEP 562 `__getattr__`)轉發而躲過人工 grep。且 L2 純函式層直接做 HTTP + CSV 解析。修法:抽 fetch 至 L1,`risk_radar` 只收 DataFrame |
| **V-L0-NAME-1** | `src/config/stock_names.py` — `get_stock_name` / `refresh` 內 late import `from src.data.core.stock_names_fetcher import ...` | L0 不得依賴任何 L1+ | late import **不改變依賴方向**,只是把違憲藏在函式體內躲過 module-level grep。檔內註解自陳「lazy import 避 L0 啟動時拉 requests」= 已知有依賴。修法:靜態表留 L0,動態查詢介面上移 |
| **V-FT-STORE-1** | `src/data/portfolio/forward_test_store.py` — `from src.compute.screener.forward_test import PICK_SNAPSHOT_HEADERS` | L1 不得 import L2 | 只為取一個 schema 常數。修法:`PICK_SNAPSHOT_HEADERS` 下沉 `shared/forward_test_thresholds.py`(L0),L1+L2 都從 L0 取 → 反向消除。**低風險、高 ROI** |
| **V-CHECKLIST-1** | `src/services/daily_checklist.py` — `from src.ui.render.macro_ui_components import` 8 個畫圖函式(`sparkline` / `multi_chart` / `bar_chart_institutional` / `stat_card` / `margin_card` / `section_header` / `_hex2rgba` / `_base_layout`) | L3 不得 import L4/L5 | ⚠️ `ARCHITECTURE.md §0.10` 把這條寫成「**為 L4 import 合規**」— **理由倒置**,同 §8.2.A.0 規則 5 所述錯誤(L3→L4 正是硬規則明文禁止的方向)。本檔現為純 re-export barrel,這 8 個 re-export 是為了讓舊 caller `from daily_checklist import sparkline` 不用改。修法:caller 改直接 import L4,barrel 刪掉這段 |
| **V-LEAD-RENDER-1** | `src/data/macro/leading_indicators.py` — `def render_leading_table(df)`（L1 檔內定義 render 函式）;consumer:`src/ui/tabs/macro/section_chips.py`、`src/ui/tabs/tab_macro.py` | L1 不得 import streamlit / 不得含 UI | ⚠️ **原 EX-PASSTHRU-1 註 1 把這條寫成合憲**（「是 render fn 而非 fetcher,合 L4 / 略豁」）。理由倒置:它是 render fn ⇒ 它不該住 L1。修法:整個函式移至 `src/ui/render/`(L4),L1 只留資料 |
| **V-PICKER-PRIV-1** | `src/ui/tabs/tab_stock_picker.py` — 4 處 `from src.data.core.data_loader import _fm_raw_headers` | L5 不得直呼 L1（且 EX-PASSTHRU-1 不涵蓋 private symbol） | 跨層直取**底線開頭的私有符號**,連 pass-through 的前提(public API)都不成立。修法:`_fm_raw_headers` 若真要跨層用就轉 public + 登記;否則改走 L3 |
| **V-APP-1**(部分結案,F2 2026-08) | `app.py` — **剩餘**:選股網區塊(整段 UI + 編排,L5)。<br>~~`_bps()`~~ / ~~`gemini_call()`~~ / ~~`_build_llm_context()`~~ **已修** | L6 應僅 orchestrate | 原 §8.2 寫「僅 orchestrator」不實。**F2 已收**:`_bps` → L1 `src/data/proxy/proxy_helper.py::build_unverified_proxy_session`(原全 repo 4 份逐字複本,含 `daily_checklist` / `leading_indicators` / `daily_data_fetchers`,全部改為 import 別名);`gemini_call` + 金鑰池 + `_build_llm_context` → L3 `src/services/app_ai_service.py`(邏輯一字未改;**刻意不**改寫成 `ai_fetcher.post_gemini` 的 wrapper —— 兩者 endpoint 版本 / sleep 策略不等價,合併屬行為變更需另案)。守衛:`tests/test_f2_app_decomposition.py`。**未修**:選股網移 L5(§-1,無 user 指派不主動動工)。<br>⚠️ 順帶查證:`_build_llm_context` **0 production caller**,搬家後仍是死碼,是否刪待 user 裁示 |
| ~~**V-UP-APP-1**~~(**已結案 F2 2026-08**) | ~~5 處 `from app import`(L5→L6):`src/ui/tabs/tab_stock_grp.py`(×2)、`src/ui/tabs/tab_stock.py`、`src/ui/tabs/tab_macro.py`、`src/ui/tabs/macro/section_news_ai.py`~~ | 跨層上行 import | 如原文預測,與 V-APP-1 **同一根因**,一起解:`gemini_call` → L3;`api_key` → L3 `get_gemini_api_key()`;`parse_stocks` → L0 `shared/parse_helpers.py`;`_tw_now_str` → L0 `shared/macro_compute.py::tw_now_str`;`_get_fm_token` → L0 `src/config/config.py::get_finmind_token`;`_bps` → tab_macro 不再需要(session 改由 L3 `macro_fetch_orchestrator` 向 L1 取)。連帶刪除 `app.py` 的 `_AppProxy` + `sys.modules['app']` 劫持(其唯一存在理由就是撐住這 5 處)。守衛:`tests/test_c3_layering_guard.py` 規則 5(`_KNOWN_VIOLATIONS` 4 條已移除,反向守衛生效)+ `tests/test_f2_app_decomposition.py` |
| **V-SMART-CACHE-1** | `src/ui/etf/etf_tab_smart.py` — 5 個 `@st.cache_data(ttl=<literal>)` 自建 cache 函式(`_cached_price` / `_cached_peer_prices` / `_cached_holdings` / `_cached_price_long` / `_cached_zh_name`) | §8.2「cache 才能集中」+ §3.3 反捏造 | L5 自建快取層 = 把本該在 L1 集中的 TTL 分散到 UI;且 5 個 `ttl=` 全是 inline 數字(1800/3600/3600/7200/86400),**未走 `shared/ttls.py` SSOT** → 同時違反 §3.3。修法:cache 下沉 L1 fetcher,或至少 ttl 改引 `TTL_30MIN` / `TTL_1HOUR` / `TTL_2HOUR` / `TTL_1DAY` |

**已確認死碼 → 已移除（v19.181 detox）**

`macro_signal_lookback_tw.py`(581) + 其**封閉死簇** `macro_validation_tw.py`(134) / `signal_threshold_optimization.py`(201，獨佔依賴前二者、自身零接線) / `multi_factor_optimization.py`(521) / `tw_backtest.py`(323) 已於 v19.181 全數移除（連同 barrel 登錄、5 個專屬 test；`test_d2_macro_sections.py` 外科移除 `TestBacktestNoLookahead`、`test_hot_money.py` 收留 tw_backtest 檔內寄生的 hot_money 測試；§4.1 evidence 已改指 `shared/signal_thresholds.py`+`shared/margin_schema.py`、§2.3 拐點驗證 clause 同步更新）。**保留** `src/data/macro/macro_cache_reader.py`(73)：`scripts/analyze_ring1_gate.py` 仍真 import。

---

**符合 EX-CACHE-1 的標準寫法**(P2-EX v18.393 補 `secrets`):
```python
try:
    import streamlit as st
except ImportError:
    class _NoOpST:
        @staticmethod
        def cache_data(*args, **kwargs):
            # 支援 @st.cache_data 和 @st.cache_data(ttl=...) 兩種呼叫
            if args and callable(args[0]):
                return args[0]
            return lambda f: f
        cache_resource = cache_data
        secrets: dict = {}  # bootstrap 讀 token 用(同 EX-L0-1);無 streamlit 時 fallback 空 dict
    st = _NoOpST()  # noqa
```

新增例外**必須**:(1) 在 §8.2.A.1 登錄（寫**模式**,不寫行號）、(2) 同步 `tests/test_c3_layering_guard.py` 白名單、(3) 對應檔案加註解指回此表、(4) PR 描述附理由。**禁止**未經登錄的潛在「軟例外」。

⚠️ **本條在 v19.180 前形同虛設**:EX-CACHE-1 漏登 12 檔、EX-PASSTHRU-1 漏登逾半,全都是「未經登錄的軟例外」——
清單自己違反了自己寫的禁令。根因是**靠人工同步一份窮舉名單**。§8.2.A.0 規則 3 的測試強制,
就是為了讓「漏登 = CI 紅燈」而非「漏登 = 沒人發現」。**C3 測試落地前,本條只能靠自律,請據此打折信任本清單。**

### 8.3 灰色地帶（audit 後的分類結果）

> **v19.180 稽核重整**:本節原本 3 條裡有 2 條已過期(見下)。灰色地帶的定義是「**還沒判定**」;
> 一旦 audit 判出結果就該搬走 —— 判定為違憲的搬 §8.2.A.2、判定為合憲的搬 §8.2.A.1、
> 已修的畫刪除線留追溯。留在本節的只該是**真的還沒判定**的。

**已結案(留追溯)**

- ~~`macro_helpers.py`：分類 L2 但有輕度 I/O（讀 `macro_thresholds.json`）~~ → **S-GRAY-1 v18.244 已修**:loader 抽至 `shared/macro_calibration.py`(L0),`macro_helpers` 改 import,介面 0 改
- ~~**`daily_checklist.py`**：跨 L1+L2+L3(fetch + cache + 摘要 + pkl 持久化)→ audit 看是否該拆檔~~ → **拆檔已完成**(PR-N1~N5 等,fetch 下沉 `src/data/daily/`、計算下沉 `shared/macro_compute.py` + `shared/stats_helpers.py`、cache 下沉 `shared/cache_layer.py`);全檔現為**純 re-export barrel**(2026-08-07 複驗:143 行,除 `_bps()` 外無實作)。<br>⚠️ **但問題換了一個**:剩下的 barrel 含 **L3→L4 上行 import**(8 個畫圖函式)+ `_bps()` 與 `app.py` 完全重複 → 已改列 §8.2.A.2 **V-CHECKLIST-1** / **V-APP-1**。原文「待 audit 是否該拆檔」已不再是待辦。
- ~~**`app.py`**：7,300 LOC,部分計算邏輯可能該下沉到 L2~~ → 大幅收斂(R7/R8/B3-γ/B3-δ 拆 AI service / news fetcher / render / fetcher 至 L1-L4)。<br>⚠️ **但「已收斂至 882 LOC,現純 orchestrator」不實**(2026-08-07 複驗:989 行,且含 L1/L3/L5 職責)→ 已改列 §8.2.A.2 **V-APP-1**。

**尚未判定（真灰色地帶）**

- **`src/data/macro/macro_core.py` / `tw_macro.py` 的 fallback 鏈深度**：多源賽跑 + durable last-known-good 快照,介於 L1 取數與 L2 仲裁之間;是否該把「源優先序仲裁」抽成 L2 純函式(可單測)尚未判定。**無 bug 觸發,§-1 不主動動工。**
- **`src/services/` 內 wrapper vs 真編排的界線**：部分 service 是 pure pass-through(等於 §8.1 step 6 的「用不到的抽象」),部分是真編排。是否該把 pure pass-through 的 service 刪掉、讓 UI 走 EX-PASSTHRU-1,尚未逐檔判定。

> 📌 **提醒**:§8.4 步驟 2 寫「§8.3 灰色地帶已點名 3 處」。該數字已不成立 —— audit 時請以 §8.2.A.2 待修表 + 本節「尚未判定」為準,**不要**以為只有 3 處。

### 8.4 做到一半的新增功能 — 先盤點再動

新增功能前 audit pipeline：
1. 現有程式大致分成哪幾塊？資料怎麼流？（對照 §8.2 七層）
2. 哪裡**違反分層**？列**檔名 + 符號名**（不是行號 —— §8.2.A.0 規則 1）。起點:§8.2.A.2 待修表 + §8.3「尚未判定」;**不要**假設那就是全部,audit 時實測補上。
3. 這次的新功能該放哪一塊？會不會被現有壞結構卡住？
4. 若需要先重構才好加,**分開提案**：「為這次必須改」vs「建議但可延後」,讓我決定範圍,**禁止**自作主張大重構。

核准範圍後才動;一次改一塊,貼 diff + 說明為何不破壞既有行為。

### 8.5 共同收尾

核准後**一次只寫 / 改一個模組**,每完成一個跑 §6 自審。
**禁止中途偏離已核准的架構**；若發現架構需要改,先停下來問。
