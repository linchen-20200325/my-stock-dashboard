"""L3 Service — 💰 存股戰情室編排（讀清單 → 抓數 → L2 評估 → 組表）。

§8.2 L3：編排 L1 抓取 + L2 純函式,不自算指標。純組表 `build_station_rows` /
`row_from_assessment` 與 I/O 分離（`metrics_fn` 依賴注入）,離線可單測；真正的
逐檔抓取 `fetch_metrics`（週K/折溢價/配息/夏普/3年報酬/同儕）需部署端網路。

§1：逐檔抓取失敗 → 該列標「資料不足/抓取失敗」,不炸整張表、不捏造數字。
"""
from __future__ import annotations

import math
import numbers
from typing import Callable

from shared import asset_currency_gate as FXG
from shared import holdings_data_short as HDS
from shared import price_asof_label as PAL
from shared.dated_value import coerce_plain_date as _coerce_plain_date
from shared import dividend_station_thresholds as T
from shared import sector_flow_thresholds as _UNITS
from shared import station_specs as SS
from src.compute.etf import dividend_station as ds

_CLASS_ICON = {T.ASSET_CORE: "🛡️ 核心", T.ASSET_SATELLITE: "🚀 衛星"}


def row_from_assessment(a: ds.HoldingAssessment) -> dict:
    """HoldingAssessment → 表格一列（純函式）。

    ⚠️ `健檢` 欄是 `worst_health`（四盞燈取最嚴重）—— 這一步會把「為什麼」整個丟掉:
    四盞燈都 ⚪ 時只剩一個裸 ⚪,而那可能是新上市 / 週數年數不足(`MISS_NOT_ENOUGH`,
    等時間)、或折溢價 / 配息這輪沒抓到(`MISS_NO_INPUT`,可重跑)。
    ⚠️ 2026-08-26 更正:原文這裡還列了第三種「或個股不適用(不是壞掉)」——
    **那是假的**,而且是上一輪編輯這支 docstring 時漏掉的同一句話。健檢四盞燈
    只掛得上 `MISS_NOT_ENOUGH` / `MISS_NO_INPUT` 兩種原因;**健檢四盞燈裡**唯一會掛
    `MISS_NOT_APPLICABLE` 的是 `assess_holding` 裡 `_is_etf=False` 那條分支,而
    個股走的是 `assess_stock`,根本不經過 `assess_holding`(本檔
    `build_station_rows` 是它唯一的 production 呼叫端,且 `asset_kind` 已由白名單
    保證是 etf)。把不會發生的原因列進來,等於叫下一個人去查一個不存在的情形。
    ⚠️ 「健檢四盞燈裡」這個限定不可省(2026-08-26 補):**本檔另有第二個掛載點** ——
    `_weekly_series_payload` 對**個股列 / 個股抓取失敗列**的走勢圖原料
    (`KEY_WEEKLY_SERIES`)標的就是 `MISS_NOT_APPLICABLE`,而且那一處 production
    真的會走到。沒有限定詞的話,這句讀起來是「全檔唯一」的全稱句 = 假話。
    L0 `station_specs.MISS_NOT_APPLICABLE` 的註解已同步列出兩個掛載點。
    row dict 是 UI / 推播 / 換股建議共同的輸入,原因在這裡
    斷掉就再也接不回去,故補兩個**底線開頭的非顯示欄**（同 `_detail` 慣例,不進表格）:
      - `_health_miss`:{規格表 key → MISS_*},逐盞燈的原因,無損。
      - `_miss_reason`:整列一句話版本(只在 `健檢` 為 ⚪ 時有值),給只想顯示一個
        圖示 + 一句話的消費端用；多盞燈原因不同時取最根本者（`most_fundamental_miss`）。

    ⚠️ 上面兩個鍵只收「**⚪ 且有登記原因**」的燈 —— 一盞 🟢 和一盞 🟡 在 row 裡
    產出的東西一模一樣（都是空的）。要畫「逐盞燈的格子牆」或算「N/M 盞可信度」,
    這兩個鍵給不出來。故再補第三個非顯示欄:
      - `_lights`:`tuple[ds.LightCell, ...]`,**逐盞燈**的 key / level / 四態 /
        缺值原因（235 另帶 `axes_used`）。純轉換,判燈結果一個字都沒動。
    """
    _add = f"{a.light.deploy_pct:.0f}%" if a.light.deploy_pct else ""
    _is_stock = a.asset_kind == T.KIND_STOCK
    # 只收「⚪ 且有登記原因」的燈:判得出來的燈沒有原因可講,塞進去會讓消費端
    # 誤以為它也缺（§1 不製造假的缺值紀錄）。
    _health_miss = {
        _k: _f.miss_reason
        for _k, _f in ((SS.KEY_HEALTH_A, a.health_a), (SS.KEY_HEALTH_B, a.health_b),
                       (SS.KEY_HEALTH_C, a.health_c), (SS.KEY_HEALTH_D, a.health_d))
        if _f.level == "⚪" and _f.miss_reason
    }
    _row = {
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
        # AUD-C3（非顯示欄）：`建議動作` 走到的分支代碼（`ds.ACTION_*`，與上一欄同一份
        # 優先序）。推播 digest 的「加碼」段以此判定，不比對中文字串、不另判一次。
        "_action": ds.action_branch(a),
        # 展開明細（UI 下鑽用；不進主表）
        "_detail": {
            "健檢A": a.health_a.msg, "健檢B": a.health_b.msg,
            "健檢C": a.health_c.msg, "健檢D": a.health_d.msg,
            "235觸發": "、".join(a.light.reasons),
            "深水防守": a.light.deepwater_note or "—",
            "3-3-3明細": a.screen.detail,
        },
        # 揭露用（非顯示欄,不進 _ETF_COLS）：見本函式 docstring。
        "_health_miss": _health_miss,
        "_miss_reason": (SS.most_fundamental_miss(_health_miss.values())
                         if a.worst_health == "⚪" else ""),
        "_light_miss": a.light.miss_reason,          # 235 燈三軸全無資料時才有值
        "_light_axes_used": list(a.light.axes_used),  # 這盞 235 燈用了哪幾個依據
        "_screen_miss": dict(a.screen.miss_reasons),  # 3-3-3 三子項各自為什麼 ❔
        # 逐盞燈的判定 + 四態(ETF 8 盞)。上面三個鍵是「只有缺的才有」,本鍵是**全部都有**。
        "_lights": ds.light_cells(a),
    }
    if a.invalid_keys:
        # 批 Z50：有燈因資料異常不判定 → 標記（只有異常才有這一鍵，正常列逐鍵不變）。
        _row[SS.KEY_INVALID_LIGHTS] = tuple(a.invalid_keys)
        # 批 Z51：哪一項、哪一句（給 ⑦ AI 輸入列事實；項目沿用戰情表既有名稱，句子就是 L2 的客戶句）。
        _k = set(a.invalid_keys)
        _row[SS.KEY_INVALID_TEXTS] = tuple(
            [(_lbl, _f.msg) for _lbl, _key, _f in (
                ("健檢A", SS.KEY_HEALTH_A, a.health_a), ("健檢B", SS.KEY_HEALTH_B, a.health_b),
                ("健檢C", SS.KEY_HEALTH_C, a.health_c), ("健檢D", SS.KEY_HEALTH_D, a.health_d))
             if _key in _k]
            + ([("3-3-3", a.screen.invalid_text)]
               if _k & {SS.KEY_SCREEN_INCEPTION, SS.KEY_SCREEN_RETURN, SS.KEY_SCREEN_PEER}
               else [])
            + ([("235", "".join(a.light.reasons))] if SS.KEY_LIGHT235 in _k else []))
    return _row


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
        # 與 ETF 列同鍵（消費端不必分兩種列型判斷）：⚪ 時說得出是「沒抓到」還是
        # 「上游給的評等不在分級表裡」——後者是 bug 訊號,不該被畫成一般的資料不足。
        "_miss_reason": sa.miss_reason,
        # 逐盞燈(個股 4 盞),與 ETF 列同鍵。⚠️ 4 盞裡只有「汰換建議」有既有判定,
        # 另三盞 `assess_stock` 從未各自判過等級 → `level` 為空字串（見 L2 的
        # `LEVEL_UNJUDGED`）。這是實作現況的誠實揭露,不是本層漏填。
        "_lights": ds.light_cells(sa),
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


KEY_WEEKLY_SERIES = "_weekly_series"
"""row dict 上「週線走勢圖原料」那一鍵的名字（底線開頭 = 非顯示欄,同 `_detail` / `_lights`）。

具名常數而非各處寫字面值:這一鍵有 4 個產出點（ETF 列 / 個股列 / 抓取失敗列 / 本檔測試）
與下游消費端,字面值散開就會有人打錯字而**靜默**拿不到序列（dict 取不到只會回 None）。
"""


