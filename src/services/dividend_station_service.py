"""L3 Service — 💰 存股戰情室編排（讀清單 → 抓數 → L2 評估 → 組表）。

§8.2 L3：編排 L1 抓取 + L2 純函式,不自算指標。純組表 `build_station_rows` /
`row_from_assessment` 與 I/O 分離（`metrics_fn` 依賴注入）,離線可單測；真正的
逐檔抓取 `fetch_metrics`（週K/折溢價/配息/夏普/3年報酬/同儕）需部署端網路。

§1：逐檔抓取失敗 → 該列標「資料不足/抓取失敗」,不炸整張表、不捏造數字。
"""
from __future__ import annotations

from typing import Callable

from shared import dividend_station_thresholds as T
from src.compute.etf import dividend_station as ds

_CLASS_ICON = {T.ASSET_CORE: "🛡️ 核心", T.ASSET_SATELLITE: "🚀 衛星"}


def row_from_assessment(a: ds.HoldingAssessment) -> dict:
    """HoldingAssessment → 表格一列（純函式）。"""
    _add = f"{a.light.deploy_pct:.0f}%" if a.light.deploy_pct else ""
    _is_stock = a.asset_kind == T.KIND_STOCK
    return {
        "代號": a.ticker,
        "名稱": a.name,
        "種類": "個股" if _is_stock else "ETF",
        "類別": _CLASS_ICON.get(a.asset_class, a.asset_class),
        "健檢": a.worst_health,
        "235 燈號": f"{a.light.icon} {a.light.label}",
        "加碼金": _add,
        "3-3-3": ("—" if _is_stock
                  else ("✅ 合格" if a.screen.passed
                        else ("❔ 待資料"
                              if None in (a.screen.inception_ok, a.screen.return_ok, a.screen.peer_ok)
                              else "❌ 未過"))),
        "建議動作": ds.suggest_action(a),
        # 展開明細（UI 下鑽用；不進主表）
        "_detail": {
            "健檢A": a.health_a.msg, "健檢B": a.health_b.msg,
            "健檢C": a.health_c.msg, "健檢D": a.health_d.msg,
            "235觸發": "、".join(a.light.reasons),
            "深水防守": a.light.deepwater_note or "—",
            "3-3-3明細": a.screen.detail,
        },
    }


def stock_row_from_assessment(sa: ds.StockAssessment) -> dict:
    """個股 StockAssessment → 個股汰換表一列（純函式,財報體檢 + KD）。

    `健檢` 欄復用 swap_level（🔴/🟡/🟢/⚪）→ 下游 build_station_digest / build_switch_advice /
    UI 高亮 沿用同一鍵,個股財報汰弱紅燈自然被換股建議的「換出」挑中（§ 不重造下游邏輯）。
    """
    _fh = f"{sa.mj_grade}（{sa.mj_score_pct}）" if sa.mj_grade else "資料不足"
    if sa.kd_k is not None and sa.kd_d is not None:
        _kd = f"K{sa.kd_k:.0f} D{sa.kd_d:.0f}｜{sa.kd_label}"
    else:
        _kd = "資料不足"
    _tv = sa.trend_verdict or {}          # B3:財報趨勢摘要
    _VMAP = {"deteriorating": "逐季轉差", "improving": "逐季改善",
             "mixed": "漲跌互見", "stable": "大致持平"}   # diff_fin_health verdict 中文化
    _trend_txt = ("⚠️ 本業由盈轉虧" if _tv.get("is_breakdown")
                  else "🌟 本業由虧轉盈" if _tv.get("is_turnaround")
                  else (_VMAP.get(str(_tv.get("verdict", "")), "—") if _tv else "—"))
    return {
        "代號": sa.ticker, "名稱": sa.name, "種類": "個股",
        "類別": _CLASS_ICON.get(sa.asset_class, sa.asset_class),
        "財報體檢": _fh, "KD": _kd, "財報趨勢": _trend_txt,
        "健檢": sa.swap_level,          # 復用下游/高亮同一鍵
        "建議動作": sa.swap_action,
        "_detail": {
            "財報總評": sa.mj_headline or "—",
            "財報弱項": "、".join(sa.mj_fail_items) or "—",
            "財報趨勢": _trend_txt,
            "KD明細": _kd,
            "KD交叉": {"golden": "黃金交叉", "death": "死亡交叉"}.get(sa.kd_cross, "無"),
        },
    }


def resolve_holding_names(holdings: list[dict]) -> list[dict]:
    """就地補持股中文名（§1 抓不到留空不捏造）。ETF→fetch_etf_zh_name、個股→get_stock_name。

    載入時呼叫,讓預覽表 + 戰情表兩處都顯示名稱（原本兩處都空）。best-effort:
    任一檔抓取失敗只 log、留原值,不擋載入。名稱查無時兩來源分別回 None / 代號本身 →
    一律視為「未知」留空（UI 仍有代號欄,不誤導）。
    """
    for h in (holdings or []):
        if str(h.get("name") or "").strip():
            continue
        tk = str(h.get("ticker") or "").strip().upper()
        if not tk:
            continue
        code = tk
        for _suf in (".TWO", ".TW"):
            if code.endswith(_suf):
                code = code[:-len(_suf)]
                break
        ak = h.get("asset_kind") or T.classify_asset_kind(tk)
        _nm = ""
        try:
            if ak == T.KIND_STOCK:
                from src.config.stock_names import get_stock_name
                _nm = str(get_stock_name(code) or "").strip()
                if _nm == code:                       # 查無時回代號本身 → 視為未知
                    _nm = ""
            else:
                # L3→L1 取數 = 正常編排方向（非 EX-PASSTHRU-1;那是 L4/L5/L6→L1 豁免）
                from src.data.etf.etf_fetch import fetch_etf_zh_name
                _nm = str(fetch_etf_zh_name(tk) or "").strip()
        except Exception as _e:  # noqa: BLE001 — 名稱抓取失敗不致命,留空（§1 不捏造）
            print(f"[dividend_station] {tk} 名稱抓取失敗: {type(_e).__name__}: {_e}")
        if _nm:
            h["name"] = _nm
    return holdings


