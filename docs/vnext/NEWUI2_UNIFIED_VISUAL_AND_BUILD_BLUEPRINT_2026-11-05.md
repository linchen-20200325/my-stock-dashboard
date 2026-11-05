# New UI2 統一視覺與施工藍圖 v0.1（2026-11-05；ChatGPT 直接撰寫）
> **狀態：PROPOSED／待視覺核准，不是第二份 Active Contract，也不是所有版型的施工授權。**
> **用途：**集中提供 Claude Code 施工所需的「現況→目標→欄位契約→互動→驗收→拆批」；避免 Claude 重做設計研究。依 2026-11-05 客戶方向「由 ChatGPT 完成文件／設計，Claude Code 寫程式」。設計及風險較高的版型細節先由客戶核准，再啟動對應施工。
>
> **優先權：** `CLAUDE.md`、`PROCESS.md`、`PROJECT_RULES.md`、最新有效 DEC 與 `NEWUI2_ACTIVE_PRESENTATION_CONTRACT_2026-11-03.md` 高於本文件。本文件不得自行覆蓋任何已核准 W 點、風險語意、公式或資料來源。歷史 `NEWUI2_WIREFRAMES_2026-11-02.md` 只讀未被取代的有效部分；實作時同讀 `NEWUI2_UI_EXECUTION_SPEC_2026-11-04.md`、`NEWUI2_VISUAL_REFERENCE_AND_PAGE_EXPANSION_2026-11-04.md`、`docs/governance/UI_VISUAL_FIDELITY_GATE.md`。手機底部四格導航已由 DEC-134／137 取代，禁止復活。
>
> **證據限制：** 客戶四面板漂亮儀表板參考圖片於對話內提供，但目前不是 repo 內可逐像素核對的資產。本藍圖引用 DEC-135／136 的有效文字視覺方向；**不宣稱 pixel parity／客戶已核准此文件所有區塊**。本文件的虛構數字只准當線框示意；實際 UI 一律從現有正式 VM / canonical 讀值。

## 1. 不可變的產品與技術護欄（A：已有裁示，立即生效）
- 正式四頁導覽：`📊 市場`、`🎯 標的`、`💼 持股`、`👤 我的`。四頁為核心而非永遠不可增頁；第五頁仍須另行用戶核准（DEC-135）。
- 人類 UI：結論／是否需注意或正式動作／主圖／簡短關鍵 evidence／數字／source+as_of+limitation。OneBrain：獨立讀**完整且可追溯的 Decision Digest**，不是 UI 卡片或 Top-N。兩者各自驗收；**不以 UI 壓縮刪除 canonical／VM／Risk Cap／RuleIDs／反證**。
- 資料狀態維持 OK／Missing／Stale／Unavailable／Not Evaluated 五態；Capability 與 Data State 分軸；缺值不補 0／HOLD／中性／安全。示意 FAKE／query `ui2_dev` 不得當真實登入或正式投資判斷。
- 既有手機左上 44px ☰、左側抽屜、四頁互動與 JS_V4 hash／白名單不可私改。手機 390×844 首屏餘裕 ≥160px 的既有守衛不得退化（已知 unavailable 只有 162.5px，任何新增上方高度都要先量測）。
- 台股與國際市場兩條趨勢主軸；EPS × PE 僅為研究方法之一，禁止自創公式／成長假設／估值門檻。個股基本面優先、A 成長動能／B 價值錯殺、Risk Cap 與 Single Action Authority 不變。
- #1019 已合併；本文件撰寫時 #1020（chip 深色對比＋💼 桌機 W-11 部分）、#1021（DEC-138 分工）仍為 open，必須合併後以新 main 重新比對，避免覆蓋兩批變更。