def _weekly_series_payload(weekly_close, *, unavailable: str = "") -> dict:
    """週K 序列 → 走勢圖原料（純函式）。**這一步只搬運與整形,不判燈、不改任何判定。**

    ## 為什麼均線 / 布林 z 在 L3 算完才進 row（不是丟原始週K 讓 L4 自己算）

    1. **L4 不該 import L2。** 只帶原始週K 的話,畫圖端就得自己呼叫
       `dividend_station.week_ma_series` / `bollinger_z_series` —— 那是 L4 反過來抓
       L2 的計算核心（§8.2 分層）。而「編排 L1 取數 + 呼叫 L2 純函式」正是本層
       （L3）檔頭寫明的職責,序列版兩支函式就是為此在 L2 備好的。
    2. **同一把尺。** 圖上的均線 / z 與 235 燈用的是**同一組 L2 函式**（序列版與純量版
       已在 L2 逐點對帳）。若讓畫面端另算一份,遲早會出現「線說沒破季線、燈說破了」。
    3. 成本可忽略:每檔一次 rolling（實測 <1 ms）,且只在**抓取那一次**算;
       擺到 L4 反而是每次 rerun 重算。

    ## 缺值語意（§1:不靜默丟一條空序列讓畫面畫出一張空圖）

    - `unavailable` 非空 → 整組沒有序列,`miss_reason` 帶該 `MISS_*`,各序列為**空
      Series**。呼叫端（個股列 / 抓取失敗列）負責挑常數,見 `build_station_rows`。
    - 有週K → `miss_reason=""`,但**逐條線**仍可能畫不出來,分別記在 `ma_miss` /
      `boll_z_miss`:
        - 週數 < 該線視窗（例:僅 30 週 → 畫不出 52 週年線）→ `MISS_NOT_ENOUGH`
          （對齊 `dividend_station.health_c` 對「週數不足」用的同一個常數）。
        - 週數夠、整條卻仍無有限值 → **看週收本身有沒有在動**:
            · 整段零波動（std≈0,布林 z 分母被遮成 NaN）→ `MISS_NO_VARIATION`
            · 否則（週收本身大量缺值,連均線都算不出來）→ `MISS_NO_INPUT`
          ⚠️ **2026-08-27 改**:原本這兩種情形一律標 `MISS_NO_INPUT`,理由寫的是
          「沿用 `light_235` 對布林軸算不出來的既有標法,不另造新詞」。
          **那個理由不成立** —— `MISS_NO_INPUT` 的文案是「上游這輪失敗,**可以重跑
          一次**」,而零波動重跑一百次 std 還是 0,是**錯的指引**（§1:錯的指引比
          沒有指引更糟）。故另立 `MISS_NO_VARIATION`（為什麼既有五個都不能用,
          寫在該常數的 docstring）。
          ⚠️ `light_235` 的 1-B（三軸全掛才標 `MISS_NO_INPUT`）**本次刻意不動**:
          三軸同時掛掉時多半真的是 VIX + 週線都沒抓到,那裡的 `MISS_NO_INPUT` 是對的;
          要逐軸給原因得先把 `Light235.miss_reason` 從單一字串改成 `dict[軸, 原因]`,
          那是 frozen dataclass 的 signature 變更,另案。
      能畫的線**不列進** miss dict —— 列進去會讓消費端以為它也缺（同 `_health_miss`
      只收「⚪ 且有登記原因」的作法）。

    回傳鍵:
      `n_weeks` / `close` / `ma`{週數: Series} / `ma_miss`{週數: MISS_*} /
      `boll_z` / `boll_z_miss` / `boll_period_weeks` / `miss_reason`
    """
    import pandas as pd

    def _empty():
        # 每條線給**各自**的空 Series（不共用同一個物件）—— 共用會讓消費端任何
        # 就地操作串到別條線上,而那種 bug 很難從畫面看出來。
        return pd.Series(dtype="float64")

    _ma_windows = (T.MA_MONTH_WEEKS, T.MA_QUARTER_WEEKS, T.MA_YEAR_WEEKS)  # §3.3 走 L0
    if unavailable or weekly_close is None or len(weekly_close) == 0:
        # ⚠️ 後兩個條件（None / 空）在 ETF 成功列**走不到** —— `assess_holding` 會先
        # 對空週K raise,那一檔改走 `_error_row`。寫在這裡不是宣稱它在擋那條路,
        # 而是本函式同時服務個股列與失敗列（那兩處本來就沒有序列),回傳形狀要一致。
        return {"n_weeks": 0, "close": _empty(),
                "ma": {_w: _empty() for _w in _ma_windows},
                "ma_miss": {_w: (unavailable or SS.MISS_NOT_ENOUGH) for _w in _ma_windows},
                "boll_z": _empty(), "boll_z_miss": unavailable or SS.MISS_NOT_ENOUGH,
                "boll_period_weeks": T.BOLL_PERIOD_WEEKS,
                "miss_reason": unavailable or SS.MISS_NOT_ENOUGH}

    _close = pd.Series(weekly_close, dtype="float64")
    _n = len(_close)
    _ma = {_w: ds.week_ma_series(_close, _w) for _w in _ma_windows}
    _z = ds.bollinger_z_series(_close, T.BOLL_PERIOD_WEEKS)

    # 週收本身的「有沒有在動」—— 供 `_line_miss` 分辨「整段零波動」與「真的沒值」。
    # 判準與 `bollinger_z_series` 的 std≈0 遮罩**同一個常數**（`T.FLOAT_ABS_TOL`），
    # 否則兩邊會出現「圖畫不出來但原因說不是零波動」的縫。
    # ⚠️ 用全序列 std 而不是逐窗檢查是**可以的**:窗是重疊的,每一個窗都 std≈0
    # ⇔ 整條常數。z 全 NaN 且週數夠 → 每個窗都不可用,故全序列判準等價。
    # `abs() < inf` 對 NaN 與 ±inf 皆為 False —— 與 `bollinger_z_series` 的
    # `usable` 遮罩逐字同一種寫法（那裡是 `s.abs() < math.inf`）。
    _finite_close = _close[_close.abs() < float("inf")]
    _flat_close = (len(_finite_close) >= 2
                   and float(_finite_close.std(ddof=0)) <= T.FLOAT_ABS_TOL)

    def _line_miss(series, window: int) -> str:
        """一條線畫不畫得出來 → 原因（畫得出來回 `""`）。判準:**有沒有任何有限值**。

        ## 2026-08-27（§1）：零波動不再標成「可以重跑一次」

        原本這裡只有兩條路:週數不足 → `MISS_NOT_ENOUGH`,否則 → `MISS_NO_INPUT`。
        但**週數夠、整條卻無有限值**在實務上最常見的成因是「整段價格零波動」——
        `bollinger_z_series` 會把 std≈0 的分母遮成 NaN（§4.4 避免 ±inf）,於是 z 整條
        算不出來。對這種情形標 `MISS_NO_INPUT` 等於告訴使用者「上游這輪失敗,
        **可以重跑一次**」—— **重跑一百次 std 還是 0**,那是錯的指引
        （與 CLAUDE.md §-2 實證第 3 條同型:`MISS_*` 選錯 → 給出錯誤的下一步）。

        ⚠️ **不能無條件改標 `MISS_NO_VARIATION`** —— 本函式**同時服務均線與布林 z**:
        均線在「整段平盤」時照樣畫得出來（平盤也是一條線,回 `""`）,它變成全 NaN 的
        成因是**週收本身大量缺值**（`week_ma_series` 用 `min_periods=1` skipna,
        要整個窗全 NaN 才會是 NaN）。那種情形是真的沒有輸入,`MISS_NO_INPUT` 才對。
        故先看週收有沒有在動（`_flat_close`）再決定,不是看是哪一條線。
        """
        if _n < window:
            return SS.MISS_NOT_ENOUGH
        if bool(series.notna().any()):
            return ""
        return SS.MISS_NO_VARIATION if _flat_close else SS.MISS_NO_INPUT

    _ma_miss: dict[int, str] = {}
    for _w in _ma_windows:                    # 只收畫不出來的線（能畫的不列,見 docstring）
        _r = _line_miss(_ma[_w], _w)
        if _r:
            _ma_miss[_w] = _r
    return {"n_weeks": _n, "close": _close, "ma": _ma, "ma_miss": _ma_miss,
            "boll_z": _z, "boll_z_miss": _line_miss(_z, T.BOLL_PERIOD_WEEKS),
            "boll_period_weeks": T.BOLL_PERIOD_WEEKS, "miss_reason": ""}


def _error_row(ticker: str, name: str, asset_class: str, asset_kind: str, reason: str,
               *, held: bool = True) -> dict:
    """單檔抓取/評估整個失敗 → 一列誠實的空白（§1 不炸整表、不捏數字）。

    `健檢` 維持 ⚪（**判燈結果不動**）,但補上 `_miss_reason=MISS_FETCH_FAILED`:
    這一列的 ⚪ 與「某盞燈缺輸入」的 ⚪ 是兩件事 —— 這裡是**整檔**沒有任何數字,
    該看的是本列的錯誤訊息（多半是代號錯或來源掛掉）,不是等時間累積。
    `MISS_FETCH_FAILED` 的定義（「這一檔整批抓取失敗」）就是為這個位置寫的。

    ⚠️ 走勢圖原料（`KEY_WEEKLY_SERIES`）**不跟著 `_miss_reason` 走**:個股列的那張圖
    本來就不存在（見 `build_station_rows` 的說明）,抓取成不成功都一樣。對個股標
    `MISS_FETCH_FAILED` 等於對使用者說「看錯誤訊息、多半是代號或來源問題」——
    修好了圖還是不會出現,那是**錯的指引**。故這一鍵**先看 `asset_kind`**:
    個股 → `MISS_NOT_APPLICABLE`,ETF → `MISS_FETCH_FAILED`。
    這裡刻意**不**走 `most_fundamental_miss`:那支是「同一件事有多個原因時挑最根本的」,
    而依 `MISS_PRIORITY` 它會挑 `MISS_FETCH_FAILED` 勝出 —— 對個股正好挑到錯的那個。
    """
    return {
        "代號": ticker, "名稱": name,
        "種類": "個股" if asset_kind == T.KIND_STOCK else "ETF",
        "類別": _CLASS_ICON.get(asset_class, asset_class),
        "健檢": "⚪", "235 燈號": "—", "加碼金": "", "3-3-3": "—",
        "建議動作": f"⚠️ 資料不足/抓取失敗：{reason}",
        "held": held,   # 換股建議用:持有(Portfolio) vs 觀察(Watchlist)
        "_detail": {"error": reason},
        "_miss_reason": SS.MISS_FETCH_FAILED,
        # 這一列沒有 assessment,但**該類別的每一盞燈都要照樣產出** —— 否則
        # 「N/M 盞可信度」的分母會因為抓取失敗的列整個消失而悄悄變小,畫面反而
        # 顯示可信度更高（§1）。
        # ⚠️ 「都要出現」≠「都進分母」:哪幾格算進分母由消費端
        # `render.station_cards._in_judged_denominator` 統一判（會排除「結構上
        # 不適用」與規格表 `emits_level=False` 的燈,後者即個股 KD）。這裡管的是
        # **不缺席**,不是分母口徑。
        # ⚠️ 原文寫死「N/40 盞」—— 分母是**動態**的（隨持股檔數與 ETF/個股成分變）,
        # 寫死的數字下一次組合變動就變成假話,故不寫數字。
        # 原因與上面 `_miss_reason` 同一個常數,不另寫字面值以免兩邊漂移。
        "_lights": ds.missing_light_cells(asset_kind, reason=SS.MISS_FETCH_FAILED),
        # 走勢圖原料:整檔沒數字 → 空序列 + 原因（§1 不丟空 Series 讓畫面畫空圖）。
        # 個股 vs ETF 挑不同常數的理由見本函式 docstring。
        KEY_WEEKLY_SERIES: _weekly_series_payload(
            None, unavailable=(SS.MISS_NOT_APPLICABLE if asset_kind == T.KIND_STOCK
                               else SS.MISS_FETCH_FAILED)),
    }