def _error_row(ticker: str, name: str, asset_class: str, asset_kind: str, reason: str,
               *, held: bool = True) -> dict:
    return {
        "代號": ticker, "名稱": name,
        "種類": "個股" if asset_kind == T.KIND_STOCK else "ETF",
        "類別": _CLASS_ICON.get(asset_class, asset_class),
        "健檢": "⚪", "235 燈號": "—", "加碼金": "", "3-3-3": "—",
        "建議動作": f"⚠️ 資料不足/抓取失敗：{reason}",
        "held": held,   # 換股建議用:持有(Portfolio) vs 觀察(Watchlist)
        "_detail": {"error": reason},
    }


def build_station_rows(holdings: list[dict], *, vix: float | None,
                       metrics_fn: Callable[[str, str], dict]) -> list[dict]:
    """逐檔評估 → 組表。metrics_fn(ticker, asset_kind) 回一 dict 指標（依賴注入,離線可測）。

    holdings: [{'ticker','name','asset_class','asset_kind'}, ...]
    metrics_fn 依 asset_kind 回不同指標：
    - ETF（定期定額）：weekly_close(必要) + premium_pct/sharpe/total_return_1y_pct/
      annual_yield_pct/inception_years/ann_return_3y_pct/cum_return_3y_pct/peer_ranks（可缺）。
    - 個股（汰換）：mj_grade/mj_score_pct/mj_headline/mj_fail_items（財報體檢）+
      kd_state（KD 狀態 dict）+ current_price（可缺;缺者標資料不足,§1）。
    """
    rows: list[dict] = []
    for h in (holdings or []):
        tk = str(h.get("ticker", "") or "").strip()
        nm = str(h.get("name", "") or "")
        ac = h.get("asset_class", T.ASSET_CORE)
        ak = h.get("asset_kind", T.KIND_ETF)         # stock / etf（fetcher 分流 + 適用性）
        held = bool(h.get("held", True))             # 持有(Portfolio) vs 觀察(Watchlist)
        if not tk:
            continue
        try:
            m = metrics_fn(tk, ak)
            if ak == T.KIND_STOCK:                       # 個股：財報體檢 + KD 汰換
                sa = ds.assess_stock(
                    ticker=tk, name=nm or str(m.get("name", "")), asset_class=ac,
                    mj_grade=m.get("mj_grade"), mj_score_pct=m.get("mj_score_pct"),
                    mj_headline=m.get("mj_headline", ""),
                    mj_fail_items=m.get("mj_fail_items"), kd=m.get("kd_state"),
                    trend=m.get("trend_verdict"))
                _row = stock_row_from_assessment(sa)
            else:                                        # ETF：定期定額 235 + 3-3-3
                a = ds.assess_holding(
                    ticker=tk, name=nm or str(m.get("name", "")), asset_class=ac,
                    asset_kind=ak, weekly_close=m["weekly_close"], vix=vix,
                    premium_pct=m.get("premium_pct"), sharpe=m.get("sharpe"),
                    total_return_1y_pct=m.get("total_return_1y_pct"),
                    annual_yield_pct=m.get("annual_yield_pct"),
                    inception_years=m.get("inception_years"),
                    ann_return_3y_pct=m.get("ann_return_3y_pct"),
                    cum_return_3y_pct=m.get("cum_return_3y_pct"),
                    peer_ranks=m.get("peer_ranks"))
                _row = row_from_assessment(a)
                # B4(v19.198):ETF 品質評等 display-only 併入明細（星等 / 費用率 / AUM 清算風險）。
                #   清算風險用 aum 因子 score≤0（= AUM≤10億,etf_quality score_aum 的 SSOT floor）判,
                #   不另立門檻(§3.3)。不動健檢 A/B/C/D 主判(架構師建議 display-first)。
                _q = m.get("etf_quality")
                if isinstance(_q, dict) and _q.get("stars") is not None:
                    _fac = _q.get("factors") or {}
                    _aum = (_fac.get("aum") or {}).get("val")
                    _aum_score = (_fac.get("aum") or {}).get("score")
                    _exp = (_fac.get("expense") or {}).get("val")
                    _liq = ("　⚠️ AUM 偏小、清算風險"
                            if isinstance(_aum_score, (int, float)) and _aum_score <= 0.0 else "")
                    _row["_detail"]["ETF品質"] = (
                        "★" * int(_q["stars"])
                        # _exp 為比例形式(0.0036 = 0.36%,get_etf_expense_ratio_safe /100 SSOT)→ ×100 顯示
                        + (f"｜費用率 {_exp * 100:.2f}%" if isinstance(_exp, (int, float)) else "")
                        + (f"｜AUM {_aum / 1e8:.0f}億" if isinstance(_aum, (int, float)) else "")
                        + _liq)
                elif isinstance(_q, dict) and _q.get("_err"):
                    _row["_detail"]["ETF品質"] = f"資料不足（{_q['_err']}）"
            _row["held"] = held
            # #38：市值 = 張數 × 現價、損益% = (現價/均價-1)。§1 缺張數/均價/現價就不算,
            #   回 None(不捏 0),下游 80/20 偏離 / 衛星停利 對 None 誠實略過。
            _lots = h.get("lots")
            _avg = h.get("avg_price")
            _cur = m.get("current_price")
            _row["市值"] = (float(_lots) * float(_cur)
                            if _lots and _cur and float(_lots) > 0 and float(_cur) > 0 else None)
            _row["損益%"] = (round((float(_cur) / float(_avg) - 1.0) * 100.0, 1)
                             if _avg and _cur and float(_avg) > 0 and float(_cur) > 0 else None)
            # 績效原值(供 UI 顯示張數/均價/現價;§1 缺 → None 不捏 0)。市值/損益% 上面已存。
            _row["張數"] = float(_lots) if _lots and float(_lots) > 0 else None
            _row["均價"] = float(_avg) if _avg and float(_avg) > 0 else None
            _row["現價"] = float(_cur) if _cur and float(_cur) > 0 else None
            rows.append(_row)
        except Exception as e:  # noqa: BLE001 — 單檔失敗不炸整表（§1 誠實標記）
            rows.append(_error_row(tk, nm, ac, ak, f"{type(e).__name__}: {e}", held=held))
    return rows


