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
    """逐檔評估 → 組表。metrics_fn(ticker) 回一 dict 指標（依賴注入,離線可測）。

    holdings: [{'ticker','name','asset_class'}, ...]
    metrics_fn 需回：weekly_close(必要) + premium_pct/sharpe/total_return_1y_pct/
      annual_yield_pct/inception_years/ann_return_3y_pct/cum_return_3y_pct/peer_ranks（可缺）。
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
            _row["held"] = held
            rows.append(_row)
        except Exception as e:  # noqa: BLE001 — 單檔失敗不炸整表（§1 誠實標記）
            rows.append(_error_row(tk, nm, ac, ak, f"{type(e).__name__}: {e}", held=held))
    return rows


# ── 真實抓取（部署端網路才跑得到；沙箱代理擋 TW/yfinance）────────────────
def fetch_vix() -> float | None:
    """最新 VIX（^VIX 收盤）。抓不到 → None（§1 不猜,235 該條件不觸發）。"""
    try:
        import yfinance as yf
        _df = yf.Ticker("^VIX").history(period="5d")
        if _df is not None and not _df.empty:
            return float(_df["Close"].dropna().iloc[-1])
    except Exception as _e:  # noqa: BLE001
        print(f"[dividend_station] VIX 抓取失敗: {type(_e).__name__}: {_e}")
    return None


def fetch_metrics(ticker: str, asset_kind: str = T.KIND_ETF) -> dict:
    """逐檔抓 L2 所需指標（best-effort;缺的回 None → 該項標資料不足）。

    日線走 L1 `fetch_etf_price`（proxy-aware、auto_adjust；**本質是 yfinance 歷史,個股
    2330.TW 亦適用**）→ 週K + 報酬 + 夏普 + 成立年；配息走 `fetch_etf_dividends`→ 年化
    配息率（個股亦可）。折溢價 `fetch_etf_nav_history` **僅 ETF**（個股無 iNAV,跳過）。
    ⚠️ 需部署端網路（沙箱代理擋）。日線為必要,無則 raise（該列標抓取失敗,§1 誠實不假裝）。
    同儕排名（3-3-3 ③）Phase 2 未接 → peer_ranks=None。
    """
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

    def _close_before(days: int) -> float | None:
        _sub = _close.loc[:_as_of - pd.Timedelta(days=days)]
        return float(_sub.iloc[-1]) if len(_sub) else None

    # 成立年數（以 5y 資料窗估算,足以判定「≥3 年」門檻）
    m["inception_years"] = ds.inception_years(_close.index.min(), _as_of)
    # 報酬（還原價 → 已含息）
    m["total_return_1y_pct"] = ds.total_return_pct(_close_before(365), _cur)
    m["cum_return_3y_pct"] = ds.total_return_pct(_close_before(365 * 3), _cur)
    m["ann_return_3y_pct"] = ds.annualized_return_pct(_close_before(365 * 3), _cur, 3.0)
    # 夏普（週報酬,rf=0 簡化）
    m["sharpe"] = ds.sharpe_weekly(weekly)

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

    # 3) 折溢價（TWSE MIS iNAV;欄位 g 已是「折溢價率(%)」,同單位比 1.5%）—— 僅 ETF
    if asset_kind == T.KIND_ETF:
        try:
            from src.data.etf.etf_fetch import fetch_etf_nav_history
            _nav = fetch_etf_nav_history(_yf)
            if _nav is not None and len(_nav):
                _pcol = next((c for c in _nav.columns if "折溢價" in str(c)), None)
                if _pcol:
                    m["premium_pct"] = float(
                        pd.to_numeric(_nav[_pcol], errors="coerce").dropna().iloc[-1])
        except Exception as _e:  # noqa: BLE001
            print(f"[dividend_station] {ticker} 折溢價缺: {type(_e).__name__}")

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
    _exclude = {str(t or "").strip().upper() for t in (exclude or [])}
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
    - 換入 = 選股池候選（caller 已排除已持有）。總經**轉守(defense)** → 換入從嚴（少給幾檔
      + stance=defensive）;未評估 → stance=unknown（只給個股層面汰弱,不套攻守）。
    """
    _macro = macro or {}
    _loaded = bool(_macro.get("loaded"))
    _defense = bool(_macro.get("defense")) if _loaded else None

    switch_out = [{"代號": str(r.get("代號", "")), "建議動作": str(r.get("建議動作", ""))}
                  for r in (rows or [])
                  if r.get("held") and r.get("健檢") == "🔴"]

    # 轉守 → 換入從嚴（少給候選）；未評估/正常 → 給滿 top
    _in_n = 3 if _defense else 5
    switch_in = [{"代號": str(c.get("代碼", c.get("代號", ""))),
                  "名稱": str(c.get("名稱", "")), "綜合分": c.get("綜合分")}
                 for c in (candidates or [])][:_in_n]

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
        "switch_in": switch_in,     # 選股池候選 → 建議換入
    }


# ── AI 戰情總結（規則式事實 + AI 潤稿;推播內容來源）──────────────────────
def build_station_digest(rows: list[dict], vix: float | None = None) -> dict:
    """戰情表 rows → 可推播的「規則式事實」摘要（純函式,離線可測,§1 不生數字）。

    只彙整**已算好**的欄位,不重抓、不推估：
    - reds：健檢 🔴 需汰弱（代號 + 建議動作）
    - adds：235 加碼觸發（加碼金非空 = deploy_pct>0）
    - errors：抓取失敗未納入判斷的代號（§1 誠實排除,不當作「無事」）
    ⚠️ 刻意**不算**核心/衛星配置偏離 —— 戰情室無部位金額資料,80/20 是價值比,
       無金額即無從計算,§1 不捏造（目標配置僅作靜態參考,見 UI caption）。
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
    return {"total": valid, "vix": vix, "reds": reds, "adds": adds, "errors": errors}


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
            f"- 建議換入（選股池候選）：{_in}\n"
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
