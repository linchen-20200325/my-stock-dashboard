"""
shared/signal_thresholds.py — 訊號門檻 / 評分權重 SSOT (v18.241 群 E)

CLAUDE.md §3.3 反捏造 — 此檔集中本專案高嚴重度 inline magic number,
由原 13 處散落 inline 抽出為命名常數，調用端皆 import from shared/。

【新增常數需】
1. 附「為何選這值」的依據（資料來源 / 業務規則 / 歷史校準）
2. 在 CLAUDE.md §3.3 範圍 / 合理性表登記（如適用）
3. 變數名編碼單位（_PCT / _RATIO / _DAYS / _LOTS / _TWD）避免 §4.1 量綱陷阱

【SSOT 與其他 shared/ 檔分工】
- shared/thresholds.py     → 殖利率分級（YIELD_HIGH/MID/LOW）
- shared/health_thresholds.py → 健康評分分級（HEALTH_GRADE_A/B_MIN, DEFENSE_THRESHOLD）
- shared/ttls.py           → cache TTL 常數
- shared/signal_thresholds.py（本檔）→ 信號觸發 / 評分權重 / 領域邊界
"""

# ════════════════════════════════════════════════════════════════
# 時間 / 校準常數
# ════════════════════════════════════════════════════════════════

TRADING_DAYS_PER_YEAR: int = 252
"""年化常數：台股一年約 252 個交易日（IRR / 年化波動率 / Sharpe 等用）。
跨檔複用，原散落於 macro_signal_lookback_tw.py:238 + etf_calc.py:68"""


# ════════════════════════════════════════════════════════════════
# 效率前緣（風險-報酬地圖）— 蒙地卡羅參數 SSOT（v19.167）
# ════════════════════════════════════════════════════════════════
# 依據:此為**描述性**風險-報酬視覺化(非規範性最佳化器)。STATE.md:512 曾拒
# 均值-變異數最佳化為「假精準」(牴觸 §1);本功能只把「你的組合」畫在歷史風險-
# 報酬空間、疊一片隨機配置雲 + 前緣參考線,**不**輸出「最適權重建議」。
# N_SIM / SEED 為命名 SSOT(§3.3 反捏造),SEED 固定確保可重現(§5:同輸入+同種子
# → 同一片雲),絕不 hardcode 於 compute 函式內。

EFFICIENT_FRONTIER_N_SIM: int = 3000
"""蒙地卡羅隨機配置雲的樣本數。3000 點:視覺上足以勾勒前緣輪廓、plotly 渲染
仍流暢(Scattergl);再多對「理解相對位置」的邊際效益低。純視覺取樣數,非統計推論。"""

EFFICIENT_FRONTIER_SEED: int = 42
"""蒙地卡羅 RNG 種子(np.random.default_rng(SEED))。固定值 → §5 可重現:
同一組持股報酬 + 同種子必產生**完全相同**的隨機配置雲(golden test 釘死)。"""

EFFICIENT_FRONTIER_MIN_COMMON_DAYS: int = 20
"""估年化 μ/Σ 所需的最少「共同交易日」。<20 日 → 共變異數估計過噪、前緣無意義,
compute_efficient_frontier 回 ok=False(§1 不捏造前緣),UI 顯示需更多共同歷史。
對齊 VaR 段「<20 共同日不計 VaR」的既有門檻(etf_tab_portfolio VaR section)。"""

EFFICIENT_FRONTIER_N_BINS: int = 25
"""前緣包絡線的波動度分箱數。把隨機雲依年化波動度切 25 等寬箱、每箱取最高報酬,
再取累積最大值 → 非遞減的「上緣」參考線(歷史估計,非建議)。25 箱:線夠平滑
又不過度貼合取樣噪音。"""


# ════════════════════════════════════════════════════════════════
# Macro 健康評分（macro_helpers.py compute_macro_health）
#
# ⚠️ v19.173 校準狀態誠實化（AI-H）— 只是註解，**不動任何數值**
# ────────────────────────────────────────────────────────────────
# 公式（macro_helpers.compute_macro_health）：
#     health = jqavg × HEALTH_WEIGHT_JQ
#              + min(score / max_score × 100, 100) × HEALTH_WEIGHT_SCORE
#              + (HEALTH_FNET_BONUS if fnet > 0 else 0)
#
# ① 名不副實：這條式子**建構上只有 2 個輸入**（jqavg = 旌旗指數 = **上漲佔比的
#    5 日移動平均**，屬「市場廣度」家族；score = 大盤評分）。融資／外資期貨／年線乖離／NDC／
#    M1B-M2／VIX／PMI／CPI／出口／ADL／新聞**一個都沒進來** —— 那些走
#    shared/macro_buckets 五桶燈號各自判讀。UI 上「五桶多盞紅、健康度仍不低」
#    因此不是 bug。顯示端揭露見 macro_buckets 的 health DangerSpec.note
#    + section_long.py 的 st.caption（v19.173）。
#
# ② 內部不一致（**權重已校準、決策門檻沒有**）：
#    下方兩個**權重**是 v19.102 用真實 2006–2026 資料擬合出來的
#    （n=4748、val AUC 0.753、overfit_flag=False，見 MACRO_HEALTH_WEIGHT_PROPOSAL.md）；
#    但吃這個分數做決策的兩個**切點** —— `HEALTH_DEFENSE_THRESHOLD`(35) 與
#    `BULL_MIN_SCORE`(4)，見專案根目錄 `macro_thresholds.json` —— 至今仍是手訂，
#    該檔 `"last_calibrated": null` / `"method": "default (uncalibrated)"` 就是證據。
#    等於「ROC 曲線畫出來了，operating point 卻隨手挑一個」：
#    權重端用 AUC 最佳化、切點端憑直覺，兩端的證據等級不對等。
#    待辦（本版**不做**，改門檻＝行為變更，需獨立驗證）：以同一份 2006–2026
#    樣本跑 ROC，用 Youden J（或指定 FPR 上限）選點，再經 PR 審閱寫回 JSON。
# ════════════════════════════════════════════════════════════════

HEALTH_WEIGHT_JQ: float = 0.6
"""景氣廣度 (jqavg) 在健康評分的權重。
v19.102 校準採納(user 核准方案 B):MACRO_HEALTH_WEIGHT_PROPOSAL.md
(真實 2006~2026 二十年、n=4748、val AUC 0.753、overfit_flag=False)
顯示 jqavg:score 相對重要性 ≈ 0.0337:0.0228 ≈ 60:40 → 自 0.4 升 0.6。
權重和 = 0.6+0.4 = 1.0(同步治癒 CLAUDE.md §4.2「權重和=1」漂移)。"""

HEALTH_WEIGHT_SCORE: float = 0.4
"""市場狀態評分 (score/max_score×100) 在健康評分的權重。
v19.102:正規化除數自 CONFIDENCE_SOURCE_COUNT(5,借用錯配 — market_regime
真實滿分為 4/6)改用 mkt_info['max_score'],詳 macro_helpers 健康段。"""

HEALTH_FNET_BONUS: int = 0
"""外資淨買超為正時的健康評分加分。
v19.102 校準採納:二十年真實資料擬合顯示 fnet 對「未來 20 日回撤 ≥8%」
預測力 ≈ 0(權重 +0.0006/億,方向甚至微偏反)→ 原 +20(佔滿分 1/5)歸零。
常數與公式形狀保留,供未來重校準時調整。

v19.173 補述:**0 是「校準後的明示歸零」,不是漏寫的 bug** —— 有 AUC 佐證
(同 §HEALTH_WEIGHT_* 那份 n=4748 / val AUC 0.753 擬合)。但也要誠實說:
它現在是 dead term(`+ 0` 恆等於沒加),可讀性差 —— 讀 compute_macro_health
的人會以為外資有進到分數裡,實際上沒有。刻意**不刪**:刪掉會讓「曾經評估過
外資、結論是無預測力」這件事從程式碼裡消失,下一個人很可能又把它加回去。
若未來重校準判定 fnet 仍無效,再考慮連同公式一起收斂(屬另案,需重跑 AUC)。"""

CONFIDENCE_SOURCE_COUNT: int = 5
"""信心度計算的來源總數（PMI/CPI/M2/Foreign/VIX 等 5 大來源）。原 macro_helpers.py:148 inline"""


# ════════════════════════════════════════════════════════════════
# TW 麥邊訊號 lookback（macro_signal_lookback_tw.py compute_tw_macro_signals）
# ════════════════════════════════════════════════════════════════

FOREIGN_5D_NET_THRESHOLD_YI: float = -500.0
"""外資 5 日累積買賣超警戒值（單位：億 TWD）。
< -500 億 → 連續 5 日大賣超，配合大盤 20D 跌幅 -5% 才觸發紅旗。原 macro_signal_lookback_tw.py:280 inline"""

MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI: float = 3400.0
"""融資餘額過熱警戒值（單位：億 TWD）。
> 3400 億 → 散戶過度槓桿（歷史 P95 經驗值）。原 macro_signal_lookback_tw.py:288 inline"""

M1B_M2_GAP_DETERIORATION_THRESHOLD: float = -2.0
"""M1B/M2 缺口惡化警戒值（單位：pts/月，月差分）。
< -2 pts → 資金結構轉差（M2 成長 > M1B）。原 macro_signal_lookback_tw.py:296 inline"""

TWII_20D_DROP_THRESHOLD_PCT: float = -5.0
"""加權指數 20 日跌幅警戒值（單位：%）。
< -5% → 加速確認弱勢，配合其他訊號觸發紅旗。原 macro_signal_lookback_tw.py:304 inline"""


# ════════════════════════════════════════════════════════════════
# v4 Strategy Engine —市場狀態評估（v4_strategy_engine.py macro_risk_signal）
# ════════════════════════════════════════════════════════════════

VIX_HIGH_RISK_THRESHOLD: float = 25.0
"""VIX 高風險紅燈門檻。> 25 觸發紅燈，max_position=20%。原 v4_strategy_engine.py:76 inline"""

VIX_MEDIUM_RISK_THRESHOLD: float = 20.0
"""VIX 中風險黃燈門檻。> 20 觸發黃燈，max_position=50%。原 v4_strategy_engine.py:87 inline"""

FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS: int = -20000
"""外資期貨高風險紅燈門檻（單位：口）。< -20000 口空單觸發紅燈。原 v4_strategy_engine.py:76 inline"""

FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS: int = -10000
"""外資期貨中風險黃燈門檻（單位：口）。< -10000 口空單觸發黃燈。原 v4_strategy_engine.py:87 inline"""


# ── 大額交易人「前五大留倉」計分門檻(D3/B7 抽出,單位:口)────────────────
# ⚠️ **與上面那條 -10000 同數字、不同義,嚴禁互相引用**:
#   `FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS` 量的是「**外資**期貨淨口」
#   (TX 大台 + MTX 小台×0.25,`li_latest['外資大小']`);
#   本組量的是「**台指期前五大交易人**未平倉淨部位」(TAIFEX largeTraderFutQryTbl,
#   `li_latest['前五大留倉']`)—— 兩者是不同的統計母體,只是門檻碰巧撞號。
#   同 `src/config/config.py` LEEK_* 三組門檻的分名理由(§3.3:同數字不同義不得合併)。
#
# 【現況誠實揭露】本組常數目前**還沒有 production consumer** ——
#   唯一在用這兩個數字的是 `src/ui/tabs/macro/section_chips.py` 的
#   「🎯 籌碼綜合判斷」計分器,那裡仍是 inline literal(`_top5 < -10000` / `_top5 > 0`)。
#   D3 只負責讓**教學卡**不再手打數字(改引本常數);把 section_chips 改成 import
#   本常數屬 🌍 總經分頁的施工範圍,不在 D3 批次內。
#   `tests/test_d3_toolbox_registry.py` 有 AST 漂移守衛盯著兩邊的數字一致。
TOP5_LARGE_TRADER_NET_WARN_LOTS: int = -10000
"""前五大交易人留倉淨部位**警戒線**（單位：口）。< -10000 口 → 籌碼綜合判斷 -1 分。
畫面 caption 寫作「前五大>1萬⚠️」。原 section_chips.py 籌碼綜合判斷 inline。"""