# ── 真實抓取（部署端網路才跑得到；沙箱代理擋 TW/yfinance）────────────────
def fetch_vix() -> float | None:
    """最新 VIX（^VIX 收盤）。抓不到 → None（§1 不猜,235 該條件不觸發）。

    D1(v19.198):改走 `macro_core.fetch_yf_close`（全站唯一 Yahoo 抓取點 —— NAS proxy +
    module-level cache）。原本直呼 yfinance 繞過此點 → 雲端節點 IP 常被 429 靜默降級,
    且同 process 同日 ^VIX 被抓兩次不共享（§2.4）。range_="6mo" 對齊 risk_radar 同源快取。
    """
    try:
        from src.data.macro.macro_core import fetch_yf_close
        _s = fetch_yf_close("^VIX", range_="6mo")
        if _s is not None and len(_s):
            import pandas as pd
            _v = pd.Series(_s).dropna()
            if len(_v):
                return float(_v.iloc[-1])
    except Exception as _e:  # noqa: BLE001
        print(f"[dividend_station] VIX 抓取失敗: {type(_e).__name__}: {_e}")
    return None


def _fetch_stock_metrics(ticker: str) -> dict:
    """個股汰換指標：財報體檢(no-AI grade) + KD 狀態 + 現價（供市值/損益%）。

    §1 best-effort：日線/KD、財報、名稱三者各自獨立 try,任一失敗只 log + 標資料不足,
    **不 raise、不炸整表**。財報走 L1 `fetch_financial_statements` → L3 no-AI
    `analyze_financial_health` + `no_ai_overall_verdict`；KD 走日 OHLC → L2
    `analyze_kd_state` + `kd_cross_state`。⚠️ 需部署端網路（沙箱代理擋 TW/FinMind）。
    """
    code = str(ticker or "").strip().upper()
    for _suf in (".TWO", ".TW"):
        if code.endswith(_suf):
            code = code[:-len(_suf)]
            break

    m: dict = {"mj_grade": None, "mj_score_pct": None, "mj_headline": "",
               "mj_fail_items": [], "kd_state": None, "current_price": None, "name": "",
               "trend_verdict": None}

    # 1) 日 OHLC → KD。B1(v19.198):改走 StockDataLoader.get_combined_data(個股專屬 4 源鏈
    #    yfinance→FinMind→.TWO,與個股單/多檔頁同源),取代原 fetch_etf_price(ETF 抓價函式:
    #    Yahoo 單源、無 FinMind fallback → 雲端 IP 被擋就整列 error)。回小寫 OHLC df,直接餵 KD。
    try:
        from src.data.core.data_loader import StockDataLoader
        _df_stk, _err_stk, _ = StockDataLoader().get_combined_data(code, 360, True)
        if (_df_stk is not None and not getattr(_df_stk, "empty", True)
                and {"close", "high", "low"}.issubset(_df_stk.columns)):
            _ohlc = _df_stk[["close", "high", "low"]].dropna()
            if len(_ohlc):
                m["current_price"] = float(_ohlc["close"].iloc[-1])
                from src.compute.strategy.tech_indicators import (
                    analyze_kd_state, kd_cross_state)
                _kd = analyze_kd_state(_ohlc)
                if _kd:
                    _kd = dict(_kd)
                    _kd["cross"] = kd_cross_state(_ohlc)
                    m["kd_state"] = _kd
        else:
            print(f"[dividend_station] {ticker} 日線/KD 無資料: {_err_stk}")
    except Exception as _e:  # noqa: BLE001 — 日線/KD 失敗不致命,標資料不足
        print(f"[dividend_station] {ticker} 日線/KD 失敗: {type(_e).__name__}: {_e}")

    # 2) 財報體檢（no-AI grade）
    try:
        from src.config.config import get_finmind_token
        _tok = get_finmind_token() or ""
    except Exception as _e:  # noqa: BLE001 — token 讀不到 → 交給 fetcher 用 env fallback
        print(f"[dividend_station] {ticker} FINMIND_TOKEN 讀取失敗,改用 env fallback: "
              f"{type(_e).__name__}")
        _tok = ""
    try:
        from src.data.core.financial_statements_fetcher import fetch_financial_statements
        from src.services.financial_health_engine import (
            analyze_financial_health, no_ai_overall_verdict)
        _fin = fetch_financial_statements(code, _tok)
        if isinstance(_fin, dict) and not _fin.get("error"):
            _fh = analyze_financial_health("", code, _fin)   # api_key="" → 純 no-AI 路徑
            _ov = no_ai_overall_verdict(_fin, _fh)
            m["mj_grade"] = _ov.get("grade")
            m["mj_score_pct"] = _ov.get("score_pct")
            m["mj_headline"] = str(_ov.get("headline", ""))
            m["mj_fail_items"] = list(_ov.get("fail_items", []) or [])
            # B3(v19.198):財報趨勢(盈轉虧/逐季惡化)。fetch_financial_statements 已回
            #   prev_period_data(730天窗 bootstrap,v18.456)→ 對上一季跑同 no-AI 體檢 →
            #   diff_fin_health 取 is_breakdown/is_turnaround → assess_stock 在 grade 掉到 C 前提前預警。
            #   近零額外抓取(prev 已在手)。§1:趨勢算不出不擋汰弱主判。
            try:
                _prev_fd = _fin.get("prev_period_data")
                if _prev_fd:
                    from src.compute.health.fin_health_diff import diff_fin_health
                    _prev_fh = analyze_financial_health("", code, _prev_fd)
                    _tv = diff_fin_health(_prev_fh, _fh, code)
                    m["trend_verdict"] = {"is_breakdown": bool(_tv.is_breakdown),
                                          "is_turnaround": bool(_tv.is_turnaround),
                                          "verdict": str(_tv.verdict)}
            except Exception as _te:  # noqa: BLE001 — 趨勢算不出不擋汰弱主判
                print(f"[dividend_station] {ticker} 財報趨勢失敗: {type(_te).__name__}")
        else:
            _err = _fin.get("error") if isinstance(_fin, dict) else "財報抓取失敗"
            print(f"[dividend_station] {ticker} 財報缺: {_err}")
    except Exception as _e:  # noqa: BLE001 — 財報失敗 → 財報體檢標資料不足,不炸整表
        print(f"[dividend_station] {ticker} 財報健檢失敗: {type(_e).__name__}: {_e}")

    # 3) 名稱（get_stock_name 查無回代號本身 → 視為未知留空）
    try:
        from src.config.stock_names import get_stock_name
        _nm = str(get_stock_name(code) or "").strip()
        if _nm and _nm != code:
            m["name"] = _nm
    except Exception as _e:  # noqa: BLE001
        print(f"[dividend_station] {ticker} 名稱抓取失敗: {type(_e).__name__}")

    return m


