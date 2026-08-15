"""src/compute/risk/concentration.py — 投組產業集中度（L2 Compute，純函式）。

回答一個問題：**「我這籃股票，是不是全押在同一個產業？」**

§8.2 layer：**L2 純函式** —— 零 I/O、零 streamlit、零 session_state。
產業別由 caller（L3）先查好再傳進來（走既有 SSOT
`services/stock_grp_service.get_industry_category` → L1 `data_loader.fetch_industry_category`，
該函式已 `@st.cache_data(ttl=TTL_1DAY)`）。本模組**不自己抓資料**。

════════════════════════════════════════════════════════════════════
兩個必須先講清楚的限制（§1 Fail Loud, Never Fake）
════════════════════════════════════════════════════════════════════

**限制 1：等權假設。**
個股組合走 `stock_watchlist` 分頁，schema 是 `['name','ticker','updated_at']`
（`gsheet_portfolio.py:60`，`:56-58` 註解明寫「§1 反捏造：**只**存三欄，無張數/均價」）。
⇒ 系統**不知道**每檔的實際部位大小，故本模組一律以「每檔權重 = 1/N」計算。
**呼叫端（UI）必須顯示這個假設**，否則使用者會以為那是他的真實集中度。
本模組在回傳物件裡帶 `basis='equal_weight'` 供 UI 引用，不讓假設隱形。

**限制 2：未分類檔不納入分母。**
查不到產業別的檔數**不歸入任何桶**（§4.6「不猜」，比照 `compute/sector_flow.py:14`
的既有範式：無產業別 → 獨立計數，不猜產業）。
⇒ 集中度描述的是「**已分類的那部分**」。`coverage_pct` 一併回傳，
UI 應在覆蓋率偏低時明確提醒數值代表性有限。

為什麼不把未分類當成一個桶？兩種做法都會失真：
  · 併成一桶 → 若那些檔其實分散在多個產業，會**低估**集中度
  · 併入最大桶 → 直接捏造
故選擇「排除 + 誠實揭露覆蓋率」，讓偏誤**被說明**而不是**被隱藏**。

════════════════════════════════════════════════════════════════════
計算式（§7 第 4 點，已與 user 對齊 2026-08-14）
════════════════════════════════════════════════════════════════════

設已分類股票共 M 檔，分屬 K 個產業，產業 i 有 n_i 檔：

    w_i  = n_i / M                    ,  Σ w_i = 1
    Top1 = max_i w_i
    Top3 = Σ_{i ∈ top-3} w_i
    HHI  = Σ w_i²                     ,  1/K ≤ HHI ≤ 1
    Neff = 1 / HHI                    ,  1 ≤ Neff ≤ K

`Neff`（有效產業數）是主要對外指標 —— 它比 HHI 好解讀：
「名義上 5 個產業，實質只有 2.5 個」比「HHI = 0.40」直觀得多。

**本模組不提供任何燈號 / 門檻**（user 2026-08-14 裁示）。
理由：分散度的「幾個才算夠」沒有普適標準，DOJ 的 HHI 1500/2500 是衡量
**產業市場結構**用的，套到投資組合沒有依據。憑空定一個就是新的 magic number（§3.3）。
⇒ 只輸出數值，判讀交給使用者。日後若要加門檻，寫進 L0 `shared/` 並註明來源。
"""
from __future__ import annotations

import math
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Mapping

__all__ = [
    "ConcentrationResult",
    "normalize_industry_name",
    "compute_industry_concentration",
]

#: `basis` 欄位的唯一合法值。目前只有等權；若未來補了張數資料，
#: 新增 'position_weighted' 並由 caller 指定，**不要**讓 UI 猜。
BASIS_EQUAL_WEIGHT = "equal_weight"


def normalize_industry_name(raw) -> str | None:
    """產業別字串正規化；無效值回 `None`（代表「未分類」）。

    為什麼需要這一步：產業別字串來自 FinMind 與 TWSE/TPEX openapi 兩個來源
    （`market_close_fetcher.py:171,203`），全形/半形、前後空白、內部多重空白
    都可能不一致。不正規化的話「半導體」與「半導體 」會被算成**兩個產業**，
    使集中度**被低估** —— 偏誤方向剛好是危險的那一邊（讓人以為比實際更分散）。

    處理：
      1. 非字串 / None → None
      2. NFKC 正規化（全形英數字母 → 半形；相容字元統一）
      3. 去頭尾空白、內部連續空白收斂為單一空格
      4. 空字串 → None
    """
    if raw is None:
        return None
    if not isinstance(raw, str):
        # 不接受 float('nan') / 數字 等；一律視為未分類，不做 str() 硬轉
        return None
    _s = unicodedata.normalize("NFKC", raw)
    _s = " ".join(_s.split())
    return _s or None


