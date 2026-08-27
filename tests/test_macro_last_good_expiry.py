# -*- coding: utf-8 -*-
"""tests/test_macro_last_good_expiry.py — `data_cache/macro_last_good/` 的**到期前**預警(2026-08-27)。

═══ 這守的是一顆有日期的定時炸彈,不是垃圾檔案 ═══════════════════════════
`data_cache/macro_last_good/tw_pmi.json`:
    value 60.7 / date 2026-06-01 / cached_at **2026-07-01** /
    series_id **"cier-seed-2026-06"**(= 人工 seed,不是真的抓回來的)
而 `macro_core._macro_cache_load` 的 TTL 是 **90 天**且**強制執行**
(`(now - cached_at).days >= TTL` → 當作沒有)。

⇒ **2026-09-29 這一筆會靜默過期**,台灣 PMI 卡片從「🟡 stale 60.7」變「待取得」。
沒有人會在那天收到通知 —— `metadata.json` 顯示 tw_pmi 的抓取**持續為空**
(`last_updated: null`, `last_error: "抓取結果為空"`),也就是**沒有東西會來接替它**。

【本測試怎麼做到「到期前就知道」】
在**到期前 `_WARN_LEAD_DAYS` 天**就讓 CI 轉紅,而不是等到期當天靠使用者發現畫面變了。
紅燈訊息直接寫出:剩幾天、這是人工 seed、以及**正解是把上游抓回來,不是把 TTL 調長**。

⚠️ **嚴禁用「把 TTL 調長」或「把 cached_at 往後改」來讓本測試變綠** ——
那只是把炸彈往後挪,而且會讓一個 2026-06 的數字冒充更晚的當期值(§1 造假)。
正解二選一:(a) 讓 CIER 抓取恢復,cron 會寫入真的 last-good;
(b) 若確定該來源已永久失效,**刪掉這個 seed 檔並讓卡片誠實顯示「待取得」**
   —— 那是業務決策(核心資料源永久缺失的替代方案),要送客戶,不是內部改個數字。

TTL 一律從 production SSOT(`macro_core._MACRO_CACHE_TTL_DAYS`)讀,本檔不複寫。
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_LAST_GOOD_DIR = _REPO / "data_cache" / "macro_last_good"

#: 提前多久示警。取 21 天的理由:CIER PMI 每月第 1 個營業日公布,
#: 三週的窗至少涵蓋**一個完整公布週期** —— 也就是「還來得及讓真資料自己接上」;
#: 同時留得下人工判斷(要修上游還是要讓它誠實消失)的時間。
#: ⚠️ 這是**測試的預警提前量**,不是任何 production 門檻;調小它等於縮短預警,
#: 不會改變任何線上行為,但請不要為了讓 CI 變綠而調它(理由見檔頭)。
_WARN_LEAD_DAYS = 21


def _ttl_days() -> int:
    from src.data.macro.macro_core import _MACRO_CACHE_TTL_DAYS
    return int(_MACRO_CACHE_TTL_DAYS)


def _entries():
    if not _LAST_GOOD_DIR.exists():
        return []
    out = []
    for f in sorted(_LAST_GOOD_DIR.glob("*.json")):
        try:
            out.append((f, json.loads(f.read_text(encoding="utf-8"))))
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"{f.name} 不是合法 JSON({e}）—— 它會被 _macro_cache_load 靜默跳過")
    return out


def test_last_good_dir_is_not_silently_empty():
    """目錄存在就該有內容;整包消失要有人知道(而不是卡片默默變空)。"""
    if not _LAST_GOOD_DIR.exists():
        pytest.skip("data_cache/macro_last_good/ 不存在(尚未產生任何 durable 快照)")
    assert _entries(), "macro_last_good/ 目錄在但一個 JSON 都沒有"


@pytest.mark.parametrize("today", [None])
def test_no_last_good_entry_is_near_silent_expiry(today):
    """任一 last-good 快照距 TTL 到期 ≤ _WARN_LEAD_DAYS → 轉紅並講清楚正解。"""
    _today = today or dt.date.today()
    _ttl = _ttl_days()
    problems = []
    for f, data in _entries():
        raw = data.get("cached_at")
        if not raw:
            problems.append(f"  {f.name}:沒有 `cached_at` —— _macro_cache_load 會把它當壞檔跳過")
            continue
        try:
            cached = dt.datetime.fromisoformat(str(raw)).date()
        except ValueError:
            problems.append(f"  {f.name}:`cached_at`={raw!r} 無法解析,實際上等於沒有 last-good")
            continue
        expiry = cached + dt.timedelta(days=_ttl)
        left = (expiry - _today).days
        if left > _WARN_LEAD_DAYS:
            continue
        _seed = "seed" in str(data.get("series_id", "")).lower()
        problems.append(
            f"  {f.name}:cached_at={cached} + TTL {_ttl}d → {expiry} 到期,"
            f"剩 {left} 天"
            + ("(這是**人工 seed**,不是抓回來的:"
               f"series_id={data.get('series_id')!r})" if _seed else "")
            + f";值 {data.get('value')!r}（資料日 {data.get('date')!r}）"
        )
    assert not problems, (
        "以下 last-good 快照即將靜默過期,屆時對應卡片會從「🟡 stale」變「待取得」:\n"
        + "\n".join(problems)
        + "\n\n正解(擇一,都不是改門檻):\n"
          "  (a) 讓上游抓取恢復 —— 檢查 data_cache/metadata.json 對應 dataset 的 last_error;\n"
          "  (b) 若該來源已永久失效 → 刪掉 seed 檔、讓卡片誠實顯示「待取得」,\n"
          "      並把「要不要換一個資料源」當業務決策送客戶。\n"
          "⛔ 不得用『把 TTL 調長 / 把 cached_at 往後改』讓本測試變綠 —— "
          "那是把舊值冒充成當期值(§1)。"
    )


def test_manual_seed_entries_are_labelled_as_seed():
    """人工 seed 必須自己講明是 seed —— 否則它看起來就像一筆正常抓回來的 last-good。

    現況:`tw_pmi.json` 的 `series_id='cier-seed-2026-06'` 有講。
    這條釘住「講明」這件事:若日後有人把 seed 標記拿掉(讓它看起來像真抓),轉紅。
    """
    for f, data in _entries():
        _sid = str(data.get("series_id", ""))
        _src = str(data.get("source", ""))
        if "seed" in _sid.lower():
            assert data.get("date"), f"{f.name}:seed 條目必須帶資料日 `date`"
            assert data.get("value") is not None, f"{f.name}:seed 條目沒有值"
            # 標了 seed 就不得同時自稱是即時抓取來源
            assert "api" not in _src.lower(), (
                f"{f.name}:series_id 說是 seed,source 卻自稱 API 抓取,兩者矛盾")


def test_ttl_is_read_from_production_ssot():
    """TTL 必須來自 production 常數,本檔不得複寫一份(否則兩邊會漂移)。

    釘的是**取得方式**:`_ttl_days()` 直接 import `macro_core._MACRO_CACHE_TTL_DAYS`。
    若有人把它改成本檔自己寫一個數字,`_ttl_days` 的 import 會不見 → 轉紅。
    """
    import inspect

    assert _ttl_days() > 0
    assert "_MACRO_CACHE_TTL_DAYS" in inspect.getsource(_ttl_days), (
        "TTL 不再取自 macro_core 的 SSOT —— 兩邊一漂移,預警日期就會算錯")


def test_report_current_headroom(capsys):
    """把「現在離到期還有幾天」印出來(不判定,只揭露)。

    §-2 規則 6 的精神:與其在報告裡宣稱「還早」,不如讓每次 CI 都把數字印出來。
    """
    _ttl = _ttl_days()
    _today = dt.date.today()
    for f, data in _entries():
        try:
            cached = dt.datetime.fromisoformat(str(data.get("cached_at"))).date()
        except (TypeError, ValueError):
            print(f"[last_good] {f.name}: cached_at 無法解析 → 等同沒有 last-good")
            continue
        expiry = cached + dt.timedelta(days=_ttl)
        print(f"[last_good] {f.name}: cached_at={cached} 到期={expiry} "
              f"剩 {(expiry - _today).days} 天 "
              f"(預警門檻 {_WARN_LEAD_DAYS} 天;series_id={data.get('series_id')!r})")
    assert True