def fetch_metrics(ticker: str, asset_kind: str = T.KIND_ETF) -> dict:
    """逐檔抓 L2 所需指標（best-effort;缺的回 None → 該項標資料不足）。

    日線走 L1 `fetch_etf_price`（proxy-aware、auto_adjust；**本質是 yfinance 歷史,個股
    2330.TW 亦適用**）→ 週K + 報酬 + 夏普 + 成立年；配息走 `fetch_etf_dividends`→ 年化
    配息率（個股亦可）。折溢價 `fetch_etf_nav_history` **僅 ETF**（個股無 iNAV,跳過）。
    ⚠️ 需部署端網路（沙箱代理擋）。日線為必要,無則 raise（該列標抓取失敗,§1 誠實不假裝）。
    同儕排名（3-3-3 ③）Phase 2 未接 → peer_ranks=None。
    **個股（asset_kind=stock）改走 `_fetch_stock_metrics`（財報體檢 + KD）,不套 235/3-3-3。**
    """
    if asset_kind == T.KIND_STOCK:
        return _fetch_stock_metrics(ticker)

    import pandas as pd
    from src.compute.etf import normalize_etf_ticker

    # ⚠️ 台股代碼須補 .TW(0056→0056.TW) 再抓,否則 fetch_etf_price/yfinance 抓空 →
    # 每檔 raise「無日線」= 整排 error(部署端實測回報)。既有 ETF 分頁都先做這步。
    _yf = normalize_etf_ticker(ticker) or ticker

    # 1) 日線（還原價）→ 週K（必要）。normalize 一律補 .TW（上市）;抓空 → 試 .TWO（上櫃,
    #    稽核 MED:上櫃存股 5314/8069 等 yfinance 用 .TWO,否則整檔 error）。
    try:
        from src.data.etf.etf_fetch import fetch_etf_price   # EX-PASSTHRU-1
        _px = fetch_etf_price(_yf, period="5y")
        if (_px is None or getattr(_px, "empty", True)) and _yf.endswith(".TW"):
            _alt = _yf[:-3] + ".TWO"
            _px2 = fetch_etf_price(_alt, period="5y")
            if _px2 is not None and not getattr(_px2, "empty", True):
                _px, _yf = _px2, _alt        # 上櫃命中 → 後續配息/折溢價亦改用 .TWO
    except Exception as _e:  # noqa: BLE001
        raise ValueError(f"{ticker} 日線抓取失敗: {type(_e).__name__}: {_e}") from _e
    if _px is None or getattr(_px, "empty", True):
        raise ValueError(f"{ticker} 無日線資料（.TW/.TWO 皆無;部署端網路或代碼確認）")
    _col = next((c for c in ("Close", "close") if c in _px.columns), None)
    if _col is None:
        raise ValueError(f"{ticker} 日線缺 Close 欄")
    _close = pd.Series(_px[_col]).dropna()
    if not isinstance(_close.index, pd.DatetimeIndex):
        _close.index = pd.to_datetime(_close.index)
    _close = _close.sort_index()
    weekly = ds.weekly_closes(_close)
    if weekly is None or len(weekly) == 0:
        raise ValueError(f"{ticker} 週K 為空")

    m: dict = {"weekly_close": weekly}
    _as_of = pd.Timestamp.today().normalize()
    _cur = float(_close.iloc[-1])
    m["current_price"] = _cur          # #38：供 市值 = 張數×現價 / 損益% 計算

    def _close_before(days: int) -> float | None:
        _sub = _close.loc[:_as_of - pd.Timedelta(days=days)]
        return float(_sub.iloc[-1]) if len(_sub) else None

    # 成立年數（以 5y 資料窗估算,足以判定「≥3 年」門檻）
    m["inception_years"] = ds.inception_years(_close.index.min(), _as_of)
    # 報酬（還原價 → 已含息）
    m["total_return_1y_pct"] = ds.total_return_pct(_close_before(365), _cur)
    m["cum_return_3y_pct"] = ds.total_return_pct(_close_before(365 * 3), _cur)
    m["ann_return_3y_pct"] = ds.annualized_return_pct(_close_before(365 * 3), _cur, 3.0)
    # 夏普（週報酬）。B2(v19.198):對齊 ETF calc_sharpe 的 rf SSOT —— 注入即時 FEDFUNDS
    #   (失敗維持 ETF_SHARPE_RF_FALLBACK_PCT),原寫死 rf=0 系統性偏寬鬆。個股走 _fetch_stock_metrics
    #   不算夏普,本段僅 ETF。
    try:
        from src.compute.etf.etf_calc import get_risk_free_rate_pct
        from src.services.etf_scoring_service import ensure_etf_rf_injected
        ensure_etf_rf_injected()               # cached(FEDFUNDS @st.cache_data 1h)
        _rf_ds = get_risk_free_rate_pct()
    except Exception as _e_rf:  # noqa: BLE001 — 取 rf 失敗 → 退 rf=0(等同修前行為),不炸
        print(f"[dividend_station] {ticker} rf 取得失敗,退 rf=0: {type(_e_rf).__name__}")
        _rf_ds = 0.0
    m["sharpe"] = ds.sharpe_weekly(weekly, rf_pct=_rf_ds)

    # 2) 年化配息率
    try:
        from src.data.etf.etf_fetch import fetch_etf_dividends
        _div = pd.Series(fetch_etf_dividends(_yf))
        if len(_div):
            _div.index = pd.to_datetime(_div.index)
            _ttm = float(_div[_div.index >= (_as_of - pd.Timedelta(days=365))].sum())
            m["annual_yield_pct"] = ds.annual_yield_pct(_ttm, _cur)
    except Exception as _e:  # noqa: BLE001 — 配息缺 → 健檢 A 標資料不足,不炸
        print(f"[dividend_station] {ticker} 配息缺: {type(_e).__name__}")

    # 3) 折溢價 —— 僅 ETF。A2(v19.198):改走 calc_premium_discount SSOT(官方 iNAV 同日
    #    inner-join + 3 守門員 G1/G2/G3 + sanity 上限),與 ETF 單/多檔頁同源。原本直取
    #    nav_history「折溢價」欄末值,末端 fallback 到 yfinance navPrice 會回「最後已公告淨值」
    #    被硬戳今日 → 假溢價卻觸發健檢D 假🟡(§1 Fail-Loud 破口,即 v18.442 修的 0050 假+5.07%)。
    #    stale_nav / premium_pct=None → **不填** m["premium_pct"] → 健檢D 標「無折溢價資料」不假判。
    if asset_kind == T.KIND_ETF:
        try:
            from src.compute.etf.etf_calc import calc_premium_discount
            from src.data.etf.etf_fetch import fetch_etf_info
            _pd_res = calc_premium_discount(fetch_etf_info(_yf) or {}, _px, _yf)
            if isinstance(_pd_res, dict) and _pd_res.get("premium_pct") is not None:
                m["premium_pct"] = float(_pd_res["premium_pct"])
        except Exception as _e:  # noqa: BLE001
            print(f"[dividend_station] {ticker} 折溢價缺: {type(_e).__name__}")

    # B4(v19.198):ETF 品質評等（內扣費用率 / AUM 清算風險 / Beta / 殖利率 CV）—— display-only,
    #   對「存股 ETF 定期健檢」補上長期內扣成本 + 清算存續維度（原本整組省略）。§1 抓不到 stars=None。
    if asset_kind == T.KIND_ETF:
        try:
            from src.compute.etf.etf_quality import compute_etf_quality
            m["etf_quality"] = compute_etf_quality(_yf)
        except Exception as _e:  # noqa: BLE001 — 品質評等缺不擋健檢主判
            print(f"[dividend_station] {ticker} ETF 品質評等缺: {type(_e).__name__}")

    # 同儕排名（3-3-3 ③）：僅 ETF 接 compute_etf_peer_ranking（個股 3-3-3 不適用 → None）。
    #   §1 best-effort：同儕不足 / 抓取失敗 → None → 該項顯示「❔ 待資料」不硬判。
    m["peer_ranks"] = _fetch_peer_ranks(_yf) if asset_kind == T.KIND_ETF else None
    return m


