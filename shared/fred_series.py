"""v18.237 FRED Series ID SSOT — Stock 端 PMI/Macro 系列散落 4 production 檔，集中為語意常數.

對稱 Fund 端 `shared/fred_series.py`（v19.70 交付），Stock-local（不走 sync_to_stock.sh，
範圍限 Stock 實際消費的 series subset）。
Replace pattern：`fetch_fred("NAPM", ...)` → `fetch_fred(FRED_NAPM, ...)`。

例外保留：
  - `test_macro_core.py` fixture：依測試契約保留字面值。
  - 註解/docstring/UI label（如 "ISM PMI（NAPM）"）：純文件描述，不需 import。

未來新增 FRED series 流程：本檔加常數 → call site `from shared.fred_series import FRED_<NAME>`。
"""
from __future__ import annotations

# ── ISM / PMI ──────────────────────────────────────────────────────
FRED_NAPM: str = "NAPM"                      # NAPM manufacturing (legacy series)
FRED_ISPMANPMI: str = "ISPMANPMI"            # ISM manufacturing PMI

# ── Regional Fed surveys ───────────────────────────────────────────
FRED_PHILLY_FED: str = "GACDFSA066MSFRBPHI"  # Philadelphia Fed manufacturing diffusion

# ── Activity / Sentiment (Proxies) ─────────────────────────────────
FRED_BSCICP02: str = "BSCICP02USM460S"       # OECD US Business Confidence (PMI proxy)

# ── TW central bank / FX (v18.270 補 TW 央行政策階段判讀) ──────────
FRED_TW_DISCOUNT_RATE: str = "INTDSRTWM193N"  # CBC 重貼現率(月頻,FRED 載 1961-)
FRED_USDTWD: str = "DEXTAUS"                  # USD/TWD 日匯率(FRED 載 1983-,Yahoo TWD=X 主、本條備援)

# ── China macro (v18.271 方向 B 補完,對稱 Fund v19.113) ────────
# 用途:台積電/出口企業終端需求 + 全球流動性二把交椅(中國)
# 注意:FRED 收錄 OECD MEI / IMF IFS 中國資料,月後 ~60 天延遲
FRED_USDCNY: str = "DEXCHUS"                  # CNY/USD 日匯率(Fund 端命名 FRED_CNH_USD,Stock 統一 USDCNY)
FRED_CHN_OECD_CLI: str = "CHNLOLITONOSTSAM"   # OECD 中國綜合領先指標(PMI 替代,trend=100)
FRED_CHN_CPI: str = "CPALTT01CNM659N"         # OECD 中國 CPI 年增率(% YoY,transformation=GY)
# ⚠️ v18.273 校正:此 series 實為 **M3 broad money level**(兆 CNY),非 YoY %
# 命名仍保留 FRED_CHN_M2 因 user 角度即「廣義貨幣」(M3 與 M2 在中國信貸脈衝
# 視角等效);FRED 無乾淨 SA 的中國 M2 series。
# 下游 china_macro_snapshot 須 pct_change(12)*100 後才能進 YoY scorer。
FRED_CHN_M2: str = "MABMM301CNM189S"          # 中國 M3 廣義貨幣 level(信貸脈衝 proxy,須 pct_change(12) 轉 YoY)
FRED_CHN_PMI: str = "BSCICP03CNM665S"         # OECD 中國商業信心(PMI proxy)
