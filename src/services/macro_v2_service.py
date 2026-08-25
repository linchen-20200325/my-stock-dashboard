"""src/services/macro_v2_service.py — L3 總經 v2 取數編排。

存在的理由(不是為了加一層抽象):

1. **快取**。走勢卡要讀的 parquet 是 4,900+ 列的長歷史。Streamlit 每次
   rerun 都會由上而下重跑整個 `app.py`,沒有快取等於每次互動都重讀兩個
   大檔。`@st.cache_data` 放這裡,L1 `macro_cache_reader` 得以維持它
   檔頭自述的「無 Streamlit 依賴」契約。
2. **分層**。§8.2「L5 UI / L4 Render 不得直呼 L1」。教學文案(`EDU_GUIDE`)
   與長歷史序列都住在 L1,由本層轉一手,UI 與 Render 只跟 L3 要東西。

§3.3 —— 本檔不寫死任何門檻或教學文字,只做轉發與快取。
"""
from __future__ import annotations

from shared.edu_tokens import resolve_edu_tokens
from shared.ttls import TTL_1HOUR

# EX-CACHE-1 標準寫法(CLAUDE.md §8.2.A.1):條件 import,只為取 cache decorator。
try:
    import streamlit as st
except ImportError:                                   # pragma: no cover
    class _NoOpST:
        @staticmethod
        def cache_data(*args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            return lambda f: f
        cache_resource = cache_data
        secrets: dict = {}
    st = _NoOpST()  # noqa

#: `DangerSpec.key` → `EDU_GUIDE` key。沒有對應者回 None,**不硬湊**一段教學。
#: 放 L3 而非 L4:這是「哪個指標對應哪篇教學」的業務對映,不是渲染細節。
_EDU_KEY: dict[str, str] = {
    "vix": "^VIX",
    "us_core_cpi": "CPILFESL",
    "ism_pmi": "NAPM",
    "dxy": "DX-Y.NYB",
    "us10y": "^TNX",
    "margin": "MI_MARGN",
    "foreign_net": "BFI82U",
    "m1b_m2_gap": "ms1.json",
    "ndc_signal": "NDC_signal",
    "tw_export": "XTEXVA01TWM664S",
}


@st.cache_data(ttl=TTL_1HOUR, show_spinner=False)
def get_chart_series() -> dict[str, list]:
    """總經 v2 走勢卡的長歷史序列。

    回傳可序列化的 `{key: [(iso_date, value), ...]}` —— 刻意不回 pd.Series,
    因為 `@st.cache_data` 對 DataFrame/Series 會做額外複製,而消費端只需要
    兩條軸。取不到的 key **不會出現在 dict 裡**(§1:不放空序列讓消費端
    誤以為有資料)。

    TTL 1 小時:來源是每日 cron 更新的本地 parquet,一小時內不可能變。
    """
    from src.data.macro.macro_cache_reader import load_v2_chart_series

    out: dict[str, list] = {}
    try:
        raw = load_v2_chart_series()
    except Exception as e:  # noqa: BLE001 — 讀不到就是沒有走勢圖,不該炸整頁
        print(f"[macro_v2_service/get_chart_series] 長歷史序列讀取失敗:{e}")
        return out

    for key, s in raw.items():
        try:
            out[key] = [(d.isoformat(), float(v)) for d, v in s.items()]
        except Exception as e:  # noqa: BLE001
            print(f"[macro_v2_service/get_chart_series] {key} 序列化失敗:{e}")
    return out


def get_edu(key: str) -> dict | None:
    """取某盞燈的教學文案,並把 `§§TOKEN§§` 代成當前實際門檻。

    找不到對應條目就回 `None` —— 消費端顯示「沒有教學條目」,
    **不編一段**(§3.3)。門檻數字由 `resolve_edu_tokens` 從 L0 SSOT 即時代入,
    所以不存在「教學卡寫 🔴 但 production 顯示 🟡」那類漂移。
    """
    from src.data.core.data_registry import EDU_GUIDE

    ek = _EDU_KEY.get(key)
    if not ek or ek not in EDU_GUIDE:
        return None
    raw = EDU_GUIDE[ek]
    return {
        "meaning": resolve_edu_tokens(raw.get("meaning", "")),
        "how_to_read": [
            (resolve_edu_tokens(a), resolve_edu_tokens(b))
            for a, b in raw.get("how_to_read", [])
        ],
        "historical_anchor": resolve_edu_tokens(raw.get("historical_anchor", "")),
        "downstream": resolve_edu_tokens(raw.get("downstream", "")),
    }
