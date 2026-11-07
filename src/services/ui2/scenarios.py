"""FAKE／scenario canonical dict（Preview 用）。

⚠️ **全部是示意資料，不是真實行情、持股或建議。** 數字刻意用易辨識的占位值，
`source` 一律以 `FAKE` 開頭、`as_of` 一律標 `FAKE`，避免被誤認為真資料。
⛔ 本檔不 import 任何取數／規則模組；不含門檻、分支、公式（只有字串占位）。

場景（六種）：cold／loaded／missing／stale／unavailable／not_evaluated。
`not_evaluated` 場景同時示意 Not Evaluated（`⬜ 尚未定義`）與 Unable to Determine
（DEC-074／075 客戶逐字 `⬜ 未評估／資料不足`）——兩者語意不同、分屬不同態（DEC-124）。
`fixed=True` 的 spec 不隨場景變化（例：Risk Cap 在 Q1 數值 Gate 前恆 `⬜ 無法判定`＝Unable to Determine）。
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from shared.ui2_contract.pages import (
    ACCOUNT_IDS, ACCOUNT_SIGNED_IN, ACCOUNT_SIGNED_OUT, ACCOUNT_UNAVAILABLE, MODE_CURATED,
    MODE_LOOKUP, MODE_LABELS, P4_DATA, P4_HOLD, P4_ME, P4_MARKET, P4_TARGET, PAGE4_LABELS, PAGE_IDS,
    SCENARIO_COLD, SCENARIO_IDS, SCENARIO_LOADED, SCENARIO_MISSING, SCENARIO_NOT_EVALUATED,
    SCENARIO_STALE, SCENARIO_UNAVAILABLE,
)
from shared.ui2_contract.text import (
    FAKE_SOURCE_PREFIX, RISK_ERROR_FMT, RISK_NOTE_UNEVALUATED_NOT_SAFE,
    RISK_SENTENCE_ALL_INSUFFICIENT, RISK_SENTENCE_NOT_LOADED, TEXT_MISSING_NOT_READY,
    TEXT_NOT_DEFINED, TEXT_NOT_EVALUATED_DATA_SHORT, TEXT_NOT_LOADED, TEXT_NOT_PROVIDED,
    TEXT_RISK_CAP_UNDETERMINABLE,
)
from src.services.ui2.data_page import data_page_canonical
from src.services.ui2.vm_common import field_from_spec

_FAKE_SRC = f"{FAKE_SOURCE_PREFIX} 示意資料"
_FAKE_ASOF = f"{FAKE_SOURCE_PREFIX} 示意"
#: 使用者可見的簡短人話原因（P1；工程原因不外露——見 Active Contract §8）。
_R_EMPTY = "此項目尚未開放"
_R_NOT_OPEN = "此功能尚未開放"
_SEARCH_REASON = "尚未開放查詢（示意資料）"


def _spec(key: str, label: str, value: str | None, **kw: Any) -> dict:
    d: dict[str, Any] = {"key": key, "label": label, "value": value,
                         "as_of": _FAKE_ASOF, "source": _FAKE_SRC}
    d.update(kw)
    return d


def _fixed_undeterminable(key: str, label: str, sub: str, reason: str) -> dict:
    return _spec(key, label, None, state="undeterminable", sub_reason=sub,
                 reason=reason, fixed=True, as_of=None, source=None)


def _fixed_not_provided(key: str, label: str, reason: str) -> dict:
    return _spec(key, label, None, state="not_provided", sub_reason=TEXT_NOT_PROVIDED,
                 reason=reason, fixed=True, as_of=None, source=None)


def _risk_cap_row() -> dict:
    """Risk Cap 閘門＝Unable to Determine（Freeze §0.1.4 第 3、5 點：目前曝險無正式來源）。

    ⛔ 等同 Not Evaluated（DEC-124）；⛔ 推導 safe／無需調整；⛔ 任何數值（不新增 Risk Cap 規則）。
    """
    return _fixed_undeterminable(
        "risk_cap", "Risk Cap", TEXT_RISK_CAP_UNDETERMINABLE,
        "必要輸入不足：目前曝險尚無正式來源")


_SNAPSHOT_DIMS = (("fundamental", "基本面"), ("valuation", "估值"), ("chips", "籌碼"),
                  ("trend", "趨勢"), ("industry", "產業"), ("market_env", "市場環境"))


def _target_block() -> dict:
    """🎯 標的頁：雙模式＋搜尋框＋查一檔 FAKE 結果（Ad-hoc、session-only；⛔ 真資料／候選池規則）。

    6 維 Snapshot 的「趨勢」「產業」＝`⬜ 尚未定義`（DEC-092 Q2；固定、不隨場景變）；「市場環境」排最後
    且為 Neutral（W-4：不搶過查一檔／基本面／valuation，⛔ 把市場訊號變成單股主要判斷）。
    其餘維度只放 FAKE 占位值（⛔ 任何投資判斷字樣）。
    """
    snapshot = [
        _spec("dim_fundamental", "基本面", "FAKE 示意"),
        _spec("dim_valuation", "估值", "FAKE 示意"),
        _spec("dim_chips", "籌碼", "FAKE 示意"),
        _spec("dim_trend", "趨勢", None, state="not_evaluated", sub_reason=TEXT_NOT_DEFINED,
              fixed=True, as_of=None, source=None),
        _spec("dim_industry", "產業", None, state="not_evaluated", sub_reason=TEXT_NOT_DEFINED,
              fixed=True, as_of=None, source=None),
        _spec("dim_market_env", "市場環境", "震盪"),
    ]
    return {
        "modes": [{"id": m, "label": MODE_LABELS[m]} for m in (MODE_CURATED, MODE_LOOKUP)],
        "default_mode": MODE_CURATED,
        "search": {
            "placeholder": "代碼／名稱",
            "name_search": _fixed_not_provided("name_search", "名稱搜尋", "請輸入代碼（名稱搜尋尚未提供）"),
            "cta": {"label": "查詢", "disabled_reason": _SEARCH_REASON},
        },
        "lookup": {
            "ticker": "FAKE-0001", "name": "FAKE 示意公司", "chips": ["股票", "FAKE 產業"],
            "summary": _spec("lookup_summary", "查詢摘要", "FAKE-0001 FAKE 示意公司 · 類型 股票"),
            "snapshot": snapshot,
            "add_watch": {"label": "加入觀察（尚未提供）",
                          "disabled_reason": "加入觀察尚未開放；這裡不會寫入任何持股或觀察清單"},
            "isolation_note": "查一檔只在這次瀏覽有效：不會加入持股、觀察或候選池，也不會改變策略、Risk Cap 或排名，不寫入 Sheet。",
            "sections": [
                {"key": "lk_fundamental", "title": "基本面", "level": "L2", "mode": MODE_LOOKUP,
                 "fields": [_fixed_not_provided("lk_f1", "基本面明細", _R_EMPTY)]},
                {"key": "lk_valuation", "title": "估值", "level": "L2", "mode": MODE_LOOKUP,
                 "fields": [_fixed_not_provided("lk_f2", "估值（EPS basis／PE 口徑）", _R_EMPTY)]},
                {"key": "lk_research", "title": "🤖 研究解釋", "level": "L2", "mode": MODE_LOOKUP,
                 "fields": [_fixed_not_provided("lk_f3", "研究解釋", _R_NOT_OPEN)]},
            ],
        },
    }


def _sections_market() -> list[dict]:
    return [
        {"key": "onebrain", "title": "🤖 OneBrain Outlook", "level": "L1", "fields": [
            _fixed_not_provided("onebrain_f", "OneBrain Outlook", _R_NOT_OPEN)]},
        {"key": "why", "title": "為什麼", "level": "L2", "fields": [
            _fixed_not_provided("why_f", "位階理由／反證／資料新鮮度／來源", _R_EMPTY)]},
        {"key": "detail", "title": "指標明細（16 項）", "level": "L3", "fields": [
            _fixed_not_provided("detail_f", "指標明細", _R_EMPTY)]},
        {"key": "raw", "title": "原始資料表", "level": "L3", "fields": [
            _fixed_not_provided("raw_f", "原始資料表", _R_EMPTY)]},
    ]


_LOOKUP_COLD = "FAKE 示意：輸入代碼並查詢後顯示"
_ME_ACTION_REASON = "登入與 Sheet 操作尚未開放"


def _me_sections() -> list[dict]:
    return [
        {"key": "settings", "title": "一般設定", "level": "L1", "fields": [
            _fixed_not_provided("strategy", "Strategy", _R_EMPTY),
            _fixed_not_provided("notify", "Notifications", _R_EMPTY),
            _fixed_not_provided("display", "Display preference", _R_EMPTY)]},
        {"key": "digest", "title": "Audit：Decision Digest", "level": "L2", "fields": [
            _spec("digest_f", "Decision Digest", None, state="not_provided",
                  fixed=True,
                  as_of=None, source=None, reason=_R_NOT_OPEN)]},
        {"key": "registry", "title": "Audit：Rule Registry（唯讀）", "level": "L2", "fields": [
            _fixed_not_provided("registry_f", "Rule Registry", _R_EMPTY)]},
        {"key": "fresh", "title": "Audit：Data Freshness", "level": "L2", "fields": [
            _fixed_not_provided("fresh_f", "Data Freshness", _R_EMPTY)]},
        {"key": "sysinfo", "title": "Audit：System Information", "level": "L2", "fields": [
            _fixed_not_provided("sys_f", "System Information", _R_EMPTY)]},
    ]


def _me_base() -> dict:
    """👤 我的（signed_in 預設；與 Batch 2 內容相同）。"""
    return {
        "page": P4_ME, "title": PAGE4_LABELS[P4_ME],
        "current_state": _spec("conn", "連線狀態", "Google 已登入（FAKE 帳號）· Sheet …FAKE00"),
        "context_rows": [],
        "action_needed": _spec("conn_issue", "連線異常", "無異常（FAKE）"),
        "next_step": _spec("next", "下一步", "無需處理（FAKE）"),
        "cta": {"label": "切換 Sheet", "disabled_reason": _ME_ACTION_REASON},
        "cards": [
            _spec("google", "Google", "已登入（FAKE）"),
            _spec("sheet", "Sheet（末 6 碼）", "FAKE00"),
            _spec("portfolio", "組合", "FAKE 組合"),
            _spec("watchlist", "觀察清單", "FAKE 觀察清單"),
        ],
        "sections": _me_sections(),
        "account": {"account_state": ACCOUNT_SIGNED_IN, "actions": [
            {"label": "切換 Sheet"}, {"label": "選組合"}, {"label": "選觀察清單"}, {"label": "Google 登出"}]},
    }


def _me_account_variant(account: str) -> dict:
    """signed_out／unavailable 的 FAKE 連線事實（⛔ 真 OAuth／Sheet）。

    語意歸類：「尚未登入」是**確定的連線事實**（OK 值），不是缺值；登入前依賴登入的欄位＝Missing 的
    `⬜ 資料未備`（不適用）；Sheet 讀取失敗＝Unavailable（真錯誤，紅）。三軸不混層。
    """
    c = _me_base()
    fixed = dict(fixed=True, as_of=None, source=None)
    if account == ACCOUNT_SIGNED_OUT:
        c["current_state"] = _spec("conn", "連線狀態", "Google 尚未登入（FAKE）", **fixed)
        c["action_needed"] = _spec("conn_issue", "連線異常", "尚未登入 Google（FAKE）", **fixed)
        c["next_step"] = _spec("next", "下一步", "請先登入 Google（登入後才會顯示 Sheet）", **fixed)
        c["cta"] = {"label": "Google 登入", "disabled_reason": _ME_ACTION_REASON}
        dep = dict(missing_kind="not_ready", reason="需先登入 Google", **fixed)
        c["cards"] = [
            _spec("google", "Google", "尚未登入", **fixed),
            _spec("sheet", "Sheet（末 6 碼）", None, **dep),
            _spec("portfolio", "組合", None, **dep),
            _spec("watchlist", "觀察清單", None, **dep),
        ]
        c["account"] = {"account_state": ACCOUNT_SIGNED_OUT, "actions": [{"label": "Google 登入"}]}
    elif account == ACCOUNT_UNAVAILABLE:
        c["current_state"] = _spec("conn", "連線狀態", "Google 已登入（FAKE 帳號）", **fixed)
        c["action_needed"] = _spec("conn_issue", "連線異常", None, state="unavailable",
                                   reason="Sheet 讀取失敗（FAKE 示意）", **fixed)
        c["next_step"] = _spec("next", "下一步", "重新讀取，或重新綁定 Sheet", **fixed)
        c["cta"] = {"label": "重新讀取", "disabled_reason": _ME_ACTION_REASON}
        c["cards"] = [
            _spec("google", "Google", "已登入（FAKE）", **fixed),
            _spec("sheet", "Sheet（末 6 碼）", None, state="unavailable",
                  reason="Sheet 讀取失敗（FAKE 示意）", **fixed),
            _spec("portfolio", "組合", None, missing_kind="not_fetched",
                  reason="Sheet 無法讀取，未取得", **fixed),
            _spec("watchlist", "觀察清單", None, missing_kind="not_fetched",
                  reason="Sheet 無法讀取，未取得", **fixed),
        ]
        c["account"] = {"account_state": ACCOUNT_UNAVAILABLE, "actions": [
            {"label": "重新讀取"}, {"label": "切換 Sheet"}, {"label": "Google 登出"}]}
    else:
        raise ValueError(f"unknown account {account!r}")
    return c


def _base(page: str) -> dict:
    if page == P4_DATA:
        return data_page_canonical()
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
            # W-4：市場位階＋Risk Cap 一行 context（輕量 chip 行；同一份 FAKE market context）
            "context_rows": [_spec("market_regime", "市場位階", "震盪"), _risk_cap_row()],
            "action_needed": _spec("no_holding_action", "是否需要行動", None, state="not_provided",
                                   sub_reason=TEXT_NOT_PROVIDED,
                                   reason="本頁不產生持股動作；動作權威＝💼 持股",
                                   fixed=True, as_of=None, source=None),
            "next_step": _spec("next", "下一步", "選一檔後進入研究頁（尚未提供）",
                               state="not_provided", sub_reason=TEXT_NOT_PROVIDED,
                               fixed=True, as_of=None, source=None),
            "cta": {"label": "查詢", "disabled_reason": _SEARCH_REASON},
            "cards": [
                _spec("industry_top", "產業機會 Top 5", "FAKE 產業 A／B／C／D／E"),
                _spec("candidates", "候選 Top 10", "FAKE 候選 01～10"),
            ],
            "sections": [
                {"key": "conditions", "title": "選股條件（收合）", "level": "L2", "mode": MODE_CURATED,
                 "fields": [_fixed_not_provided("cond_f", "選股條件", _R_EMPTY)]},
                {"key": "full", "title": "完整 6 欄表／跨季趨勢", "level": "L3", "mode": MODE_CURATED,
                 "fields": [_fixed_not_provided("full_f", "完整表", _R_EMPTY)]},
            ],
            "target": _target_block(),
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
                _spec("holdings_table", "持股清單", "FAKE 4 欄精簡表"),
            ],
            "sections": [
                {"key": "onebrain", "title": "🤖 OneBrain 持股摘要", "level": "L1", "fields": [
                    _fixed_not_provided("ob_f", "OneBrain 持股摘要", _R_NOT_OPEN)]},
                {"key": "why", "title": "明細", "level": "L2", "fields": [
                    _fixed_not_provided("why_f", "基本面／風險／籌碼／證據", _R_EMPTY)]},
                {"key": "raw", "title": "原始明細", "level": "L3", "fields": [
                    _fixed_not_provided("raw_f", "原始明細", _R_EMPTY)]},
            ],
        }
    if page == P4_ME:
        return _me_base()
    raise ValueError(f"unknown page {page!r}")


def _transform(spec: dict, scenario: str, idx: int, cold_reason: str = "按 🚀 更新後載入（FAKE 示意）") -> dict:
    """場景轉換：只改呈現狀態旗標，⛔ 計算任何值。"""
    if spec.get("fixed"):
        return spec
    s = dict(spec)
    if scenario == SCENARIO_COLD:
        s.update(value=None, state="not_evaluated", sub_reason=TEXT_NOT_LOADED,
                 as_of=None, source=None, reason=cold_reason)
    elif scenario == SCENARIO_MISSING and idx in (1, 3):
        s.update(value=None, missing_kind="not_ready" if idx == 3 else "not_fetched")
    elif scenario == SCENARIO_STALE and idx in (0, 2):
        s.update(state="stale", stale_days=3 if idx == 0 else None)
    elif scenario == SCENARIO_UNAVAILABLE and idx in (1, 2):
        s.update(value=None, state="unavailable", reason="FAKE 來源逾時（示意）")
    elif scenario == SCENARIO_NOT_EVALUATED and idx == 0:     # Not Evaluated：規則未定義 → 未執行
        s.update(value=None, state="not_evaluated", sub_reason=TEXT_NOT_DEFINED)
    elif scenario == SCENARIO_NOT_EVALUATED and idx == 2:     # Unable to Determine（DEC-074／075 字樣）
        s.update(value=None, state="undeterminable", sub_reason=TEXT_NOT_EVALUATED_DATA_SHORT)
    return s


def _transform_current(spec: dict, scenario: str, cold_reason: str = "按 🚀 更新後載入（FAKE 示意）") -> dict:
    s = dict(spec)
    if scenario == SCENARIO_COLD:
        s.update(value=None, state="not_evaluated", sub_reason=TEXT_NOT_LOADED,
                 as_of=None, source=None, reason=cold_reason)
    elif scenario == SCENARIO_MISSING:
        s.update(value=None, missing_kind="not_ready")
    elif scenario == SCENARIO_STALE:
        s.update(state="stale", stale_days=3)
    elif scenario == SCENARIO_UNAVAILABLE:
        s.update(value=None, state="unavailable", reason="FAKE 來源逾時（示意）")
    elif scenario == SCENARIO_NOT_EVALUATED:   # DEC-075：位階因必要輸入不足而無法判定（≠ Not Evaluated）
        s.update(value=None, state="undeterminable", sub_reason=TEXT_NOT_EVALUATED_DATA_SHORT)
    return s


def _status_of(spec: dict) -> str:
    """spec → 其 L1 狀態字樣（借用 vm_common 的唯一映射；⛔ 另寫一套）。"""
    f = field_from_spec(spec)
    return f.status_text or ""


def _fake_conclusion(c: dict) -> dict:
    """今日結論（DEC-081 Q2-1 句型）：各判斷**獨立並列**以「；」相接；缺值／不可用／未評估**明寫**；
    ⛔「但／因此」硬做因果；⛔ 由位階或指標推導多空／動作。內容為 FAKE 示意（標 `FAKE 示意結論：`）。
    句中的「市場目前狀態」值是 canonical 的 FAKE 占位值**原樣複述**，不是推論。
    """
    cs = c["current_state"]
    if cs.get("state") == "not_evaluated" and cs.get("sub_reason") == TEXT_NOT_LOADED:
        return _spec("conclusion", "今日結論", None, state="not_evaluated", sub_reason=TEXT_NOT_LOADED,
                     reason="按 🚀 更新後載入（FAKE 示意）", as_of=None, source=None)
    f = field_from_spec(cs)
    clauses = [f"市場目前狀態 {f.value_text}" + (f"（{f.status_text}）" if f.status_text and f.value_text else "")
               if f.value_text else f"市場目前狀態 {f.status_text}"]
    for card in c["cards"]:
        cf = field_from_spec(card)
        if cf.status_text:                         # 非 OK 一律明寫（missing 不當中性）
            clauses.append(f"{cf.label} {cf.status_text}")
    clauses.append("各項判斷並列、互不推導")
    return _spec("conclusion", "今日結論", "FAKE 示意結論：" + "；".join(clauses),
                 as_of=None, source=None)


def _fake_main_risk(scenario: str) -> dict:
    """今日主要風險（L1）。退化／護欄句逐字取自 DEC-117 Q6（`shared/ui2_contract/text.py`）。

    ⛔ 本檔不產生任何風險項（燈色＋桶名＋燈名＋方向）：Preview 的 loaded／stale＝capability 尚未提供。
    冷啟動＝**不出列**（無風險項列），只外露 `⬜ 尚未載入，請按更新`（灰，⛔ 紅）。
    """
    base = dict(as_of=None, source=None)
    if scenario == SCENARIO_COLD:
        return _spec("main_risk_f", "今日主要風險", None, state="not_evaluated",
                     sub_reason=RISK_SENTENCE_NOT_LOADED, **base)
    if scenario == SCENARIO_MISSING:
        return _spec("main_risk_f", "今日主要風險", None, state="undeterminable",
                     sub_reason=RISK_SENTENCE_ALL_INSUFFICIENT, **base)
    if scenario == SCENARIO_UNAVAILABLE:
        return _spec("main_risk_f", "今日主要風險", None, state="unavailable",
                     reason=RISK_ERROR_FMT.format(error="FAKE 來源逾時（示意）"), **base)
    if scenario == SCENARIO_NOT_EVALUATED:
        return _spec("main_risk_f", "今日主要風險", None, state="not_evaluated",
                     sub_reason="⬜ 尚未評估", reason=RISK_NOTE_UNEVALUATED_NOT_SAFE, **base)
    return _spec("main_risk_f", "今日主要風險", None, state="not_provided", sub_reason=TEXT_NOT_PROVIDED,
                 reason="風險摘要尚未提供；這裡不推導任何風險", **base)


def fake_canonical(page: str, scenario: str, account: str | None = None) -> dict:
    """回傳 `page`×`scenario` 的 FAKE canonical dict（每次回新 dict，呼叫端可安全改動）。

    `account`（僅 👤 我的）：`signed_in`（預設，＝Batch 2 內容）／`signed_out`／`unavailable`；
    非 signed_in 的連線事實不隨 `scenario` 轉換（fixed），其餘頁忽略此參數。
    """
    if page not in PAGE_IDS:
        raise ValueError(f"unknown page {page!r}")
    if scenario not in SCENARIO_IDS:
        raise ValueError(f"unknown scenario {scenario!r}")
    if account is not None and account not in ACCOUNT_IDS:
        raise ValueError(f"unknown account {account!r}")
    if page == P4_DATA:        # 固定誠實空殼：不套場景轉換（沒有任何資料事實可示意）
        c = data_page_canonical()
        c["scenario"] = scenario
        c["is_fake"] = True
        return c
    if page == P4_ME and account in (ACCOUNT_SIGNED_OUT, ACCOUNT_UNAVAILABLE):
        c = _me_account_variant(account)
        c["scenario"] = scenario
        c["is_fake"] = True
        c["cards"] = [dict(s) for s in c["cards"]]
        return c
    c = deepcopy(_base(page))
    c["scenario"] = scenario
    c["is_fake"] = True
    # 🎯 標的頁沒有「🚀 更新」入口（精選走載入 gate、查一檔走搜尋）→ 冷啟動說明不得指向不存在的按鈕
    cold_reason = ("FAKE 示意：精選尚未載入" if page == P4_TARGET
                   else "FAKE 示意：尚未載入" if page == P4_ME
                   else "按 🚀 更新後載入（FAKE 示意）")
    c["current_state"] = _transform_current(c["current_state"], scenario, cold_reason)
    c["cards"] = [_transform(s, scenario, i, cold_reason) for i, s in enumerate(c["cards"])]
    if scenario == SCENARIO_COLD and c.get("next_step") is None and page != P4_ME:
        c["next_step"] = _spec("next", "下一步", "按 🚀 更新", fixed=True, as_of=None, source=None)
    if page == P4_ME:   # 我的頁：連線異常／下一步隨場景（非投資動作）
        c["action_needed"] = _transform_current(c["action_needed"], scenario, cold_reason)
        c["next_step"] = _transform_current(c["next_step"], scenario, cold_reason)
    if page == P4_MARKET:
        c["conclusion"] = _fake_conclusion(c)
        c["main_risk"] = _fake_main_risk(scenario)
    if page == P4_TARGET:
        # 市場位階 context 與市場頁同一份 FAKE 位階，且隨場景同步（W-4；不得與市場頁各說各話）
        c["context_rows"] = [_transform_current(r, scenario) if r.get("key") == "market_regime" else r
                             for r in c["context_rows"]]
        lk = c["target"]["lookup"]
        lk["summary"] = _transform_current(lk["summary"], scenario, _LOOKUP_COLD)
        lk["queried"] = scenario != SCENARIO_COLD          # cold：尚未查詢，只有搜尋框＋灰色說明
        lk["snapshot"] = [
            (_transform_current(d, scenario, _LOOKUP_COLD) if d["key"] == "dim_market_env"
             else _transform(d, scenario, i, _LOOKUP_COLD))
            for i, d in enumerate(lk["snapshot"])]
    return c
