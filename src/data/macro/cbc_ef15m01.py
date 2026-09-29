"""cbc_ef15m01.py — 中央銀行 PXWeb EF15M01（貨幣總計數-日平均數）回應解析 SSOT（L1，純函式）。

DL-f1-s1（2026-09-28）：自 `scripts/update_macro_history.py` 搬出（DL-f1-r1 #732 寫成，
真實全表探針 run 36419092722 驗過）。**同一份回應全站只有這一處解析實作**（CLAUDE.md §2.1）；
兩個 caller 共用：
  - `scripts/update_macro_history.fetch_finmind_m1m2`：排程寫 `data_cache/finmind_m1m2.parquet`，取**餘額**；
  - `src/data/macro/tw_macro._try_cbc_ef15m01`：線上即時三層備援 Tier 2，取**官方年增率**。
根因（DL-f1-s1）：舊的線上解析讀頂層 `DataSet`／`Structure`（舊格式），CBC 現行回應是
`{meta, data:{dataSets, structure}}` ⇒ 恆回 None，線上 M1B／M2 一直落到 Tier 3 `^TWII` 動能代理。

本模組只做「回應 → 表」：**不 import streamlit、不做網路 I/O**（取數在 caller，走
`proxy_helper.fetch_url`），只 print 診斷（§1 fail loud）。

回應形狀（探針 GitHub Actions run 36408641177 實測）
  meta.title = "5.貨幣總計數-A.日平均數依期間"、meta.units = "新台幣百萬元,%"
  data.structure.Table1 = 15 個序列標籤（M1A、M1B、M2 各一；標籤是全形字）
  data.structure.Table2 = ["原始值", "年增率"]
  data.dataSets 每列 = [期間, 序列0 原始值, 序列0 年增率, 序列1 原始值, …]；缺值是字串 "-"

解析原則（**依標籤成對，不猜欄位位置**）
  ① 值欄數必須 = len(Table1) × len(Table2)，任一列不符 → 整表拒用並印出標籤；
  ② 序列以 NFKC 正規化後的**完整名稱**唯一命中（M1A 不得冒充 M1B；0 或 ≥2 命中都拒用）；
  ③ 量度以 Table2 標籤找「原始值」（= 餘額）與「年增率」（官方值）；
  ④ "-" = 缺值，**不填 0**；餘額缺值的月份顯式剔除並逐月印出；
  ⑤ 對帳：由餘額自算的年增率須與表內官方年增率一致（容差推導見 `ef15_yoy_tolerance_pp`）。
     **致命範圍**（`fatal_from` 起的月份 = 會影響 caller 輸出的月份，由 caller 推出，見
     `ef15_fatal_from`）內任一列超出 → 整表拒用（選錯欄、配錯對、表內自相矛盾都不得輸出）；
     更早的列照樣對帳，但只印 ⚠️（筆數、max|Δ|、前 10 筆）不拒用 —— 它們不影響輸出，
     而 caller 每次都重解析全表，一筆舊歷史被修訂到不一致就會天天擋住。
     M1B、M2 在致命範圍內各自至少要有 1 列對帳通過，否則拒用（無從驗證欄位配對）。
單位：meta.units 的「原始值」單位必須等於 `MONEY_SUPPLY_CACHE_UNIT_LABEL`（新台幣百萬元），
不一致就拒用 —— parquet 對讀取端承諾的是百萬元（`export_stock_db` 再 ÷100 成億元外送）。

自腳本搬出時的變動（**其餘逐字未改**；行為等價由 `tests/test_b7b_r1_ef15m01_level.py`
一字不改全過佐證）：
  - 名稱去掉開頭底線成公開名（跨模組不取 private symbol）；腳本端保留舊名（re-export，見該檔）。
  - `parse_cbc_ef15m01` 新增兩個 keyword-only 參數：`log_tag`（診斷前綴；腳本傳原本的
    `[finmind_m1m2/EF15M01]`，輸出逐字不變）與 `cell`（單格解析函式；預設 `ef15_cell`）。
  - 輸出多帶 `m1b_yoy`／`m2_yoy` 兩欄（表內官方年增率，缺值 NaN），給線上路徑用；
    腳本端只取 date／m1b／m2 三欄。
  - 期間解析抽成 `ef15_period`（解析器與 `ef15_latest_month` 共用同一條規則）。
"""
from __future__ import annotations

import datetime as _dt
import math
import re
import unicodedata

import pandas as pd