@dataclass(frozen=True)
class ConcentrationResult:
    """產業集中度計算結果。

    所有比例欄位單位為 **百分比（0–100）**，非小數 —— 欄名以 `_pct` 結尾標示
    （§4.1 命名規範：變數須編碼單位）。`hhi` 與 `n_eff` 是無單位純量。
    """

    n_total: int
    """投組總檔數（含未分類）。"""

    n_classified: int
    """成功取得產業別的檔數（= 計算分母 M）。"""

    n_unclassified: int
    """查不到產業別的檔數。**未納入**任何計算。"""

    n_industries: int
    """已分類部分涵蓋的相異產業數（= K）。"""

    coverage_pct: float
    """`n_classified / n_total * 100`。UI 應在此值偏低時提醒代表性有限。"""

    weights_pct: dict[str, float] = field(default_factory=dict)
    """{產業別: 佔已分類部位的百分比}，由大到小排序。總和 ≈ 100。"""

    counts: dict[str, int] = field(default_factory=dict)
    """{產業別: 檔數}，由大到小排序。與 `weights_pct` 同序。"""

    top1_pct: float | None = None
    """最大單一產業佔比（%）。無已分類檔時為 None。"""

    top3_pct: float | None = None
    """前三大產業合計佔比（%）。產業數不足 3 時等於全部（即 100）。"""

    hhi: float | None = None
    """Herfindahl–Hirschman Index，值域 [1/K, 1]。無已分類檔時為 None。"""

    n_eff: float | None = None
    """有效產業數 = 1 / HHI，值域 [1, K]。無已分類檔時為 None。"""

    basis: str = BASIS_EQUAL_WEIGHT
    """權重基礎。UI **必須**據此標註假設，見模組 docstring「限制 1」。"""

    @property
    def is_computable(self) -> bool:
        """是否算得出集中度（至少要有 1 檔取得產業別）。

        為 False 時 `hhi` / `n_eff` / `top*_pct` 皆為 None，
        UI 應顯示診斷訊息而**不是**顯示 0 或「完美分散」——
        後者會把「不知道」渲染成「很好」，是最糟的假訊號（§1）。
        """
        return self.n_classified > 0


def compute_industry_concentration(
    industry_by_ticker: Mapping[str, object],
) -> ConcentrationResult:
    """計算投組的產業集中度（等權假設）。

    Args:
        industry_by_ticker:
            {股票代號: 產業別}。值為 None / '' / 非字串 一律視為「未分類」。
            **鍵重複的情形由 Mapping 型別本身排除**（同一檔不會計兩次）。

    Returns:
        `ConcentrationResult`。空投組回 `n_total=0` 且 `is_computable=False`，
        **不拋例外**（空投組是正常狀態，非錯誤）。

    複雜度：O(N)，N = 投組檔數。單次 Counter 掃描 + 一次排序 O(K log K)，
    K ≤ N 且實務上 K < 40（TWSE 產業別約 33 類）。無逐列迴圈的隱性 O(N²)。

    邊界行為（§4.6）：
        · 空投組            → n_total=0, is_computable=False
        · 全部未分類        → n_classified=0, is_computable=False（**不**回 hhi=0）
        · 單一檔且已分類    → hhi=1.0, n_eff=1.0（數學正確：1 檔就是 1 個產業）
        · 全部同一產業      → hhi=1.0, n_eff=1.0
        · 產業數 < 3        → top3_pct = 100.0（前三大就是全部）
    """
    _total = len(industry_by_ticker)

    # 正規化 + 過濾未分類。Counter 一次掃完，O(N)。
    _norm = (normalize_industry_name(v) for v in industry_by_ticker.values())
    _counts = Counter(_i for _i in _norm if _i is not None)

    _classified = sum(_counts.values())
    _unclassified = _total - _classified
    _k = len(_counts)
    _coverage_pct = (_classified / _total * 100.0) if _total > 0 else 0.0

    if _classified == 0:
        # §1：算不出來就明說算不出來，不回 0（0 會被畫面渲染成「完美分散」）
        return ConcentrationResult(
            n_total=_total,
            n_classified=0,
            n_unclassified=_unclassified,
            n_industries=0,
            coverage_pct=_coverage_pct,
        )

    # 由大到小排序（檔數相同時以產業名排序，確保結果**可重現**，§5 冪等性）
    _ordered = sorted(_counts.items(), key=lambda kv: (-kv[1], kv[0]))

    _weights_pct: dict[str, float] = {}
    _counts_ord: dict[str, int] = {}
    _hhi = 0.0
    for _ind, _n in _ordered:
        _w = _n / _classified          # 小數形式，用於 HHI
        _weights_pct[_ind] = _w * 100.0
        _counts_ord[_ind] = _n
        _hhi += _w * _w

    _top1_pct = next(iter(_weights_pct.values()))
    _top3_pct = sum(list(_weights_pct.values())[:3])

    # n_eff = 1/HHI。理論上 HHI ≥ 1/K > 0 恆成立（權重為正且和為 1），
    # 但仍顯式 guard —— §4.4「大數除以小數」：浮點累加後若異常趨零，
    # 寧可回 None 讓 UI 顯示「無法計算」，也不要吐出 inf 汙染畫面。
    _n_eff = (1.0 / _hhi) if _hhi > 0.0 and math.isfinite(_hhi) else None

    return ConcentrationResult(
        n_total=_total,
        n_classified=_classified,
        n_unclassified=_unclassified,
        n_industries=_k,
        coverage_pct=_coverage_pct,
        weights_pct=_weights_pct,
        counts=_counts_ord,
        top1_pct=_top1_pct,
        top3_pct=_top3_pct,
        hhi=_hhi,
        n_eff=_n_eff,
    )
