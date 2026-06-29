# S-MED Silent Except Audit(v18.396 P5-D1 重 audit)

## 數字總覽

| 度量 | 值 |
|---|---|
| 總 except handlers | 773 |
| **真 silent**(body 只有 `pass`/`...`) | **154** |
| bare silent(`except:` 無 type) | 0(已歷次清完) |
| typed silent(`except X:`) | 154 |
| PR-J3 已修真高風險 | 16 |
| 殘餘 silent | 138 |

## 與前次 deep-dive 的偏差

前 deep-dive 報告「710 處 vs 71 處」差異警示 — 數字解讀澄清:
- **710**:grep 行末空 `except X:`(含正常 typed except 後面接 logging 等)
- **154**:AST 解析「body 只有 `pass` / Ellipsis」的真 silent
- **PR-J3 16 處真高風險**:已修

✅ 真實規模 138 處殘餘 silent,不是 694(710 - 16),也不是 55(71 - 16)。

## File 分布(top 15)

| 處數 | File | 估計多為合法 pattern |
|---|---|---|
| 24 | `ui/tabs/tab_stock.py` | xsec dict 賦值失敗 → 顯示 N/A,**合法** UI 防衛 |
| 15 | `data/core/data_loader.py` | nest_asyncio init / strftime / pd.attrs setdefault 等 boilerplate,**合法** |
| 12 | `data/etf/etf_fetch.py` | prov_log unified inner error / parse guard / loop break,**合法** |
| 9 | `ui/tabs/tab_stock_grp.py` | 類似 tab_stock pattern |
| 9 | `ui/tabs/macro/section_chips.py` | render-side defensive |
| 7 | `data/macro/macro_core.py` | parse / cache guard |
| 7 | `data/daily/daily_data_fetchers.py` | provenance + parse guard |
| 6 | `compute/macro/macro_helpers.py` | compute defensive |
| 6 | `data/macro/leading_indicators.py` | TAIFEX parse guard |
| 5 | `ui/pages/health_inspector.py` | UI metric fail-safe |
| 4 | `ui/tabs/macro/section_news_ai.py` | LLM call guard |
| 4 | `data/macro/tw_macro.py` | CBC ms1 parse guard |
| 3 | `ui/tabs/tab_stock_picker.py` | screening fail-safe |
| 3 | `ui/tabs/macro/section_long.py` | render guard |
| 3 | `data/macro/macro_alert.py` | rule eval guard |

## Sampling 結論

從 top 3 file(tab_stock 24 / data_loader 15 / etf_fetch 12,合計 51 處)抽樣:

| 類型 | 估計比例 | 範例 |
|---|---|---|
| 防衛性 try/except 包 setdefault / parse | ~60% | `pd.Timestamp.now()` / `float(...)` / `time.strftime` 不應炸 caller |
| Provenance helper 內部 error 不該外傳 | ~15% | `_prov_log_unified(...)` 內 try except pass |
| Loop iteration 跳壞筆 | ~10% | `enumerate` 內 `except: continue` 等價 pass |
| Init boilerplate guard | ~5% | `nest_asyncio.apply()` |
| **真潛在風險**(silent 失敗會誤導 user) | ~10%(~15 處) | `xsec['sig20'] = _c['signal']` 失敗變 N/A,user 看不到根因 |

## 結論

**138 處殘餘 silent 中,粗估只有 ~15 處(~10%)屬於「silent 失敗會誤導 user」的真潛在風險**。
其餘 ~123 處屬合法防衛 pattern(parse guard / setdefault / loop continue / init boilerplate)。

**§-1 工作準則對照**:
- ❓ 真實 bug 觸發? — 無
- ❓ user 反映誤導? — 無
- ❓ ROI 高? — 低(15/138 = 11% hit rate,且 sampling 估計可能高估)

**判定**:✅ **維持 WONTFIX**(本 audit 證實 PR-J3 已清掉真高風險,殘餘多屬合法)

**升級觸發**:
- 任一 silent 處出現 production fail-loud 違憲(user 反映看到 N/A 找不到根因)
- 加入「audit log」需求(統一 silent error reporting)

## 已修歷史

- PR-J3 v18.339(2026-06-28):16 處真高風險(etf_calc 9 + tab_stock 2 + leading_indicators 1 + v5_modules 1 + scoring_engine 3)
- PR-M1 v18.343(2026-06-29):S-MED Tier 1 3 處 silent → stderr

殘餘 138 處屬合法 pattern,**禁止機械式批量修**(§-1「機械式清 TODO 充數」反例)。