def _mark_insufficient(row: dict, *, ak: str, held: bool) -> None:
    """XV-H1-EXT（客戶 2026-10-28 裁示 A：missing ≠ HOLD；unavailable ≠ safe）。就地標記。

    資料不足的兩種情形（只有成立時才加 `SS.KEY_INSUFFICIENT`，資料完整的列逐鍵不變）：
    - `SS.INSUFF_ALL_UNJUDGED`：該列每一盞燈都判不出 —— ETF：健檢四燈皆 ⚪（`健檢` 取最嚴重、
      ⚪ 排最低，⇒ `健檢=="⚪"` 即四燈皆 ⚪）**且**建議分支落在巡航（⇒ 235 無加碼／停利，亦為 ⚪）；
      個股：汰換燈 `健檢=="⚪"`（財報缺或契約漂移）。
    - `SS.INSUFF_NO_PRICE`：持有列缺現價（含現價資料異常被排除，`現價` 為 None）。
    `建議動作` 換成 `SS.INSUFFICIENT_ACTION_TEXT` 的列：既有建議是**持有結論**（ETF 巡航「⚪ 巡航：
    維持定期定額」、個股 🟢「續抱」）、或個股汰換燈 ⚪（財報資料不足，本來就無法判定；原句移到
    `_detail["原建議動作"]` 保留）—— 缺資料不得以「續抱」當替代結論。
    QA 回修 #7：**只有真的被換成 ⬜ 的列**才帶 `SS.KEY_INSUFFICIENT`（才會被列成「無法判定」）；
    可證明的結論（🔴 汰弱、加碼、停利、🟡 留意）一字不動、⛔ 不列入「無法判定」——
    持有且缺現價者改帶 `SS.KEY_PRICE_MISSING_KEPT`（事實句「缺現價（結論不受影響）」）。
    判燈規則與 `_action` 分支代碼不動。
    """
    _is_stock = ak == T.KIND_STOCK
    _hold = (row.get("健檢") == "🟢") if _is_stock else (row.get("_action") == ds.ACTION_CRUISE)
    _unjudged = row.get("健檢") == "⚪" and (_is_stock or row.get("_action") == ds.ACTION_CRUISE)
    # 複驗 C MINOR-1：個股 ⚪ 若是**契約漂移**（grade 不在已知分級，L2 `assess_stock` 明定 ⛔ 不得畫成
    # 「資料不足」）→ 保留 L2 原診斷句「⚪ 財報評等「Z」不在已知分級內（上游契約漂移,請回報）…」，
    # ⛔ 不換成 ⬜；它仍由 L0 `holdings_data_short.row_data_short` 計入組合層資料不足。
    # 只有「沒有輸入」的 ⚪ 才換 ⬜。
    # ⚠️ 揭露：本函式改的是 L3 列的 `建議動作` 文字 —— 舊 UI 存股戰情室（`src/ui/etf/etf_tab_dividend_station`）
    #   與新 UI 共用 `get_station_rows`，故舊 UI 的這一欄同樣會顯示 ⬜ 句。屬 missing ≠ HOLD 之修正，舊 UI 檔未改。
    if _is_stock and _unjudged and row.get("_miss_reason") == SS.MISS_CONTRACT_DRIFT:
        _unjudged = False
    _no_price = held and row.get("現價") is None
    _replace = _unjudged or (_no_price and _hold)
    if _replace:
        row[SS.KEY_INSUFFICIENT] = tuple(
            _r for _r, _on in ((SS.INSUFF_ALL_UNJUDGED, _unjudged), (SS.INSUFF_NO_PRICE, _no_price))
            if _on)
        if not _hold and isinstance(row.get("_detail"), dict):
            row["_detail"]["原建議動作"] = row.get("建議動作", "")
        row["建議動作"] = SS.INSUFFICIENT_ACTION_TEXT
    elif _no_price:
        row[SS.KEY_PRICE_MISSING_KEPT] = True


def build_station_rows(holdings: list[dict], *, vix: float | None,
                       metrics_fn: Callable[[str, str], dict]) -> list[dict]:
    """逐檔評估 → 組表。metrics_fn(ticker, asset_kind) 回一 dict 指標（依賴注入,離線可測）。

    holdings: [{'ticker','name','asset_class','asset_kind'}, ...]
    metrics_fn 依 asset_kind 回不同指標：
    - ETF（定期定額）：weekly_close(必要) + premium_pct/sharpe/total_return_1y_pct/
      annual_yield_pct/inception_years/ann_return_3y_pct/cum_return_3y_pct/peer_ranks（可缺）。
    - 個股（汰換）：mj_grade/mj_score_pct/mj_headline/mj_fail_items（財報體檢）+
      kd_state（KD 狀態 dict）+ current_price（可缺;缺者標資料不足,§1）。

    每一列（ETF / 個股 / 抓取失敗三種都算）**必有** `KEY_WEEKLY_SERIES` 這個非顯示鍵,
    內容是週線走勢圖原料（週收 + 4/13/52 週均線 + 20 週布林 z）。沒有序列的列帶空
    Series + `miss_reason`,**不是把鍵拿掉** —— 見 `_weekly_series_payload` docstring。
    """
    rows: list[dict] = []
    for h in (holdings or []):
        tk = str(h.get("ticker", "") or "").strip()
        nm = str(h.get("name", "") or "")
        ac = h.get("asset_class", T.ASSET_CORE)
        # ⚠️ **走 L0 白名單,不是 `or`、更不是 `get(key, default)`**
        # (2026-08-26 user 核准)。規則本體與完整理由在
        # `shared/dividend_station_thresholds.normalize_asset_kind` 的 docstring:
        # 值不在 `(KIND_ETF, KIND_STOCK)` 之內一律回頭走代號規則重判,
        # falsy(`None` / `""`)與 truthy 髒值(`"ETF"` 大寫 / `"fund"` /
        # `"unknown"`)都攔。
        # 一句話版的後果:漏出第三種值 → `assess_holding` 判 `_is_etf=False` →
        # 4 盞燈標 `MISS_NOT_APPLICABLE` → 被 `_in_judged_denominator`
        # **移出分母** → 可信度**虛高到滿分並打開巡航 gate**
        # (實測同一檔 0050:'etf' 是 7/8=88% gate 關,'ETF' 是 4/4=100% gate 開)。
        # 規則放 L0 而不是留在這裡,是因為 L5 預覽表
        # (`ui/etf/etf_tab_dividend_station._holding_preview_row`)也要用同一把尺 ——
        # 兩邊各寫一份,同一頁的兩個「種類」欄就會不一致。
        # 守衛:`tests/test_station_layer1.py::TestAssetKindNormalisation`
        # (含「拿掉白名單就轉紅」與「兩支同名 classify 值域不同」兩條)。
        ak = T.normalize_asset_kind(h.get("asset_kind"), tk)   # stock / etf（fetcher 分流 + 適用性）
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
                # 走勢圖原料:個股列**結構上沒有**這張圖 —— `_fetch_stock_metrics`
                # 走 `StockDataLoader.get_combined_data` 只取 現價 + KD,從頭到尾
                # 沒有週K 序列;而週線走勢圖是 235 燈 / 健檢C 的視覺化,個股走
                # `assess_stock`（另一組 4 盞燈）根本不跑那一套。
                # ⚠️ 常數挑 `MISS_NOT_APPLICABLE`,理由是**其餘四個都會給錯的指引**:
                #   NOT_ENOUGH「等時間累積」→ 等一百年也不會有（不是筆數問題）;
                #   NO_INPUT「可以重跑一次」/ FETCH_FAILED「看錯誤訊息」→ 沒有東西
                #   失敗過,重跑一樣沒有;CONTRACT_DRIFT 是「有值但形態不對」,這裡
                #   連值都不該有。只有「這類持股不適用（不是壞掉）」是真的。
                # ⚠️ 這一鍵**一定要在**（不是「沒有就不放」）—— 靠鍵存不存在讓畫面
                # 去猜「沒資料」還是「不適用」,正是 §1 要擋的那種靜默。
                _row[KEY_WEEKLY_SERIES] = _weekly_series_payload(
                    None, unavailable=SS.MISS_NOT_APPLICABLE)
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
                # 走勢圖原料:序列本來就在手上（`weekly_closes` 這一步算完就被丟掉）,
                # 這裡只是把它帶進 row —— **零新增外部抓取**。均線 / 布林 z 一起在
                # 這層算完,理由見 `_weekly_series_payload` docstring（L4 不 import L2 +
                # 與 235 燈同一把尺）。判燈邏輯一個字都沒動。
                _row[KEY_WEEKLY_SERIES] = _weekly_series_payload(m["weekly_close"])
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
            # 批 Z49（客戶 2026-10-13 裁示 B）：NaN／±inf／轉不成數字 ＝ 資料異常 —— 該值**不參與
            # 計算**（⛔ 不換成 0／前值／任何替代值），並在列上標出是哪幾項（`SS.KEY_INVALID_INPUTS`，
            # 只有異常時才有這一鍵）。修前：`inf` 通過下面的 `> 0` 擋關 → 市值／損益% 變 inf；
            # 轉不成數字則整列落進 except 被講成「整批抓取失敗」。
            _invalid = tuple(_item for _item, _v in ((SS.ITEM_LOTS, _lots),
                                                     (SS.ITEM_AVG_PRICE, _avg),
                                                     (SS.ITEM_PRICE, _cur))
                             if SS.is_invalid_number(_v))
            if _invalid:
                print(f"[dividend_station] {tk} 資料異常（{'、'.join(_invalid)}）→ 不參與計算")
                _row[SS.KEY_INVALID_INPUTS] = _invalid
                _lots = None if SS.ITEM_LOTS in _invalid else _lots
                _avg = None if SS.ITEM_AVG_PRICE in _invalid else _avg
                _cur = None if SS.ITEM_PRICE in _invalid else _cur
            _row["市值"] = (float(_lots) * float(_cur)
                            if _lots and _cur and float(_lots) > 0 and float(_cur) > 0 else None)
            _row["損益%"] = (round((float(_cur) / float(_avg) - 1.0) * 100.0, 1)
                             if _avg and _cur and float(_avg) > 0 and float(_cur) > 0 else None)
            # 績效原值(供 UI 顯示張數/均價/現價;§1 缺 → None 不捏 0)。市值/損益% 上面已存。
            _row["張數"] = float(_lots) if _lots and float(_lots) > 0 else None
            _row["均價"] = float(_avg) if _avg and float(_avg) > 0 else None
            _row["現價"] = float(_cur) if _cur and float(_cur) > 0 else None
            # XV-ASOF：價格時間＋來源（非顯示鍵，加性；💼 ① E17 位置讀它）。過期價照樣計入上面兩個數字。
            for _k in PAL.PRICE_ASOF_KEYS:
                _row[_k] = m.get(_k)
            if held and not FXG.is_confirmed_twd_ticker(tk):
                # XV-H3（客戶 2026-10-28 裁示 A）：幣別未確認（外幣／看不出來）→ 不得與 TWD 加總；
                # 成本幣別未定義 ⇒ 損益% 亦不可判定。市值／損益% 一律 None（⛔ 不換算、不猜匯率）。
                _row[FXG.KEY_FX_UNCONFIRMED] = True
                _row["市值"] = None
                _row["損益%"] = None
            _mark_insufficient(_row, ak=ak, held=held)
            if (_row.get(FXG.KEY_FX_UNCONFIRMED) and ak == T.KIND_STOCK
                    and not _row.get(SS.KEY_INSUFFICIENT) and _row.get("健檢") == "🟢"):
                # DEC-102(3)（客戶 2026-10-28，XV-FX-ROW-ACTION＝同意）：外幣個股 🟢 續抱結論可證明 → 保留原句，
                #   同列加註停利判不了（損益% 已因幣別未定義為 None）；⛔ 不換成 ⬜。台股列不經此分支、逐字不變。
                _row["建議動作"] = f"{_row.get('建議動作', '')}　{FXG.fx_take_profit_note(tk)}"
            rows.append(_row)
        except Exception as e:  # noqa: BLE001 — 單檔失敗不炸整表（§1 誠實標記）
            rows.append(_error_row(tk, nm, ac, ak, f"{type(e).__name__}: {e}", held=held))
    return rows