from shared.signal_thresholds import MONEY_SUPPLY_CACHE_UNIT_LABEL  # L1 → L0（§8.2 合法下行）

EF15_FILE = "EF15M01"
EF15_TITLE_KEY = "日平均"                  # source 字串宣稱「日平均餘額」的依據，必須在 meta.title 內
EF15_SERIES = (("m1b", "M1B", "貨幣總計數-M1B"),   # (輸出欄, 簡稱, NFKC＋去空白後的完整序列名)
               ("m2", "M2", "貨幣總計數-M2"))
EF15_MEASURE_LEVEL = "原始值"
EF15_MEASURE_YOY = "年增率"
EF15_UNIT_YOY = "%"
EF15_MISSING = "-"
EF15_PERIOD_RE = re.compile(r"^(\d{4})M(\d{2})$")
# 對帳容差的三個來源（推導見 `ef15_yoy_tolerance_pp`）：
EF15_YOY_DECIMALS = 2          # 表內官方年增率只到小數兩位（實測 "7.34"、"10.00"）
EF15_LEVEL_STEP = 1.0          # 餘額以「百萬元」整數發布 → 相鄰可表示值的間距 = 1 百萬元
EF15_FLOAT_EPS_PP = 1e-9       # 十進位字串 → 二進位浮點的表示誤差（遠小於前兩項）

_DEFAULT_LOG_TAG = f"[cbc_ef15m01/{EF15_FILE}]"


def cbc_norm_label(t: str) -> str:
    """標籤正規化：全形→半形（NFKC）、大寫、去空白（比對序列名用）。"""
    return "".join(unicodedata.normalize("NFKC", str(t)).upper().split())


def ef15_yoy_tolerance_pp(level_t: float, level_t12: float) -> float:
    """|自算年增率 − 表內官方年增率| 的容許上界（百分點）。三項相加：

    (1) 官方年增率只到小數兩位：表內值 = 四捨五入(真值, 2) → 誤差 ≤ 半個最小位數
        = 0.5 × 10⁻² = **0.005 pp**。前提「四捨五入、不是截斷」的依據是**真實全表實測**
        （GitHub Actions run 36419092722，EF15M01 全表 1987-05～2026-07）：M1B、M2 各 459 列
        可對帳，自算年增率四捨五入到兩位後與官方 **459/459** 列相同，截斷到兩位只有 233/459、
        222/459 列相同；|自算 − 官方| 最大 **0.004993**（M1B，2010-12）、**0.004999** pp
        （M2，2024-09），全數落在本容差內。
        ⚠️ 探針三列真實資料的恆等式（M1B＝M1A＋活期儲蓄、M2＝M1B＋準貨幣）**本身無法區分捨入方式**
        —— 四捨五入、截斷、floor、ceil 在那三列都有可行解（QA 以 Fourier–Motzkin 消去法驗證）；
        實作組先前據此寫的「截斷無解」不成立，已撤回，改以上述全表實測為依據。
    (2) 餘額以百萬元整數發布：每個餘額的捨入誤差 ≤ δ = 0.5 × `EF15_LEVEL_STEP`。
        自算 r = (a/b − 1)×100；a、b 各偏離 ≤ δ 時
        |Δr| = 100·|b·εa − a·εb| / (b·(b+εb)) ≤ **100·δ·(a + b) / (b·(b − δ))**（精確上界，非近似）。
        本表最小的 M1B 餘額約 1.26e6 百萬元 → 此項 < 1e-4 pp；仍逐列計入，不假設可忽略。
    (3) 浮點表示誤差 → `EF15_FLOAT_EPS_PP`。
    超出三者之和 = 不是捨入能解釋的差 → 選錯欄／配錯對／表內自相矛盾 → fail loud。
    呼叫端須保證 level_t12 > δ（否則無法對帳，由呼叫端直接判不符）。
    """
    _delta = 0.5 * EF15_LEVEL_STEP
    _half_ulp = 0.5 * 10.0 ** (-EF15_YOY_DECIMALS)
    _rounding = 100.0 * _delta * (abs(level_t) + abs(level_t12)) / (level_t12 * (level_t12 - _delta))
    return _half_ulp + _rounding + EF15_FLOAT_EPS_PP


def ef15_labels(seq) -> list | None:
    """PXWeb `structure.TableN`（[{"data": "…"}, …]）→ 標籤字串 list；任一項取不到字串 → None。"""
    if not isinstance(seq, list) or not seq:
        return None
    out = []
    for x in seq:
        t = x.get("data") if isinstance(x, dict) else x
        if not isinstance(t, str) or not t.strip():
            return None
        out.append(t)
    return out


