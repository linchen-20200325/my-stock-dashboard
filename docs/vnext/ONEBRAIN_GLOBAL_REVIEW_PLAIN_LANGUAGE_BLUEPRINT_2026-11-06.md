# New UI2｜總結 OneBrain（跨域複核＋白話文）設計提案 v0.1

> 2026-11-06 客戶新增方向：除各頁 OneBrain 專家分析外，再提供一個上層**總結 OneBrain**，重新檢視所有已完成分域分析，產出人人可讀的短／中／長期白話報告；**每一層 AI 回覆都要白話文**。本文件 PROPOSED / docs-only；不代表實際 LLM runtime、額外模型費用、完整 coverage、來源授權或投資動作已上線。以 base main `343f0e0e`、本 PR 既有 Evidence / Token 治理文件為設計前提。

## 1. 不是五套互不相干的大腦
- 📊市場、🎯標的、💼持股、🗂資料各頁可以顯示「分析此頁」入口；👤我的優先維持設定與稽核，不必每次執行昂貴 AI。
- 同一份 approved canonical facts + headless Complete Evidence Ledger；每個頁面是**scoped analysis view**，而不是從 UI 卡片、Top-N、目前 Tab DOM 抄字給 LLM。
- 上層「總結 OneBrain」讀取分域的**typed/cited report**（evidence refs、時間、missing、counter evidence、scope 與版本），並依 Required Evidence Manifest 向**內部唯讀 Evidence Store**核對重要事實與反證，不是僅將幾篇 AI 自述再請一個 AI 潤稿。
- 所有 AI 執行階段都禁止自行外連、搜尋新聞、呼叫新資料 API、查未核准來源或回寫 canonical。必要來源由資料層另案治理接入。

## 2. 三種方案比較
| 方案 | 優點 | 主要缺點 | 裁定 |
|---|---|---|---|
| 直接合併各頁 AI 文字 | 成本低 | 遺漏與幻覺經過多層語言轉述會放大、難追證據 | 不採 |
| 每次總結強制重新餵全部原始資料 | 檢查較直觀 | 高 Token、容易過上下文、反覆工作 | 不採為常態 |
| **分域 typed evidence reports + ledger references + deterministic coverage gate + 可回查的總結** | 可控成本、可檢驗完整性及跨頁矛盾 | 需建 orchestration 與驗收 | **推薦** |

## 3. 工作流程與輸出契約（待 runtime/Schema Gate）
```text
經核准來源 → L1/L2/Canonical → Deterministic/Risk Cap/Action Authority
                  ↓
    Required Evidence Manifest + Complete Evidence Ledger
       ├─ 市場研究員 → 引用式報告
       ├─ 個股研究員 → 引用式報告
       ├─ 持股研究員 → 引用式報告
       └─ 資料健康度 → 完整度報告（可先 deterministic）
                  ↓
    總結 OneBrain = 抽核原始證據 + 跨域矛盾 + 正反證覆蓋
                  ↓
      白話文：一句話結論 → 短／中／長 → 風險 → 下一步觀察
```

### 分域報告必備內容
- scope / producer snapshot version / as_of / evidence_ids and negative_ids / required-available-processed-omitted counts / findings / opposing_signals / unknowns / limitations / financial-semantic authority。
- 是否實際餵入 evidence 必須由執行紀錄驗證，不能因模型輸出提及某 source 就認定涵蓋。
- 原始資料的更新需要讓舊分析的 cache key/hash 失效；總結不准拿不同資料日期的分析當同步快照。

### 總結 OneBrain 的驗收條件
1. **不以 AI 自評覆蓋率**；確定性 validator 查每個必需 evidence 是否有被處理/引用，含負面證據。超 Token 應分批處理或 PARTIAL，不 silent truncate。
2. 對跨域矛盾作分析而不是投票：市場短弱、個股中強、產業長強允許並存；明說期間與分歧來源。
3. 不准用模型推論製造新的正式買賣動作或擅改 Risk Cap；正式行動一律來自既有 Single Action Authority。
4. 分域任一 essential pack 為 unavailable/partial 時，上層結論必須標範圍限制，不因其他頁已完成就蓋掉。
5. 需校驗 evidence_id 存在、來源經批准、as_of 未冒充當期、輸出未引用未供給模型的事實；使用者說想要其他新聞，也只能回報缺料，不能讓 AI 自搜。

## 4. 白話文標準（所有 OneBrain 共用）
- 第一段只回答「目前怎麼了、對我有何影響」；其後「短期／中期／長期」各用 1–3 句可理解的投資語言。
- 白話文不能省掉**重要風險、反證、資料缺口與不確定性**。例如把「營業活動現金流低於淨利」說成「帳面有賺錢，但實際收到的現金沒有跟上」；原始金額、比率、日期及模型規則放到 evidence_ref 下鑽。
- 最後列「接下來要查什麼」而非杜撰新的確定交易指令。短期中期長期不固定 3/6/9 個月，未核准視窗絕不能私下釘門檻。
- 對資料頁，先用 deterministic 的失敗清單／能力說明；只有多來源根因需要分析才用 LLM，節省 Token。
- 研究來源及人名可保留**內部 provenance**，不可作公開卡片或 OneBrain 功能名稱。

## 5. 介面草案與最小施工路徑
- 市場/標的/持股／資料各有頁內 OneBrain 按鈕；**全站總結入口建議放 📊 市場的「🤖 總結 OneBrain」**，不另增第六個主頁（五主頁中已有 🗂資料）；手機入口不得擠壓既有 ≥160px 首屏守衛，實際位置要再過視覺 Gate。
- 點擊總結不應強制每頁重跑 AI：先檢查報告 snapshot/time coverage，可重用相容 cache，不足部分 scoped refresh；沒有 source 授權的資料仍不可取。
- 先只批准 UI 草稿與 read-only coverage 掃描；Evidence schema、AI 調度、工具權限、模型路由、token 花費管理與 cache 需 High Gate。