# ── 真實抓取（部署端網路才跑得到；沙箱代理擋 TW/yfinance）────────────────
def fetch_vix(*, strict: bool = False) -> float | None:
    """最新 VIX（^VIX 收盤）。抓不到 → None（§1 不猜,235 該條件不觸發）。

    D1(v19.198):改走 `macro_core.fetch_yf_close`（全站唯一 Yahoo 抓取點 —— NAS proxy +
    module-level cache）。原本直呼 yfinance 繞過此點 → 雲端節點 IP 常被 429 靜默降級,
    且同 process 同日 ^VIX 被抓兩次不共享（§2.4）。range_="6mo" 對齊 risk_radar 同源快取。

    `None` **只有一個意思：抓不到**（2026-09-26 批次 5 查證）。它**不**代表休市／假日／
    還沒去要 —— `fetch_yf_close` 底層固定抓 2 年、切 6 個月，休市日照樣拿得到最後一根收盤；
    「還沒去要」由呼叫端自己的 gate 管（本函式被呼叫就是要了）。`fetch_yf_close` 的契約是
    **一切抓取失敗都回空 Series、不拋**（proxy 失敗／429／JSON 壞皆然）→ 那一種在這裡變成 `None`。

    strict（v2「💼 我的持股」VIX 卡用；預設 False = 既有行為一字不變）：
      True → **例外不吞**，原樣往上拋（不印本檔那行 log）；`None` 的語意同上（抓不到）。
      會穿過來的例外依上段契約**不是**「抓不到」，而是程式／部署層的錯（如 late import
      失敗）—— 併成 `None` 會讓畫面把它講成「上游這輪失敗、重跑一次」，那是錯的指引。
      既有 caller（`get_station_rows` → v1 ETF 戰情室分頁／每日推播腳本／v2 戰情表）
      不傳 strict，行為不變（同 `get_switch_in_candidates(strict=)` 的作法，PR #693）。
    """
    if strict:
        return _latest_vix_close()
    try:
        return _latest_vix_close()
    except Exception as _e:  # noqa: BLE001
        print(f"[dividend_station] VIX 抓取失敗: {type(_e).__name__}: {_e}")
    return None


def _latest_vix_close() -> float | None:
    """`fetch_vix()` 的本體（**不吞例外**）。上游沒回任何可用收盤 → `None`。"""
    from src.data.macro.macro_core import fetch_yf_close
    _s = fetch_yf_close("^VIX", range_="6mo")
    if _s is not None and len(_s):
        import pandas as pd
        _v = pd.Series(_s).dropna()
        if len(_v):
            return float(_v.iloc[-1])
    return None


def _price_asof_fields(as_of, src, *, ffilled_last: bool = False,
                       ffilled_from=None) -> dict:
    """XV-ASOF（客戶 2026-10-28 確認線框 Q1～Q3＝A，DEC-102）：價格的時間＋來源 → 非顯示鍵。

    **加性**：只多出 `PAL.PRICE_ASOF_KEYS` 這幾個鍵，`current_price` 與所有數字一個字都沒動；
    過期價**照樣**計入市值／損益（是否排除未裁示，本函式只標示）。
    stale 判定：L0 `PAL.assess_price_freshness`（`expected_latest_trading_day()` ＋ freshness SSOT
    `DAILY_MAX_LAG_TRADING_DAYS`），⛔ 本檔不寫任何天數。
    「今天」＝台北當日（L3 `trading_calendar_service.taipei_today`，⛔ 不用伺服器本地時區）。
    """
    from src.services.trading_calendar_service import taipei_today
    _as_of = _coerce_plain_date(as_of)
    _stale, _exp, _lag = PAL.assess_price_freshness(_as_of, today=taipei_today())
    _src = str(src) if src and str(src) in PAL.SOURCE_DISPLAY else None
    return {PAL.KEY_PRICE_AS_OF: _as_of,
            PAL.KEY_PRICE_SRC: _src,
            PAL.KEY_IS_STALE: _stale,
            PAL.KEY_IS_FALLBACK: PAL.is_fallback_source(_src),
            PAL.KEY_FFILLED_LAST: bool(ffilled_last),
            PAL.KEY_FFILLED_FROM: _coerce_plain_date(ffilled_from),
            PAL.KEY_PRICE_EXPECTED_DAY: _exp,
            PAL.KEY_PRICE_LAG_DAYS: _lag}


#: 拿不到價格時的非顯示鍵（全部 None／False；⛔ 不用今天代替）。
_PRICE_ASOF_EMPTY: dict = {PAL.KEY_PRICE_AS_OF: None, PAL.KEY_PRICE_SRC: None,
                           PAL.KEY_IS_STALE: None, PAL.KEY_IS_FALLBACK: None,
                           PAL.KEY_FFILLED_LAST: False, PAL.KEY_FFILLED_FROM: None,
                           PAL.KEY_PRICE_EXPECTED_DAY: None, PAL.KEY_PRICE_LAG_DAYS: None}


def _fetch_stock_metrics(ticker: str, *, failed: dict | None = None) -> dict:
    """個股汰換指標：財報體檢(no-AI grade) + KD 狀態 + 現價（供市值/損益%）。

    §1 best-effort：日線/KD、財報、名稱三者各自獨立 try,任一失敗只 log + 標資料不足,
    **不 raise、不炸整表**。財報走 L1 `fetch_financial_statements` → L3 no-AI
    `analyze_financial_health` + `no_ai_overall_verdict`；KD 走日 OHLC → L2
    `analyze_kd_state` + `kd_cross_state`。⚠️ 需部署端網路（沙箱代理擋 TW/FinMind）。

    failed：見 `fetch_metrics` 的同名參數（None ＝ 既有行為一字不變，回傳 dict 也一樣）。
    """
    code = str(ticker or "").strip().upper()
    for _suf in (".TWO", ".TW"):
        if code.endswith(_suf):
            code = code[:-len(_suf)]
            break

    m: dict = {"mj_grade": None, "mj_score_pct": None, "mj_headline": "",
               "mj_fail_items": [], "kd_state": None, "current_price": None, "name": "",
               "trend_verdict": None, **_PRICE_ASOF_EMPTY}

    # 1) 日 OHLC → KD。B1(v19.198):改走 StockDataLoader.get_combined_data(個股專屬 4 源鏈
    #    yfinance→FinMind→.TWO,與個股單/多檔頁同源),取代原 fetch_etf_price(ETF 抓價函式:
    #    Yahoo 單源、無 FinMind fallback → 雲端 IP 被擋就整列 error)。回小寫 OHLC df,直接餵 KD。
    try:
        from src.data.core.data_loader import StockDataLoader
        # failed 模式：暫時性失敗照樣拋（strict）—— 否則它與「查無資料」同形，分不開。
        _df_stk, _err_stk, _ = (
            StockDataLoader().get_combined_data(code, 360, True) if failed is None
            else StockDataLoader().get_combined_data(code, 360, True, strict=True))
        if (_df_stk is not None and not getattr(_df_stk, "empty", True)
                and {"close", "high", "low"}.issubset(_df_stk.columns)):
            _ohlc = _df_stk[["close", "high", "low"]].dropna()
            if len(_ohlc):
                m["current_price"] = float(_ohlc["close"].iloc[-1])
                # XV-ASOF：同一根 K 的日期 ＋ L1 寫在 attrs 的實際成功那一腿（加性，不改現價）。
                #   ⚠️ 讀 `_df_stk` 原表（`_ohlc` 是子集，同 index），⛔ 不另抓一次。
                if "date" in _df_stk.columns:
                    try:
                        m.update(_price_asof_fields(
                            _df_stk.loc[_ohlc.index[-1], "date"],
                            getattr(_df_stk, "attrs", {}).get("price_src")))
                    except Exception as _e_asof:  # noqa: BLE001 — 時間來源算不出 → 照舊 None（不擋現價）
                        print(f"[dividend_station] {ticker} 價格時間來源判定失敗: "
                              f"{type(_e_asof).__name__}: {_e_asof}")
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
        if failed is not None and m["current_price"] is None:   # 現價已到手＝只有 KD 壞
            failed[FAILED_PRICE] = f"{type(_e).__name__}: {_e}"

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
        _fs_failed: dict = {}
        _fin = (fetch_financial_statements(code, _tok) if failed is None
                else fetch_financial_statements(code, _tok, failed=_fs_failed))
        if _fs_failed and failed is not None:
            # 三張表任一沒拿到 FinMind 成功回應 → 體檢分數（整張或少評幾項）都不可信。
            failed[FAILED_STATEMENTS] = "；".join(str(_v) for _v in _fs_failed.values())
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
        if failed is not None:
            failed[FAILED_STATEMENTS] = f"{type(_e).__name__}: {_e}"

    # 3) 名稱（get_stock_name 查無回代號本身 → 視為未知留空）
    try:
        from src.config.stock_names import get_stock_name
        _nm = str(get_stock_name(code) or "").strip()
        if _nm and _nm != code:
            m["name"] = _nm
    except Exception as _e:  # noqa: BLE001
        print(f"[dividend_station] {ticker} 名稱抓取失敗: {type(_e).__name__}")

    return m


#: `fetch_metrics(..., failed=)` 寫入的鍵（哪一腿抓取失敗）。**只有失敗才寫。**
FAILED_PRICE = "price"            # 個股：日線（現價）那一腿
FAILED_STATEMENTS = "statements"  # 個股：財報體檢那一腿（三張表任一沒拿到 / 例外）
FAILED_DIVIDEND = "dividend"      # ETF：配息序列
FAILED_PREMIUM = "premium"        # ETF：折溢價那一腿拋例外
FAILED_PEER = "peer"              # ETF：同儕排名