## 2. 視覺設計系統（B：UI 提案，須顧客確認視覺再改主題）
| 元素 | 視覺目標／施工限制 |
|---|---|
| 全域 | 深 navy 品牌 rail＋低雜訊頁首；卡片亮色／淺色、明顯層級、圖表先於文字牆；沿用現有正式產品名稱與四頁頁名，不沿用基金界面名稱 |
| 色彩 | 先由現有 `src/ui2/shell/css.py` 與 `.streamlit/config.toml` 提取實際 tokens；**此文件不批准**自行切全站 Light／反轉卡片底色；要先出 dark/bright 兩種可視稿，評估 #1020 chip 對比（深底、亮底 WCAG 皆須測） |
| 桌機 | 1440×900；左固定 rail（目前約 176px）、主要工作區適合卡片網格；每頁恰一個主視覺焦點，次要圖不競爭 |
| 手機 | 390×844；首屏先決策；不新增長駐帳戶列；卡片單欄／必要時 2+1 KPI；主要圖保留足夠辨識高度；不出現水平捲動 |
| 文字 | 卡片 1 行結論＋少量數字＋狀態；色彩不是唯一語意；主要圖下方一行 SPEC（頻率／單位／source／as_of／缺值規則，取現有 VM 實際欄位） |
| 缺資料圖槽 | Primary 維持高度與明確「⬜ 尚未提供／資料未備／無法判定」之正確類別；小圖可收斂為一行 placeholder，不能畫假的走勢、線段或 0 |

## 3. 共用 Shell 與帳戶入口（B：使用者已核准方向；細節須視覺 Gate）
**手機收合（390px）**：在既有保留的頂端 44px 互動帶，左側 ☰、中間正式產品標識（不以產品名稱長字串擠壓），右側人物圖示；內容首屏高度不因此下移。主頁仍由 ☰ 抽屜切換，人物圖示只管 Account，不增第五頁或第二套主導航。

**手機點人物圖示**：顯示小型帳戶面板（Popover／受控折疊方案待施工前技術選型）；帳戶面板和 ☰ 抽屜**不可同時開啟**；點遮罩／Esc 關閉並返還焦點；Tab 不可進入隱藏內容。若因 Streamlit rerun 競態無法保證、會觸碰 JS_V4 或使 UI first fold <160px，停手交由 JS 安全 Gate 而不是偷偷加 JS。

**桌機（1440px）**：保持固定 rail，順序為 Logo／Account compact／四頁；**不在頁首複製同一個登入 CTA**。Account 面板與 👤「連線狀態」的欄位應出自相同正式 auth contract（尚未完成），不建立假狀態。

**帳戶狀態規範：**
- **目前可施工之 preview 占位**：`⬜ 尚未提供`（Capability），Google 登入按鈕 disabled，原因「登入與 Sheet 操作尚未開放」。這不是「未登入」，更不是 signed-out 的真實判定。
- **未來正式 auth（僅線框，不授權接線）**：登入成功後用同一契約顯示必要使用者識別、登出、必要時切換帳號／Sheet。切換帳號的觸發條件與安全模型（失效、重導、同步、確認）須獨立 Auth Gate；沒有契約時不要畫可操作按鈕。
- **狀態邊界**：`ui2_account`、FAKE、URL query、`ui2_dev`、頁面 DOM 都不是認證證據；不得顯示 Token、Email 全文（是否可顯示部分識別依契約）、credential 或 Sheet ID 全碼。
- **無障礙**：44×44px 可操作目標、清晰 label、focus return、Esc、Enter/Space、reduced motion、關閉內容不留在 accessibility tree；在 iOS／Android／Cloud Manage app 仍需獨立實機驗證。
- **不覆蓋 #1019 已核准抽屜行為**；Account 互斥與關閉策略若要新增 JS，另開 JS Gate，不混入 #1020。

## 4. 四頁逐頁藍圖（沿用既有責任／明確列出待核准視覺項）

### 📊 市場
**第一眼**：今日結論 + 更新今日戰情（主 CTA 的 enable/disabled 與原因取現有正式值）→ 三核心狀態：市場目前狀態、Risk Cap、今日主要風險。手機依 DEC-127／133：市場目前狀態 → Risk Cap → 是否需要行動 → 下一步 → 今日主要風險；桌機三 tile 後再呈現行動與下一步。OneBrain Outlook 槽只顯示既有已準備好之內容或誠實 unavailable。
**第二眼**：唯一台股 Primary 主圖及一行 SPEC；核心指標摘要；國際 small multiples、VIX、Macro mini（依既有有效契約排序）。**未接歷史序列時 Primary 只放語意正確的 Placeholder；不能以一筆 TWII 最新收盤點推造時間序列**。
**不在 UI**：16 指標逐筆牆、完整位階 WHY、工程 Gate、raw JSON；保留於 VM／Evidence，Digest coverage 獨立稽核。
**需核准**：圖 A 尺寸／實際變數映射／各卡配置、全域亮卡片 skin；不得自行增新資料源。