TOP5_LARGE_TRADER_NET_BULL_LOTS: int = 0
"""前五大交易人留倉淨部位**偏多線**（單位：口）。> 0 口 → 籌碼綜合判斷 +1 分。
⚠️ 0 與 -10000 之間**不計分**（既非加分也非減分）—— 這是刻意的稀疏設計,
不是漏寫;教學卡必須照實說「這區間不亮燈」,不得腦補一個中性帶。"""


# ════════════════════════════════════════════════════════════════
# scoring_engine — ATR % 風險分級
# ════════════════════════════════════════════════════════════════

ATR_PCT_LOW: float = 0.03
"""ATR% 低波動門檻（atr_pct = ATR14 / close）。< 3% → atr_score=2。原 scoring_engine.py:92 inline"""

ATR_PCT_HIGH: float = 0.05
"""ATR% 高波動門檻。3-5% → atr_score=1；> 5% → 0。原 scoring_engine.py:92 inline"""


# ════════════════════════════════════════════════════════════════
# exit_signals — 月線正乖離
# ════════════════════════════════════════════════════════════════

MA20_POSITIVE_DEVIATION_THRESHOLD_PCT: float = 15.0
"""月線（MA20）正乖離率警戒值（單位：%）。
> +15% → 月線正乖離過大，列入 bearish 警示條件。原 exit_signals.py:80 inline"""


# ════════════════════════════════════════════════════════════════
# v5_modules — 龍多股篩選
# ════════════════════════════════════════════════════════════════

CONTRACT_LIABILITY_YOY_GROWTH_THRESHOLD_PCT: float = 20.0
"""合約負債年增率（YoY）入選龍多股的門檻（單位：%）。
> 20% → 訂單能見度強。原 v5_modules.py:57 inline"""

CAPEX_TO_EQUITY_RATIO_THRESHOLD_PCT: float = 80.0
"""資本支出 / 股本比率入選龍多股的門檻（單位：%）。
> 80% → 大舉擴產訊號。原 v5_modules.py:58 inline"""

CONTRACT_LIABILITY_TO_EQUITY_RATIO_THRESHOLD_PCT: float = 50.0
"""合約負債 / 股本比率「客戶預付旺」門檻（單位：%）。v19.178 抽出。

≥ 50% → 客戶大量預付、訂單能見度高，與 CAPEX_TO_EQUITY_RATIO_THRESHOLD_PCT（80%）
任一成立即判「符合龍頭高成長特徵」。原 `src/ui/tabs/tab_stock.py:1681` inline `>= 50`，
且同一行的判定文案（餵給個股 AI prompt 的「龍頭擴產檢測」）另抄一份 `50%`
→ §3.3 兩份複本。注意與 `CONTRACT_LIABILITY_YOY_GROWTH_THRESHOLD_PCT`（20%）**語意不同**：
後者是合約負債的**年增率**，本常數是合約負債**對股本的比率**，不可互換。"""


# ════════════════════════════════════════════════════════════════
# 市場狀態判斷 — market_strategy.market_regime()
# ════════════════════════════════════════════════════════════════

MARKET_BREADTH_NEUTRAL_PCT: float = 50.0
"""市場廣度（漲跌家數比 ad_ratio,0-100% 上漲家數佔比）中性分界。

> 50% → 廣度正向（多數個股上漲）；< 50% → 廣度偏弱。與 `shared/macro_buckets.py`
`adl` DangerSpec（yellow=50.0/red=35.0）同一尺度、同一資料源(`daily_data_fetchers.
fetch_adl` 的 `ad_ratio` 欄位)，避免同名參數在兩處用不同中心值（v18.449 修復:
`market_regime()` 原碼誤用 `ad_ratio > 1.0` 當門檻 + 預設值 1.0，屬「比值」尺度
語意，與實際資料源的「0-100% 百分比」尺度不符——預設值恰好等於門檻，導致此因子
從未真正生效過，UI 上「市場廣度」chip 永遠顯示同一個寫死 1.00。原 market_strategy.
py:107 inline `1.0`"""

# ════════════════════════════════════════════════════════════════
# ETF — 主動式 ETF 折溢價邊界
# ════════════════════════════════════════════════════════════════

ACTIVE_ETF_PREMIUM_MAX_PCT: float = 2.0
"""主動式 ETF |折溢價| 門檻（單位：%）。
> 2% → NAV 可能 stale。原 etf_calc.py:272 inline `_ACTIVE_PREM_MAX`"""

PASSIVE_ETF_PREMIUM_MAX_PCT: float = 3.0
"""被動式 ETF |折溢價| 合理上限（單位：%）。超過視為 NAV 過時配當日市價的假溢價。

v18.442:0050 production bug — 即時來源(yfinance navPrice / goodinfo)回「最後一筆
已公告淨值」並被 fetch_etf_nav_history 硬戳 `_last_bd`(今日)。若該 NAV 實為數日前值
(0050 案 104.03=06/29 淨值),配當日已上漲的市價(109.3)→ 同日 inner-join 成功、日期
守門員(G1/G3)全過(日期已被造假成今日),但算出假 +5.07%「嚴禁追高」。原 G2 上限守門員
只對主動式生效(`_is_active_etf`),被動式 0050 漏接 → 補此常數。

值 = 3.0 對齊 ETF_PREMIUM_HIGH_PREMIUM_PCT 帶頂(> 3% 原即「禁止追高」極端區):被動式
(尤其深度套利的大型市值型)真實溢價幾乎不越 1%,>3% 幾可斷定為 NAV 未更新;同時保留海外
連結型 ETF(如 00646)隔夜跳空的真實 1-3% 溢價顯示,避免誤殺。主動式(NAV T+1 易延遲)仍取
較嚴的 2%。§1 寧缺勿假:超限一律回 stale(顯示「NAV 資料延遲」)而非假折溢價。"""

ETF_SHARPE_RF_FALLBACK_PCT: float = 5.33
"""ETF 夏普值無風險利率 fallback(單位:% 年化)。

v19.106(第九份 review ⑨):原 etf_calc.calc_sharpe 預設寫死 rf=5.33(2024 年
FEDFUNDS 水準),利率變動後夏普失真。現行設計:etf_grp_compare_service 於批次
評分前抓 FRED FEDFUNDS(1h cache)注入 `etf_calc.set_risk_free_rate_pct`;本常數
僅在注入失敗(FRED 全斷)時作 fallback — 對齊 Fund repo `fund_service._RF_ANNUAL`
同 pattern(由 app 注入 FEDFUNDS)。值保留 5.33 = 原行為,注入失敗時零位移。"""


# ════════════════════════════════════════════════════════════════
# 今日關鍵橫幅 — 急變層 Δ 門檻(v19.108,第九份 4-C 精簡版)
# 門檻層直接吃 MACRO_ALERT_RULES(config.py SSOT)命中,不另設第二套;
# 本組常數只管「急變層」(單期變化率),僅涵蓋 macro_info 內有真 prev/序列
# 的指標(§1 不對只有單點的指標腦補變化)。
# ════════════════════════════════════════════════════════════════

KEY_ALERT_VIX_DAY_SPIKE_PCT: float = 20.0
"""VIX 單日漲幅急變門檻(單位:%)。

vix block 帶 3 個月日序列(macro_snapshot fetch_vix_block `values`),取最後
兩點算單日變化。≥ +20% = 罕見級恐慌急升(2018 Volmageddon +115%、2020/2、
2024/8 圓套利平倉皆遠超此值;20% 約一年觸發 1~3 次,當「今天必須看」級)。
只看急升不看急跌(恐慌消退非風險事件)。"""

KEY_ALERT_FED_FUNDS_MOVE_PCTPT: float = 0.20
"""聯邦基金月均利率單期變動門檻(單位:百分點)。

fed_funds block 帶 current+prev(月均)。|Δ| ≥ 0.20 個百分點 ≈ 該月有
一碼(0.25)級的政策動作(月均平滑後略低於 0.25)— 升降息節奏改變當
「今天必須看」級,雙向皆亮(升息=緊縮風險/降息=衰退對沖訊號)。"""


# ════════════════════════════════════════════════════════════════
# Macro 通用領域邊界（macro_core.py / merrill_clock.py）v18.242 W3b
# ════════════════════════════════════════════════════════════════

RECESSION_LOGIT_COEF_SPREAD: float = -1.5
"""衰退機率 logit 回歸 — 利差 (10Y-3M) 係數。對齊 Fund 端同名常數。
logit = COEF_SPREAD * spread_10y3m + COEF_INTERCEPT,經 sigmoid → recession prob。
原 macro_core.py:1307 inline"""

RECESSION_LOGIT_COEF_INTERCEPT: float = -0.8
"""衰退機率 logit 回歸 — 截距項。原 macro_core.py:1307 inline"""

PMI_VALID_MIN: float = 30.0
"""PMI 採購經理指數合理下限（歷史極端衰退底部）。
< 30 視為解析錯誤過濾。對應 CLAUDE.md §3.2 + §4.2 不變量。原 merrill_clock.py:107 inline"""

PMI_VALID_MAX: float = 70.0
"""PMI 採購經理指數合理上限（歷史極端擴張頂部）。
> 70 視為解析錯誤過濾。原 merrill_clock.py:107 inline"""

MACRO_MERGE_ASOF_TOLERANCE_DAYS: int = 40
"""跨頻 merge_asof tolerance（單位：日曆日）。
月 macro vs 日 series 對齊用,40 日覆蓋一個月內任意營業日 backward join。
對應 CLAUDE.md §2.3 + §4.5 時序對齊。原 macro_core.py:1336 inline"""

MACRO_TREND_LOOKBACK_PERIODS: int = 6
"""macro snapshot trend arrow lookback 視窗（單位：期,月度資料即 6 個月）。
用於 make_indicator() 的 trend 箭頭計算。原 macro_core.py:1366 inline"""


# ════════════════════════════════════════════════════════════════
# 三大法人 sanity check(§3.2 v18.299)
# ════════════════════════════════════════════════════════════════

INST_NET_OUTLIER_VOLUME_RATIO: float = 5.0
"""三大法人單日買賣超 outlier 判定門檻(倍數)。
CLAUDE.md §3.2:|inst_net_shares| > 30D 均量 × 5.0 視為異常筆,可能為:
- 大宗交易 / 鉅額委託(非正常市場行為,投資判斷不能依此)
- FinMind/TWSE 解析錯誤(欄位錯位、單位誤判)
- 該股流動性極差(小型股,30D 均量本身偏低 → ratio 容易爆表)
觸發後 caller 應:(a) log 告警 + (b) 旗標 is_outlier=True,**不**靜默使用。

數值依據:依台股法人散戶結構,正常單日法人淨買賣超約 5-15% 均量。
> 5× 均量 = > 500% 比率,屬統計極端尾部,需人工檢視。"""