def fetch_metrics(ticker: str, asset_kind: str = T.KIND_ETF, *,
                  failed: dict | None = None) -> dict:
    """逐檔抓 L2 所需指標（best-effort;缺的回 None → 該項標資料不足）。

    日線走 L1 `fetch_etf_price`（proxy-aware、auto_adjust；**本質是 yfinance 歷史,個股
    2330.TW 亦適用**）→ 週K + 報酬 + 夏普 + 成立年；配息走 `fetch_etf_dividends`→ 年化
    配息率（個股亦可）。折溢價 `fetch_etf_nav_history` **僅 ETF**（個股無 iNAV,跳過）。
    ⚠️ 需部署端網路（沙箱代理擋）。日線為必要,無則 raise（該列標抓取失敗,§1 誠實不假裝）。
    同儕排名（3-3-3 ③）Phase 2 未接 → peer_ranks=None。
    **個股（asset_kind=stock）改走 `_fetch_stock_metrics`（財報體檢 + KD）,不套 235/3-3-3。**

    failed（v2「🔬 查一檔」用；預設 None ＝ 既有行為一字不變，回傳 dict 也一樣）：
      傳一個 dict 進來 → **抓取失敗**的那幾腿以 `FAILED_*` 為鍵寫進去（值＝失敗說明）；
      **真的沒有**（沒配過息、沒有 iNAV、同儕不足、查無資料）不寫。回傳值不變 ——
      否則「抓不到」與「沒有」在回傳值裡長得一模一樣（都是 None），呼叫端分不開。
      ⚠️ 折溢價：本層的例外，以及 `calc_premium_discount` 自己吞掉的例外（Q5-r2 起由
      L2 `failed=` 回報）才寫；「所有路徑都沒給」本層分不開，照舊不寫。
    """
    if asset_kind == T.KIND_STOCK:
        return (_fetch_stock_metrics(ticker) if failed is None
                else _fetch_stock_metrics(ticker, failed=failed))

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
    # XV-ASOF：ETF 固定 Yahoo 還原那一腿（`fetch_etf_price`，auto_adjust=True）；
    #   最後一根是否為 L1 `df.ffill()` 補出來的，讀 L1 既有 attrs（批 Z48），⛔ 不另判。
    m.update(_PRICE_ASOF_EMPTY)
    try:
        from src.data.etf.etf_fetch import PRICE_CLOSE_FFILLED_ATTR
        _ff = set(getattr(_px, "attrs", {}).get(PRICE_CLOSE_FFILLED_ATTR) or ())
        _last = _close.index[-1]
        _last_s = pd.Timestamp(_last).strftime("%Y-%m-%d")
        _ff_last = _last_s in _ff
        _ff_from = None
        if _ff_last:
            _orig = [_i for _i in _close.index
                     if pd.Timestamp(_i).strftime("%Y-%m-%d") not in _ff and _i < _last]
            _ff_from = _orig[-1] if _orig else None
        m.update(_price_asof_fields(_last, PAL.SRC_YAHOO_ADJ,
                                    ffilled_last=_ff_last, ffilled_from=_ff_from))
    except Exception as _e_asof:  # noqa: BLE001 — 時間來源算不出 → 照舊 None（不擋現價）
        print(f"[dividend_station] {ticker} 價格時間來源判定失敗: {type(_e_asof).__name__}: {_e_asof}")

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
        _div_raw = fetch_etf_dividends(_yf)
        if failed is not None:
            from src.data.etf.etf_fetch import DIVIDENDS_FETCH_FAILED_ATTR
            _div_fail = getattr(_div_raw, "attrs", {}).get(DIVIDENDS_FETCH_FAILED_ATTR)
            if _div_fail:     # L1 的失敗旗標（PR #694）；空序列而無旗標 ＝ 真的沒配息
                failed[FAILED_DIVIDEND] = str(_div_fail)
        _div = pd.Series(_div_raw)
        if len(_div):
            _div.index = pd.to_datetime(_div.index)
            _ttm = float(_div[_div.index >= (_as_of - pd.Timedelta(days=365))].sum())
            m["annual_yield_pct"] = ds.annual_yield_pct(_ttm, _cur)
    except Exception as _e:  # noqa: BLE001 — 配息缺 → 健檢 A 標資料不足,不炸
        print(f"[dividend_station] {ticker} 配息缺: {type(_e).__name__}")
        if failed is not None and m.get("annual_yield_pct") is None:
            failed[FAILED_DIVIDEND] = f"{type(_e).__name__}: {_e}"

    # 3) 折溢價 —— 僅 ETF。A2(v19.198):改走 calc_premium_discount SSOT(官方 iNAV 同日
    #    inner-join + 3 守門員 G1/G2/G3 + sanity 上限),與 ETF 單/多檔頁同源。原本直取
    #    nav_history「折溢價」欄末值,末端 fallback 到 yfinance navPrice 會回「最後已公告淨值」
    #    被硬戳今日 → 假溢價卻觸發健檢D 假🟡(§1 Fail-Loud 破口,即 v18.442 修的 0050 假+5.07%)。
    #    stale_nav / premium_pct=None → **不填** m["premium_pct"] → 健檢D 標「無折溢價資料」不假判。
    if asset_kind == T.KIND_ETF:
        try:
            from src.compute.etf.etf_calc import calc_premium_discount
            from src.data.etf.etf_fetch import fetch_etf_info
            # failed 模式（Q5-r2）：L2 自己的 `except` 吞掉的例外也要接得到 —— 否則它與
            # 「所有路徑都沒給」回的是同一個 dict。L2 只記例外，不記「沒給」（見其 docstring）。
            _pd_failed: dict = {}
            _pd_res = (calc_premium_discount(fetch_etf_info(_yf) or {}, _px, _yf)
                       if failed is None else
                       calc_premium_discount(fetch_etf_info(_yf) or {}, _px, _yf,
                                             failed=_pd_failed))
            if isinstance(_pd_res, dict) and _pd_res.get("premium_pct") is not None:
                m["premium_pct"] = float(_pd_res["premium_pct"])
            elif failed is not None and _pd_failed:
                failed[FAILED_PREMIUM] = "；".join(str(_v) for _v in _pd_failed.values())
        except Exception as _e:  # noqa: BLE001
            print(f"[dividend_station] {ticker} 折溢價缺: {type(_e).__name__}")
            if failed is not None and m.get("premium_pct") is None:
                failed[FAILED_PREMIUM] = f"{type(_e).__name__}: {_e}"

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
    m["peer_ranks"] = ((_fetch_peer_ranks(_yf) if failed is None
                        else _fetch_peer_ranks(_yf, failed=failed))
                       if asset_kind == T.KIND_ETF else None)
    return m


def _fetch_peer_ranks(ticker: str, *, failed: dict | None = None
                      ) -> dict[int, float] | None:
    """接 L2 `compute_etf_peer_ranking` → 3-3-3 kernel 期望的 {月數: 分位(0=最強)}。

    轉換（§4.1 語意對齊）：
    - 交易日視窗 63/126/252 → 月 3/6/12（PEER_WINDOWS_MONTHS）。
    - percentile（0~100，贏過同儕的%，**越高越強**）→ 分位 `(100−percentile)/100`
      （0=最強、1=最弱；kernel 的「前 1/3」= 分位 ≤ 1/3 = percentile ≥ 66.7）。
    §1：`_err`（同儕不足/抓取失敗）或某視窗缺 → 該月不填 → kernel peer_ok 維持不可判定。

    failed（見 `fetch_metrics`）：例外 → 寫 `FAILED_PEER`。頂層 `_err` 只在**同儕本來就有
    ≥ `T.PEER_MIN_GROUP_SIZE` 檔**時才算抓取失敗（L2 的 `_err` 有三種來源：同儕不足門檻 →
    同儕不足（真的沒有）；
    同儕夠但批次價格抓空 → 「yfinance 抓不到價格」；批次處理拋例外 → 例外類名。
    後兩者都是抓取／計算失敗）。以回傳的 `peers` 檔數分，不比對 `_err` 字面。
    """
    try:
        from src.compute.etf.etf_calc import compute_etf_peer_ranking
        _pr = compute_etf_peer_ranking(ticker)
    except Exception as _e:  # noqa: BLE001 — 同儕算不出不擋整檔健檢
        print(f"[dividend_station] {ticker} 同儕排名失敗: {type(_e).__name__}: {_e}")
        if failed is not None:
            failed[FAILED_PEER] = f"{type(_e).__name__}: {_e}"
        return None
    if not isinstance(_pr, dict) or _pr.get("_err"):
        if (failed is not None and isinstance(_pr, dict)
                and len(_pr.get("peers") or ()) >= T.PEER_MIN_GROUP_SIZE):
            failed[FAILED_PEER] = str(_pr.get("_err"))
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
def get_station_macro(*, strict: bool = False) -> dict:
    """取當前總經位階（唯讀,不打 API;§1 讀不到標未評估,不瞎給攻守）。

    session 內走 `allocation_service.get_macro_regime()`（併本 session warroom,是全站
    唯一 regime 橋樑）;退化 `macro_state_locker.get_macro_state()`（只讀 macro_state.json
    快照）。攻守姿態沿用 `position_throttle`（不自創刻度）。回正規化 dict。

    strict（v2「💼 我的持股」總經位階卡用；預設 False = 既有行為一字不變）：
    True → 兩條讀取都走 `strict=True`，退化路徑的例外**不吞** ——「讀壞了」≠「未評估」。
    """
    _state = None
    try:
        from src.services.allocation_service import get_macro_regime
        _state = get_macro_regime(strict=True) if strict else get_macro_regime()
    except Exception:  # noqa: BLE001 — 無 session / 匯入失敗 → 退離線快照
        _state = None
    if not isinstance(_state, dict) or not _state:
        try:
            from src.services.macro_state_locker import get_macro_state
            _state = get_macro_state(strict=True) if strict else get_macro_state()
        except Exception as _e:  # noqa: BLE001 — §1 讀不到當未評估,不炸
            if strict:
                raise
            print(f"[dividend_station] 位階讀取失敗: {type(_e).__name__}: {_e}")
            _state = None
    if not isinstance(_state, dict):
        _state = {}

    from shared.regime_arbiter import SOURCE_UNEVALUATED_BREADTH as _RA_SOURCE_UNEVALUATED_BREADTH
    from shared.regime_arbiter import is_not_loaded_pending_breadth as _is_not_loaded_pending_breadth
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
        # DEC-075 回修（MUST-2，schema-additive）：未評估原因是「缺真實市場廣度」（契約 source 旗標）。
        "breadth_unevaluated": _state.get("source") == _RA_SOURCE_UNEVALUATED_BREADTH,
        # DH-REGIME-NOWARROOM（2026-10-23，PR #910，schema-additive）：總經尚未載入且代理廣度不計分
        #   （`shared.regime_arbiter.is_not_loaded_pending_breadth`，契約旗標 ＋ 呼叫當下的 L0 旗標）—— 只選文案。
        "not_loaded_pending_breadth": _is_not_loaded_pending_breadth(_state),
    }


def get_switch_in_candidates(*, regime: str | None = None,
                             exclude: list[str] | None = None,
                             top_n: int = 5,
                             strict: bool = False) -> list[dict]:
    """換入候選 ← 選股網「選股池」top（沿用畫面同源 get_ranked_picks,已快取子呼叫）。

    §1：選股網不可用 / 空 → 回 []（caller 顯示「選股池暫無候選」）,不捏造標的。
    exclude：已持有代號（不建議換入自己已有的）。regime 傳給選股網套空頭濾網。

    strict（v2「💼 我的持股」換股卡用；預設 False = 既有行為一字不變）：
      True → **取不到 ≠ 0 檔**。存活池讀取例外、或存活池為空（季快照未就緒）一律
      `raise`，不回 [] —— 否則 caller 會把「選股池沒拿到」畫成「這一輪沒有候選」
      （§1 靜默失敗）。存活池有東西、排完 0 檔：非空頭 regime 下只可能是「每一檔都因
      勾選因子資料不足被排除」→ 同樣 raise；空頭 regime 下分不出是濾網剔光還是缺資料
      → 回 []（見 `_ranked_picks_strict`）。
      ⚠️ `get_ranked_picks` 自抓存活池時會吞例外、回空表 + note，0 列因此分不出兩者；
      故 strict 模式**自己先抓存活池**再傳進去（`survivors_df=`），例外照常往上拋。
      既有 caller（v1 ETF 戰情室分頁 / 每日推播腳本）不傳 strict，行為不變。
    """
    # §後綴 SSOT:exclude（已持有代號）去 .TW/.TWO 再比對,否則 '2330.TW' 擋不掉 bare '2330'
    # → 已持有卻被推「換入」(稽核 1b)。候選 _code 亦 normalize 後比對。
    _exclude = {T.normalize_ticker(t) for t in (exclude or []) if str(t or "").strip()}
    if strict:
        return _pick_candidates(_ranked_picks_strict(regime=regime, top_n=top_n),
                                _exclude, top_n)
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
    return _pick_candidates(_df, _exclude, top_n)