def _fetch_peer_ranks(ticker: str) -> dict[int, float] | None:
    """接 L2 `compute_etf_peer_ranking` → 3-3-3 kernel 期望的 {月數: 分位(0=最強)}。

    轉換（§4.1 語意對齊）：
    - 交易日視窗 63/126/252 → 月 3/6/12（PEER_WINDOWS_MONTHS）。
    - percentile（0~100，贏過同儕的%，**越高越強**）→ 分位 `(100−percentile)/100`
      （0=最強、1=最弱；kernel 的「前 1/3」= 分位 ≤ 1/3 = percentile ≥ 66.7）。
    §1：`_err`（同儕不足/抓取失敗）或某視窗缺 → 該月不填 → kernel peer_ok 維持不可判定。
    """
    try:
        from src.compute.etf.etf_calc import compute_etf_peer_ranking
        _pr = compute_etf_peer_ranking(ticker)
    except Exception as _e:  # noqa: BLE001 — 同儕算不出不擋整檔健檢
        print(f"[dividend_station] {ticker} 同儕排名失敗: {type(_e).__name__}: {_e}")
        return None
    if not isinstance(_pr, dict) or _pr.get("_err"):
        return None
    _day_to_month = {63: 3, 126: 6, 252: 12}
    _out: dict[int, float] = {}
    for _days, _mon in _day_to_month.items():
        _slot = _pr.get(_days)
        if isinstance(_slot, dict) and _slot.get("percentile") is not None:
            _out[_mon] = (100.0 - float(_slot["percentile"])) / 100.0
    return _out or None


