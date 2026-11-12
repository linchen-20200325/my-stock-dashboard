# CLAUDE.md 歷史分冊（2026-11-12 搬入；⛔ 非現行規則、非 SSOT、非接手點）

> **來源**：`CLAUDE.md`（main `16a93a4e`，完整 SHA `16a93a4ee7673fd21c0f07a1f2d32a1ad5ed8dc8`）原 L473–L476、L981–L1006、L1074–L1114，共 3 個連續區段（§-1.5.C「掃描方法」條列；§-1.5.G「方法（三步）」與「掃描結果（據實）」兩小段；§0「填寫紀錄」標題行之下的引言與步驟 1～4）；**逐字、依原順序**行切片搬入，未改字、未重排、未摘要。**搬移日**：2026-11-12。**依據**：客戶 DEC-173 Q4「CLAUDE.md 僅允許真正失效的純歷史內容歸檔；重複補註可在不改變規範效力下收斂為指向。永久規則、現行補註、客戶原文、規範位階及必要上下文一律保留。」與 Q6（逐字搬至 repo 內正式歷史分冊、保留 Git 歷史與可還原路徑）。**未搬**：各節標題行、§-1.5.C 其餘條列（「⚠️ **未複驗事項**」條列〔內含「現況仍不得宣稱『本檔已無牴觸』」〕、「📌 **跨檔狀態更新**」、「**跨檔待辦**」〔內含「衝突時以 §-1.5 為準」位階句〕）、§-1.5.G 引言與「⚠️ 本輪已知盲點」1–7 條、§8.2.A.2「已確認死碼 → 已移除（v19.181 detox）」小段（「**保留** `src/data/macro/macro_cache_reader.py`」句與移除紀錄同一行，整行留主檔；其餘僅剩粗體小標，單獨搬走會使該行失去上下文，故整段不搬），以及其餘全部條文。
> **定位**：本檔為歷史分冊，非現行規則、非 SSOT、非接手點；現行規則與其位階一律以 `CLAUDE.md`（含各節標題、刪除線、補註、客戶原文 fence）、`PROCESS.md`、`docs/DECISIONS.md` 為準。文中「本節」「本輪」「上述」「本次」「見 §…」「下一欄」等相對指涉，一律指搬移前的 `CLAUDE.md`。
> **還原**：每段以 `CLAUDE_HISTORY_SEGMENT` 註解夾住、標原行號；取該段 BEGIN 註解後的一個空行之後、END 註解前的一個空行之前的行（即原行，依原行號順序），替換主檔對應 `CLAUDE_HISTORY_INDEX` 區塊（BEGIN 註解行至 END 註解行，含兩端；區塊上標 `lines=` 原行號），即逐位元組還原；或 `git show 16a93a4e:CLAUDE.md`。

<a id="claude-hist-1-5-c"></a>
<!-- CLAUDE_HISTORY_SEGMENT:BEGIN src=CLAUDE.md base=16a93a4e lines=473-476 -->

- **掃描方法**：對 `CLAUDE.md` 全檔（700 行，量測日 2026-08-27）grep 關鍵字
  `請示` / `裁示` / `派工` / `稽核` / `複驗` / `交付` / `報告` / `user` / `客戶` /
  `停手` / `動工` / `核准` / `對齊` / `先停下來問` / `讓我決定` / `給我確認`，
  逐一判讀命中處是「規則」還是「歷史紀錄 / 稽核現況」，只對**規則**做牴觸判定。

<!-- CLAUDE_HISTORY_SEGMENT:END lines=473-476 -->

<a id="claude-hist-1-5-g"></a>
<!-- CLAUDE_HISTORY_SEGMENT:BEGIN src=CLAUDE.md base=16a93a4e lines=981-1006 -->

**方法（三步）**
1. **逐字對讀**：把 v3 原文與 v1 逐句對映，先產出 §-1.5.E 的對照表（新增／收斂／不變 三種判定），
   **先 diff 再落筆**，不是把新版貼一遍。
2. **雙向關鍵字掃描**（v3 同時有收緊與放寬，**兩個方向都掃**）：
   - **正向**（v3 新增主題，找既有條文有沒有講同一件事）：
     `搬遷 / 目錄 / 孤兒 / Orphan / Archive / 死碼 / dead code / 實體刪除 / 清理 /
      退避 / 轟炸 / backoff / 成交量 / 融資…單位 / 灰色 / 紅色 / 假性 /
      網格 / 3 欄 / 三欄 / Checkbox / 延遲載入 / 重繪 / st.form`
   - **反向**（v3 是**收緊型**規範 → **必須**掃既有的**放寬句／豁免句**）：
     `免 / 不必 / 無需 / 直接做 / 不觸發 / 豁免 / 例外 / 逕行 / 自決`
     ⚠️ **這一輪的反向掃描是照 §8 前言那條方法論教訓做的**：`c901d47` 那一輪掃「要問客戶」類
     關鍵字，**結構上永遠掃不到**一個關鍵字都不含的豁免句。**本輪的主要收穫全部來自反向掃描。**
3. **實地查證**（不憑文件轉述）：`ls src/`、`ls src/data/`、`ls src/ui/`、`ls src/compute/`、
   `ls shared/`、`grep -n streamlit requirements.txt`、`grep -n tab_macro_v2 app.py`、
   `find . -name tab1_macro.py`、`grep -rn '\^VIX' src/`。**結果逐項寫進 §-1.5.D 與判定內文。**

**掃描結果（據實）**
- **正向命中 0 的項目**（→ 該處為純新增，**沒有舊表述需要加刪除線**）：
  `退避` / `轟炸` / `backoff` / `成交量` / `灰色` / `紅色` / `假性` / `網格` / `3 欄` / `Checkbox` / `延遲載入`。
- **反向命中的真張力共 5 處**，全部已就地處置：
  (1) §-1.5.A-2 邊界段「不是趁機清全 repo」（判定 3）；
  (2) §8 前言「不觸發…直接做」清單（判定 3，就地補註）；
  (3) §8.2.A.1 **EX-PASSTHRU-1**（判定 2）；
  (4) §8.2.A.2 待修表前言「本表不構成主動動工的授權」＋ §8.3「無 bug 觸發不主動動工」（判定 3）；
  (5) §8.4 step 4「分開提案讓我決定範圍」vs v3「嚴禁拋選擇題」（判定 8）。
- **跨檔**：`PROCESS.md §2`「動工前大掃除」的同精神補註**已同步**（本次授權含該檔）。

<!-- CLAUDE_HISTORY_SEGMENT:END lines=981-1006 -->

<a id="claude-hist-0"></a>
<!-- CLAUDE_HISTORY_SEGMENT:BEGIN src=CLAUDE.md base=16a93a4e lines=1074-1114 -->

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

<!-- CLAUDE_HISTORY_SEGMENT:END lines=1074-1114 -->