# ════════════════════════════════════════════════════════════════
# 個股組合（tab_stock_grp）— 操作狀態燈 + 多因子評級（v18.322 SSOT 化）
# 原 inline 散落於 tab_stock_grp.py / scoring_engine.py，本版抽出。
# 詳見 SPEC.md「個股組合評分門檻 SSOT」。同步退役「舊評分」(④ 汰弱留強改純健康度排)。
# ════════════════════════════════════════════════════════════════

GRP_VOL_SHRINK_RATIO: float = 0.7
"""操作狀態燈「量縮」判定：當日量 < 20 日均量 × 0.7。
配合健康度 A 級 + 多頭 + 近 20MA → 🔵 加碼燈（量縮打底蓄勢）。原 tab_stock_grp.py:299 inline"""

GRP_NEAR_MA20_BIAS_PCT: float = 3.0
"""操作狀態燈「近 20MA」判定：|MA20 乖離率| < 3%（單位：%）。
貼近月線視為位階健康，為 🔵 加碼燈條件之一。原 tab_stock_grp.py:300 inline"""

GRP_BIAS_OVERHEAT_WARN_PCT: float = 25.0
"""操作狀態燈「乖離過熱」警示：MA20 乖離率 > +25%（單位：%）→ 🟡 警示燈。
短線漲多偏離月線過大。原 tab_stock_grp.py:303 inline"""

GRP_NEWS_BEARISH_CONFIDENCE_MIN: float = 50.0
"""組合風控「利空新聞」採信門檻：AI 情緒 confidence ≥ 50 才計入利空。
低於 50 視為雜訊不計。原 tab_stock_grp.py:601 inline"""

MULTIFACTOR_GRADE_A_MIN: float = 75.0
"""多因子總分 A 級下限（0-100）。≥75 → A（強）。原 scoring_engine.py:355 inline。
與健康度分級（HEALTH_GRADE_A_MIN=80）為不同評分體系，門檻各自獨立。"""

MULTIFACTOR_GRADE_B_MIN: float = 55.0
"""多因子總分 B 級下限（0-100）。≥55 → B（中）；< 55 → C（弱）。原 scoring_engine.py:357 inline"""

MULTIFACTOR_ENTRY_MIN: float = 70.0
"""多因子總分「入選候選」門檻（0-100）。≥70 → 列為可進場候選（③ 多因子排行）。
原 tab_stock_grp.py:521 inline"""

TREND_MIN_REVENUE_MONTHS: int = 1
"""財報趨勢分數「月營收子分數可評分」最少月份數（B5-b 2026-08）。

`compute_monthly_revenue_subscore` 在 `yoy_vals` 為空時回 `(0.0, {"n_months": 0})`
——那個 0.0 **不是「持平」而是「沒有資料」**。消費端（🏆 個股組合「📊 財報趨勢×轉機」）
必須用本常數判定該檔是否可評分，缺料一律標「⚪ 無法評分」，
不得讓 0.0 混進 5 段判定（0.0 正好落在「➖ 中性」帶正中央）。"""

TREND_MIN_FIN_SNAPSHOTS: int = 2
"""財報趨勢分數「季財報子分數可評分」最少快照季數（B5-b 2026-08）。

鏡射 `src/compute/health/fin_trend_score.compute_fin_trend_subscore`：
`n < 2 → (0.0, {"reason": "insufficient_snapshots"})`。同理那個 0.0 是「無法比較」
不是「沒有變化」。兩處一致性由 `tests/test_b5b_stock_grp.py` 的**行為斷言**釘住
（真的呼叫 compute_fin_trend_subscore 驗邊界），不是字串掃描。"""

SCREENER_MIN_FACTOR_COVERAGE_RATIO: float = 0.5
"""選股網（fundamental_screener_service）綜合分「最低因子涵蓋」門檻（比例，0-1）。

一檔要「有資料的勾選因子數 > 勾選因子總數 × 本比例」（嚴格過半）才進綜合排序，
否則綜合分 = None（排最後）。防「只有單一因子有資料、又剛好高分」的股（如只有
抗跌RS=100 的上櫃股）以 100 衝頂 —— 此為 v19.90「綜合分只平均有資料因子」的反向
副作用（缺料完全不罰 → 單因子高分封頂）。比較用嚴格 `>`：3 勾需 ≥2、2 勾需 2、
1 勾需 1（單因子勾選維持原行為）。"""


# ════════════════════════════════════════════════════════════════
# scoring_engine 評分曲線 / 交易濾網斷點（v18.324 全抽，user 2026-06-27 指定）
# ─────────────────────────────────────────────────────────────────
# 說明：本區塊收 scoring_engine.py 各「判斷門檻」(value→score/label/signal 的比較斷點)。
# **不收**：指標視窗期(MA5/20/60/120、RSI14、ATR14、rolling 20)=TA 慣例非判斷門檻、
#   評分輸出值(2/1/0 子分、/6 /3 *100 正規化)=評分刻度結構、數學防呆(1e-10)、
#   年化倍數(×4)、日數慣例(360/365)、自然零界(>0)。
# 前綴分名（MOM_/RISK_/RS_/SQ_/FGMS_/LEAD_/CL_/BOLL_/FAKEOUT_/RR_/ATR_STOP_/
#   TIME_STOP_/VCP_/SQUEEZE_/POS_）確保「同數字不同義」不被硬湊成同一常數。
# ════════════════════════════════════════════════════════════════

# ── 動能分數（calc_momentum_score）────────────────────────────
MOM_SHARPE_GOOD: float = 0.5
"""Sharpe-like 動能（Return20/Sigma20 年化代理）優分門檻：>0.5 → 2 分。原 scoring_engine.py:89 inline"""

# ── 風險分數（calc_risk_score）波動率分級 ─────────────────────
RISK_VOL_VERYLOW_RATIO: float = 0.02
"""日波動率（20D std）極低門檻：<2% → +1 分（ETF/權值股）。原 scoring_engine.py:206 inline"""

RISK_VOL_LOW_RATIO: float = 0.035
"""日波動率正常低門檻：<3.5% → +1 分（原 3% 門檻已鬆寬）；≥3.5% 視為高波動高風險。原 scoring_engine.py:207 inline"""

# ── RS 相對強度（calc_rs_score）────────────────────────────────
# 無大盤基準時：個股絕對漲幅(%) 映射分數
RS_ABS_RET_T1_PCT: float = 50.0
"""RS 絕對漲幅 T1：≥50% → 100 分。原 scoring_engine.py:278 inline"""
RS_ABS_RET_T2_PCT: float = 30.0
"""RS 絕對漲幅 T2：≥30% → 90 分。原 scoring_engine.py:279 inline"""
RS_ABS_RET_T3_PCT: float = 15.0
"""RS 絕對漲幅 T3：≥15% → 75 分。原 scoring_engine.py:280 inline"""
RS_ABS_RET_T4_PCT: float = 5.0
"""RS 絕對漲幅 T4：≥5% → 60 分。原 scoring_engine.py:281 inline"""
# 有大盤基準時：RS = 個股漲幅 / |大盤漲幅| 分段
RS_IDX_FLAT_EPS_PCT: float = 1.0
"""RS 大盤近乎平盤門檻(v19.90 批次3b):|大盤 N 日漲幅| < 1.0% 視為平盤,走絕對
漲幅路徑,避免 rs = stock_chg / |idx_chg| 在近零分母時爆炸(如 idx=0.01% → 放大
數千倍 → 誤判 100 分)。原只守 idx_chg==0,近零仍炸。不動 RS_BAND 校準值,僅把
分母近零的退化情形導向既有絕對漲幅路徑。"""
RS_BAND_T1: float = 2.0
"""RS 相對強度 T1：≥2.0 → 100 分（強勢）。原 scoring_engine.py:288 inline"""
RS_BAND_T2: float = 1.5
"""RS 相對強度 T2：≥1.5 → 90 分。原 scoring_engine.py:289 inline"""
RS_BAND_T3: float = 1.0
"""RS 相對強度 T3：≥1.0 → 75 分（與大盤同步）。原 scoring_engine.py:290 inline"""
RS_BAND_T4: float = 0.5
"""RS 相對強度 T4：≥0.5 → 55 分；≥0 → 40；<0 → 20（弱勢）。原 scoring_engine.py:291 inline"""

# ── RS σ 標準化超額報酬分級（calc_relative_strength / 抗跌 RS 選股）───────
# Mansfield 式：RS = (個股區間報酬 − 大盤區間報酬) / 大盤日報酬σ。單位 = σ（標準差倍數）。
# 用於「大盤下跌時仍贏過大盤」語意（比值法 RS_BAND 在大盤負報酬時會失真，故另立此組）。
RS_SIGMA_LEAD_MIN: float = 1.0
"""RS σ 領漲門檻：avg_rs ≥ +1.0σ → 🔴 逆勢強股（顯著強於大盤）。原 v5_modules.py:124 inline"""
RS_SIGMA_MILD_MIN: float = 0.3
"""RS σ 溫和抗跌門檻：avg_rs ≥ +0.3σ → 🟡 偏強（略強於大盤）。原 v5_modules.py:127 inline"""
RS_SIGMA_LAG_MAX: float = -0.3
"""RS σ 落後門檻：avg_rs < −0.3σ → 🟢 弱勢（弱於大盤，空頭優先出清）；[−0.3,0.3) → ⚪ 同步。原 v5_modules.py:130 inline"""

# ── 獲利品質 SQ（calc_quality_score）─────────────────────────
SQ_GM_TREND_DELTA_PCT: float = 1.0
"""毛利率趨勢顯著門檻：近2季均 - 前2季均 > +1pp → ↑；< -1pp → ↓；其間 → 持穩。原 scoring_engine.py:470 inline"""
SQ_REV_UP_RATIO: float = 1.02
"""營收趨勢↑門檻：近2季均 > 前2季均 × 1.02（成長>2%）。原 scoring_engine.py:477 inline"""
SQ_GM_LEVEL_HIGH_PCT: float = 50.0
"""毛利率絕對值高分線：≥50% → SGM=100。原 scoring_engine.py:488 inline"""
SQ_GM_LEVEL_LOW_PCT: float = 10.0
"""毛利率絕對值低分線：≤10% → SGM=40；10~50% 線性內插。原 scoring_engine.py:489 inline"""
SQ_GOOD_MIN: float = 75.0
"""SQ 獲利品質「優質」標籤下限（≠ 多因子總分 75，本為毛利×營收交叉品質分）。原 scoring_engine.py:496 inline"""
SQ_STABLE_MIN: float = 55.0
"""SQ「穩健」標籤下限。原 scoring_engine.py:497 inline"""
SQ_FAIR_MIN: float = 40.0
"""SQ「普通」標籤下限；< 40 → 弱。原 scoring_engine.py:498 inline"""

