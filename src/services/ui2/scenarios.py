"""FAKE／scenario canonical dict（Preview 用）。

⚠️ **全部是示意資料，不是真實行情、持股或建議。** 數字刻意用易辨識的占位值，
`source` 一律以 `FAKE` 開頭、`as_of` 一律標 `FAKE`，避免被誤認為真資料。
⛔ 本檔不 import 任何取數／規則模組；不含門檻、分支、公式（只有字串占位）。

場景（六種）：cold／loaded／missing／stale／unavailable／not_evaluated。
`fixed=True` 的 spec 不隨場景變化（例：Risk Cap 在 Q1 數值 Gate 前恆 `⬜ 無法判定`）。
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from shared.ui2_contract.pages import (
    P4_HOLD, P4_ME, P4_MARKET, P4_TARGET, PAGE4_LABELS, PAGE_IDS, SCENARIO_COLD,
    SCENARIO_IDS, SCENARIO_LOADED, SCENARIO_MISSING, SCENARIO_NOT_EVALUATED,
    SCENARIO_STALE, SCENARIO_UNAVAILABLE,
)
from shared.ui2_contract.text import (
    FAKE_SOURCE_PREFIX, TEXT_MISSING_NOT_READY, TEXT_NOT_DEFINED,
    TEXT_NOT_EVALUATED_DATA_SHORT, TEXT_NOT_LOADED, TEXT_NOT_PROVIDED,
    TEXT_RISK_CAP_UNDETERMINABLE,
)

_FAKE_SRC = f"{FAKE_SOURCE_PREFIX}·scenario"
_FAKE_ASOF = f"{FAKE_SOURCE_PREFIX}-ASOF"


def _spec(key: str, label: str, value: str | None, **kw: Any) -> dict:
    d: dict[str, Any] = {"key": key, "label": label, "value": value,
                         "as_of": _FAKE_ASOF, "source": _FAKE_SRC}
    d.update(kw)
    return d


def _fixed_not_evaluated(key: str, label: str, sub: str, reason: str) -> dict:
    return _spec(key, label, None, state="not_evaluated", sub_reason=sub,
                 reason=reason, fixed=True, as_of=None, source=None)


def _fixed_not_provided(key: str, label: str, reason: str) -> dict:
    return _spec(key, label, None, state="not_provided", sub_reason=TEXT_NOT_PROVIDED,
                 reason=reason, fixed=True, as_of=None, source=None)


def _risk_cap_row() -> dict:
    return _fixed_not_evaluated(
        "risk_cap", "Risk Cap", TEXT_RISK_CAP_UNDETERMINABLE,
        "上限數值尚未核准（Q1 數值 Gate 前恆為此）")


def _sections_market() -> list[dict]:
    return [
        {"key": "main_risk", "title": "今日主要風險", "level": "L1", "fields": [
            _fixed_not_provided("main_risk_f", "今日主要風險", "Preview：尚未接線")]},
        {"key": "onebrain", "title": "🤖 OneBrain Outlook", "level": "L1", "fields": [
            _fixed_not_provided("onebrain_f", "OneBrain Outlook", "Stage G 前不提供")]},
        {"key": "why", "title": "為什麼（L2）", "level": "L2", "fields": [
            _fixed_not_provided("why_f", "位階理由／反證／資料新鮮度／來源", "Preview：尚未接線")]},
        {"key": "detail", "title": "指標明細（16 項）（L3）", "level": "L3", "fields": [
            _fixed_not_provided("detail_f", "指標明細", "Preview：尚未接線")]},
        {"key": "raw", "title": "原始資料表／工程診斷（L3）", "level": "L3", "fields": [
            _fixed_not_provided("raw_f", "原始資料表", "Preview：尚未接線")]},
    ]


def _base(page: str) -> dict:
    if page == P4_MARKET:
        return {
            "page": page, "title": PAGE4_LABELS[page],
            "current_state": _spec("regime", "市場目前狀態", "震盪"),
            "context_rows": [_risk_cap_row()],
            "next_step": None,
            "cta": {"label": "🚀 更新今日戰情"},
            "cards": [
                _spec("twii", "台股", "12,345.67"),
                _spec("vix", "VIX", "12.34"),
                _spec("us10y", "US 10Y", "1.23%"),
                _spec("spread", "利差", "0.12"),
                _spec("dxy", "DXY", "123.45"),
                _spec("pmi", "PMI／景氣", "50.0"),
            ],
            "sections": _sections_market(),
        }
    if page == P4_TARGET:
        return {
            "page": page, "title": PAGE4_LABELS[page],
            "current_state": _spec("pick_summary", "精選摘要", "產業 Top 5 · 候選 10／完整 50（FAKE）"),
            "context_rows": [_risk_cap_row()],
            "action_needed": _spec("no_holding_action", "是否需要行動", None, state="not_provided",
                                   sub_reason=TEXT_NOT_PROVIDED,
                                   reason="本頁不產生持股動作；動作權威＝💼 持股",
                                   fixed=True, as_of=None, source=None),
            "next_step": _spec("next", "下一步", "選一檔後進入研究 workspace（尚未提供）",
                               state="not_provided", sub_reason=TEXT_NOT_PROVIDED,
                               fixed=True, as_of=None, source=None),
            "cta": {"label": "查詢"},
            "cards": [
                _spec("industry_top", "產業機會 Top 5", "FAKE 產業 A／B／C／D／E"),
                _spec("candidates", "候選 Top 10", "FAKE 候選 01～10"),
            ],
            "sections": [
                {"key": "conditions", "title": "選股條件（收合）", "level": "L2", "fields": [
                    _fixed_not_provided("cond_f", "選股條件", "Preview：尚未接線")]},
                {"key": "full", "title": "完整 6 欄表／跨季趨勢（L3）", "level": "L3", "fields": [
                    _fixed_not_provided("full_f", "完整表", "Preview：尚未接線")]},
            ],
        }
    if page == P4_HOLD:
        return {
            "page": page, "title": PAGE4_LABELS[page],
            "current_state": _spec("portfolio", "組合狀態", "FAKE 組合 · 12 檔"),
            "context_rows": [
                _risk_cap_row(),
                _spec("exposure", "目前曝險", None, missing_kind="not_ready", fixed=True,
                      reason="無現金／總資產來源", as_of=None, source=None),
            ],
            "next_step": None,
            "cta": {"label": "🚀 更新持股戰情"},
            "cards": [
                _spec("holdings_table", "Holdings（占位）", "FAKE 4 欄精簡表"),
            ],
            "sections": [
                {"key": "onebrain", "title": "🤖 OneBrain 持股摘要", "level": "L1", "fields": [
                    _fixed_not_provided("ob_f", "OneBrain 持股摘要", "Stage G 前不提供")]},
                {"key": "why", "title": "L2 明細", "level": "L2", "fields": [
                    _fixed_not_provided("why_f", "基本面／風險／籌碼／證據", "Preview：尚未接線")]},
                {"key": "raw", "title": "L3 原始明細", "level": "L3", "fields": [
                    _fixed_not_provided("raw_f", "原始明細", "Preview：尚未接線")]},
            ],
        }
    if page == P4_ME:
        return {
            "page": page, "title": PAGE4_LABELS[page],
            "current_state": _spec("conn", "連線狀態", "Google 已登入（FAKE 帳號）· Sheet …FAKE00"),
            "context_rows": [],
            "action_needed": _spec("conn_issue", "連線異常", "無異常（FAKE）"),
            "next_step": _spec("next", "下一步", "無需處理（FAKE）"),
            "cta": {"label": "切換 Sheet"},
            "cards": [
                _spec("google", "Google", "已登入（FAKE）"),
                _spec("sheet", "Sheet（末 6 碼）", "FAKE00"),
                _spec("portfolio", "組合", "FAKE 組合"),
                _spec("watchlist", "觀察清單", "FAKE 觀察清單"),
            ],
            "sections": [
                {"key": "settings", "title": "一般設定", "level": "L1", "fields": [
                    _fixed_not_provided("strategy", "Strategy", "Preview：尚未接線"),
                    _fixed_not_provided("notify", "Notifications", "Preview：尚未接線"),
                    _fixed_not_provided("display", "Display preference", "Preview：尚未接線")]},
                {"key": "digest", "title": "Audit：Decision Digest", "level": "L2", "fields": [
                    _spec("digest_f", "Decision Digest", None, state="not_provided",
                          sub_reason="⬜ 尚未提供（待 Headless Digest）", fixed=True,
                          as_of=None, source=None, reason="Stage F 前不提供")]},
                {"key": "registry", "title": "Audit：Rule Registry（唯讀）", "level": "L2", "fields": [
                    _fixed_not_provided("registry_f", "Rule Registry", "Preview：尚未接線")]},
                {"key": "fresh", "title": "Audit：Data Freshness", "level": "L2", "fields": [
                    _fixed_not_provided("fresh_f", "Data Freshness", "Preview：尚未接線")]},
                {"key": "sysinfo", "title": "Audit：System Information", "level": "L2", "fields": [
                    _fixed_not_provided("sys_f", "System Information", "Preview：尚未接線")]},
            ],
        }
    raise ValueError(f"unknown page {page!r}")


def _transform(spec: dict, scenario: str, idx: int) -> dict:
    """場景轉換：只改呈現狀態旗標，⛔ 計算任何值。"""
    if spec.get("fixed"):
        return spec
    s = dict(spec)
    if scenario == SCENARIO_COLD:
        s.update(value=None, state="not_evaluated", sub_reason=TEXT_NOT_LOADED,
                 as_of=None, source=None, reason="按 🚀 更新後載入（FAKE 冷啟動）")
    elif scenario == SCENARIO_MISSING and idx in (1, 3):
        s.update(value=None, missing_kind="not_ready" if idx == 3 else "not_fetched")
    elif scenario == SCENARIO_STALE and idx in (0, 2):
        s.update(state="stale", stale_days=3 if idx == 0 else None)
    elif scenario == SCENARIO_UNAVAILABLE and idx in (1, 2):
        s.update(value=None, state="unavailable", reason="FAKE 來源逾時（示意）")
    elif scenario == SCENARIO_NOT_EVALUATED and idx in (0, 2):
        s.update(value=None, state="not_evaluated",
                 sub_reason=TEXT_NOT_DEFINED if idx == 0 else TEXT_NOT_EVALUATED_DATA_SHORT)
    return s


def _transform_current(spec: dict, scenario: str) -> dict:
    s = dict(spec)
    if scenario == SCENARIO_COLD:
        s.update(value=None, state="not_evaluated", sub_reason=TEXT_NOT_LOADED,
                 as_of=None, source=None, reason="按 🚀 更新後載入（FAKE 冷啟動）")
    elif scenario == SCENARIO_MISSING:
        s.update(value=None, missing_kind="not_ready")
    elif scenario == SCENARIO_STALE:
        s.update(state="stale", stale_days=3)
    elif scenario == SCENARIO_UNAVAILABLE:
        s.update(value=None, state="unavailable", reason="FAKE 來源逾時（示意）")
    elif scenario == SCENARIO_NOT_EVALUATED:
        s.update(value=None, state="not_evaluated", sub_reason=TEXT_NOT_EVALUATED_DATA_SHORT)
    return s


def fake_canonical(page: str, scenario: str) -> dict:
    """回傳 `page`×`scenario` 的 FAKE canonical dict（每次回新 dict，呼叫端可安全改動）。"""
    if page not in PAGE_IDS:
        raise ValueError(f"unknown page {page!r}")
    if scenario not in SCENARIO_IDS:
        raise ValueError(f"unknown scenario {scenario!r}")
    c = deepcopy(_base(page))
    c["scenario"] = scenario
    c["is_fake"] = True
    c["current_state"] = _transform_current(c["current_state"], scenario)
    c["cards"] = [_transform(s, scenario, i) for i, s in enumerate(c["cards"])]
    if scenario == SCENARIO_COLD and c.get("next_step") is None and page != P4_ME:
        c["next_step"] = _spec("next", "下一步", "按 🚀 更新", fixed=True, as_of=None, source=None)
    if page == P4_ME:   # 我的頁：連線異常／下一步隨場景（非投資動作）
        c["action_needed"] = _transform_current(c["action_needed"], scenario)
        c["next_step"] = _transform_current(c["next_step"], scenario)
    return c
