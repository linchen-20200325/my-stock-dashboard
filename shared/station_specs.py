"""shared/station_specs.py — L0 戰情室燈號規格表（2026-08-25）。

## 為什麼需要這個檔

戰情室**有**結構化的燈（每檔 ETF 8 盞、每檔個股 4 盞，L2 已用 frozen dataclass
表達），**但沒有「一筆一盞燈」的規格清單**。燈的規格（單位 / 方向 / 門檻 / 來源）
只以**中文字串**存在 `Flag.msg` 裡 —— 畫面端無法列舉、無法反查、無法回答
「這盞燈可不可信」。

這正是總經 v2 做得到四態揭露、戰情室做不到的唯一結構落差：
總經有 `shared/macro_buckets.BUCKET_DANGER_SPECS`（16 筆 `DangerSpec`），
戰情室什麼都沒有。本檔補上對應物。

## 這個檔**不做**什麼（很重要）

- **不重抄任何門檻數字**。所有門檻一律 `import` 自
  `shared/dividend_station_thresholds.py`（既有 L0 SSOT），本檔只是把
  「哪盞燈用哪個門檻、單位是什麼、方向是高好還是低好」記錄下來。
  §3.3：本檔零 inline magic number。
- **不判燈**。判燈邏輯留在 L2 `src/compute/etf/dividend_station.py`，
  本檔只描述規格。改判燈規則不該動這裡，改揭露方式才動這裡。

## 四態的語意（與總經 v2 對齊）

| 狀態 | 意思 | 燈會亮嗎 | 該怎麼辦 |
|---|---|---|---|
| `live` | 正常運作 | ✅ | 照讀 |
| `degraded` | 有值、燈會亮，但**門檻本身已失去判別力** | ✅ | 別照門檻讀，看相對變化 |
| `missing` | 這輪沒取到值 | ❌ | 看 reason 決定怎麼補 |
| `unwired` | 決策端**刻意沒接** | ❌ 永遠不亮 | 別等它亮 |

⚠️ **`unwired` 與 `missing` 的差別是本檔存在的主要理由。** 戰情室現在把
「刻意沒接」「這輪沒抓到」「該項缺輸入」「一切正常」**全部畫成 ⚪**
（是的，包含「一切正常」—— 見 `dividend_station.py` 的 `suggest_action`
「⚪ 巡航：維持定期定額」）。使用者無從分辨。
"""
from __future__ import annotations

from dataclasses import dataclass

from shared import dividend_station_thresholds as T

# ══════════════════════════════════════════════════════════════════
# 規格
# ══════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class StationSpec:
    """一盞燈的規格。欄位語意刻意對齊 `shared.macro_buckets.DangerSpec`，
    讓兩邊的畫面可以共用同一套四態渲染邏輯。"""

    key: str                      #: 程式用識別字（跨層傳遞的 canonical key）
    label: str                    #: 畫面用中文名
    kind: str                     #: T.KIND_ETF / T.KIND_STOCK / "both"
    group: str                    #: 分組（health / timing / screen / stock）
    unit: str                     #: "%" / "" / "σ" …（§4.1:單位一律寫明）
    direction: str                #: high_bad / low_bad / band / categorical
    threshold_text: str           #: 門檻的人話描述（由下方常數組出，不寫死數字）
    source: str                   #: 這盞燈的值從哪來（給明細面板顯示）
    why: str                      #: 這盞燈在防什麼（一句話，寫給使用者看）

    #: 決策端刻意沒接 → 永遠不會亮。`False` 時 `unwired_reason` **必填**。
    wired: bool = True
    unwired_reason: str = ""

    #: 有值、燈會亮，但門檻已失去判別力。`False` 時 `degraded_reason` **必填**。
    discriminative: bool = True
    degraded_reason: str = ""


# ══════════════════════════════════════════════════════════════════
# 註冊表 —— ETF 8 盞 + 個股 4 盞
# ══════════════════════════════════════════════════════════════════
#
# ⚠️ 門檻文字一律用 f-string 從 T.* 組出，**不得**寫死數字（§3.3）。
#    上游改門檻，這裡自動跟著改；不存在「規格表寫 1.5% 但實作用 2%」的漂移。