# ── 前瞻成長動能 FGMS（calc_forward_momentum_score）─────────
FGMS_W_CL: float = 0.40
"""FGMS 維度權重 — 合約負債動能。原 scoring_engine.py:657 inline"""
FGMS_W_INV: float = 0.30
"""FGMS 維度權重 — 存貨營收背離率。原 scoring_engine.py:657 inline"""
FGMS_W_THREE: float = 0.20
"""FGMS 維度權重 — 三率趨勢。原 scoring_engine.py:657 inline"""
FGMS_W_CAPEX: float = 0.10
"""FGMS 維度權重 — 資本支出強度。原 scoring_engine.py:657 inline"""
FGMS_CL_RATIO_STRONG: float = 0.5
"""合約負債 CL Ratio（最新CL/近4季均營收）強門檻：>0.5。原 scoring_engine.py:572 inline"""
FGMS_CL_RATIO_MID: float = 0.2
"""CL Ratio 中門檻：>0.2 → 55 分。原 scoring_engine.py:574 inline"""
FGMS_CL_RATIO_LOW: float = 0.05
"""CL Ratio 低門檻：>0.05 → 40 分。原 scoring_engine.py:575 inline"""
FGMS_CL_QOQ_UP_PCT: float = 10.0
"""CL QoQ 加速門檻：>10% → 動能向上。原 scoring_engine.py:572 inline"""
FGMS_CL_QOQ_DOWN_PCT: float = -10.0
"""CL QoQ 衰退門檻：<-10% → 20 分。原 scoring_engine.py:576 inline"""
FGMS_DIV_T1_PCT: float = 15.0
"""存貨營收背離率（Rev YoY - 存貨天數 YoY）T1：>15% → 100 分（賣得快）。原 scoring_engine.py:611 inline"""
FGMS_DIV_T2_PCT: float = 5.0
"""背離率 T2：>5% → 75 分。原 scoring_engine.py:612 inline"""
FGMS_DIV_T3_PCT: float = -5.0
"""背離率 T3：≥-5% → 50 分。原 scoring_engine.py:613 inline"""
FGMS_DIV_T4_PCT: float = -15.0
"""背離率 T4：≥-15% → 30 分；< -15% → 10 分。原 scoring_engine.py:614 inline"""
FGMS_REV_YOY_GOOD_PCT: float = 10.0
"""無背離資料時的營收 YoY 退路門檻：>10% → 65；>0 → 50；其餘 30。原 scoring_engine.py:617 inline"""
FGMS_RATE_DELTA_PCT: float = 0.5
"""三率（毛利/營益/淨利率）趨勢顯著門檻：近2季均 vs 前2季均差 > ±0.5pp 計入。原 scoring_engine.py:632 inline"""
FGMS_CAPEX_T1_PCT: float = 20.0
"""資本支出 YoY T1：>20% → 100 分（積極擴產）。原 scoring_engine.py:649 inline"""
FGMS_CAPEX_T2_PCT: float = -20.0
"""資本支出 YoY T2：>-20% → 45 分；≤-20% → 20 分。原 scoring_engine.py:651 inline"""
FGMS_LABEL_T1: float = 75.0
"""FGMS「前景亮麗」標籤下限。原 scoring_engine.py:679 inline"""
FGMS_LABEL_T2: float = 60.0
"""FGMS「動能向上」標籤下限。原 scoring_engine.py:680 inline"""
FGMS_LABEL_T3: float = 45.0
"""FGMS「持平觀察」標籤下限。原 scoring_engine.py:681 inline"""
FGMS_LABEL_T4: float = 30.0
"""FGMS「動能減弱」標籤下限；< 30 → 前景偏弱。原 scoring_engine.py:682 inline"""

# ── 基本面先行指標 narrative（calc_leading_indicators_detail）─
LEAD_CL_QOQ_SURGE_PCT: float = 20.0
"""I3 合約負債 QoQ 爆增：>20% → 🟢。原 scoring_engine.py:820 inline"""
LEAD_CL_QOQ_UP_PCT: float = 5.0
"""I3 合約負債 QoQ 穩健：>5% → 🟢；>-5% → 🟡 持平。原 scoring_engine.py:822 inline"""
LEAD_CL_QOQ_DOWN_PCT: float = -5.0
"""I3 合約負債 QoQ 下降：≤-5% → 🔴。原 scoring_engine.py:824 inline"""
LEAD_ASSET_DISPOSAL_RATIO: float = 2.0
"""I4/I5 重大資產處分偵測：處分資產現金流入 / CapEx_TTM > 2.0 → 事件驅動。原 scoring_engine.py:870,922 inline"""
LEAD_CAPEX_RATIO_CHG_UP_PCT: float = 15.0
"""I4 資本支出/營收比率 YoY 顯著上升：>15% → 🟢 積極擴產。原 scoring_engine.py:885 inline"""
LEAD_CAPEX_RATIO_CHG_DOWN_PCT: float = -20.0
"""I4 CapEx 比率 YoY 收縮容忍：>-20% → 🟡；≤-20% → 🔴 縮減投資。原 scoring_engine.py:891 inline"""
LEAD_INV_QOQ_DROP_PCT: float = -10.0
"""I5 存貨/銷售比 QoQ 大降：<-10% → 🟢 快速去化。原 scoring_engine.py:943,949 inline"""
LEAD_INV_QOQ_RISE_PCT: float = 15.0
"""I5 存貨/銷售比 QoQ 上升容忍：<15% → 🟡；≥15% → 🔴 積壓風險。原 scoring_engine.py:953 inline"""

# ── 進階量化因子 check_*（v3.2）───────────────────────────────
# v19.174 去識別化：原標題帶尊稱，改為中性描述
CL_SURGE_YOY_PCT: float = 30.0
"""合約負債大增（隱形冠軍因子）YoY 門檻：>30% 且 ratio>10% → 隱形冠軍潛力。原 scoring_engine.py:1096 inline"""
CL_SURGE_RATIO_PCT: float = 10.0
"""合約負債/資本額比率門檻：>10%。原 scoring_engine.py:1096 inline"""
CL_GROWTH_YOY_PCT: float = 15.0
"""合約負債成長中標籤門檻：YoY >15%。原 scoring_engine.py:1099 inline"""
BOLL_BW_WIDE_PCT: float = 3.0
"""布林帶寬爆發門檻：今日帶寬 >3%。原 scoring_engine.py:1128 inline"""
BOLL_BW_TIGHT_PCT: float = 2.0
"""布林帶寬壓縮門檻：今日帶寬 <2% → 蓄勢待發。原 scoring_engine.py:1131 inline"""
BOLL_UPPER_PROXIMITY: float = 0.98
"""布林突破收盤逼近上軌比例：收盤 ≥ 上軌×0.98。原 scoring_engine.py:1128 inline"""
FAKEOUT_VOL_RATIO: float = 3.0
"""假突破爆量門檻：成交量 > 20日均量 ×3。原 scoring_engine.py:1153 inline"""
FAKEOUT_TAIL_RATIO: float = 0.6
"""假突破長上影線門檻：(最高-收盤)/(最高-最低) >0.6 → 主力出貨。原 scoring_engine.py:1153 inline"""
RS_STRONG_DAYS_MIN: int = 3
"""相對強度強勢股門檻：近N日中至少 3 天個股漲幅 > 大盤。原 scoring_engine.py:1179 inline"""

# ── 風控 / 部位（calc_rr_ratio / calc_atr_stop / check_time_stop / VCP / squeeze / position）──
RR_DEFAULT_TARGET_GAIN: float = 0.15
"""盈虧比預設目標漲幅：entry × (1+0.15) = +15%。原 scoring_engine.py:1190 inline"""
RR_MIN: float = 2.0
"""盈虧比通過門檻：≥2.0 才顯示（模組四剔除 <2）。原 scoring_engine.py:1196 inline"""
ATR_STOP_MULTIPLIER: float = 1.5
"""ATR 動態停損預設倍數：Stop = Entry - 1.5×ATR14。原 scoring_engine.py:978 inline default"""
ATR_STOP_FIXED_PCT: float = 8.0
"""ATR 計算失敗/資料不足時的固定停損百分比：8%（stop = entry×0.92）。原 scoring_engine.py:986,988 inline"""
TIME_STOP_MIN_GAIN: float = 0.02
"""時間停損最低報酬門檻：持有滿 max_days 但報酬 <2% → 建議換股。原 scoring_engine.py:1016 inline default"""
TIME_STOP_MAX_DAYS: int = 15
"""時間停損最大持有天數：超過 15 天且報酬不足 → 觸發。原 scoring_engine.py:1016 inline default"""
VCP_ATR_CONTRACTION_RATIO: float = 0.8
"""VCP 波動收縮確認：ATR5 < ATR20 ×0.8。原 scoring_engine.py:1050 inline"""
SQUEEZE_SHORT_RATIO_MIN: float = 0.3
"""軋空加分券資比門檻：>30%（short_ratio>0.3）。原 scoring_engine.py:1071 inline"""
SQUEEZE_INST_BUY_DAYS_MIN: int = 3
"""軋空加分法人連買門檻：≥3 天。原 scoring_engine.py:1071 inline"""
SQUEEZE_BONUS: int = 5
"""軋空加分分數：券資比+法人連買同時成立 → 總分 +5（上限 100）。原 scoring_engine.py:1072 inline"""
POS_MAX_RISK_PCT: float = 0.015
"""動態部位單筆最大虧損比例：總資金 ×1.5%。原 scoring_engine.py:1208 inline default"""
POS_ATR_MULTIPLIER: float = 1.5
"""動態部位停損 ATR 倍數：Stop = Entry - 1.5×ATR14。原 scoring_engine.py:1223 inline"""
POS_MAX_STOP_PCT: float = 0.85
"""動態部位最大停損保護：stop_loss 不低於 entry×0.85（最大停損 15%）。原 scoring_engine.py:1224 inline"""


# ════════════════════════════════════════════════════════════════
# 融資餘額警戒黃線 + 市場廣度 + macro_compass 殖利率（v18.326 PR-C 稽核 B 類）
# user 2026-06-27 跨檔稽核補抽。divergent 值各自具名（保行為），不一致處於 SPEC §15 旗標待統一。
# ════════════════════════════════════════════════════════════════

MARGIN_BALANCE_WARN_THRESHOLD_YI: float = 2500.0
"""融資餘額**黃線**警戒值（億 TWD）。> 2500 億 → 🟡 警戒（紅線 3400 見 MARGIN_BALANCE_OVERHEAT）。
v18.327：統一黃線（MK 籌碼面「提早預警」邏輯），SQL 邏輯卡片原 2800 已下修對齊本值。
原 daily_checklist:816 / tab_macro:949,986,2172,2186,4289 inline。"""

MARGIN_BALANCE_SANITY_MIN_YI: float = 500.0
"""融資餘額多源解析**合理區間下限**（億 TWD，§3.2 範圍檢查）。
換算後 < 500 億 → 疑似單位誤判（如仟元被當萬元,錯 10×）或抓錯欄位,棄用該來源改走下一 fallback。
台股融資餘額 2008 金融海嘯低點 ≈1,100 億,現代史未低於此值。v19.74 review 修正新增,
取代 daily_data_fetchers.fetch_margin_balance 原 inline `100 < x < 30_000` 過鬆區間。"""

MARGIN_BALANCE_SANITY_MAX_YI: float = 10000.0
"""融資餘額多源解析**合理區間上限**（億 TWD = 1 兆，§3.2 範圍檢查）。
換算後 > 1 兆 → 疑似單位誤判（如元被當仟元,錯 100×~1000×）,棄用該來源改走下一 fallback。
近年高點 ≈3,300 億（2024/07）,上限留 3× 頭部空間避免多頭市場誤殺真值。v19.74 review 修正新增。"""