### 🎯 標的
**首屏**：市場精選／即時查一檔雙模式、代碼／名稱搜尋與誠實能力說明、查詢摘要及 W-4 market context micro-line。保持 session-only，不偷偷寫 Sheet。
**精選視覺**：產業機會 Top 5 為唯一 Primary（以正式可用淨流入等既有欄位畫橫條，資料缺漏改 placeholder）；候選 Top 10 簡潔行列，保留「查看全部候選／CSV／查看此檔」、一行選股條件。
**查一檔**：Header + 六維 Snapshot → 唯一 Primary 價格圖 → 基本面／估值／籌碼／產業／風險圖卡（僅正式有資料的視覺），EPS basis／PE source／as_of 在一行 SPEC；研究解釋槽與加入觀察功能在未開放時 disabled。
**需核准**：價格圖與基本面圖卡的具體排列、精選列表卡式／表式、無有效序列時的主圖占位；不得假造估值或技術指標。

### 💼 持股
**首屏**：組合名稱／資料日與更新持股戰情主 CTA（disable 必保留）、Risk Cap／目前曝險／組合狀態 tile、今日需處理／下一步；「尚未評估」不可混進「無需調整」，不得自行算曝險分母。沿用已核准 W-11；#1020 的既有 header＋三 tile 局部修改若合併則直接在其基礎接續，不重做。
**第二眼**：唯一 Portfolio Overview Primary（績效／benchmark 依正式資料可用性）、持股表 L1 既有八欄、建議持股區間（資料與正式動作權威現有才可顯示）、策略與集中度小圖及 OneBrain 持股摘要槽；手機以精簡卡／可進入表格次層，不能使首屏成長表。
**需核准**：Primary Portfolio 圖、表格手機轉列規則、W-11 缺失的「組合名稱·資料日」行與「今日需處理」單行布局；禁止新增投資動作邏輯。

### 👤 我的
**首屏**：連線狀態＋單一主 CTA（不可與帳戶面板重複做兩個操作權威）；目前正式登入能力尚無 contract，維持 capability 占位。
**第二眼**：Portfolio／Watchlist／Strategy／Notifications／Display 設定（沒有寫入 Gate 就 disabled）→ P6 資料健康度入口／待核准 Level 1/2/3 → Audit：Decision Digest Viewer、Rule Registry（唯讀、預設收合）。
**資料健康度**：Level 1 每項 Data State 與 Capability 拆兩欄；Level 2 source／as_of／freshness／provenance；Level 3 脫敏 developer diagnostic（預設收合），Secret／原始 traceback 不得曝露。P6 與 Auth state 需分開批次 Gate。
**需核准**：重複 CTA 收斂後的實際位置、P6 的資料健康度視覺線框、哪些目前未接線欄位只作空槽。

## 5. 每頁驗收欄位契約（不得為 UI 新造正式證據）
| 頁 | 來源／契約檢查 | 降級規則 |
|---|---|---|
| 市場 | 現有 VM：狀態、Risk Cap、Action、結論、source、as_of；16 項完整 Evidence 別軌稽核 | 歷史序列未備＝主圖槽缺值；無正式 action＝不製造加碼／減碼 |
| 標的 | 現有候選池、標的 Snapshot、EPS basis、估值、籌碼、產業／風險來源、market context | 無行情／EPS／歷史＝各卡顯示對應缺值，不補 0 或推測 target |
| 持股 | Portfolio VM、來源日期、正式 Risk Cap／System Action、八欄 Holdings 表 | 分母缺失＝曝險無法判定；缺行動資料不等於「全部續抱」 |
| 我的 | Capability 占位、當前設定、資料健康度 VM／source／provenance（可得者） | 無正式 auth contract＝不顯示真實登入成功；缺健康欄位列為資料契約缺口 |