def _ranked_picks_strict(*, regime: str | None, top_n: int):
    """strict 版取排名：存活池自己抓（例外不吞）；空池 → raise（訊息用排名器自己的 note 原文）。"""
    from src.services.fundamental_screener_service import (
        SCREEN_ANGLE_LABELS, composite_rank_candidates, get_fundamental_survivors,
        get_ranked_picks)
    _factors = list(SCREEN_ANGLE_LABELS.values())     # 全角度,同非 strict 路徑
    _surv, _ = get_fundamental_survivors()
    if _surv is None or getattr(_surv, "empty", True) or "stock_id" not in _surv.columns:
        # 空池的說明由排名器自己給（SSOT，本檔不另寫一句）；空池時它不做任何掃描即返回。
        _, _note = composite_rank_candidates(_surv, factors=_factors)
        raise RuntimeError(_note)
    _df, _note = get_ranked_picks(_factors, top_n=max(top_n * 4, 40), survivors_df=_surv,
                                  regime=regime, auto_fetch=True)
    # 存活池有東西、排完卻 0 檔，只有兩條路（`get_ranked_picks` 的結構，逐步對過）：
    #   (1) 綜合排名 `drop_unscored=True` 把**每一檔**都排除（勾選因子資料不足）→ 缺資料；
    #   (2) 空頭濾網把排名剔光 → 有效結果（濾網只在 regime ∈ THROTTLE_VETO_REGIMES 時動手，
    #       且對空表直接返回，不會把 (1) 蓋掉）。
    # regime **不在**否決集 → 濾網根本沒動 → 只可能是 (1) → raise（訊息用排名器自己的 note）。
    # regime 在否決集 → (1)(2) 從回傳值分不出來（只剩解析 note 散文，那是猜）→ 照舊回 []。
    if (_df is None or getattr(_df, "empty", True)) and not _is_veto_regime(regime):
        raise RuntimeError(_note)
    return _df


def _is_veto_regime(regime) -> bool:
    """同 `fundamental_screener_service._apply_bear_market_filter` 的判定（L0 SSOT 否決集）。"""
    from shared.position_throttle import THROTTLE_VETO_REGIMES
    if isinstance(regime, dict):       # 同上游防呆：誤傳整個 macro-state dict
        regime = regime.get("regime")
    try:
        return regime in THROTTLE_VETO_REGIMES
    except TypeError:
        return False


def _pick_candidates(_df, _exclude: set, top_n: int) -> list[dict]:
    """排名表 → 換入候選（排除已持有、取前 top_n）。空表 → []。"""
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


#: 批 Z51：`SS.KEY_INVALID_LIGHTS` 裡**與換入結論無關**、不得連帶排除換入的燈。
#: 換入篩選只看 `健檢`（A–D 取最嚴重）；235 加碼燈（含 VIX）不參與換入判定 —— VIX 是全市場
#: 同一個值，若連帶排除，一次 VIX 異常就會讓整份觀察清單改由選股池遞補（改了與 235 無關的結論）。
#: 3-3-3 三子項同理：換入規則本來就不看 3-3-3（修前 3-3-3 ❌ 也不擋換入）→ 異常不改變換入結論。
#: （批 Z50 曾一併排除 3-3-3 異常，屬判斷過寬、非客戶核准規則；2026-10-13 總管裁定更正。）
#: 健檢 A–D 會直接決定 `健檢` 欄 → 異常照舊排除（不在本集合）。
#: ⚠️ `_invalid_lights` 本身仍完整保留這些 key（⑦ prompt 的「資料異常未判」要用），只在這裡略過。
_SWITCH_IN_IGNORED_INVALID: frozenset[str] = frozenset({SS.KEY_LIGHT235})
_SWITCH_IN_IGNORED_INVALID |= {SS.KEY_SCREEN_INCEPTION, SS.KEY_SCREEN_RETURN, SS.KEY_SCREEN_PEER}

#: 批 Z53：換出判定是 `健檢 == 🔴`，`健檢` ＝ L2 `_worst_level`（健檢 A–D 取最嚴重）。
#: 四盞裡**只有 A、B 會亮 🔴**（C、D 最多 🟡），而 B 沒有資料異常路徑（L2 不標 `invalid`）
#: ⇒ 會改變換出結論的資料異常只有**健檢 A**：A 判得出來時可能是 🔴，判不出來就不知道該不該換出。
#: C／D 異常只影響 🟡／🟢，不改變換出結論 → 不列（照舊由 ⑦「資料異常未判」揭露）。
#: 標籤沿用 `row_from_assessment()` 寫進 `SS.KEY_INVALID_TEXTS` 的項目名。
_SWITCH_OUT_INVALID_KEYS: frozenset[str] = frozenset({SS.KEY_HEALTH_A})
_SWITCH_OUT_INVALID_LABELS: tuple[str, ...] = ("健檢A",)
#: 批 Z58 更正：上面「B 沒有資料異常路徑」在批 Z53 當時屬實，批 Z58 起**不再成立** ——
#: L2 `health_b` 對 Sharpe NaN／±inf 改判 ⚪ 並標 `invalid`（修前 NaN 亮 🟢、-inf 亮 🔴）。
#: B 會亮 🔴（Sharpe < 0 → 汰弱）⇒ B 判不出來也就判不出要不要換出 → 與 A 同列（接在尾端，A 的既有行不動）。
_SWITCH_OUT_INVALID_KEYS |= {SS.KEY_HEALTH_B}
_SWITCH_OUT_INVALID_LABELS += ("健檢B",)

#: 批 Z58：換入判定是觀察清單列 `健檢 == 🟢`（`健檢` ＝ 健檢 A–D 取最嚴重）。觀察清單列因健檢 A–D
#: 資料異常被排除在換入之外時，只有列上 `健檢` 是 🟢／⚪ 的那幾列**可能**本該是 🟢（補回那盞燈只會
#: 讓等級持平或變嚴重；🔴／🟡 再怎麼補都不會變 🟢）→ 只列這幾列。235／3-3-3 不參與換入（見
#: `_SWITCH_IN_IGNORED_INVALID`）→ 只取健檢 A–D 的客戶句。標籤沿用 `SS.KEY_INVALID_TEXTS` 的項目名。
_SWITCH_IN_INVALID_LABELS: tuple[str, ...] = ("健檢A", "健檢B", "健檢C", "健檢D")


def switch_in_invalid_rows(rows: list[dict]) -> list[dict]:
    """批 Z58：觀察清單列（`held=False`）因健檢資料異常**沒被判過能不能換入**的那幾列（純函式）。

    回 `[{"代號", "項目": ((項目, 客戶句), …)}]`（項目／句子取自列上 `SS.KEY_INVALID_TEXTS`，
    只取健檢 A–D）；沒有 → `[]`。條件與 `build_switch_advice` 換入篩選同一把尺
    （`SS.KEY_INVALID_LIGHTS` 扣掉 `_SWITCH_IN_IGNORED_INVALID` 後非空），再限 `健檢` 為 🟢／⚪
    （理由見 `_SWITCH_IN_INVALID_LABELS`）。整批抓取失敗的列不列（另有出口）。
    ⚠️ 刻意**不**塞進 `build_switch_advice()` 的回傳 —— 那份 dict 也餵舊 UI 與 LINE 推播，
    本函式只給新 UI ④ 卡判「這一輪沒有可換入」是不是有效結論。
    """
    return [
        {"代號": str(r.get("代號", "")),
         "項目": tuple(_t for _t in (r.get(SS.KEY_INVALID_TEXTS) or ())
                       if _t[0] in _SWITCH_IN_INVALID_LABELS)}
        for r in (rows or [])
        if (not r.get("held")) and not r.get("_detail", {}).get("error")
        and (set(r.get(SS.KEY_INVALID_LIGHTS) or ()) - _SWITCH_IN_IGNORED_INVALID)
        and r.get("健檢") in ("🟢", "⚪")]