PRICE_CACHE_HOLIDAY_TOLERANCE_CALENDAR_DAYS: int = 14
"""價格 pkl 快取「序列最新日 vs 預期交易日」容忍窗（單位:日曆日）。
原 app_stock_fetchers.fetch_price_data inline `<= 5`（只涵蓋週末+1 假日）;
台股春節封關最長 gap = 13 日曆日（2025:1/21 封關 → 2/3 開紅盤）,原 5 天窗在連假期間
把「休市無新資料」誤判為 stale → 每次冷啟動全檔強制重抓 → 撞 FinMind/yfinance 限流。
放寬至 14 涵蓋春節最壞情境;真正的資料新鮮度仍由 pkl TTL(0.5h)+ @st.cache_data TTL 把關,
本窗僅防「快取剛寫入但序列過舊」極端態,放寬的完整性代價可忽略。v19.74 review 修正新增。"""

BREADTH_BULL_PCT: float = 60.0
"""市場廣度（jq_ratio / ADL 上漲佔比 %）多頭線：≥60% → 🟢 多頭積極 / bull regime。
原 tab_macro:880,1345-1348,4052-4053,4058-4059 inline。"""

BREADTH_NEUTRAL_PCT: float = 40.0
"""市場廣度中性/黃線：40~60% → 🟡 中性均衡 / neutral regime；< 40% → bear。
v18.327：統一黃線，「全市場健康度」beginner KPI(880) 原 30 已上修對齊本值（提供預警緩衝區）。
原 tab_macro:880,1345-1348,4052-4053,4058-4059 inline。"""

BREADTH_BEAR_PCT: float = 20.0
"""市場廣度位階標籤底線：≥20% → '20~40%' 位階；< 20% → '0~20%'（極弱）。原 tab_macro:1345 inline。"""

# ── v19.183 D2：短線急殺桶「上漲佔比 × ADL」判讀門檻（§3.3 收斂）─────────────
# 同一個檔（section_short.py）同時存在兩套寫法：KPI 卡已走 BREADTH_BULL/NEUTRAL，
# 但上方的 `_adl_concl` 分支還寫著 inline 70 / 60 / 40 —— 改一邊漏一邊的典型佈局。
# 60 / 40 直接改吃既有常數；70 這一階原本沒有具名常數，於此補上。

BREADTH_STRONG_BULL_PCT: float = 70.0
"""市場廣度「全面多頭」線：上漲佔比 ≥70% → 廣度充足，可積極持股。
比 `BREADTH_BULL_PCT`(60) 更嚴的一階，只用於 section_short 的敘事分級，
**不參與**任何燈號 / regime 判定。原 section_short.py `_ratio2 >= 70` inline。"""

# ── AD 值（漲家 − 跌家，單位：家數）判讀門檻 ─────────────────────────────
# ⚠️ §4.1 量綱：AD 值是**家數差**（整數，量級數百），與上方 BREADTH_*（**百分比**）
# 不同量綱，兩者不可互相代入。

BREADTH_AD_EXPANSION_COUNT: int = 200
"""AD 值 > +200 家 → 🟢 廣度擴張、多頭健康。原 section_short.py inline `_adl_ad > 200`。"""

BREADTH_AD_CONTRACTION_COUNT: int = -100
"""AD 值 < −100 家 → 🔴 廣度萎縮、主力集中在少數股；
−100 ≤ AD ≤ +200 → 🟡 廣度收窄、市場整理。原 section_short.py inline `_adl_ad >= -100`。"""

BREADTH_AD_DIVERGENCE_COUNT: int = -50
"""指數上漲但 AD 值 < −50 家 → 背離警訊（少數權值股撐盤）。
原 section_short.py inline `_ad2 < -50` / `_adl_ad < -50`（兩處同值）。"""

BREADTH_DIVERGENCE_INDEX_PCT: float = 0.5
"""背離偵測所需的**指數**日漲跌幅門檻（%）：|大盤 pct| > 0.5% 才視為「指數明確上漲/下跌」，
避免用 ±0.05% 的雜訊日去宣告「指數漲但廣度萎縮」。
原 section_short.py inline `_twii_pct2 > 0.5` / `< -0.5` / `_twii_pct > 0.5`（三處同值）。"""

# ── v19.183 D2：拐點面板乖離門檻（§3.3 收斂）────────────────────────────────
# ⚠️ 與 `STOCK_BIAS_*`（個股，±20 / ±15）**同名不同義**：本組是**大盤指數**
# （^TWII）的拐點偵測門檻，敏感度刻意更高（頂/底轉折要早知道），不可互換。

PIVOT_BIAS_240_PCT: float = 10.0
"""大盤年線(MA240)乖離拐點門檻（%，左右對稱）：
> +10% → 頂部拐點區間；< −10% → 底部拐點區間。
原 src/ui/tabs/macro/section_state.py inline `_b240 > 10` / `< -10`。"""

PIVOT_BIAS_20_PCT: float = 8.0
"""大盤月線(MA20)乖離拐點門檻（%，取絕對值）：|bias20| > 8% → 短線過熱 / 超賣。
原 src/ui/tabs/macro/section_state.py inline `abs(_b20) > 8`。"""

TNX_VALUATION_PRESSURE_PCT: float = 4.5
"""macro_compass 10Y 殖利率(TNX)估值壓力**紅線**：≥4.5% → 🔴 估值壓力（科技股不利）。
注意：與 MACRO_THRESHOLDS['US10Y'] 的 red_above=5.0 **刻意不同源**（compass 快訊用較嚴 4.5，
US10Y 桶 regime 用 5.0），屬不同用途。原 macro_core.py:499 inline。"""

TNX_NEUTRAL_PCT: float = 3.5
"""macro_compass TNX 中性**黃線**：3.5~4.5% → 🟡 中性區；< 3.5% → 🟢 寬鬆有利。原 macro_core.py:500 inline。"""

PCR_PERCENT_SCALE_MIN: float = 10.0
"""選擇權 PCR「百分比刻度 vs 比值刻度」判別線（§4.1 量綱陷阱 SSOT，v19.178）。

本專案同一個 PCR 有**兩種刻度**共存：
  - `li_latest['選PCR']`：`leading_indicators` 寫入時已 ×100 → **百分比刻度**（50~200，
    UI 卡片直接顯示用；section_chips 的 80 / 130 / 150 判斷即用此刻度）
  - `config.MACRO_ALERT_RULES['pcr']` / `macro_state_locker.calculate_system_state`：
    **標準 PCR 比值刻度**（0.5~2.0）

跨刻度直接比較 = 100× 誤差（實測 126.80 配「>1.5 極度恐慌」→ 恆真）。判別規則：
`value > PCR_PERCENT_SCALE_MIN` 視為百分比刻度，除以 100 換回比值。
10.0 這個切點很寬鬆但安全：真實 PCR 比值歷史上從未逼近 10（極端恐慌約 2.0），
百分比刻度也從未低到 10（那等於比值 0.1）—— 兩個刻度的值域完全不重疊，無誤判區。

原為 `src/data/macro/macro_alert.py:295` inline `> 10`，v19.178 抽出供
`section_news_ai` 的 AI context 共用（避免兩處各寫一個判別線 → §3.3 漂移）。"""

PCR_PERCENT_VALID_MAX: float = 500.0
"""選擇權 PCR **百分比刻度**的合理上界（§3.2 範圍檢查，v19.180 B2-b）。

與 `PCR_PERCENT_SCALE_MIN` 合成一組完整的刻度判別區間
（實作 SSOT：`shared/pcr_scale.normalize_pcr_to_ratio`）::

    ≤0            → 兩種刻度都不成立（PCR = putV/callV 恆為正）→ None + log
    (0, 10]       → 標準比值刻度，原值即比值
    (10, 500]     → 百分比刻度，÷100 換回比值（→ 0.1~5.0）
    >500          → 兩種刻度都解釋不通 → None + log（§1 不猜換算）

500 這個上界**不是腦補**，取自寫入端自己的收值窗：
`src/data/macro/leading_indicators.py:970` 的 `taifex_pcr` 只接受
`20 < val < 500` 的百分比值、超出即丟棄。下游沿用同一上界，
避免出現「寫入端已經拒收、消費端卻照單全收」的不一致。"""


# ════════════════════════════════════════════════════════════════
# 進場操作層:停利停損 / 量比 / 趨勢分級(v18.328 PR-C 稽核三項違憲)
# user 2026-06-27 audit 提出 P1/P2/P3:個股 Tab 進場操作邏輯統一 SSOT,
# 兩 Tab(個股 / 個股組合)未來共用此處常數。
# ════════════════════════════════════════════════════════════════

# ── 停利停損(個股 Tab 進場操作建議區 / PR-C P2)──
STOP_PROFIT_T1_PCT: float = 5.0
"""停利目標 1:短線先入袋(+5%)。原 tab_stock.py:575 inline `_cur_p * 1.05`。"""

STOP_PROFIT_T2_PCT: float = 10.0
"""停利目標 2:波段目標(+10%)。原 tab_stock.py:576 inline `_cur_p * 1.10`。"""

STOP_LOSS_DEFAULT_PCT: float = 8.0
"""預設停損:跌破認賠(-8%)。原 tab_stock.py:577 inline `_cur_p * 0.92`。
注意:與 ATR_STOP_FIXED_PCT(8% / scoring_engine 風控)同值但語意分離 —
本常數是「個股 Tab 顯示用建議值」,後者是「ATR 失敗 fallback」。"""

HARD_STOP_LOSS_PCT: float = 7.0
"""「什麼時候買/賣」區塊的**硬停損**(-7%)。原 `section_when_buy_sell.py`
inline `round(_p2 * 0.93, 2)` + 兩處手打的「-7%」字面(D1 v19.185 抽出)。

⚠️ 與 `STOP_LOSS_DEFAULT_PCT`(8%)**刻意不同值、不同語意**:
  - 8% = 頁頂「建議停損」卡的預設方案(對應 FIXED_PLAN_RR_*);
  - 7% = 進出場訊號區的較緊硬停損,與「月線停損 / 5MA 停利」並列成一組
    由緊到鬆的價位帶。
兩者同時出現在同一頁,故各自具名,**禁止**互相取代(取代會讓 K 線圖上兩條
不同的水平線疊在一起,使用者會以為系統只有一個停損)。"""

# ── 固定停利停損方案的「先天盈虧比」(v19.179 B1-b)────────────────
# tab_stock.py:640 原寫 `(_tp1_p - _cur_p) / (_cur_p - _sl_p)`,而 _tp1_p / _sl_p
# 都是「現價 × 固定百分比」⇒ 現價被完整約掉,結果 **恆等於 T1% / 停損%**,
# 對任何股票、任何價格都是同一個數(實機 2330 顯示 0.63x)。舊碼旁邊卻標
# 「≥1.5 較理想」= 這個方案在數學上永遠達不到的目標 → §1 假結論。
#
# 這兩個常數把「它是方案的結構性常數,不是個股資訊」寫進型別本身:
#   - 由 SSOT 百分比推導,改門檻時自動同步(§3.3 不得 inline 0.625)
#   - 不從 round() 後的價位反推 → 沒有 ±0.01 的假抖動冒充「因股而異」
FIXED_PLAN_RR_T1: float = STOP_PROFIT_T1_PCT / STOP_LOSS_DEFAULT_PCT
"""固定方案盈虧比(停利目標1 對 預設停損)= 5% / 8% = 0.625。

**與個股無關的常數**。<1 代表「用 T1 出場時,承擔的風險大於目標獲利」。
UI 顯示這個值時,文案必須說明它是方案先天值,不可標任何「≥N 較理想」的門檻
(那會變成一個永遠不達標的假目標)。"""