def ef15_cell(v):
    """值欄字串 → float；"-" → None（缺值，**不是 0**）；其他無法解析的內容 → ValueError（不猜）。"""
    s = str(v).replace(",", "").strip()
    if s == EF15_MISSING:
        return None
    x = float(s)
    if not math.isfinite(x):
        raise ValueError(f"非有限數值 {v!r}")
    return x


def ef15_period(p) -> _dt.date | None:
    """期間欄 'YYYYMmm' → 該資料月月初（datetime.date）；格式不符或月份不在 1～12 → None（不猜）。

    解析器與 `ef15_latest_month` 共用這一條規則（自腳本搬出時抽出，判定與原本逐字相同；
    年份 0000 這類 `datetime.date` 不接受的值照舊由 `datetime.date` 拋 ValueError）。
    """
    _m = EF15_PERIOD_RE.match(str(p).strip())
    if not _m or not 1 <= int(_m.group(2)) <= 12:
        return None
    return _dt.date(int(_m.group(1)), int(_m.group(2)), 1)


def ef15_fatal_from(start: _dt.date) -> _dt.date:
    """寫入窗口起點 `start` → 對帳「致命範圍」的第一個資料月（月初）。

    寫入的是 date ≥ start 的月份；每一列的 gap 還要用到同月去年（t−12）的餘額。
    所以會影響寫入結果的月份 = 第一個寫入月往前推 12 個月起的全部月份
    （等價於「d ≥ start − 12 個月」；資料月以月初表示）。
    例：start=2006-10-03 → 第一個寫入月 2006-11-01 → 回 2005-11-01；
        start=2026-07-01 → 回 2025-07-01。
    線上路徑（`tw_macro._try_cbc_ef15m01`）把「表內最新資料月」當成唯一的寫入月傳入 →
    致命範圍 = 最新月與其往前 12 個月（最新月官方年增率的 t−12 基期起）。
    """
    y, m = start.year, start.month
    if start.day > 1:                        # 當月月初 < start → 當月不寫入，第一個寫入月是下個月
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return _dt.date(y - 1, m, 1)


def ef15_latest_month(sdmx) -> _dt.date | None:
    """回應 `data.dataSets` 期間欄中最新的合法資料月（月初）；結構不對或沒有合法期間 → None。

    只讀每列第 0 格（期間），**不解析任何數值** —— 數值一律由 `parse_cbc_ef15m01` 解析與驗證。
    用途：線上路徑以它推出對帳致命範圍（`ef15_fatal_from(本函式回傳值)`）；
    本函式容忍壞列（略過），壞列本身交給 `parse_cbc_ef15m01` 拒用並印出原因。
    """
    _data = sdmx.get("data") if isinstance(sdmx, dict) else None
    rows = _data.get("dataSets") if isinstance(_data, dict) else None
    if not isinstance(rows, list):
        return None
    latest = None
    for r in rows:
        if not isinstance(r, list) or not r:
            continue
        try:
            d = ef15_period(r[0])
        except ValueError:                   # 年份 0000 之類：解析器會拒用，此處只略過
            continue
        if d is not None and (latest is None or d > latest):
            latest = d
    return latest


