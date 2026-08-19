"""shared/macro_forward_test_schema.py — 總經燈號前進式驗證 schema SSOT(L0 Infra)。

為什麼需要這個模組
------------------
2026-08-19 實測發現的根因:**`calc_traffic_light` 沒有 headless 路徑** ——
燈號、健康分、信心分數這三個數字從來沒有離開過瀏覽器 session。
它們每天被算出來、渲染、然後消失。於是:

- 「紅燈準不準」這個問題**在本 repo 從來沒有樣本外證據**;
- 唯一能離線重算的是 `scripts/calibrate_macro_traffic.py` 的**重建版**,
  而重建版與線上版實測至少在兩處系統性不同:
  `conf`(重建恆 60 / 線上可達 100)、`m1b_m2_prev`(重建有真值 / 線上恆 None)。
  也就是說,至今所有關於燈號的量化討論都建立在一個近似值上。

本組模組的唯一職責:**把線上真的算出來的那個數字,每個交易日落地一列**,
之後才談得上事後對帳。

為什麼 schema 放 L0(而不是跟著 L2 純函式)
-----------------------------------------
直接對照 `CLAUDE.md §8.2.A.2` 的 **V-FT-STORE-1**:
`src/data/portfolio/forward_test_store.py`(L1)為了拿一個 schema 常數而
`from src.compute.screener.forward_test import PICK_SNAPSHOT_HEADERS`(L2)——
**L1 不得 import L2**,而該表自己開的修法就是「常數下沉 L0,L1+L2 都從 L0 取」。
本模組一開始就照那個修法蓋,不重犯一次同樣的錯。

欄位設計原則(§8.1 step 6 自評過度設計)
--------------------------------------
**不存**各腿原始值(ad_ratio / fnet / li_* / margin ...)—— 那些在
`data_cache/` 已有獨立落地,重複存是冗餘,且會讓本檔變成第二份真相。
**只存**「當天這套規則對外講了什麼」+「事後對帳算報酬所必需的最小資訊」。

`git_sha` / `ruleset_hash` 不是可有可無:2026-08-19 一天之內燈號規則就改了
三次(信心 gate 語意、m1b 腿停用、throttle 切點)。沒有這兩欄,三個月後看到
一列 🔴 將無法回答「當時跑的是哪一版規則」,整份資料的可稽核性歸零。
"""
from __future__ import annotations

#: 一列 = 一個交易日的燈號快照。順序即 parquet 欄序。
MACRO_FWD_TEST_HEADERS: tuple[str, ...] = (
    # ── 身分 / 去重鍵 ──────────────────────────────────────────────
    "date",             # str 'YYYY-MM-DD'(TW 交易日)。**唯一鍵**,重跑同日覆蓋
    "captured_at",      # str ISO8601 +08:00,實際跑批時刻(≠ date,用來抓 cron 漂移)
    # ── 燈號結論(這就是要驗的東西)────────────────────────────────
    "icon",             # str '🟢'/'🟡'/'🔴'/'⬜'
    "label",            # str 畫面上那句話(如「空頭防禦｜降低部位」)
    "effective_regime",  # str canonical 結論 'bull'/'neutral'/'caution'/'bear'/'unknown'
    "regime_source",    # str 哪條仲裁分支生效(同一顏色可能來自不同分支)
    "defense",          # bool 空頭防禦旗標
    # ── 分數(事後可重算 tier / 換切點回溯用)───────────────────────
    "health",           # float|None 0-100 總經健康分
    "health_partial",   # bool True = health 少了一條腿
    "score",            # float market_regime 原始得分
    "max_score",        # float 當日實際分母(會隨選填腿在/不在浮動 —— 必存)
    "jqavg",            # float|None 旌旗指數(health 的 0.6 權重腿)
    # ── 信心 / 缺失(Wave 1 的產物,本身也要驗)──────────────────────
    "conf",             # int 0-100 顯示用項數比
    "conf_groups",      # str JSON,3 個獨立故障域各自是否還活著
    "missing_sources",  # str '|' 分隔;空字串 = 全齊
    # ── 對帳所需最小市場資訊 ──────────────────────────────────────
    "twii_close",       # float|None 當日 ^TWII 收盤(點)。**沒有它就算不出後續報酬**
    "inputs_as_of",     # str|None 輸入腿的資料日(外資 T+1、Yahoo EOD → 可能 ≠ date)
    # ── 可稽核性(規則版本)─────────────────────────────────────────
    "git_sha",          # str 跑批當下的 commit(短 sha)
    "ruleset_hash",     # str 決定燈號的那組常數的 hash(見 compute_ruleset_hash)
    "schema_version",   # int 本 schema 版本,破壞性改欄時 +1
)

#: 破壞性改欄(刪欄 / 改語意)時 +1;純新增欄不必動。
MACRO_FWD_TEST_SCHEMA_VERSION: int = 1

#: 去重鍵。一個交易日只該有一列;重跑同日 → 後寫者勝(規則可能已改)。
MACRO_FWD_TEST_KEY: str = "date"

#: parquet 落地路徑(相對 repo root)。子目錄是刻意的 —— `.gitignore` 有
#: `data_cache/*.parquet` 頂層規則,放子目錄才追蹤得到(同 forward_test/ 手法)。
MACRO_FWD_TEST_RELPATH: tuple[str, ...] = ("data_cache", "macro_forward_test", "signals.parquet")

#: `missing_sources` 的分隔符。用 '|' 而非 ',' —— 來源名稱本身含中文頓號與括號,
#: 逗號在 CSV 匯出時會炸欄。
MISSING_SEP: str = "|"

#: 事後對帳的真值定義 —— **刻意與 `scripts/calibrate_macro_traffic` 同一份**,
#: 不另立第二套。兩套真值 = 兩套結論,而且沒人會發現它們不一樣。
#: hit ⇔ (後 N 日路徑 MDD < MDD_THR_PCT) AND (後 N 日報酬 < RET_MAX_PCT)
FWD_EVAL_HORIZON_DAYS: int = 60
FWD_EVAL_MDD_THR_PCT: float = -10.0
FWD_EVAL_RET_MAX_PCT: float = 0.0