def build_switch_advice(rows: list[dict], macro: dict | None,
                        candidates: list[dict] | None) -> dict:
    """換股建議（純函式,離線可測,§1 不生標的）。

    - 換出 = **持有(held)** 且 健檢🔴（汰弱）。觀察清單的紅燈不算「換出」（你沒持有）。
    - 換入 = **優先**你親手選進「觀察清單(held=False)」且健檢綠燈的標的（#34）;觀察清單無
      綠燈才 fallback 選股池 candidates（caller 已排除已持有）。總經**轉守(defense)** → 換入
      從嚴（少給幾檔 + stance=defensive）;未評估 → stance=unknown（只給汰弱,不套攻守）。
    - 批 Z50：有燈因**資料異常**不判定的列（`SS.KEY_INVALID_LIGHTS`）**不得**列入換入 ——
      `健檢` 把 ⚪ 排最低，一盞異常加三盞 🟢 仍是 🟢，不能當「綠燈」推薦。缺資料的 ⚪ 照舊。
    - 批 Z51：**235 燈**與 **3-3-3** 的資料異常**不**連帶排除換入 —— 換入規則不看 235／VIX／
      3-3-3，判不出來只讓那盞不下結論（見 `_SWITCH_IN_IGNORED_INVALID`）。健檢 A–D 異常照舊排除。
    - 批 Z53：**持有列**的健檢 A（四盞裡唯一會亮 🔴 且有資料異常路徑的燈；批 Z58 起健檢 B 亦同）因資料異常不判定、
      且該列 `健檢` 不是 🔴 → 那一列**沒被判過要不要換出**（不是「沒有紅燈」）→ 另列在
      `switch_out_invalid`：`[{"代號", "項目": ((項目, 客戶句), …)}]`（項目／句子取自列上
      `SS.KEY_INVALID_TEXTS`，只取健檢 A（批 Z58 起含 B）；理由見 `_SWITCH_OUT_INVALID_KEYS`）。**只有異常時才有這一鍵**
      —— 正常輸出逐鍵不變；`switch_out` 本身不動（🔴 照列）。整批抓取失敗的列不列（另有出口）。
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
                     and not (set(r.get(SS.KEY_INVALID_LIGHTS) or ()) - _SWITCH_IN_IGNORED_INVALID)
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

    _out = {
        "regime": _macro.get("regime"), "loaded": _loaded, "defense": _defense,
        "posture": _macro.get("posture_label"), "posture_range": _macro.get("posture_range"),
        "stance": stance,
        "switch_out": switch_out,   # 持有紅燈 → 建議換出
        "switch_in": switch_in,     # 換入候選（優先觀察清單綠燈,否則選股池）
        "switch_in_src": switch_in_src,   # "watchlist"(你選的) / "screener"(全自動 fallback)
    }
    # 批 Z53：持有列健檢 A（唯一會亮 🔴 且有資料異常路徑的燈；批 Z58 起含 B）資料異常、判不出要不要換出
    # （見 `_SWITCH_OUT_INVALID_KEYS`；只有異常時才有這一鍵）。
    _out_invalid = [
        {"代號": str(r.get("代號", "")),
         "項目": tuple(_t for _t in (r.get(SS.KEY_INVALID_TEXTS) or ())
                       if _t[0] in _SWITCH_OUT_INVALID_LABELS)}
        for r in (rows or [])
        if r.get("held") and r.get("健檢") != "🔴"
        and not r.get("_detail", {}).get("error")
        and set(r.get(SS.KEY_INVALID_LIGHTS) or ()) & _SWITCH_OUT_INVALID_KEYS]
    if _out_invalid:
        _out["switch_out_invalid"] = _out_invalid
    return _out


# ── XV-H3：幣別未確認的持有列（不得與 TWD 加總）────────────────────────────
def fx_excluded_codes(rows: list[dict]) -> list[str]:
    """持有、非整批抓取失敗、且被 `build_station_rows` 標了 `FXG.KEY_FX_UNCONFIRMED` 的列代號（保序去重）。

    XV-H3（客戶 2026-10-28 裁示 A）：只要非空，總市值／未實現損益合計／80/20 一律**不算**
    （⛔ 不把剩餘台股包裝成完整組合）；畫面、LINE、AI 改講 `FXG.FX_PARTIAL_TEXT` ＋ 未納入清單。
    判定只走 L0 `asset_currency_gate.is_confirmed_twd_ticker`（同一把尺，見該檔）。
    """
    return list(dict.fromkeys(
        str(r.get("代號", "")) for r in (rows or [])
        if r.get("held") and not (r.get("_detail") or {}).get("error")
        and r.get(FXG.KEY_FX_UNCONFIRMED)))


# ── 第 1 層結論卡:組合層彙總（純函式,#階段C）────────────────────────────
def compute_portfolio_totals(rows: list[dict]) -> dict | None:
    """組合層的「未實現損益 / 檔數 / 總市值」（純函式,§1 缺就不算）。

    為什麼放 L3 而不是讓 L5 自己乘:L5 的檔頭寫明「只呼叫 L3,不自算」,而這裡要做
    **張 → 股 → 元** 的單位還原（§4.1 量綱陷阱:漏乘 1000 股/張 = 1000 倍低估）。
    把它留在畫面層等於讓同一個乘法散在 UI 各處,而 `_perf_row` 已經有一份
    「÷10 換成萬元」的變形 —— 再加一份就是第三套算式。

    ⚠️ `SHARES_PER_LOT`(1 張 = 1000 股)一律取自 `shared/sector_flow_thresholds`
    —— §3.3 不在這裡寫死 1000。該檔檔頭就是拿「漏乘 = 1000 倍低估」當單位陷阱的
    範例;常數住在 sector_flow 檔內是既有事實,**不是**為了本函式新造一個常數。

    ⚠️ 單位:`row["市值"]` 是 `張數 × 現價`（**張·元**,供 80/20 比例用,不含股數）,
    本函式回的 `value_twd` / `pnl_twd` 是**元**（已乘 `SHARES_PER_LOT`）。
    欄名依 §4.1 命名規範帶單位,呼叫端不必再猜。

    只納入 **held 且張數/均價/現價三者皆有** 的列（`build_station_rows` 缺任一
    就存 None,不捏 0）。部分持股缺金額 → `partial=True`,呼叫端必須把
    `valued_n / held_n` 講出來 —— 否則使用者會把「三檔裡只算了一檔」的損益
    當成整個組合的損益（§1 錯的數字比沒有數字更危險）。

    全無可計價持股 → 回 `None`（畫面顯示「算不出來」,**不顯示 0**）。
    XV-H3（客戶 2026-10-28 裁示 A）：有任何幣別未確認的持有列（`fx_excluded_codes` 非空）→ 回 `None`
    （⛔ 不把剩餘台股的總額當成整個組合；由呼叫端講 `FX_PARTIAL_TEXT`）。
    """
    if fx_excluded_codes(rows):
        return None
    _cost = _value = 0.0
    _held_n = _valued_n = 0
    for r in (rows or []):
        if not r.get("held") or (r.get("_detail") or {}).get("error"):
            continue
        _held_n += 1
        if r.get(SS.KEY_INVALID_INPUTS):
            # 批 Z49：張數／均價／現價任一是異常值 → 整個總額不算（⛔ 不剔除那一檔後照算）。
            return None
        _lots, _avg, _cur = r.get("張數"), r.get("均價"), r.get("現價")
        if not all(isinstance(_v, (int, float)) and _v > 0
                   for _v in (_lots, _avg, _cur)):
            continue
        _valued_n += 1
        _shares = float(_lots) * _UNITS.SHARES_PER_LOT      # 張 → 股（§4.1 SSOT,不寫死 1000）
        _cost += _shares * float(_avg)
        _value += _shares * float(_cur)
    if _valued_n == 0 or _cost <= 0:
        return None
    return {
        "value_twd": _value,
        "cost_twd": _cost,
        "pnl_twd": _value - _cost,
        # 分母是**成本**(不是市值)—— 報酬率的定義如此;_cost>0 已在上面守住。
        "pnl_pct": (_value / _cost - 1.0) * 100.0,
        "held_n": _held_n, "valued_n": _valued_n,
        "partial": _valued_n < _held_n,
    }


# ── 80/20 配置偏離 + 衛星停利（#38；80/20 看市值＝張數×現價，停利看損益%＝均價＋現價；§1 缺就不算）──
def compute_allocation_split(rows: list[dict]) -> dict | None:
    """80/20 實際配置偏離（純函式）。核心=ETF、衛星=個股（郭俊宏:核心配息ETF/衛星成長股,
    以代號類型近似;主題型 ETF 會被算核心,UI 已註記此近似）。

    只納入 **held 且有市值(市值>0)** 的列。§1：部分 held 缺金額 → partial=True(僅供參考);
    全無市值 → None（UI 不顯示、不捏造）。
    XV-H3（客戶 2026-10-28 裁示 A）：有任何幣別未確認的持有列 → None（⛔ 不顯示不完整的比例）。
    """
    if fx_excluded_codes(rows):
        return None
    _core = _sat = 0.0
    _held_n = _valued_n = 0
    for r in (rows or []):
        if not r.get("held") or r.get("_detail", {}).get("error"):
            continue
        _held_n += 1
        if {SS.ITEM_LOTS, SS.ITEM_PRICE} & set(r.get(SS.KEY_INVALID_INPUTS) or ()):
            # 批 Z49：市值的兩個輸入（張數／現價）任一是異常值 → 整個比例不算
            # （⛔ 不剔除那一檔後照算；均價不進市值，只有均價異常時不影響本函式）。
            return None
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
    - reds：健檢 🔴 需汰弱（代號 + 建議動作）—— **持有與觀察清單都算**（舊 UI 計數沿用，結構不動）
    - held_reds：reds 中**持有列**（`held` 為真）那幾筆，結構同 reds。AI prompt 的
      「健檢紅燈需汰弱」行只用這份 —— 觀察清單的 🔴 不得讓 AI 叫客戶賣沒持有的標的（AUD-C3）。
    - adds：235 加碼 —— **持有列**（`held` 為真）且 `建議動作` 走的就是「加碼」那條分支
      （`_action == ds.ACTION_ADD`）。AUD-C3（2026-10-15）：原本只看 `加碼金` 非空
      （＝235 燈 deploy_pct>0），繞過 `suggest_action` 的優先序（汰弱 > 停利 > 趨勢暫停 >
      加碼）→ 同一檔同時被推「建議換出」與「加碼 50%」、每檔「暫停加碼」都被推成加碼，
      且觀察清單（未持有）也被推成加碼。`加碼金` 欄本身（235 燈 deploy_pct）不動。
    - watch_adds：**觀察清單（未持有）**列中、`建議動作` 同樣走「加碼」分支者
      → [{"代號", "燈號"}]（燈號＝235 燈 emoji，供 UI；推播與 prompt 只輸出代號。
      不帶含「加碼」字樣的燈號名稱、不帶加碼金）。
      分開放，避免未持有標的被描述成持股加碼操作；不計入「今日要動作」。
    - errors：抓取失敗未納入判斷的代號（§1 誠實排除,不當作「無事」）
    - allocation：80/20 實際配置偏離（只納入市值＝張數×現價 > 0 的持有列;全無市值 → None,#38）
    - take_profit：衛星獲利達 15% 嚴格停利清單（有損益%才判;#38）
    - invalid（批 Z51，**只有異常時才有這一鍵**）：有燈因資料異常不判定的列
      （`SS.KEY_INVALID_TEXTS`）→ [{"代號", "項目": ((項目, 客戶句), …)}]。正常時 digest 逐鍵不變。
      批 Z52：**持有列**的持股輸入異常（`SS.KEY_INVALID_INPUTS`，批 Z49 的張數／均價／現價）
      同樣列入（項目＝`SS.ITEM_*`、句子＝`SS.invalid_data_text(項目)`，接在該列燈的項目之後）——
      張數／現價壞 → 配置那一行不寫；衛星均價／現價壞 → 停利判不出，兩者都是「判不出來」不是「沒事」。
      觀察清單列不列（這三個值只進 `allocation`／`take_profit`，兩者都只看持有列）。
    """
    reds: list[dict] = []
    held_reds: list[dict] = []
    adds: list[dict] = []
    watch_adds: list[dict] = []
    errors: list[str] = []
    drift: list[str] = []
    valid = 0
    for r in (rows or []):
        if r.get("_detail", {}).get("error"):
            errors.append(str(r.get("代號", "")))
            continue
        if HDS.is_contract_drift(r):
            # 複驗 C 第二輪 MINOR-A：契約漂移列判不出 ⇒ ⛔ 不算進「有效判斷檔數」，另列事實。
            drift.append(str(r.get("代號", "")))
            continue
        valid += 1
        if r.get("健檢") == "🔴":
            reds.append({"代號": str(r.get("代號", "")),
                         "建議動作": str(r.get("建議動作", ""))})
            if r.get("held"):           # 持有判法同 `build_switch_advice`
                held_reds.append(reds[-1])
        if r.get("_action") == ds.ACTION_ADD:
            # 持有 / 觀察的判法同 `build_switch_advice`（`r.get("held")` 為真＝持有，
            # 否則＝觀察清單）—— 換出段與加碼段對同一列不會一邊算持有、一邊算觀察。
            if r.get("held"):
                adds.append({"代號": str(r.get("代號", "")),
                             "235": str(r.get("235 燈號", "")),
                             "加碼金": str(r.get("加碼金", ""))})
            else:
                # 觀察清單只帶燈號 emoji：`235 燈號` 欄＝`f"{icon} {label}"`（見
                # `row_from_assessment`），label 本身含「加碼」字樣（「急跌加碼」…），
                # 未持有的標的不得被讀成加碼指令 → 只取空白前的 icon，不帶 label、不帶加碼金。
                watch_adds.append({"代號": str(r.get("代號", "")),
                                   "燈號": str(r.get("235 燈號", "") or "").split(" ", 1)[0]})
    _out = {"total": valid, "vix": vix, "reds": reds, "held_reds": held_reds, "adds": adds,
            "watch_adds": watch_adds, "errors": errors,
            "allocation": compute_allocation_split(rows),
            "take_profit": flag_take_profit(rows)}

    def _bad_inputs(r: dict) -> tuple:
        # 批 Z52：持有列被 L3 標了異常的持股輸入（張數 → 均價 → 現價，L3 固定順序）。
        return tuple(r.get(SS.KEY_INVALID_INPUTS) or ()) if r.get("held") else ()

    _invalid_rows = [{"代號": str(r.get("代號", "")),
                      "項目": tuple(r.get(SS.KEY_INVALID_TEXTS) or ())
                      + tuple((_i, SS.invalid_data_text(_i)) for _i in _bad_inputs(r))}
                     for r in (rows or [])
                     if not r.get("_detail", {}).get("error")
                     and (r.get(SS.KEY_INVALID_TEXTS) or _bad_inputs(r))]
    if _invalid_rows:
        _out["invalid"] = _invalid_rows
    # XV-H1-EXT（客戶 2026-10-28 裁示 A）：資料不足的列（`SS.KEY_INSUFFICIENT`，燈全判不出／
    # 持有列缺現價）→ 列出代號與原因（**只有非空時才有這一鍵**，資料完整時 digest 逐鍵不變）。
    # 下游（⑦ prompt、LINE 正文）據此不給「續抱」類組合層結論。抓取失敗列另在 errors。
    # QA 回修 #11：每筆標明持有／觀察清單（`held`）。#7：只收建議動作真的被換成 ⬜ 的列。
    _insufficient = [{"代號": str(r.get("代號", "")), "原因": tuple(r.get(SS.KEY_INSUFFICIENT) or ()),
                      "held": bool(r.get("held"))}
                     for r in (rows or [])
                     if not r.get("_detail", {}).get("error") and r.get(SS.KEY_INSUFFICIENT)]
    if _insufficient:
        _out["insufficient"] = _insufficient
    # QA 回修 #7：持有列缺現價、但結論可證明（未換成 ⬜）→ 另列事實（只有非空才有這一鍵）。
    _kept = [str(r.get("代號", "")) for r in (rows or [])
             if not r.get("_detail", {}).get("error") and r.get(SS.KEY_PRICE_MISSING_KEPT)]
    if _kept:
        _out["price_missing_kept"] = _kept
        # 複驗 C MINOR-2：其中的衛星（個股）—— 停利判不了（只有非空才有這一鍵）。
        _kept_sat = [str(r.get("代號", "")) for r in (rows or [])
                     if not r.get("_detail", {}).get("error") and r.get(SS.KEY_PRICE_MISSING_KEPT)
                     and r.get("種類") == "個股"]
        if _kept_sat:
            _out["price_missing_kept_satellite"] = _kept_sat
    # XV-H3：幣別未確認、未納入總額／比例的持有列（只有非空才有這一鍵；`allocation` 此時為 None）。
    _fx = fx_excluded_codes(rows)
    if _fx:
        _out["fx_excluded"] = _fx
    # 複驗 C MAJOR-1/2：組合層「資料不足」的單一判定（L0 `holdings_data_short.row_data_short`）
    # → 代號清單（只有非空才有這一鍵）。⑦ prompt 與 LINE 一律以 `digest_data_short()` 讀它。
    _short = list(dict.fromkeys(str(r.get("代號", "")) for r in (rows or []) if HDS.row_data_short(r)))
    if _short:
        _out["data_short"] = _short
    if drift:                          # 複驗 C 第二輪 MINOR-A（只有非空才有這一鍵）
        _out["contract_drift"] = drift
    return _out