FIXED_PLAN_RR_T2: float = STOP_PROFIT_T2_PCT / STOP_LOSS_DEFAULT_PCT
"""固定方案盈虧比(停利目標2 對 預設停損)= 10% / 8% = 1.25。同上為常數。"""

# ── 量比軸線(個股三段 + 組合兩段,設計差保留但 SSOT 化 / PR-C P3)──
VOLUME_RATIO_SURGE: float = 1.5
"""量比異常放量:≥1.5× 20 日均量 → 🟢 強訊號。
個股 Tab 健康度卡片(原 inline 1.5)。原 tab_stock.py:1041 inline。"""

VOLUME_RATIO_MILD: float = 1.0
"""量比溫和放量:≥1.0× 但 <1.5× → 🟡 中性偏多。
個股 Tab 健康度卡片(原 inline 1.0)。原 tab_stock.py:1041 inline。"""

VOLUME_RATIO_DRY: float = 0.5
"""量比嚴重量縮:<0.5× 20 日均量 → 🟡 量能不足警示。
個股 Tab 警示列(原 inline 0.5)。原 tab_stock.py:1024 inline。

P2-3 v18.381 補:scoring_helpers.py:183 量比警戒(主力介入)門檻。"""

VOLUME_RATIO_SURGE_HIGH: float = 3.0
"""量比 >3.0× 視為重大消息 / 主力介入(scoring_helpers 評分)。

P2-3 v18.381:抽自 src/compute/scoring/scoring_helpers.py:183 inline。"""

CHINA_USDCNY_STRONG: float = 7.0
"""USDCNY <7.0 視為強勢人民幣(中國副盤評分 100 滿分)。
P2-3 v18.381:抽自 macro_helpers.py:947 inline。"""

CHINA_USDCNY_NEUTRAL: float = 7.2
"""USDCNY 7.0-7.2 中性區(評分 50)。C-3 v18.382 補抽。"""

CHINA_USDCNY_WEAK: float = 7.4
"""USDCNY 7.2-7.4 偏弱區(評分 25)、>7.4 大貶區(評分 0)。C-3 v18.382 補抽。"""

# ── RSI 帶區間評分(scoring_helpers 內 5 段)──────────────────
RSI_STRONG_LOW: float = 50.0
"""RSI 50-70 強勢區間(scoring_helpers.py:165 評分 20 滿分)。C-1 v18.382 抽自 inline。"""

RSI_NEUTRAL_WEAK_LOW: float = 40.0
"""RSI 40-50 中性偏弱(scoring_helpers.py:168 評分 12)。C-1 v18.382 抽自 inline。"""

# ── ETF 上下漲日數判定 ───────────────────────────────────────
ETF_UP_DOWN_DAYS_THRESHOLD: float = 60.0
"""ETF 近期上漲日 / 下跌日數 >60% 視為強弱訊號(etf_calc.py:901-907)。
C-2 v18.382 抽自 inline。觸發 🟡/🔴 燈號分流。

P2-3 v18.381 收尾:VOLUME_RATIO_SURGE_HIGH=3.0、CHINA_USDCNY_STRONG=7.0。

註:本檔下方仍有舊段 docstring,以下保留原樣不動。
注意:與 GRP_VOL_SHRINK_RATIO(0.7,組合 Tab 操作狀態燈量縮)刻意分開 —
個股用較嚴(0.5,嚴重量縮才警示),組合用較鬆(0.7,操作狀態燈),屬不同顆粒度設計。"""

# ── 趨勢分級 MA 配置(兩 Tab 應共用 / PR-C P1)──
TREND_USE_MA60: bool = True
"""趨勢判定主 MA 選擇:True=MA60(短中期更靈敏,個股 / 組合 Tab 統一);
False=MA100(舊組合 Tab 行為,保留旗標供 A/B 比較)。
原違憲:個股用 MA60 vs 組合用 MA100,同股雙 Tab 判斷反差。"""


# ════════════════════════════════════════════════════════════════
# ETF Tab 顯示閾值(v18.329 PR-D ETF audit 三項違憲)
# user 2026-06-27 audit:ETF 單檔 / 多檔 / 組合三 Tab inline magic 抽出。
# ════════════════════════════════════════════════════════════════

# ── ETF 基本閾值(PR-D P3)──
ETF_DIV_YOY_DECLINE_PCT: float = -10.0
"""ETF 配息 12M YoY 衰退警示:< -10% → 🔴 配息衰退。
原 etf_tab_single.py:228 inline `_div_yoy < -10`。"""

ETF_INCEPTION_YEARS_MIN: float = 3.0
"""ETF 成立年數最低門檻:≥ 3 年才算有完整週期樣本(避免追新 ETF)。
原 etf_tab_single.py:252 inline `_incept_yrs >= 3`。"""

ETF_CAGR_TARGET_PCT: float = 7.0
"""ETF 3Y CAGR 目標值:≥ 7% → 🟢 達標。對齊長期市場報酬基準。
原 etf_tab_single.py:244, etf_tab_grp_compare.py:78 兩處 inline `>= 7`。"""

ETF_TRACKING_ERROR_MAX_PCT: float = 1.5
"""ETF 追蹤誤差最大門檻:> 1.5% → 🟡 警示(追蹤效率不佳)。
原 etf_tab_single.py:410 inline `te > 1.5`。"""

# ── ETF 星等映射(C2 v18.402,4 段門檻 5 顆星)──
ETF_RATING_EXCELLENT_MIN: float = 0.80
"""ETF 加權分 5★(優異):score ≥ 0.80。"""

ETF_RATING_VERY_GOOD_MIN: float = 0.65
"""ETF 加權分 4★(很好):0.65 ≤ score < 0.80。"""

ETF_RATING_GOOD_MIN: float = 0.50
"""ETF 加權分 3★(尚可):0.50 ≤ score < 0.65。"""

ETF_RATING_FAIR_MIN: float = 0.35
"""ETF 加權分 2★(普通):0.35 ≤ score < 0.50;< 0.35 → 1★。
原 etf_scoring_helpers.py:78-87 + etf_quality.py:147-156 inline 4 數字共用。"""

# ── ETF 折溢價分級(PR-D P2,4 段)──
ETF_PREMIUM_DEEP_DISCOUNT_PCT: float = -2.0
"""ETF 折價深度買進區:≤ -2% → 🟢 建議買進(NAV 大幅折價)。
原 etf_tab_single.py:343 inline。"""

ETF_PREMIUM_FAIR_DISCOUNT_PCT: float = -0.5
"""ETF 折價合理區:-2% ~ -0.5% → 🔵 合理偏低。
原 etf_tab_single.py:347 inline。"""

ETF_PREMIUM_FAIR_PREMIUM_PCT: float = 1.0
"""ETF 中性 / 微溢價區:-0.5% ~ 1% → ⚪ 中性。
原 etf_tab_single.py:353 inline。"""

ETF_PREMIUM_HIGH_PREMIUM_PCT: float = 3.0
"""ETF 高溢價暫緩區:1% ~ 3% → 🔴 暫緩;> 3% → 🔴 禁止追高。
原 etf_tab_single.py:357 inline。"""

# ── σ 位階分級(PR-D P2,4 段 z-score)──
ETF_SIGMA_DEEP_BUY: float = -2.0
"""σ位階深度買進:z ≤ -2σ → 🟢 大買訊號(深度超賣)。
原 etf_tab_single.py:470 inline。"""

ETF_SIGMA_BUY: float = -1.0
"""σ位階買進:-2σ ~ -1σ → 🔵 小買(輕度超賣)。
原 etf_tab_single.py:473 inline。"""

ETF_SIGMA_REDUCE: float = 1.0
"""σ位階減碼:1σ ~ 2σ → 🟡 減碼(輕度過熱)。
原 etf_tab_single.py:476 inline。"""

ETF_SIGMA_STOP_PROFIT: float = 2.0
"""σ位階停利:≥ 2σ → 🔴 停利(深度過熱)。
原 etf_tab_single.py:479 inline。"""


# ════════════════════════════════════════════════════════════════
# ETF VCP 訊號最低資料量(v18.330 PR-E U-4)
# ════════════════════════════════════════════════════════════════

ETF_VCP_MIN_DAYS: int = 210
"""ETF VCP 形態判定最低資料量(交易日)。< 210 天 → 顯示「資料不足」不判 VCP。
210 ≈ 10 個月,確保有足夠樣本看到波幅收縮 + MA200 站上。
原 etf_calc.py:222 + etf_tab_single.py:344 兩處 inline `< 210` 重複。"""


# ════════════════════════════════════════════════════════════════
# ETF 流動性評分閾值(v18.330 PR-E U-6)
# 原 etf_calc.py:392-437 calc_liquidity_score 內 inline 4 處,本次抽 SSOT。
# ════════════════════════════════════════════════════════════════

ETF_AVG_VOL_20D_LOW_LOTS: int = 500
"""ETF 20 日均量流動性紅燈門檻(張)。< 500 張 → 🔴 流動性風險。原 etf_calc.py:416 inline。"""

ETF_AVG_VOL_20D_FAIR_LOTS: int = 1000
"""ETF 20 日均量流動性黃燈門檻(張)。500 ~ 1000 張 → 🟡 流動性偏弱。原 etf_calc.py:419 inline。"""

ETF_AUM_LOW_YI: float = 5.0
"""ETF AUM 規模紅燈門檻(億 TWD)。< 5 億 → 🔴 流動性風險。原 etf_calc.py:426 inline。"""

ETF_AUM_FAIR_YI: float = 10.0
"""ETF AUM 規模黃燈門檻(億 TWD)。5 ~ 10 億 → 🟡 流動性偏弱。原 etf_calc.py:429 inline。"""


# ════════════════════════════════════════════════════════════════
# ETF 衛星 σ 位階分級(quick_signals 用)(v18.331 PR-F U-7)
# 注意:與 ETF_SIGMA_DEEP_BUY/BUY/REDUCE/STOP_PROFIT(PR-D 抽,etf_tab_single 用)
# 是不同算法 — 本組是 etf_calc._quick_signals「跌了就買」5 段(MA20 ± n×σ),
# PR-D 那組是 etf_tab_single「年化波動率 z-score」4 段。兩組同為 σ 語意但顆粒不同。
# ════════════════════════════════════════════════════════════════

ETF_QUICK_SIGMA_DISASTER: float = 3.0
"""ETF 衛星 σ位階「股災價」:close < MA20 - 3σ → 🟢🟢🟢 大買 50%。
原 etf_calc.py:81 inline `3 * _std`。"""

ETF_QUICK_SIGMA_OVERSOLD: float = 2.0
"""ETF 衛星 σ位階「超跌價」:close < MA20 - 2σ → 🟢🟢 買 30%。
原 etf_calc.py:82 inline `2 * _std`。"""

ETF_QUICK_SIGMA_CHEAP: float = 1.0
"""ETF 衛星 σ位階「便宜價」:close < MA20 - 1σ → 🟢 小買 20%。
原 etf_calc.py:83 inline `1 * _std`。"""

ETF_QUICK_SIGMA_HIGH: float = 1.5
"""ETF 衛星 σ位階「偏高」:close ≥ MA20 + 1.5σ → 🟠 不追高 / 減碼。
原 etf_calc.py:84 inline `1.5 * _std`。"""

ETF_QUICK_SIGMA_OVERBOUGHT: float = 2.0
"""ETF 衛星 σ位階「準備停利」:close ≥ MA20 + 2σ → 🔴 分批停利。
原 etf_calc.py:85 inline `2 * _std`。與 OVERSOLD 同值但語意分離(下行 vs 上行)。"""