STATION_SPECS: list[StationSpec] = [
    # ── ETF 健檢 A/B/C/D ──────────────────────────────────────────
    StationSpec(
        key="health_a", label="A 不吃本金", kind=T.KIND_ETF, group="health",
        unit="%", direction="low_bad",
        threshold_text="🔴 近一年總報酬 < 年化配息率（吃到本金）",
        source="ETF 5 年日線回推 365 天總報酬 vs TTM 配息 / 現價",
        why="配息看起來很香，但如果總報酬追不上配息率，領到的是自己的本金。",
    ),
    StationSpec(
        key="health_b", label="B 夏普", kind=T.KIND_ETF, group="health",
        unit="", direction="low_bad",
        threshold_text=f"🔴 Sharpe < {T.SHARPE_NEG_THRESHOLD:g}",
        source="5 年日報酬年化（無風險利率視為 0）",
        why="承擔了波動卻沒換到超額報酬 —— 那不如放定存。",
    ),
    StationSpec(
        key="health_c", label="C 趨勢防守", kind=T.KIND_ETF, group="health",
        unit="", direction="categorical",
        threshold_text=f"🟡 週收 < {T.MA_QUARTER_WEEKS} 週季線**且**季線下彎",
        source="週 K（由日線衍生）",
        why="兩個條件同時成立才算轉弱 —— 只是跌破季線不夠，季線本身要開始往下。",
    ),
    StationSpec(
        key="health_d", label="D 折溢價", kind=T.KIND_ETF, group="health",
        unit="%", direction="high_bad",
        threshold_text=f"🟡 溢價 > {T.PREMIUM_ALERT_PCT:g}%",
        source="近 35 交易日 NAV 對照市價",
        why="溢價買進等於先付一筆看不見的手續費。個股沒有這個概念，故不適用。",
    ),
    # ── ETF 235 加碼引擎（三取一取最嚴重）──────────────────────────
    StationSpec(
        key="light235", label="235 加碼燈", kind=T.KIND_ETF, group="timing",
        unit="σ", direction="low_bad",
        threshold_text=(
            f"{T.BOLL_PERIOD_WEEKS} 週布林 z ≤ −1σ / −2σ / −3σ "
            f"三段加碼；z > +{T.Z_TAKE_PROFIT_PARTIAL:g}σ 分批停利、"
            f"> +{T.Z_TAKE_PROFIT_FORCE:g}σ 強制停利"
        ),
        source="週 K 20 週布林 + VIX + 年線位置，三條件取最嚴重",
        why="跌得越深、加碼越多。三個條件只要有一個觸發就算，取最嚴重那個。",
    ),
    # ── ETF 3-3-3 篩選（三個子項）─────────────────────────────────
    StationSpec(
        key="screen_inception", label="3-3-3 ① 成立年數", kind=T.KIND_ETF,
        group="screen", unit="年", direction="low_bad",
        threshold_text=f"需 ≥ {T.MIN_INCEPTION_YEARS:g} 年",
        source="ETF 基本資料成立日",
        why="太年輕的 ETF 沒經歷過完整多空，過去表現參考價值有限。",
    ),
    StationSpec(
        key="screen_return", label="3-3-3 ② 三年報酬", kind=T.KIND_ETF,
        group="screen", unit="%", direction="low_bad",
        threshold_text="需為正報酬",
        source="ETF 5 年日線回推 3 年",
        why="三年還是負的，代表這不是短期回檔的問題。",
    ),
    StationSpec(
        key="screen_peer", label="3-3-3 ③ 同儕排名", kind=T.KIND_ETF,
        group="screen", unit="", direction="low_bad",
        threshold_text=(
            f"需 {'/'.join(f'{m}M' for m in T.PEER_WINDOWS_MONTHS)} "
            f"三個時間框**皆**落在同類前 1/{round(1 / T.PEER_TOP_FRACTION)}"
        ),
        source=f"同類 ETF 排名（同類少於 {T.PEER_MIN_GROUP_SIZE} 檔時不計算）",
        why="三個時間框都要贏，避免只是剛好某一段跑得好。",
        # ⚠️ 這不是「未接線」——2026-08-25 查證確認實作已接
        # `compute_etf_peer_ranking`（service 層），只是 L3 的 docstring 還停在
        # 「Phase 2 未接」的舊文案、與實作漂移了。真正的問題是：同類不足
        # `PEER_MIN_GROUP_SIZE` 檔時回 None，而畫面上那個「❔ 待資料」跟
        # 「整檔抓取失敗」長得一模一樣 —— 那是揭露問題，由本檔的四態解決。
    ),
    # ── 個股 4 盞 ─────────────────────────────────────────────────
    StationSpec(
        key="stock_health", label="財報體檢", kind=T.KIND_STOCK, group="stock",
        unit="", direction="categorical",
        threshold_text=(
            f"評等 {'/'.join(T.STOCK_HEALTH_GRADES)}；"
            f"{'/'.join(T.STOCK_SWAP_GRADES)} 列入汰換候選"
        ),
        source="財報體檢引擎（季報）",
        why="個股不像 ETF 有一籃子分散，體質壞掉就是壞掉。",
    ),
    StationSpec(
        key="stock_trend", label="財報趨勢", kind=T.KIND_STOCK, group="stock",
        unit="", direction="categorical",
        threshold_text="盈轉虧 / 逐季惡化 / 轉機（兩季比較）",
        source="本季 vs 上一季財報",
        why="體檢分數是靜態的，趨勢告訴你它正在變好還是變壞。",
        discriminative=False,
        degraded_reason=(
            "這格只比較**最近兩季**，看不出趨勢。同一份季度快照其實有 6 季"
            "（114Q1 起）可以算斜率，但戰情室目前沒接上去 —— 所以「逐季惡化」"
            "這個說法在這裡其實只有一季的根據。該怎麼看：把它當「上季到這季有沒有"
            "轉折」，真要看趨勢請到 🏆 個股組合的「📊 財報趨勢×轉機」區塊。"
        ),
    ),
    StationSpec(
        key="stock_kd", label="KD 指標", kind=T.KIND_STOCK, group="stock",
        unit="", direction="categorical",
        threshold_text="高檔鈍化 / 黃金交叉 / 死亡交叉",
        source="個股 360 日 OHLC",
        why="短線進出場的參考，不決定要不要續抱。",
    ),
    StationSpec(
        key="stock_swap", label="汰換建議", kind=T.KIND_STOCK, group="stock",
        unit="", direction="categorical",
        threshold_text="🔴 換出 / 🟡 留意 / 🟢 續抱",
        source="財報體檢 + 趨勢 + KD 匯總",
        why="上面三盞燈的結論。這是彙總，不是第四個獨立判斷。",
    ),
]