#: XV-H1-EXT：資料不足（抓取失敗／燈全判不出／缺現價／無有效判斷檔）時取代「續抱」引導句。
_INSUFFICIENT_INSTRUCTION: str = (
    "有標的資料不足或抓取失敗,列在『資料不足／無法判定』的標的請寫『資料不足／無法判定』,"
    "其餘已列出的結論照原樣講,不得給組合層『全部續抱』類總結,也不得自行補上缺少的資料。")


def build_summary_prompt(digest: dict, switch: dict | None = None) -> str:
    """digest(+換股建議) → LLM prompt（純字串,數字全來自 digest/switch；AI 僅潤稿,§1/T5）。

    switch=build_switch_advice() 的 dict（可選）；帶入時 AI 摘要會含「當前位階 → 換股建議」。
    """
    _vix = digest.get("vix")
    _vix_txt = f"{_vix:.1f}" if isinstance(_vix, (int, float)) else "抓取失敗"
    if SS.is_invalid_number(_vix):
        # 批 Z51：VIX 是 NaN／±inf／轉不成數字 → 不把 nan／inf 送進 ⑦ prompt，改客戶句（None 照舊）。
        _vix_txt = SS.invalid_data_text("VIX")
    # AUD-C3：只列持股的 🔴（`held_reds`）；觀察清單的紅燈不是「需汰弱」。
    _reds = "、".join(f"{d['代號']}（{d['建議動作']}）"
                      for d in digest.get("held_reds", [])) or "無"
    _adds = "、".join(f"{d['代號']} {d['235']} 加碼{d['加碼金']}"
                      for d in digest.get("adds", [])) or "無"
    _errs = "、".join(digest.get("errors", [])) or "無"
    # AUD-C3：觀察清單（未持有）的 235 燈號另起一行（只有非空時才有這行，原 prompt 逐字不變）；
    # 只列代號（不寫「加碼 N%」、不帶含「加碼」的燈號名稱、不帶燈號 emoji —— 燈三 🔴 易被讀成
    # 汰弱紅燈）—— 未持有的標的不是持股加碼操作。
    _watch = digest.get("watch_adds") or []
    # 批 Z51：有燈因資料異常不判定 → 附一行事實（客戶句組成），且**不送**「續抱」那句指示 ——
    # 「235 加碼觸發：無」在這時是「判不出來」不是「沒觸發」，引導 AI 說續抱等於替它下結論。
    _inv = digest.get("invalid") or []
    # xview V1：有效判斷檔數 0（每檔抓取全失敗／total 缺或非數）→ 也**不送**「續抱」那句 ——
    # 比照 LINE 正文 `format_holdings_message` 既有 `total<=0` 防線（稽核🔴A）：零資料不給安心結論。
    # ~~只看 total；部分失敗／燈全 ⚪／無現價**不在**此列（客戶 Z51/Z52 範圍，既有測試釘住）。~~
    # ↑ 2026-10-28 客戶裁示 XV-H1-EXT 取代（有意識的變更，⛔ 不是漏刪）：三者現在也不放續抱句，見下。
    # QA 回修：total 須為**有限值且 ≥1** 才算有判斷（inf／NaN／0.5 → 不可判斷；與 LINE 正文 `int()` 後 `<=0` 同向）。
    _tot = digest.get("total")
    _no_judged = not (isinstance(_tot, numbers.Real) and not isinstance(_tot, bool)
                      and math.isfinite(_tot) and _tot >= 1)
    # XV-H1-EXT（客戶 2026-10-28 裁示 A，取代 Z51/Z52 對「部分失敗／燈全判不出／缺現價仍帶續抱」的語意）：
    # 「續抱」那句只在 total 有限且 ≥1、**無**抓取失敗、**無**燈全判不出、**無**缺現價時才放；
    # 否則改放一句明確指示（資料不足者寫「資料不足／無法判定」、不得給組合層「全部續抱」類總結、
    # 不得補資料）。只有 Z51/Z52 資料異常（`invalid`）時維持修前作法（兩句都不放）。
    _ins = digest.get("insufficient") or []
    _kept = digest.get("price_missing_kept") or []
    # 複驗 C MAJOR-1/2：與 ①／LINE 同一份判定（L0 `holdings_data_short.digest_data_short`）。
    _short = HDS.digest_data_short(digest)
    _guide = (_INSUFFICIENT_INSTRUCTION if _short
              else "" if _inv else "沒有紅燈也沒有加碼時,請明講『續抱、定期定額即可』。")
    _base = (
        "你是台股『存股戰情室』的推播助理。根據以下今日持股健檢結果,用繁體中文寫 3~6 句的推播摘要,"
        "聚焦『今天要不要動作』。只能引用下列數據,嚴禁自行杜撰任何代號、數字或未列出的結論;"
        + _guide + "\n"
        f"- 目前 VIX：{_vix_txt}\n"
        f"- 有效判斷檔數：{digest.get('total', 0)}\n"
        f"- 健檢紅燈需汰弱：{_reds}\n"
        f"- 235 加碼觸發：{_adds}\n"
        + ("- 觀察清單（未持有）235 燈號："
           + "、".join(d["代號"] for d in _watch) + "\n" if _watch else "")
        + f"- 抓取失敗未納入：{_errs}\n"
    )
    if _inv:
        _base += ("- 資料異常未判："
                  + "、".join(f"{d['代號']}（" + "　".join(f"{_lbl}：{_txt}" for _lbl, _txt in d["項目"])
                             + "）" for d in _inv) + "\n")
    if digest.get("contract_drift"):
        # 複驗 C 第二輪 MINOR-A：契約漂移列（保留原診斷句、不換 ⬜）在事實裡點名。
        _base += f"- 資料異常未判（契約漂移）：{'、'.join(str(_c) for _c in digest['contract_drift'])}\n"
    for _lbl, _grp in (("持有", [d for d in _ins if d.get("held", True)]),
                       ("觀察清單", [d for d in _ins if not d.get("held", True)])):
        if _grp:
            _base += (f"- 資料不足／無法判定（{_lbl}）："
                      + "、".join(f"{d['代號']}（" + "、".join(SS.INSUFF_REASON_TEXT.get(_r, str(_r))
                                                             for _r in d.get("原因", ())) + "）"
                                 for d in _grp) + "\n")
    _kept_sat = set(digest.get("price_missing_kept_satellite") or ())
    for _txt, _grp in ((SS.PRICE_MISSING_KEPT_TEXT, [c for c in _kept if c not in _kept_sat]),
                       (SS.PRICE_MISSING_KEPT_SAT_TEXT, [c for c in _kept if c in _kept_sat])):
        if _grp:
            _base += f"- {_txt}：{'、'.join(str(_c) for _c in _grp)}\n"
    _fx = digest.get("fx_excluded") or []
    if _fx:
        # XV-H3（客戶 2026-10-28 裁示 A）：外幣／幣別未確認資產不進總額 ⇒ AI 拿不到混幣總額，
        # 只拿到「哪幾檔未納入、為什麼、比例無法完整判定」這個事實（⛔ 不送比例數字）。
        _base += (f"- 未納入總市值與配置比例：{FXG.fx_excluded_text(_fx).removeprefix('未納入：')}"
                  "（總市值／配置比例無法完整判定）\n")
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
        # ⚠️ 2026-08-24 user 指定移除「總經位階」:LINE 訊息那一行已拿掉
        # (src/compute/notify/holdings_digest_message.py),AI prompt 這段若留著,
        # 總結段落仍會講「當前總經位階 / 建議持股 X%」—— 刪一半等於沒刪,而且更糟:
        # 訊息本文沒有的東西卻由 AI 講出來,使用者無從對照數字從哪來。
        # 連帶移除 `_stance_note`(攻守指引)—— 它整段語意都建立在總經位階上。
        _base += (
            "── 換股建議 ──\n"
            f"- 建議換出（你持有的紅燈汰弱）：{_out}\n"
            f"- 建議換入（來源：{'你的觀察清單' if switch.get('switch_in_src') == 'watchlist' else '選股池全自動排名'}）：{_in}\n"
            "請把「換出 X → 換入 Y」講清楚。\n"
            "**不要**提及總經位階、景氣循環階段、或任何持股成數 —— "
            "本則訊息不提供這些判斷,由 AI 自行補上等同捏造(§1)。\n"
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