# ════════════════════════════════════════════════════════════════
# 個股 Tab 補強 SSOT(v18.331 PR-F U-10 / U-12 / U-13)
# user 2026-06-27 audit 殘留個股 Tab inline magic 收尾。
# ════════════════════════════════════════════════════════════════

# ── 布林帶邊界 2-tier(LOOSE warning / STRICT action,U-10 + Batch 5d v18.432)──
BB_NEAR_UPPER_RATIO: float = 0.97
"""布林帶「貼近上軌」LOOSE tier(3% tolerance):close >= upper × 0.97 → 強勢突破預警。
原 tab_stock.py:746 inline,U-10 v18.331 抽出。
caller:tab_stock.py / section_when_buy_sell.py / tech_indicators.py(calc_bollinger 結果 dict)
語意:篩選/掃描用,寬鬆判斷「靠近上軌」涵蓋更多 candidates。"""

BB_NEAR_UPPER_STRICT_RATIO: float = 0.995
"""布林帶「貼近上軌」STRICT tier(0.5% tolerance):close >= upper × 0.995 → 短線爆發買點(嚴格)。
v18.432 Batch 5d 抽出。
caller:src/compute/strategy/v5_modules.py:247(布林通道訊號 fn)
語意:訊號層 action,嚴格門檻避免假突破誤判;與 LOOSE 0.97 形成 2-tier 漸進判讀。"""

BB_DROP_OUT_RATIO: float = 0.95
"""布林帶「跌出上軌」訊號:close < upper × 0.95 且 close > ma → 動能轉弱。
原 tab_stock.py:747 inline。"""

# ── 布林帶寬收縮 2-tier(Phase 2 Batch 5b v18.429)──
BB_BW_SHRINK_WARN_RATIO: float = 0.7
"""布林帶寬「收縮警示」threshold:bw < bw_mean × 0.7 → KPI 變綠 / 「帶寬極縮 ⚡」標籤。
3 caller:section_health_score.py:152,153 + section_vcp_bollinger.py:71"""

BB_BW_SHRINK_ACTION_RATIO: float = 0.6
"""布林帶寬「極度收縮」action threshold:bw < bw_mean × 0.6 → 訊號框 + verdict
「布林帶寬極度收縮:即將爆發」。2 caller:section_vcp_bollinger.py:77,91。
SSOT 設計:warn(0.7)→ action(0.6)兩 tier 漸進判讀。"""

# ── RS 帶狀(U-12)──
STOCK_RS_STRONG_MIN: float = 75.0
"""個股 RS 相對強度「強勢」門檻:RS ≥ 75 → 跑贏大盤明顯。
原 tab_stock.py:809 inline。"""

STOCK_RS_NEUTRAL_MIN: float = 50.0
"""個股 RS 相對強度「中性」門檻:50 ≤ RS < 75 → 與大盤同步。
< 50 → 弱勢(落後大盤)。原 tab_stock.py:809 inline。"""

# ── 月線乖離(U-13)──
STOCK_BIAS_OVERHEAT_PCT: float = 20.0
"""個股年線(MA240)正乖離過熱警示:bias > +20% → 分批出場建議。
原 tab_stock.py:981 inline `_bias_i > 20`(已部分使用 SSOT 化)。"""

STOCK_BIAS_DEEP_DEVIATION_PCT: float = 20.0
"""個股年線負乖離布局區:bias < -20% → 左側布局訊號。
原 tab_stock.py:952 inline `_bias_i < -20`。與 OVERHEAT 同值但語意分離。"""

STOCK_BIAS_MILD_DEVIATION_PCT: float = 15.0
"""個股月線(MA20)中度乖離警示:|bias| > 15% → 短線過熱 / 過冷。
原 tab_stock.py:803/830/832 inline 多處。"""

# ── 勝利方程式 / SOP 進場檢核(D1 v19.185)──
WINNING_FORMULA_HEALTH_MIN: float = 75.0
"""「🏆 勝利方程式」個股健康度條件:health ≥ 75 才算通過。

原 `section_psy_checklist.py` inline 裸數字 `75`,而**同一行的畫面文案**也各自
手寫「≥75」—— 兩份複本(§3.3)。抽出後 code 與 label 共用同一個數字。
**數值完全未變**。語意:比 `HEALTH_GRADE_A_MIN`(80,技術面 A 級)寬一階,
因為勝利方程式是「5 項合議」而非單項把關,單項門檻不需要頂到 A 級。"""

WINNING_FORMULA_MIN_PASS: int = 4
"""「🏆 勝利方程式」放行門檻:5 項條件中至少 4 項成立。

原 inline 裸數字 `4`,而卡片標題卻寫「需全部符合」(= 5 項) —— **畫面宣稱的門檻
≠ 判定式**(D1 v19.185 稽核)。抽出後標題改由本常數插值,不可能再各說各話。"""

SOP_SURGE_LOOKBACK_DAYS: int = 5
"""SOP 進場檢核 / 今日禁止操作的「近 N 日漲幅」回看**交易日**數。

D1 v19.185:原 `section_psy_checklist.py` 同一頁用了兩個基期 —— 檢核 ② 取
`close.iloc[-6]`(= 5 個交易日前)、禁止操作清單取 `close.iloc[-5]`(= 4 個交易日
前),兩個都標「近5日漲幅」卻是不同數字。收斂為單一常數 + 單一算式(`iloc[-(N+1)]`)。
※ 交易日 ≠ 日曆日(§4.1)。"""

SOP_SURGE_WARN_PCT: float = 5.0
"""SOP 進場檢核 ②「未追高」門檻:|近 5 交易日漲幅| ≤ 5% 視為通過。原 inline `5`。"""

SOP_SURGE_HARD_PCT: float = 10.0
"""SOP 進場檢核 ② 的**硬鎖**門檻:|近 5 交易日漲幅| > 10% → checkbox 禁止勾選。
原 inline `10`。"""

SOP_BAN_SURGE_PCT: float = 4.0
"""「今日禁止操作」追高條款:|近 5 交易日漲幅| > 4% → 列入禁止清單。原 inline `4`。
※ 比 `SOP_SURGE_WARN_PCT`(5%)嚴 —— 兩者**語意不同**(勸阻 vs 通過檢核),
不是同一個門檻的兩份複本,故各自具名。"""

SOP_BAN_MONTHLY_LOSS_PCT: float = -5.0
"""「今日禁止操作」情緒條款:本月報酬 < -5% → 列入禁止清單。原 inline `-5`。"""


# ════════════════════════════════════════════════════════════════
# ETF 投組 Tab 投組特有 SSOT(v18.332 PR-G U-9)
# 2026-06-28 etf_tab_portfolio.py 深度 audit 殘留 8 處 inline magic 收斂。
# 投組層特有(single/grp 不消費):分散度、再平衡、壓測、VaR。
# ════════════════════════════════════════════════════════════════

# ── 再平衡(G1 P3)──
PORTFOLIO_REBAL_TOLERANCE_DEFAULT_PCT: float = 5.0
"""ETF 投組再平衡容忍偏離預設值 %:|實際-目標| > 5% → 觸發再平衡建議。
Slider 範圍 1-15,預設 5。原 etf_tab_portfolio.py:86 inline。"""

PORTFOLIO_TARGET_SUM_TOLERANCE_PP: float = 1.0
"""ETF 投組「目標權重」總和容差(百分點):|Σ target_pct - 100| > 1pp → 目標本身不成立,
再平衡檢查回**無法判定**(§1:不拿一組加不到 100% 的目標去算偏離,那個偏離沒有意義)。
留 1pp 是給使用者四捨五入(如 33.3/33.3/33.3 = 99.9)的空間。B5-a v19.180 新增。"""

# ── 核心/衛星 配置(B5-a v19.180)──
PORTFOLIO_CORE_SAT_TOLERANCE_PP: float = 10.0
"""核心/衛星比 vs regime 目標的**雙邊**容忍帶(百分點):|實際核心% - 目標核心%| > 10pp
→ 🔴 偏離目標。

SSOT 理由(§3.3):此數字原本一式三份且語意漂移 ——
  1. `etf_tab_portfolio.py:599/602` inline `10`(只控 metric delta 顏色)
  2. `etf_tab_portfolio.py:615` 文案寫「±10pp 容忍」(**雙邊**)
  3. `src/compute/strategy/portfolio_manager.py:22 _REBALANCE_THRESHOLD = 0.10`
     實際判定式 `excess_ratio >= 0.10` 是**單邊**(只抓衛星超標),
     衛星不足 30pp 也永遠不觸發 → 畫面說 ±10pp 是假的。
B5-a 起判定改走 `portfolio_gates.evaluate_core_satellite_gate` 的雙邊比對,
文案與判定式對齊到本常數。`_REBALANCE_THRESHOLD` 仍服務 portfolio_manager
既有 caller(個股衛星超標警報),語意不同故不合併。"""

# ── 分散度(G1 P1+P2)──
ETF_CORR_HIGH_THRESHOLD: float = 0.85
"""ETF 投組相關係數「同質性過高」警示:任兩檔 Pearson corr > 0.85
→ ⚠️ 資產同質性過高。原 etf_tab_portfolio.py:493 inline。"""

PORTFOLIO_OVERLAP_WEIGHT_THRESHOLD_PCT: float = 30.0
"""ETF 持股重疊(權重 Overlap%)警示:任兩檔權重共同持股加總 > 30%
→ ⚠️ 建議擇一保留。原 etf_tab_portfolio.py:549 inline(weight branch)。"""

PORTFOLIO_OVERLAP_JACCARD_THRESHOLD_PCT: float = 50.0
"""ETF 持股重疊(Jaccard 集合)警示:|A∩B|/|A∪B| > 50%
→ ⚠️ 建議擇一保留。原 etf_tab_portfolio.py:549 inline(jaccard branch)。"""

# ── 壓力測試(G2)──
PORTFOLIO_STRESS_TEST_DROP_PCT: float = -20.0
"""ETF 投組壓力測試 S&P500 下跌幅度(%):用於估算 Beta 加權虧損。
業界常用 -20% 中型空頭情境。原 etf_tab_portfolio.py:618 inline `-0.20`。"""

PORTFOLIO_STRESS_TEST_LOSS_WARN_PCT: float = 20.0
"""ETF 投組壓測虧損警示門檻(%):組合預估虧損 > 20%
→ ⚠️ 尾部風險超標,建議增加避險。原 etf_tab_portfolio.py:627/630/632 inline。"""

# ── VaR 風險值(G2)──
PORTFOLIO_VAR_95_PERCENTILE: float = 0.05
"""ETF 投組 VaR 95% 信心區間分位數:quantile(0.05)。
歷史模擬法取最差 5% 分位數,即「100天中95天虧損不超過此值」。
原 etf_tab_portfolio.py:664 inline。"""

PORTFOLIO_VAR_99_PERCENTILE: float = 0.01
"""ETF 投組 VaR 99% 信心區間分位數:quantile(0.01)。
歷史模擬法取最差 1% 分位數(更保守的尾部評估)。
原 etf_tab_portfolio.py:665 inline。"""

PORTFOLIO_VAR_MONTHLY_WARN_PCT: float = 10.0
"""ETF 投組月度 99% VaR 警示門檻(%):月度尾部虧損 > 10%
→ ⚠️ 尾部風險偏高,建議增加防禦部位。原 etf_tab_portfolio.py:689/693/699 inline。"""