#: `key` → spec 快查表。
SPECS_BY_KEY: dict[str, StationSpec] = {s.key: s for s in STATION_SPECS}


def specs_for(kind: str) -> list[StationSpec]:
    """取某一類持股適用的燈。`kind` ∈ {T.KIND_ETF, T.KIND_STOCK}。

    `kind="both"` 的 spec 兩邊都回。ETF 8 盞、個股 4 盞（實測釘在測試裡）。
    """
    return [s for s in STATION_SPECS if s.kind in (kind, "both")]


# ══════════════════════════════════════════════════════════════════
# 四態
# ══════════════════════════════════════════════════════════════════

STATE_LIVE = "live"
STATE_DEGRADED = "degraded"
STATE_MISSING = "missing"
STATE_UNWIRED = "unwired"

#: 缺值原因。與 `shared/macro_buckets.py` 的 `MISSING_*` 同精神：
#: 處置方式不同的缺值必須分開，混在一起等於要使用者自己猜。
MISS_NO_INPUT = "no_input"          #: 該項的輸入沒抓到（如缺配息率）
MISS_FETCH_FAILED = "fetch_failed"  #: 整檔抓取失敗
MISS_NOT_ENOUGH = "not_enough"      #: 有資料但不足以計算（如週數 < 20）
MISS_NOT_APPLICABLE = "n/a"         #: 這類持股不適用（如個股沒有折溢價）

#: 缺值原因 → 給使用者的「該怎麼辦」。畫面直接印這句。
MISS_TEXT: dict[str, str] = {
    MISS_NO_INPUT: "這盞燈需要的數字沒抓到 —— 通常是上游來源這輪失敗，可以重跑一次。",
    MISS_FETCH_FAILED: "這一檔整批抓取失敗 —— 看該列的錯誤訊息，多半是代號或來源問題。",
    MISS_NOT_ENOUGH: "資料筆數不夠算 —— 新上市或剛納入的標的會這樣，等時間累積。",
    MISS_NOT_APPLICABLE: "這類持股不適用這盞燈（不是壞掉）。",
}


def classify_state(spec: StationSpec, *, has_value: bool,
                   reason: str | None = None) -> str:
    """決定一盞燈的四態。**不判燈**，只判「這盞燈可不可信」。

    順序有意義：
      1. `wired=False`   → 永遠 unwired（就算硬塞值進來也一樣）
      2. `discriminative=False` → degraded（**有值、燈照亮**，只是別照門檻讀）
      3. 沒值           → missing
      4. 其餘           → live
    """
    if not spec.wired:
        return STATE_UNWIRED
    if not has_value:
        return STATE_MISSING
    if not spec.discriminative:
        return STATE_DEGRADED
    return STATE_LIVE


#: 四態的畫面表示。**刻意不用 ⚪** —— 戰情室現行把
#: 「一切正常（⚪ 巡航）」「該項缺資料」「整檔抓取失敗」三種意思
#: 全部畫成 ⚪，使用者無從分辨。這裡給四態各自獨立的符號，
#: 並把 ⚪ 留給「巡航＝正常」那個既有語意（user 2026-08-25 拍板拆開）。
STATE_META: dict[str, tuple[str, str]] = {
    STATE_LIVE: ("運作中", "🟢"),
    STATE_DEGRADED: ("門檻已失準", "🟠"),
    STATE_MISSING: ("無資料", "▨"),
    STATE_UNWIRED: ("未接線", "⛔"),
}
