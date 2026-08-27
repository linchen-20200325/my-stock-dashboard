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


# ══════════════════════════════════════════════════════════════════════
# 卡 B：加權指數日 K 的 OHLC（2026-08-27）
# ══════════════════════════════════════════════════════════════════════
#
# 為什麼另開一支而不是塞進 `get_chart_series()`:那支的契約是
# `{key: [(iso_date, value), ...]}` —— **一條**序列。K 線要 open/high/low/close
# 四條,硬塞會讓同一個回傳值「有時是一條、有時是四條」,消費端得靠記憶判斷
# 現在是哪一種(§3.3 的第二把尺)。形狀不同就分開,不是多一個 key 的事。
#
# 為什麼不在 L5 直接 `pd.read_parquet`:讀檔是 I/O,§8.2 明文 L5 不做。
# 本層轉一手並負責 cache（parquet 4,900+ 列,每次 rerun 重讀不可接受）。
# **本層不新增 L1 程式**,直接用既有的 `macro_cache_reader.load_parquet_safe`。

#: 加權指數 OHLC 的 parquet 檔名 + 必要欄位。欄名**全小寫**（實測 4,919 列:
#: date/open/high/low/close/volume/source/fetched_at）。
_TWII_PARQUET_NAME: str = "twii_ohlcv.parquet"

#: 回傳 dict 的四個價格欄。**只在這裡列一次** —— 取值、長度檢查、缺欄訊息
#: 全部走這個 tuple,分兩處寫就會出現「檢查了 low、訊息卻說 close」。
#: ⚠️ **沒有 volume**:該欄自 2026-07-09 起連續 33 個交易日全為 0
#: （實測至 2026-08-25,之後無非零值）。畫出來是一排貼在零軸上的空白,
#: 傳達「這段期間沒有人交易」這個假訊息 —— §1:與其畫一排零,不如不畫。
_TWII_OHLC_COLS: tuple[str, ...] = ("open", "high", "low", "close")


@st.cache_data(ttl=TTL_1HOUR, show_spinner=False)
def get_twii_ohlc(n_trading_days: int) -> dict:
    """加權指數**最近 n 個交易日**的 OHLC。取不到 → 回 `{}`（§1:不回空殼）。

    Parameters
    ----------
    n_trading_days : int
        要幾根 K 棒。**沒有預設值** —— 「畫幾天」是畫面決策,屬 L5,
        給了預設值就會出現兩個地方各有一份天數(§3.3)。
        parquet 的**每一列就是一個交易日**,故直接取尾端 n 列,
        不需要 trading calendar（同 `macro_cache_reader.load_extreme_risk_legs`
        取 20 交易日報酬的既有作法）。

    Returns
    -------
    dict
        ``{"xs": [iso_date...], "open": [...], "high": [...],
           "low": [...], "close": [...]}``,五個 list **等長**。
        檔案不存在 / 壞檔 / 缺欄 / 空表 → `{}`。

    Notes
    -----
    回可序列化的 list 而非 DataFrame:`@st.cache_data` 對 DataFrame 會做額外
    複製,而消費端(L4 `OHLC`)的契約本來就是「已攤平的 list」。
    """
    from pathlib import Path

    from src.data.macro.macro_cache_reader import (
        DEFAULT_PARQUET_CACHE_DIR,
        load_parquet_safe,
    )

    if n_trading_days < 1:
        # §1:炸掉而不是默默回空 —— 回空的話畫面顯示「日 K 畫不出來」,
        # 而真正的原因(呼叫端傳了 0)不會有任何人看到。
        raise ValueError(f"n_trading_days 必須 ≥ 1,收到 {n_trading_days!r}")

    _path = Path(DEFAULT_PARQUET_CACHE_DIR) / _TWII_PARQUET_NAME
    _need = {"date", *_TWII_OHLC_COLS}
    df = load_parquet_safe(_path, _need)
    if df is None:
        print(f"[macro_v2_service/get_twii_ohlc] {_TWII_PARQUET_NAME} 讀不到或缺欄"
              f"（需要 {sorted(_need)}）→ 不畫日 K")
        return {}

    try:
        import pandas as pd

        _d = df.copy()
        _d["date"] = pd.to_datetime(_d["date"], errors="coerce")
        # 四欄任一為 NaN 的列整列丟掉:K 棒少一隻腳就畫不出來,
        # 而 plotly 會照畫(缺的那一段接起來)—— 看起來正常的錯誤畫面(§1)。
        _before = len(_d)
        _d = _d.dropna(subset=["date", *_TWII_OHLC_COLS]).sort_values("date")
        if _before != len(_d):
            print(f"[macro_v2_service/get_twii_ohlc] 丟棄 {_before - len(_d)} 列"
                  f"（date 或 OHLC 任一為空;不補值、不內插）")
        if _d.empty:
            return {}
        _d = _d.tail(n_trading_days)
        return {
            "xs": [d.date().isoformat() for d in _d["date"]],
            **{c: [float(v) for v in _d[c]] for c in _TWII_OHLC_COLS},
        }
    except Exception as e:  # noqa: BLE001 — 單張圖取不到不該讓整頁炸
        print(f"[macro_v2_service/get_twii_ohlc] 處理失敗:{e}")
        return {}