# ── 組合累積報酬 vs 基準(v19.166)──
PORTFOLIO_BENCHMARK_TICKER: str = "0050.TW"
"""ETF 投組「與 0050 累積報酬比較」的被動基準代號(§3.3 反捏造:禁止 inline '0050.TW')。
概念同 shared/forward_test_thresholds.py:FORWARD_TEST_BENCHMARK('0050'),同指元大台灣50;
但兩者服務不同 fetcher:forward_test 走 fetch_stock_history_1y(無 .TW 後綴),ETF 投組走
fetch_etf_price(yfinance,需 .TW 後綴)。故格式不同、各自 SSOT,不硬併。"""

# ── §3.2 USD/TWD 即期匯率合理範圍 sanity(B1-a v19.179)──
USDTWD_SANITY_MIN: float = 25.0
"""USD/TWD 即期匯率 sanity 下界(TWD per 1 USD)。低於此視為抓錯欄位/單位反了
(例如抓成 TWD→USD 的 0.031),**不可**拿來換匯 —— §1 寧可 fail loud 也不用髒匯率。
歷史區間約 [28, 35],留 3 元緩衝。原 src/data/macro/tw_macro.py:1307 inline `25`
(該檔不在 B1-a 檔案範圍,待後續 PR 改 import 本常數以真正單一化)。"""

USDTWD_SANITY_MAX: float = 40.0
"""USD/TWD 即期匯率 sanity 上界(TWD per 1 USD)。同 USDTWD_SANITY_MIN。
原 src/data/macro/tw_macro.py:1307 inline `40`。"""


# ════════════════════════════════════════════════════════════════
# v18.436「全做」audit 翻案 — 8 處 inline magic 收 SSOT(#3-10)
# user 2026-06-30 全域深挖 audit 找出;此段補抽,語意化各門檻。
# ════════════════════════════════════════════════════════════════

# ── #3 外資期貨防禦訊號(macro_helpers 健康評分)──
FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD: int = 30000
"""外資期貨淨部位「大空單防禦訊號」門檻(單位:口,絕對值)。
macro_helpers.compute_macro_health:健康評分 <2 且外資淨空單 |部位| >30000 口
且方向為空(<0)→ 觸發 _defense 防禦旗標。約 75 億 TWD 規模。
原 src/compute/macro/macro_helpers.py:92 inline。注意:與 v4_strategy_engine 的
FOREIGN_FUTURES_HIGH/MEDIUM_RISK(-20000/-10000)語意不同 — 後者是分級紅黃燈,
本常數是健康評分內的單一防禦觸發,刻意分離。"""

# ── #4 VPOC 套牢賣壓距離(v4_strategy_engine Task 3)──
VPOC_PRESSURE_DISTANCE_THRESHOLD: float = 0.15
"""VPOC(體積加權最大量價位)套牢賣壓距離門檻(比例,0.15=15%)。
當前價 < VPOC 且 (VPOC-現價)/現價 < 0.15 → 判定上方有近 N 日最大量套牢賣壓。
原 src/compute/strategy/v4_strategy_engine.py:214 inline。"""

# ── #5 ETF 基金經理新任門檻(etf_calc 經理人燈號)──
ETF_MANAGER_TENURE_NEW_DAYS: int = 180
"""ETF 基金經理「新任」判定門檻(單位:天,約 6 個月)。
任期 <180 天視為新經理人,表現待觀察 → UI 顯示「再給時間」建議。
原 src/compute/etf/etf_calc.py:915 inline。"""

# ── #6 FGMS 存貨營收背離 — 無背離資料時的 YoY 退路評分 ──
FGMS_NO_DIV_GOOD_SCORE: int = 65
"""FGMS 存貨/營收背離無 inv_days 資料時:營收 YoY >FGMS_REV_YOY_GOOD_PCT(10%)
→ 退路評分 65。原 src/compute/scoring/scoring_engine.py:654 inline。"""

FGMS_NO_DIV_POSITIVE_SCORE: int = 50
"""FGMS 退路:營收 YoY >0 但未達 good → 評分 50。原 scoring_engine.py:654 inline。"""

FGMS_NO_DIV_DECLINE_SCORE: int = 30
"""FGMS 退路:營收 YoY <=0 → 評分 30。原 scoring_engine.py:654 inline。"""

# ── #7 KD 超買 / 超賣邊界(scoring_helpers 健康度 KD 評分)──
KD_OVERBOUGHT_LEVEL: float = 80.0
"""KD 高檔區邊界:K>80 黃金交叉視為「高檔黃叉注意」(評分降)。
原 src/compute/scoring/scoring_helpers.py:222 inline。"""

KD_OVERSOLD_LEVEL: float = 20.0
"""KD 低檔區邊界:K>20 且死亡交叉視為一般死叉(評分 5);K<=20 為超賣不另扣。
原 src/compute/scoring/scoring_helpers.py:225 inline。與 KD_OVERBOUGHT_LEVEL 對稱。"""

KD_PASSIVATION_DAYS: int = 3
"""KD 鈍化(passivation)判定天數:K 連續 N 日 ≥ KD_OVERBOUGHT(高檔鈍化=強勢續漲,
非賣訊)或 ≤ KD_OVERSOLD(低檔鈍化)。台股慣例 3 日。v19.94 analyze_kd_state。"""

KD_DIVERGENCE_LOOKBACK: int = 40
"""KD 背離(divergence)回看窗(交易日),切兩半(各 20)比高低點:價創高但 K 沒創高
=頂背離(空);價創低但 K 沒創低=底背離(多)。v19.94 analyze_kd_state。"""

# ── #9 IBS(內結構 Internal Bar Strength)反彈 / 賣壓邊界 ──
IBS_OVERSOLD_THRESHOLD: float = 0.2
"""IBS 收低門檻(比例):IBS<=0.2(收當日區間低 20% 內)→ 隔日易反彈(評分 +10)。
原 src/compute/scoring/scoring_helpers.py:207 inline。"""

IBS_OVERBOUGHT_THRESHOLD: float = 0.8
"""IBS 收高門檻(比例):IBS>=0.8(收當日區間高 20% 內)→ 隔日易賣壓(評分 +2)。
原 src/compute/scoring/scoring_helpers.py:210 inline。"""

# ── #10 18 個月回測完整度門檻(tw_backtest 拐點驗證)──
BACKTEST_18M_DAYS_THRESHOLD: int = 547
"""18 個月前向報酬「資料完整」判定門檻(單位:日,547≈18.2 月)。
拐點事件距今 >=547 天且 r18 非空 → 標記該事件回測完整。
原 src/compute/strategy/tw_backtest.py:218-219 inline(同值寫兩處)。"""


# ════════════════════════════════════════════════════════════════
# 統一指標卡 band 表(v19.109,未完成清單第 5 步試點 — 總經拼圖模組八)
# 每表 = list[(下限含 lo, 燈色鍵, 燈標籤, 燈義一句)],依 lo 降冪,末項 lo=-inf
# 兜底。resolver 用 value >= lo 取第一命中 → **判定邏輯與燈義文字同源**,
# 文字永不與門檻漂移(§3.3;原 section_mid 5 卡門檻全 inline,已收斂至此)。
# 邊界語意註記:CPI 3.5/2.5 原為「>」改「≥」(恰等值時燈更保守一級);
# 出口 0.0 原為「>0」改「≥0」(恰 0.0 顯綠)。兩者僅影響恰好等值的月份,
# 一位小數月頻資料實務機率 ~0,方向已於 v19.109 記錄。
# ════════════════════════════════════════════════════════════════

NDC_SIGNAL_BANDS: list = [
    (38.0, 'red',    '🔴 紅燈 過熱',   '景氣過熱,政策收緊風險升高'),
    (32.0, 'yellow', '🟡 黃紅燈 繁榮', '景氣趨熱,注意過熱苗頭'),
    (23.0, 'green',  '🟢 綠燈 穩定',   '景氣穩定,基本面有撐'),
    (17.0, 'blue',   '🔵 黃藍燈 趨緩', '景氣轉弱,觀察是否進一步下滑'),
    (float('-inf'), 'blue', '🔵 藍燈 衰退', '景氣低迷,歷史上常屬逆勢佈局區'),
]
"""NDC 景氣對策信號分數帶(9~45 分)。原 section_mid.py:72-75 inline 38/32/23/17。"""

TW_EXPORT_YOY_BANDS: list = [
    (0.0, 'green',  '✅ 正成長', '出口動能正成長,基本面有撐'),
    (-5.0, 'yellow', '⚠️ 轉弱',  '出口轉弱,留意基本面背離'),
    (float('-inf'), 'red', '🔴 衰退', '出口明顯衰退,基本面警示'),
]
"""台灣海關出口年增率帶(單位:%)。原 section_mid.py:85-87 inline 0/-5。"""

TW_PMI_CARD_BANDS: list = [
    (50.0, 'green',  '✅ 擴張',     '製造業擴張,內外需動能正向'),
    (47.0, 'yellow', '⚠️ 輕微收縮', '輕微收縮,留意內需與外銷動能'),
    (float('-inf'), 'red', '🔴 嚴重收縮', '嚴重收縮,台股出口/電子股承壓'),
]
"""台灣製造業 PMI 卡片帶(50 榮枯線;47=50-3 原 inline 緩衝)。原 section_mid.py:98-101。"""

US_CORE_CPI_YOY_BANDS: list = [
    (3.5, 'red',    '🔴 通膨偏高', '通膨偏高,Fed 升息壓力大,外資易自台股提款'),
    (2.5, 'yellow', '⚠️ 通膨黏性', '通膨黏性,降息路徑放緩'),
    (float('-inf'), 'green', '✅ 通膨受控', '通膨受控,降息可期'),
]
"""美國核心 CPI YoY 帶(單位:%;Fed 目標 2%)。原 section_mid.py:115-117 inline 3.5/2.5。"""

FED_FUNDS_RATE_BANDS: list = [
    (5.0, 'red',    '🔴 利率高位', '利率高位(>5%),緊縮壓力大'),
    (3.0, 'yellow', '⚠️ 中性偏緊', '中性偏緊(3-5%),資金成本仍高'),
    (float('-inf'), 'green', '✅ 寬鬆環境', '寬鬆環境(<3%),資金成本友善'),
]
"""聯邦資金月均利率帶(單位:%)。原 section_mid.py:136-139 inline 5.0/3.0。"""


# ════════════════════════════════════════════════════════════════
# 週 MACD 出場訊號(v19.110,user 核准升級標準參數)
# ════════════════════════════════════════════════════════════════

WK_MACD_FAST_SPAN: int = 12
"""週 MACD 快線 EMA span(標準參數;v19.110 自 3/5/3 代理升級,可與券商對照)。"""

WK_MACD_SLOW_SPAN: int = 26
"""週 MACD 慢線 EMA span(標準參數)。"""

WK_MACD_SIGNAL_SPAN: int = 9
"""週 MACD 訊號線(DEA)EMA span(標準參數)。"""

WK_MACD_DAYS_PER_WEEK: int = 5
"""週K合成:每 5 個交易日一組(close 無日期索引下的近似慣例)。"""

WK_MACD_MIN_WEEKS: int = 35
"""週 MACD 最低樣本(週):EMA26 需 26 根熱身 + DEA 9 根 → 35 週(175 交易日)
為最低可用。不足 → 訊號誠實回 False,**不**退回 3/5/3(§1 一名一義不混模型)。"""