def get_station_rows(holdings: list[dict]) -> tuple[list[dict], float | None]:
    """畫面入口：抓 VIX（一次）+ 逐檔 → 組表。回 (rows, vix)。"""
    vix = fetch_vix()
    rows = build_station_rows(holdings, vix=vix, metrics_fn=fetch_metrics)
    return rows, vix


# ── 換股建議（換出=持有🔴汰弱 · 換入=選股池候選 · 總經位階當攻守閘門）──────────
def get_station_macro() -> dict:
    """取當前總經位階（唯讀,不打 API;§1 讀不到標未評估,不瞎給攻守）。

    session 內走 `allocation_service.get_macro_regime()`（併本 session warroom,是全站
    唯一 regime 橋樑）;退化 `macro_state_locker.get_macro_state()`（只讀 macro_state.json
    快照）。攻守姿態沿用 `position_throttle`（不自創刻度）。回正規化 dict。
    """
    _state = None
    try:
        from src.services.allocation_service import get_macro_regime
        _state = get_macro_regime()
    except Exception:  # noqa: BLE001 — 無 session / 匯入失敗 → 退離線快照
        _state = None
    if not isinstance(_state, dict) or not _state:
        try:
            from src.services.macro_state_locker import get_macro_state
            _state = get_macro_state()
        except Exception as _e:  # noqa: BLE001 — §1 讀不到當未評估,不炸
            print(f"[dividend_station] 位階讀取失敗: {type(_e).__name__}: {_e}")
            _state = None
    if not isinstance(_state, dict):
        _state = {}

    _regime = str(_state.get("regime", "unknown") or "unknown")
    _loaded = bool(_state.get("is_loaded", False)) and _regime != "unknown"
    _health = _state.get("health")
    _defense = _state.get("defense")

    _posture_label, _posture_range = None, None
    if _loaded and isinstance(_health, (int, float)):
        try:
            from shared.position_throttle import compute_position_throttle
            _thr = compute_position_throttle(float(_health), _regime, bool(_defense))
            _posture_label = f"{_thr['icon']} {_thr['posture']}"
            _posture_range = f"{_thr['lo_pct']}–{_thr['hi_pct']}%"
        except Exception as _e:  # noqa: BLE001 — 姿態算不出不擋位階本身
            print(f"[dividend_station] 姿態油門失敗: {type(_e).__name__}: {_e}")

    return {
        "regime": _regime, "loaded": _loaded,
        "light": _state.get("light"), "health": _health,
        "defense": bool(_defense) if _loaded else None,
        "posture_label": _posture_label or ("總經未評估" if not _loaded else None),
        "posture_range": _posture_range,
    }


def get_switch_in_candidates(*, regime: str | None = None,
                             exclude: list[str] | None = None,
                             top_n: int = 5) -> list[dict]:
    """換入候選 ← 選股網「選股池」top（沿用畫面同源 get_ranked_picks,已快取子呼叫）。

    §1：選股網不可用 / 空 → 回 []（caller 顯示「選股池暫無候選」）,不捏造標的。
    exclude：已持有代號（不建議換入自己已有的）。regime 傳給選股網套空頭濾網。
    """
    # §後綴 SSOT:exclude（已持有代號）去 .TW/.TWO 再比對,否則 '2330.TW' 擋不掉 bare '2330'
    # → 已持有卻被推「換入」(稽核 1b)。候選 _code 亦 normalize 後比對。
    _exclude = {T.normalize_ticker(t) for t in (exclude or []) if str(t or "").strip()}
    try:
        from src.services.fundamental_screener_service import (
            SCREEN_ANGLE_LABELS, get_ranked_picks)
        _factors = list(SCREEN_ANGLE_LABELS.values())     # 全角度,同畫面「全勾」
        _df, _note = get_ranked_picks(_factors, top_n=max(top_n * 4, 40),
                                      regime=regime, auto_fetch=True)
    except Exception as _e:  # noqa: BLE001 — 選股池讀取失敗回空,不炸戰情室
        print(f"[dividend_station] 選股池候選讀取失敗: {type(_e).__name__}: {_e}")
        return []
    if _df is None or getattr(_df, "empty", True):
        return []

    _out: list[dict] = []
    for _rec in _df.to_dict("records"):
        _code = str(_rec.get("代碼", _rec.get("代號", "")) or "").strip().upper()
        if not _code or _code in _exclude:
            continue
        _out.append({"代碼": _code, "名稱": str(_rec.get("名稱", "") or ""),
                     "綜合分": _rec.get("綜合分")})
        if len(_out) >= top_n:
            break
    return _out