def parse_cbc_ef15m01(sdmx, fatal_from: _dt.date | None = None, *,
                      log_tag: str | None = None, cell=None
                      ) -> tuple[pd.DataFrame | None, str]:
    """CBC EF15M01 回應 → (DataFrame[date, m1b, m2, m1b_yoy, m2_yoy], 說明) 或 (None, 拒用原因)。

    純函式（無 I/O，只 print 診斷）。date = 資料月月初（datetime.date）；m1b／m2 = 日平均餘額，
    單位新台幣百萬元，int64（與既有 parquet schema 一致）；m1b_yoy／m2_yoy = 表內**官方年增率**
    （%，float64；該格為 "-" 時 NaN —— 不補值）。規則見模組 docstring。

    `fatal_from`：對帳「致命範圍」的第一個資料月（排程以 `ef15_fatal_from(start)` 傳入；
    線上路徑以 `ef15_fatal_from(ef15_latest_month(回應))` 傳入）。
    d ≥ fatal_from 的列對帳不符 → 整表拒用；更早的列不符 → 只印 ⚠️。
    None = 全表都是致命範圍（最嚴；直接呼叫本函式時的預設）。
    ⚠️ 只有「對帳不符」分範圍；格式錯誤（期間、欄數、無法解析的值、非整數餘額）一律整表拒用。
    `log_tag`：診斷訊息前綴（None → `[cbc_ef15m01/EF15M01]`）。
    `cell`：單格解析函式（None → `ef15_cell`）；只有「"-" → None、其餘轉 float 或拋
    TypeError/ValueError」這個契約。腳本端以自己的 `_ef15_cell` 名稱傳入，保留既有守衛測試
    （`test_mq3_reconcile_comparison_is_nan_safe`）模擬「上游有限檢查被拿掉」的注入點。
    """
    tag = _DEFAULT_LOG_TAG if log_tag is None else log_tag
    _cell = ef15_cell if cell is None else cell

    def _fail(reason: str, **dump):
        _extra = "".join(f" {k}={v!r}" for k, v in dump.items())
        print(f"{tag} ❌ 拒用：{reason}{_extra}")
        return None, reason

    if not isinstance(sdmx, dict):
        return _fail(f"回應不是 JSON 物件（{type(sdmx).__name__}）")
    _data = sdmx.get("data")
    _struct = _data.get("structure") if isinstance(_data, dict) else None
    rows = _data.get("dataSets") if isinstance(_data, dict) else None
    t1 = ef15_labels(_struct.get("Table1")) if isinstance(_struct, dict) else None
    t2 = ef15_labels(_struct.get("Table2")) if isinstance(_struct, dict) else None
    if t1 is None or t2 is None or not isinstance(rows, list) or not rows:
        return _fail("缺 data.structure.Table1／Table2（字串標籤）或 data.dataSets",
                     top_keys=list(sdmx.keys())[:10],
                     data_keys=(list(_data.keys())[:10] if isinstance(_data, dict)
                                else type(_data).__name__),
                     Table1=t1, Table2=t2)

    # ① 值欄數 = len(Table1) × len(Table2)（每一列都要成立）
    n_val = len(t1) * len(t2)
    bad_len = [(i, len(r) if isinstance(r, list) else type(r).__name__)
               for i, r in enumerate(rows) if not (isinstance(r, list) and len(r) == n_val + 1)]
    if bad_len:
        return _fail(f"值欄數 ≠ len(Table1)×len(Table2) = {len(t1)}×{len(t2)} = {n_val}"
                     f"（含期間欄每列應為 {n_val + 1} 格；不符 {len(bad_len)} 列，"
                     f"前 5 =(列號, 格數) {bad_len[:5]}）", Table1=t1, Table2=t2)

    # ③ 量度：Table2 須恰有一個「原始值」、一個「年增率」
    t2n = [cbc_norm_label(t) for t in t2]
    j_lv = [j for j, t in enumerate(t2n) if t == cbc_norm_label(EF15_MEASURE_LEVEL)]
    j_yy = [j for j, t in enumerate(t2n) if t == cbc_norm_label(EF15_MEASURE_YOY)]
    if len(j_lv) != 1 or len(j_yy) != 1:
        return _fail(f"Table2 須各恰有一個「{EF15_MEASURE_LEVEL}」與「{EF15_MEASURE_YOY}」"
                     f"（實得 {len(j_lv)}／{len(j_yy)}）", Table2=t2)
    j_lv, j_yy = j_lv[0], j_yy[0]

    # 表頭：日平均（source 宣稱的依據）＋ 單位（與 parquet 單位契約一致）
    _meta = sdmx.get("meta") if isinstance(sdmx.get("meta"), dict) else {}
    if EF15_TITLE_KEY not in cbc_norm_label(_meta.get("title") or ""):
        return _fail(f"meta.title 不含「{EF15_TITLE_KEY}」→ 不能宣稱是日平均餘額",
                     title=_meta.get("title"))
    _units = cbc_norm_label(_meta.get("units") or "").split(",")
    if (len(_units) != len(t2)
            or _units[j_lv] != cbc_norm_label(MONEY_SUPPLY_CACHE_UNIT_LABEL)
            or _units[j_yy] != EF15_UNIT_YOY):
        return _fail(f"meta.units 與量度不對應（須 {EF15_MEASURE_LEVEL}＝"
                     f"{MONEY_SUPPLY_CACHE_UNIT_LABEL}、{EF15_MEASURE_YOY}＝{EF15_UNIT_YOY}）",
                     units=_meta.get("units"), Table2=t2)

    # ② 序列：NFKC 正規化後的完整名稱唯一命中；欄位 = 1 + i × len(Table2) + j
    t1n = [cbc_norm_label(t) for t in t1]
    cols = {}
    for key, short, name in EF15_SERIES:
        hits = [i for i, t in enumerate(t1n) if t == cbc_norm_label(name)]
        if len(hits) != 1:
            return _fail(f"序列「{name}」須以完整名稱唯一命中，實得 {len(hits)} 個", Table1=t1)
        i = hits[0]
        cols[key] = (short, t1n[i], 1 + i * len(t2) + j_lv, 1 + i * len(t2) + j_yy)

    # ④ 逐列解析："-" = 缺值；其他解析不了的內容 → 拒用（不猜）
    recs: dict = {}
    for r in rows:
        _p = str(r[0]).strip()
        d = ef15_period(_p)
        if d is None:
            return _fail(f"期間格式不是 YYYYMmm：{_p!r}")
        if d in recs:
            return _fail(f"期間重複：{_p}")
        vals = {}
        for key, (short, _lab, c_lv, c_yy) in cols.items():
            try:
                lv, yy = _cell(r[c_lv]), _cell(r[c_yy])
            except (TypeError, ValueError) as e:
                return _fail(f"{_p} {short} 值無法解析（{e}）",
                             level_raw=r[c_lv], yoy_raw=r[c_yy])
            if lv is not None and not float(lv).is_integer():
                return _fail(f"{_p} {short} 餘額不是整數百萬元（格式或單位變了？）",
                             level_raw=r[c_lv])
            vals[key] = (lv, yy)
        recs[d] = vals

    _miss = {key: sorted(d for d, v in recs.items() if v[key][0] is None) for key in cols}
    dropped = sorted(set(_miss["m1b"]) | set(_miss["m2"]))
    if dropped:
        print(f"{tag} ⚠️ 餘額欄為「{EF15_MISSING}」→ 剔除 {len(dropped)} 個月（不填 0、不補值）："
              + "；".join(f"{cols[k][0]} 缺 {[d.strftime('%Y-%m') for d in v]}"
                         for k, v in _miss.items() if v))
    keep = {d: v for d, v in recs.items() if d not in set(dropped)}
    if not keep:
        return _fail("剔除缺值月份後無任何月份")

    # ⑤ 對帳：自算年增率（t ÷ t−12 − 1，t−12 = 同月去年）vs 表內官方年增率
    #    致命範圍（d ≥ fatal_from；None = 全表）不符 → 拒用；更早的列不符 → 只警示。
    _delta = 0.5 * EF15_LEVEL_STEP
    _scope = "全表" if fatal_from is None else f"≥ {fatal_from:%Y-%m}"
    n_ok = {k: 0 for k in cols}          # 致命範圍內對帳通過
    n_ok_early = {k: 0 for k in cols}    # 致命範圍之前對帳通過
    n_skip = {k: 0 for k in cols}
    worst = {k: 0.0 for k in cols}
    bad, warn = [], []                   # (期間, 序列, 自算年增率 | 原因, 官方, |Δ|)
    for d in sorted(keep):
        _prev = keep.get(_dt.date(d.year - 1, d.month, 1))
        _fatal = fatal_from is None or d >= fatal_from
        for key, (short, _lab, _c1, _c2) in cols.items():
            a, off = keep[d][key]
            if off is None or _prev is None:
                n_skip[key] += 1                    # 無官方年增率 或 t−12 無餘額 → 無從對帳
                continue
            b = _prev[key][0]
            if b <= _delta:
                (bad if _fatal else warn).append(
                    (d.strftime("%Y-%m"), short, "t−12 餘額 ≤ 捨入半階,無法對帳", off, math.inf))
                continue
            calc = (a / b - 1) * 100
            diff = abs(calc - off)
            # 寫成「不是 ≤ 容差」而非「> 容差」：任何 NaN 都判不符（fail-safe），不會被靜默算成通過
            if not diff <= ef15_yoy_tolerance_pp(a, b):
                (bad if _fatal else warn).append(
                    (d.strftime("%Y-%m"), short, round(calc, 6), off, round(diff, 6)))
            else:
                (n_ok if _fatal else n_ok_early)[key] += 1
                worst[key] = max(worst[key], diff)
    if bad:
        # DL-f1-s19：拒用原因依實際原因分類（只改訊息；上面的拒用／放行判定一字未動）。
        # 原本一律寫「超出捨入容差」—— 致命範圍內只剩「t−12 餘額 ≤ 捨入半階」的列時，
        # 精確原因只出現在同一行的前 10 筆明細。分類依 `bad` 每筆第 3 格（上方註解「自算年增率 | 原因」）：
        # 數值 = 自算年增率 → 超出捨入容差；字串 = 無法對帳的原因 → 直接沿用該字串（不在此重打一份）。
        # 只有一種原因：句型與原本相同（不另標列數）；多種並存：逐一寫出、各標列數。前綴「對帳不符 N 列」不變。
        _n_tol = sum(not isinstance(e[2], str) for e in bad)
        _other = [e[2] for e in bad if isinstance(e[2], str)]
        _causes = [("自算年增率 vs 表內官方年增率，超出捨入容差", _n_tol)] if _n_tol else []
        _causes += [(w, _other.count(w)) for w in dict.fromkeys(_other)]
        _why = "；".join(c if len(_causes) == 1 else f"{c} {n} 列" for c, n in _causes)
        return _fail(f"對帳不符 {len(bad)} 列（致命範圍 {_scope}；{_why}）", first10=bad[:10])
    for key, (short, _lab, _c1, _c2) in cols.items():
        if n_ok[key] == 0:
            return _fail(f"{short} 在致命範圍（{_scope}）內無任何可對帳的列 → 無法驗證欄位配對")
    if warn:
        # DL-f1-s41：比照 DL-f1-s19（上方拒用句）依原因分類（只改訊息；上面的警示／放行判定一字未動）。
        # 原本 max|Δ| 取全部 warn 的第 5 格 ——「t−12 餘額 ≤ 捨入半階」的列在那一格記 math.inf ⇒
        # 只要有這類列就印成「infpp」，也分不出是哪一種不符。分類同上方：第 3 格是數值 = 自算年增率
        # → 超出捨入容差類，max|Δ| 只在這一類裡取；是字串 = 無法對帳的原因 → 直接沿用該字串。
        # 只有容差類：整行與原本逐字相同；只有一種無法對帳原因：寫該原因（不標列數）；多種並存：
        # 逐一寫出、各標列數（容差類附 max|Δ|）。前綴「對帳不符 N 列」與 first10 明細不變。
        _tol = [w for w in warn if not isinstance(w[2], str)]
        _other = [w[2] for w in warn if isinstance(w[2], str)]
        _mx = f"max|Δ|={max(w[4] for w in _tol):.6f}pp" if _tol else ""
        _parts = ([f"自算年增率 vs 表內官方年增率，超出捨入容差 {len(_tol)} 列（{_mx}）"] if _tol else [])
        _parts += [f"{c} {_other.count(c)} 列" for c in dict.fromkeys(_other)]
        if not _other:
            _why = _mx
        elif len(_parts) == 1:
            _why = _other[0]
        else:
            _why = "；".join(_parts)
        print(f"{tag} ⚠️ 致命範圍（{_scope}）之前對帳不符 {len(warn)} 列（不影響寫入的資料，"
              f"只警示、不拒用）：{_why} first10={warn[:10]!r}")

    ds = sorted(keep)
    out = pd.DataFrame({
        "date": ds,
        "m1b": pd.array([int(keep[d]["m1b"][0]) for d in ds], dtype="int64"),
        "m2": pd.array([int(keep[d]["m2"][0]) for d in ds], dtype="int64"),
    })
    # DL-f1-s1：官方年增率（T1 權威值）一併帶出，給線上路徑用；缺值（"-"）→ NaN，不補值。
    # 排程路徑（腳本）只取 date／m1b／m2，這兩欄不進 parquet。
    for key in cols:
        out[f"{key}_yoy"] = pd.array(
            [math.nan if keep[d][key][1] is None else float(keep[d][key][1]) for d in ds],
            dtype="float64")
    desc = "; ".join(f"{short} label={lab}" for short, lab, _c1, _c2 in cols.values())
    print(f"{tag} ✅ 日平均餘額 {len(out)} 個月（{ds[0]:%Y-%m}～{ds[-1]:%Y-%m}，{desc}）；"
          f"對帳（致命範圍 {_scope}）" + "、".join(
              f"{cols[k][0]} {n_ok[k]} 列＋範圍前 {n_ok_early[k]} 列 max|Δ|={worst[k]:.4f}pp"
              for k in cols)
          + f"；範圍前不符（只警示）{len(warn)} 列"
          + "；無從對帳（無官方年增率或無 t−12 餘額）"
          + "、".join(f"{cols[k][0]} {n_skip[k]} 列" for k in cols))
    return out, desc
