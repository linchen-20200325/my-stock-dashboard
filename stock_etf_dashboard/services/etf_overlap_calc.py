"""L2 Service — ETF 成分穿透與重疊曝險（Overlap）。

把「直接持有的個股」與「ETF 內含的成分」穿透到同一層底層標的,**去重複計數**：
直接持有 2330 + 0050 內含 2330 → 合併到同一個 2330 的總曝險。

§1 防呆熔斷：任一 ETF 成分抓不到 / top-N 未揭露全部 → 覆蓋率下降,曝險標為
「下限」而非靜默補 0。純函式,無 I/O。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..core import constants as C
from ..core.circuit_breaker import require


def _norm_alias_map(alias_map: dict[str, str] | None) -> dict[str, str]:
    """把 alias_map 正規化成 O(1) 查表（大小寫/空白統一），只做一次。"""
    if not alias_map:
        return {}
    return {str(k).strip().upper(): str(v).strip().upper()
            for k, v in alias_map.items()}


def _canon(name: str, norm_alias: dict[str, str]) -> str:
    """跨命名正規化：能對到 canonical 就用它,對不到保留原名（不假裝合併）。"""
    key = str(name).strip().upper()
    return norm_alias.get(key, key)


@dataclass(frozen=True)
class ExposureRow:
    name: str
    market_value: float          # 穿透後歸屬到此標的的市值
    exposure_pct: float          # 佔總投組 %
    via_direct: float            # 其中來自直接持股的市值
    via_etf: float               # 其中來自 ETF 穿透的市值
    breach: bool                 # 是否 > 集中度門檻


@dataclass(frozen=True)
class ExposureReport:
    rows: list[ExposureRow]
    total_value: float
    penetrated_value: float
    coverage_pct: float
    is_complete: bool
    alerts: list[str]                       # 超標的底層標的
    incomplete_etfs: list[str]              # 成分抓不到的 ETF
    note: str
    meta: dict = field(default_factory=dict)


def compute_penetrated_exposure(
    direct_holdings: list[dict],
    etf_holdings: list[dict],
    *,
    alias_map: dict[str, str] | None = None,
) -> ExposureReport:
    """穿透加總。

    direct_holdings: [{'ticker','market_value'}, ...]
    etf_holdings   : [{'ticker','market_value','holdings': {underlying: weight%}|None}, ...]
    """
    direct_holdings = direct_holdings or []
    etf_holdings = etf_holdings or []
    norm_alias = _norm_alias_map(alias_map)

    total_value = 0.0
    for h in direct_holdings:
        mv = float(h.get("market_value", 0.0))
        require(mv >= 0, f"direct market_value 不可為負: {h}")
        total_value += mv
    for e in etf_holdings:
        mv = float(e.get("market_value", 0.0))
        require(mv >= 0, f"etf market_value 不可為負: {e}")
        total_value += mv
    require(total_value > 0, "投組總市值必須 > 0（無持股無從計算曝險）")

    via_direct: dict[str, float] = {}
    via_etf: dict[str, float] = {}
    incomplete_etfs: list[str] = []

    # 直接持股：本身就是底層,全額歸屬
    for h in direct_holdings:
        key = _canon(h["ticker"], norm_alias)
        via_direct[key] = via_direct.get(key, 0.0) + float(h.get("market_value", 0.0))

    # ETF：穿透成分權重
    for e in etf_holdings:
        etf_mv = float(e.get("market_value", 0.0))
        holdings = e.get("holdings")
        if not holdings:                     # None 或空 → 成分未知,§1 標記不完整
            incomplete_etfs.append(str(e.get("ticker", "?")))
            continue
        covered = 0.0
        for underlying, weight in holdings.items():
            w = float(weight)
            require(w >= 0, f"成分權重不可為負: {underlying}={w}")
            covered += w
            key = _canon(underlying, norm_alias)
            via_etf[key] = via_etf.get(key, 0.0) + etf_mv * w / 100.0
        # top-N 未揭露的尾巴（covered<100）自然留在 uncovered,拉低覆蓋率

    # 合併去重複計數
    all_keys = set(via_direct) | set(via_etf)
    penetrated_value = 0.0
    rows: list[ExposureRow] = []
    for key in all_keys:
        d = via_direct.get(key, 0.0)
        t = via_etf.get(key, 0.0)
        mv = d + t
        penetrated_value += mv
        pct = mv / total_value * 100.0
        rows.append(ExposureRow(
            name=key, market_value=round(mv, 2),
            exposure_pct=round(pct, 2), via_direct=round(d, 2),
            via_etf=round(t, 2),
            breach=pct > C.SINGLE_NAME_EXPOSURE_ALERT_PCT,
        ))

    rows.sort(key=lambda r: r.exposure_pct, reverse=True)
    coverage_pct = penetrated_value / total_value * 100.0
    is_complete = (not incomplete_etfs) and coverage_pct >= C.OVERLAP_MIN_COVERAGE_PCT
    alerts = [r.name for r in rows if r.breach]

    if is_complete:
        note = f"穿透完整（覆蓋率 {coverage_pct:.1f}%）"
    else:
        reasons = []
        if incomplete_etfs:
            reasons.append(f"{len(incomplete_etfs)} 檔 ETF 成分未知")
        if coverage_pct < C.OVERLAP_MIN_COVERAGE_PCT:
            reasons.append(f"覆蓋率僅 {coverage_pct:.1f}%")
        note = "⚠ 穿透不完整（" + "、".join(reasons) + "）— 下列曝險為下限"

    return ExposureReport(
        rows=rows, total_value=round(total_value, 2),
        penetrated_value=round(penetrated_value, 2),
        coverage_pct=round(coverage_pct, 2), is_complete=is_complete,
        alerts=alerts, incomplete_etfs=incomplete_etfs, note=note,
        meta={"threshold_pct": C.SINGLE_NAME_EXPOSURE_ALERT_PCT},
    )