def build_switch_advice(rows: list[dict], macro: dict | None,
                        candidates: list[dict] | None) -> dict:
    """換股建議（純函式,離線可測,§1 不生標的）。

    - 換出 = **持有(held)** 且 健檢🔴（汰弱）。觀察清單的紅燈不算「換出」（你沒持有）。
    - 換入 = **優先**你親手選進「觀察清單(held=False)」且健檢綠燈的標的（#34）;觀察清單無
      綠燈才 fallback 選股池 candidates（caller 已排除已持有）。總經**轉守(defense)** → 換入
      從嚴（少給幾檔 + stance=defensive）;未評估 → stance=unknown（只給汰弱,不套攻守）。
    """
    _macro = macro or {}
    _loaded = bool(_macro.get("loaded"))
    _defense = bool(_macro.get("defense")) if _loaded else None

    switch_out = [{"代號": str(r.get("代號", "")), "建議動作": str(r.get("建議動作", ""))}
                  for r in (rows or [])
                  if r.get("held") and r.get("健檢") == "🔴"]

    # 轉守 → 換入從嚴（少給候選）；未評估/正常 → 給滿 top
    _in_n = 3 if _defense else 5
    # #34：換入優先 = 你觀察清單(held=False)裡健檢🟢的（親手選的池子）;空才 fallback 選股池。
    _watch_greens = [{"代號": str(r.get("代號", "")), "名稱": str(r.get("名稱", "")),
                      "綜合分": None}
                     for r in (rows or [])
                     if (not r.get("held")) and (not r.get("_detail", {}).get("error"))
                     and r.get("健檢") == "🟢"]
    if _watch_greens:
        switch_in = _watch_greens[:_in_n]
        switch_in_src = "watchlist"
    else:
        switch_in = [{"代號": str(c.get("代碼", c.get("代號", ""))),
                      "名稱": str(c.get("名稱", "")), "綜合分": c.get("綜合分")}
                     for c in (candidates or [])][:_in_n]
        switch_in_src = "screener"

    if not _loaded:
        stance = "unknown"
    elif _defense:
        stance = "defensive"
    elif _macro.get("regime") == "bull":
        stance = "aggressive"
    else:
        stance = "neutral"

    return {
        "regime": _macro.get("regime"), "loaded": _loaded, "defense": _defense,
        "posture": _macro.get("posture_label"), "posture_range": _macro.get("posture_range"),
        "stance": stance,
        "switch_out": switch_out,   # 持有紅燈 → 建議換出
        "switch_in": switch_in,     # 換入候選（優先觀察清單綠燈,否則選股池）
        "switch_in_src": switch_in_src,   # "watchlist"(你選的) / "screener"(全自動 fallback)
    }


# ── 80/20 配置偏離 + 衛星停利（#38：有張數/均價才算,§1 缺就不算）───────────
def compute_allocation_split(rows: list[dict]) -> dict | None:
    """80/20 實際配置偏離（純函式）。核心=ETF、衛星=個股（郭俊宏:核心配息ETF/衛星成長股,
    以代號類型近似;主題型 ETF 會被算核心,UI 已註記此近似）。

    只納入 **held 且有市值(市值>0)** 的列。§1：部分 held 缺金額 → partial=True(僅供參考);
    全無市值 → None（UI 不顯示、不捏造）。
    """
    _core = _sat = 0.0
    _held_n = _valued_n = 0
    for r in (rows or []):
        if not r.get("held") or r.get("_detail", {}).get("error"):
            continue
        _held_n += 1
        _v = r.get("市值")
        if not isinstance(_v, (int, float)) or _v <= 0:
            continue
        _valued_n += 1
        if r.get("種類") == "個股":
            _sat += float(_v)
        else:
            _core += float(_v)
    _total = _core + _sat
    if _total <= 0:
        return None
    _core_pct = _core / _total * 100.0
    return {
        "core_pct": round(_core_pct, 1), "sat_pct": round(100.0 - _core_pct, 1),
        "core_target": T.CORE_TARGET_PCT, "sat_target": T.SATELLITE_TARGET_PCT,
        "core_dev": round(_core_pct - T.CORE_TARGET_PCT, 1),
        "total_value": round(_total, 0),
        "partial": _valued_n < _held_n, "held_n": _held_n, "valued_n": _valued_n,
    }


def flag_take_profit(rows: list[dict]) -> list[dict]:
    """衛星（個股）獲利達停利門檻 → 嚴格停利滾回核心（純函式）。

    郭俊宏:衛星獲利 15~20% 嚴格停利。門檻 `SATELLITE_TAKE_PROFIT_PCT`(=15)。
    §1：僅對 held 衛星(個股)且**有損益%**者判;無成本(損益%=None) → 不判、不捏造。
    """
    _out: list[dict] = []
    for r in (rows or []):
        if not r.get("held") or r.get("_detail", {}).get("error"):
            continue
        if r.get("種類") != "個股":          # 衛星 = 個股（同 80/20 近似）
            continue
        _pnl = r.get("損益%")
        if isinstance(_pnl, (int, float)) and _pnl >= T.SATELLITE_TAKE_PROFIT_PCT:
            _out.append({"代號": str(r.get("代號", "")), "損益%": round(float(_pnl), 1)})
    return _out