## 6. 三路徑比較與建議
| 路徑 | 正確性／風險 | 速度／成本 | 決策 |
|---|---|---|---|
| A. 四頁／Auth／P6 一次大改 | 回歸與 auth、Risk Cap 風險高 | 重跑多、Token 高 | 不採 |
| **B. 單一完整藍圖＋每批 ≤3 項施工** | 遵守既有 Gate，可逐步驗收 | 最小充分 | **推薦** |
| C. 各頁邊施工邊設計 | 需求來回、規格漂移 | 重複研究成本高 | 不採 |

**順序：** 0. 完成 #1020 視覺局部收尾、#1021 治理文件 CI／合併；1. 由 ChatGPT／客戶一次審閱本藍圖內 B 類布局；2. 全域 tokens／樣式與四頁視覺（每批 ≤3 個獨立安全改動）；3. 圖表與資料對照（有正式 source／schema 才接，否則 placeholder）；4. 手機帳戶 popover（只限 Capability，占位與安全互斥）；5. P6 資料健康度；6. OneBrain Evidence Coverage Audit 與 Digest runtime（需 High／獨立 Gate）。
每一批後比對 390×844、1440×900，附 before/after 可見截圖＋不變量測＋獨立 QA，CI Fast／Slow／`ui2-browser-gate` 成功才能依合併治理處理。

## 7. 視覺 Decision Gate（客戶只需看一次的未核准 B 類集合）
- **V-01 全站 skin**：深色 canvas＋亮色卡片（提案）還是全暗卡？要確保 chip、圖表、表格在 dark／light 環境對比。
- **V-02 📊**：主圖與國際小圖的尺寸、排列；無資料時圖槽占位樣式。
- **V-03 🎯**：精選 Top 5／Top 10 表達、查一檔 Primary 與基本面／估值小圖排版。
- **V-04 💼**：W-11 完整主圖／八欄表／資料日行／需處理單行及手機轉列。
- **V-05 👤**：單一 CTA、P6 Level 1／2/3 內容密度。
- **V-06 Account**：手機右上人物圖示展開方式與遮罩／抽屜互斥（方向已獲核准；實際圖面與行為需驗收）。
上述是**設計提案／批准點**，不得把本 docs-only PR 的合併當成上述全部核准。可由 ChatGPT 依提案提供可檢視視覺圖，客戶核准後登記新 DEC。

## 8. Claude Code 施工交接／驗收協議
1. 開工先 GitHub Verification Gate：main、open/draft PR、branches、相關 commits／diff、CI、`CLAUDE.md`、`PROJECT_RULES.md`、DECISIONS／BACKLOG／HANDOFF／PROJECT_STATE／Active Contract；先確認新 DEC 核准對應 B 類布局。
2. 不再重做 ChatGPT 已完成的設計研究，只回報**可證明的規格衝突或資料缺口**；內部技術路徑至少比較三案，選 Minimum Sufficient Effort。
3. 施工小批建議 Sonnet 5.5／Medium（純 CSS／既有 UI）；JS 安全範圍、Auth 真正接線、Risk Cap／Digest semantic 改動需先停手，必要時 Opus 5.5／High。
4. 每批最多三個安全工作，至少一組**與實作者獨立**的 QA；提交 screenshot、對比／focus／Esc／手機寬度、Mutation/guard 測試，不能把 CSS snapshot 當資料正確證明。
5. 視覺：只有已核准 layout 可施工；新區塊／新增、刪除、移動欄位或元件未核准必停；Visual Fidelity 依既有 Gate，QA＋CI 綠但視覺不合格仍不得宣稱 Stage complete。
6. Source／canonical、VM／Digest、資安／auth contract、Risk Cap／System Action、JS_V4 等不可變量要有對應釘住的測試；不改 `src` 之外的其他姊妹 repo。
7. 合併與交接：feature branch→PR→獨立 QA→required CI→符合 Auto-Ship 才 squash merge；append-only 更新正式紀錄，保留未驗項，主分支 CI 不能查到時標 unverified。完成後回報一次，勿頻繁進度輸出。
