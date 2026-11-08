"""src/data/sector_flow/reader.py — 板塊資金潮汐本地快取讀取(L1 Data).

讀 `data_cache/sector_flow/` 三檔(cron `scripts/update_sector_flow.py` 每交易日凍結):
  - bubble_latest.json  秒讀泡泡座標(**必要**;缺/壞 → ok=False sentinel)
  - metadata.json       `last_updated`=資料觀測日(判 staleness);`updated_at`=cron 執行時戳(僅供顯示)
  - ticker_sector.json  {裸股號: 產業別}(持股→板塊對映;缺 → 空 dict,highlight 略過)

§8.2 L1:純檔案 I/O,無 streamlit、無業務邏輯、無跨層上行 import(對齊
`forward_test_store.py` / `macro_cache_reader.py`)。以 repo root 相對定位,免受 CWD 影響。

§1 Fail Loud, Never Fake:缺檔 / 壞檔 **不炸 UI**,回明確 sentinel(ok=False + reason 或
is_stale 旗標)讓 L5 顯示誠實訊息;**絕不**回傳 dummy 板塊或偽造更新時間。
§3.3:staleness 門檻走 L0 SSOT 常數 `SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS`,無 inline magic number。

D1(客戶 2026-11-08 核准,DEC-148):新鮮度改取「可信的實際來源觀測日」,**不再**用 cron 執行時間。
  ~~由 `metadata.updated_at`(cron 執行時間)距今判新鮮~~ → 有意識的修改,⛔ 不是漏刪。
  舊寫法的缺陷:上游全敗時 cron 仍重寫 `updated_at=now`、`last_updated`(parquet date 最大值)卻停在舊日 ⇒
  執行時間冒充資料日,過期資料被判 fresh(§1 假新鮮)。舊寫法的理由(單一時戳、好懂)仍成立,被權衡掉的是真實性。
  觀測日 = `metadata.last_updated`(嚴格 `YYYY-MM-DD`;已由 `scripts/publish_data_pr.py::reconcile_metadata` 以 parquet 對帳)。
  缺 / 無法解析 / 晚於今日(台北日期)/ 與 `updated_at` 矛盾 ⇒ **一律 is_stale=True**,reason 保留診斷原因;
  ⛔ 絕不以 `updated_at` 頂替觀測日。門檻 `SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS` 數值不變;
  週末 / 休市不做額外推論,純依日曆日門檻。
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# 台北「今天」的 SSOT(§4.5 repo 慣例 UTC+8;macro_compute.tw_now 持有該常數,不另開第 N 份複本)
from shared.macro_compute import tw_now
from shared.sector_flow_thresholds import SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS

# repo root:reader.py 位於 src/data/sector_flow/ → parents[3] 為 repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CACHE_DIR = _REPO_ROOT / "data_cache" / "sector_flow"
BUBBLE_PATH = _CACHE_DIR / "bubble_latest.json"
META_PATH = _CACHE_DIR / "metadata.json"
TICKER_SECTOR_PATH = _CACHE_DIR / "ticker_sector.json"


def _load_json(path: Path):
    """讀 JSON;檔不存在回 None,壞檔當缺檔(log + None,不炸)。"""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as _e:  # noqa: BLE001 — 壞檔不該炸 UI,降級當無資料
        print(f"[sector_flow_reader] 讀取失敗 {path.name}: {type(_e).__name__}: {_e}")
        return None


def _parse_iso_utc(s):
    """ISO 8601 字串 → aware UTC datetime;None / 無法解析 → None。"""
    if not s:
        return None
    try:
        _t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if _t.tzinfo is None:
        _t = _t.replace(tzinfo=timezone.utc)
    return _t.astimezone(timezone.utc)


#: 觀測日只接受嚴格 `YYYY-MM-DD`(⛔ 不用 `fromisoformat` 的寬鬆格式如 `20261106`、不從時戳字串截取)。
_OBS_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _parse_observation_date(raw):
    """metadata.last_updated → date;非 str / 格式不符 / 不是合法日曆日 → None(⛔ 不猜、不截取)。"""
    if not isinstance(raw, str):
        return None
    _s = raw.strip()
    if not _OBS_DATE_RE.fullmatch(_s):
        return None
    try:
        return date.fromisoformat(_s)
    except ValueError:
        return None


def _compute_staleness(meta, *, today: date | None = None
                       ) -> tuple[bool, str | None, str | None, str | None]:
    """由 metadata.last_updated(**資料觀測日**)判是否過期。
    回 `(is_stale, reason, meta_updated_at_str, observation_date_iso)`。

    D1(DEC-148):新鮮度只看「來源觀測日距今(日曆日)> `SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS`」。
    `updated_at`(cron 執行時間)**只原樣回傳供顯示/診斷,絕不參與新鮮度,也不頂替觀測日**。

    Args:
        today: 基準日(台北日期;測試注入;None → `tw_now().date()`)。

    §1:下列任一 ⇒ is_stale=True 且 reason 說明原因(不假設新鮮):
      - metadata 缺 / `last_updated` 缺或無法解析 ⇒ 「觀測日未知」,observation_date=None
      - 觀測日晚於今日 ⇒ 「資料日晚於今日,無法判定」,observation_date=None(不可信,不外露)
      - 觀測日晚於 `updated_at` 的台北日期(執行前就有「未來」資料)⇒ 「矛盾,無法判定」,observation_date=None
      - 觀測日距今 > 門檻 ⇒ 過期(觀測日可信,照實回傳)
    """
    _upd = meta.get("updated_at") if isinstance(meta, dict) else None
    if not isinstance(meta, dict):
        return True, "metadata.json 缺失或格式不符,觀測日未知(§1 不假設新鮮)", _upd, None
    _raw = meta.get("last_updated")
    _obs = _parse_observation_date(_raw)
    if _obs is None:
        return (True,
                f"觀測日未知:metadata.last_updated 缺失或無法解析(值={_raw!r});"
                f"⛔ 不以排程執行時間 updated_at 頂替資料日",
                _upd, None)
    _today = today if today is not None else tw_now().date()
    if _obs > _today:
        return (True,
                f"資料日 {_obs} 晚於今日 {_today},無法判定新鮮度(時鐘或上游日期異常)→ 視為過期",
                _upd, None)
    _upd_dt = _parse_iso_utc(_upd)
    if _upd_dt is not None:
        _upd_tw_date = (_upd_dt + timedelta(hours=8)).date()   # UTC → 台北日期(§4.5 UTC+8)
        if _obs > _upd_tw_date:
            return (True,
                    f"資料日 {_obs} 晚於排程執行日 {_upd_tw_date}(metadata 內部矛盾),無法判定新鮮度 → 視為過期",
                    _upd, None)
    _age_days = (_today - _obs).days
    if _age_days > SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS:
        return (True,
                f"資料日 {_obs} 距今 {_age_days} 日,超過 "
                f"{SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS} 日門檻",
                _upd, _obs.isoformat())
    return False, None, _upd, _obs.isoformat()


def read_sector_flow_cache(*, strict: bool = False, today: date | None = None) -> dict:
    """讀三個本地快取檔 → 結構化 view dict。

    strict(v2「🔍 找標的」泡泡圖卡用;預設 False = 既有行為一字不變):
      True → **壞檔 ≠ 還沒產生**。`bubble_latest.json` **存在**但讀不出來(JSON 壞)
      或格式不符(非 dict / `sectors` 非 list)→ `raise`,不回 ok=False sentinel ——
      否則 caller 會把「快取壞了」畫成「快取尚未產生」(§1 靜默失敗)。
      檔案**不存在**仍回 ok=False(那才是真的還沒產生)。

    today(D1;測試注入,預設 None = 台北今日):判新鮮度的基準日。

    Returns
    -------
    成功:
        {
          'ok': True,
          'sectors': list[dict],        # bubble_latest.json 的 sectors(泡泡座標)
          'updated_at': str | None,     # bubble_latest.json 的更新時戳
          'window_size': int | None,
          'n_trading_days_used': int | None,
          'ticker_sector': dict,        # {裸股號: 產業別};缺檔 → {}
          'is_stale': bool,             # D1:資料觀測日(metadata.last_updated)距今 > 門檻;缺/壞/未來/矛盾 → True
          'stale_reason': str | None,
          'meta_updated_at': str | None,  # metadata.updated_at = cron **執行時間**(⛔ 不是資料日;僅顯示)
          'observation_date': str | None, # D1:可信的資料觀測日 `YYYY-MM-DD`;未知/不可信 → None(⛔ 不以 updated_at 頂替)
          'tpex_complete': bool | None, # 批 Z39:窗口內 TPEx 全成功;舊 JSON 缺鍵 → None
          'n_absent_cells': int | None, # 批 Z39:交易日軸缺席格數(不補 0);缺鍵 → None
        }
        板塊層 `unavailable` / `n_missing_days`(批 Z39)隨 `sectors` 原樣透傳。
    缺 bubble_latest.json / 壞檔 / schema 不符:
        {'ok': False, 'reason': str}
    """
    if strict and BUBBLE_PATH.exists():
        bubble = json.loads(BUBBLE_PATH.read_text(encoding="utf-8"))
        if not isinstance(bubble, dict) or not isinstance(bubble.get("sectors"), list):
            _sec = bubble.get("sectors") if isinstance(bubble, dict) else None
            raise ValueError(
                f"{BUBBLE_PATH.name}: {type(bubble).__name__}, "
                f"sectors={type(_sec).__name__}")
    else:
        bubble = _load_json(BUBBLE_PATH)
    if not isinstance(bubble, dict) or not isinstance(bubble.get("sectors"), list):
        return {"ok": False,
                "reason": "板塊資金快取尚未產生(缺 bubble_latest.json 或格式不符)"}

    meta = _load_json(META_PATH)
    is_stale, stale_reason, meta_upd, obs_date = _compute_staleness(meta, today=today)

    ts = _load_json(TICKER_SECTOR_PATH)
    ticker_sector = ts if isinstance(ts, dict) else {}
    # 容錯:若 cron 未來改成 {'map': {...}} 包裝,取內層;否則視為 flat {code: sector}。
    if isinstance(ticker_sector.get("map"), dict):
        ticker_sector = ticker_sector["map"]

    return {
        "ok": True,
        "sectors": bubble["sectors"],
        "updated_at": bubble.get("updated_at"),
        "window_size": bubble.get("window_size"),
        "n_trading_days_used": bubble.get("n_trading_days_used"),
        "ticker_sector": ticker_sector,
        "is_stale": is_stale,
        "stale_reason": stale_reason,
        "meta_updated_at": meta_upd,
        "observation_date": obs_date,
        # 批 Z39(Q-z28=A):原樣透傳,缺鍵 → None(UI 以 `is not True` 判 → 顯示「目前僅含上市資料」)
        "tpex_complete": bubble.get("tpex_complete"),
        "n_absent_cells": bubble.get("n_absent_cells"),
    }