# ── AI 戰情總結（規則式事實 + AI 潤稿;推播內容來源）──────────────────────
def build_station_digest(rows: list[dict], vix: float | None = None) -> dict:
    """戰情表 rows → 可推播的「規則式事實」摘要（純函式,離線可測,§1 不生數字）。

    彙整**已算好**的欄位,不重抓、不推估：
    - reds：健檢 🔴 需汰弱（代號 + 建議動作）
    - adds：235 加碼觸發（加碼金非空 = deploy_pct>0）
    - errors：抓取失敗未納入判斷的代號（§1 誠實排除,不當作「無事」）
    - allocation：80/20 實際配置偏離（有張數/均價才算;缺 → None,#38）
    - take_profit：衛星獲利達 15% 嚴格停利清單（有損益%才判;#38）
    """
    reds: list[dict] = []
    adds: list[dict] = []
    errors: list[str] = []
    valid = 0
    for r in (rows or []):
        if r.get("_detail", {}).get("error"):
            errors.append(str(r.get("代號", "")))
            continue
        valid += 1
        if r.get("健檢") == "🔴":
            reds.append({"代號": str(r.get("代號", "")),
                         "建議動作": str(r.get("建議動作", ""))})
        if str(r.get("加碼金", "") or "").strip():
            adds.append({"代號": str(r.get("代號", "")),
                         "235": str(r.get("235 燈號", "")),
                         "加碼金": str(r.get("加碼金", ""))})
    return {"total": valid, "vix": vix, "reds": reds, "adds": adds, "errors": errors,
            "allocation": compute_allocation_split(rows),
            "take_profit": flag_take_profit(rows)}


def build_summary_prompt(digest: dict, switch: dict | None = None) -> str:
    """digest(+換股建議) → LLM prompt（純字串,數字全來自 digest/switch；AI 僅潤稿,§1/T5）。

    switch=build_switch_advice() 的 dict（可選）；帶入時 AI 摘要會含「當前位階 → 換股建議」。
    """
    _vix = digest.get("vix")
    _vix_txt = f"{_vix:.1f}" if isinstance(_vix, (int, float)) else "抓取失敗"
    _reds = "、".join(f"{d['代號']}（{d['建議動作']}）" for d in digest.get("reds", [])) or "無"
    _adds = "、".join(f"{d['代號']} {d['235']} 加碼{d['加碼金']}"
                      for d in digest.get("adds", [])) or "無"
    _errs = "、".join(digest.get("errors", [])) or "無"
    _base = (
        "你是台股『存股戰情室』的推播助理。根據以下今日持股健檢結果,用繁體中文寫 3~6 句的推播摘要,"
        "聚焦『今天要不要動作』。只能引用下列數據,嚴禁自行杜撰任何代號、數字或未列出的結論;"
        "沒有紅燈也沒有加碼時,請明講『續抱、定期定額即可』。\n"
        f"- 目前 VIX：{_vix_txt}\n"
        f"- 有效判斷檔數：{digest.get('total', 0)}\n"
        f"- 健檢紅燈需汰弱：{_reds}\n"
        f"- 235 加碼觸發：{_adds}\n"
        f"- 抓取失敗未納入：{_errs}\n"
    )
    _alloc = digest.get("allocation")
    if _alloc:
        _partial = "（部分持股缺金額,僅供參考）" if _alloc.get("partial") else ""
        _base += (
            f"- 實際配置：核心 {_alloc['core_pct']:.0f}% / 衛星 {_alloc['sat_pct']:.0f}%"
            f"（目標 {_alloc['core_target']:.0f}/{_alloc['sat_target']:.0f}，"
            f"核心偏離 {_alloc['core_dev']:+.0f}%）{_partial}\n"
        )
    _tp = digest.get("take_profit") or []
    if _tp:
        _tp_txt = "、".join(f"{d['代號']}(+{d['損益%']:.0f}%)" for d in _tp)
        _base += (f"- 衛星達停利門檻(≥{T.SATELLITE_TAKE_PROFIT_PCT:.0f}%)"
                  f"建議嚴格停利滾回核心：{_tp_txt}\n")   # §3.3 走 SSOT,不硬寫 15
    if switch:
        _out = "、".join(f"{d['代號']}（{d['建議動作']}）"
                         for d in switch.get("switch_out", [])) or "無"
        _in = "、".join(f"{d['代號']} {d.get('名稱', '')}".strip()
                        for d in switch.get("switch_in", [])) or "無"
        _posture = switch.get("posture") or "總經未評估"
        _stance_note = {
            "defensive": "總經轉守 → 偏守:優先汰弱、換入從嚴、勿追高。",
            "aggressive": "總經多頭 → 可積極把汰弱標的換成選股池強候選。",
            "neutral": "總經中性 → 正常汰弱換優。",
            "unknown": "總經未評估 → 只依個股健檢汰弱,不套總經攻守(不瞎猜方向)。",
        }.get(switch.get("stance", "unknown"), "")
        _base += (
            "── 換股建議（搭配總經位階）──\n"
            f"- 當前總經位階：{switch.get('regime')}（姿態 {_posture}"
            f"{('，建議持股 ' + switch['posture_range']) if switch.get('posture_range') else ''}）\n"
            f"- 建議換出（你持有的紅燈汰弱）：{_out}\n"
            f"- 建議換入（來源：{'你的觀察清單' if switch.get('switch_in_src') == 'watchlist' else '選股池全自動排名'}）：{_in}\n"
            f"- 攻守指引：{_stance_note}\n"
            "請把「換出 X → 換入 Y」講清楚;位階未評估時不要編造攻守方向。\n"
        )
    return _base


def build_ai_summary(digest: dict, gemini_fn: Callable[..., str],
                     switch: dict | None = None) -> str:
    """digest(+換股建議) + 注入的 gemini_fn → AI 潤稿推播文字。

    §8.2 L3：AI 呼叫由 caller 注入（gemini_fn），本層只組 prompt + 轉呼叫。
    §1：gemini_fn 失敗**往上拋**,由 UI 誠實顯示錯誤,不回假摘要。
    """
    prompt = build_summary_prompt(digest, switch=switch)
    return gemini_fn(prompt, max_tokens=700)
