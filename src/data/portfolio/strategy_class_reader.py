"""L1 Data — 策略分類**唯讀** reader（AB-4r；D2.5 §5 序 5）。

`read_strategy_classes(sheet_id=...)` 讀 `strategy_class` 分頁 → `StrategyReadResult`。
解析規則全在 L0 `shared/strategy_class_schema.py`；本檔只做「拿到原字串」與狀態轉換：

- sheet_id 為 None／空字串（含只有空白）→ status="not_bound"、0 entries（不打 Google）。
- sheet_id 非空但 `sanitize_sheet_id` 後為空（發布連結、"e"、含非法字元）→ `ValueError`（DEC-083 B3）。
- 分頁不存在 → status="worksheet_missing"、0 entries（⛔ 讀取**不建**分頁，經
  `gsheet_portfolio.read_worksheet_values` 的只開不建路徑）。
- 表頭不符 → `gsheet_portfolio.SheetSchemaMismatchError`（沿用既有讀取的同一例外型別，
  `classify_read_error` 才分得出 schema_mismatch；原 L0 例外保留在 `__cause__`）。
- 未登入 / 權限 / 網路 / 找不到 Sheet 等 → 原樣上拋（§1，不吞成「未分類」）。

⛔ 零寫入、零 streamlit import、不新增 scope／credential（沿用 `gsheet_portfolio` 的本人 OAuth client 與快取）。
⚠️ 雙通道：呼叫端必須固定傳**綁定的那本** sheet_id（`session_binding_snapshot()`），本檔不自行挑通道。
⛔ 本批不接 builder、不接 UI（接線另批）。
"""
from __future__ import annotations

from shared.sheet_id import sanitize_sheet_id
from shared.strategy_class_schema import (
    STATUS_NOT_BOUND,
    STATUS_WORKSHEET_MISSING,
    STRATEGY_HEADERS,
    STRATEGY_WORKSHEET_NAME,
    StrategyReadResult,
    StrategySchemaMismatchError,
    empty_result,
    parse_strategy_records,
)
from src.data.portfolio import gsheet_portfolio as _gsp


def read_strategy_classes(*, sheet_id: str | None) -> StrategyReadResult:
    """讀一本 Sheet 的策略分類（唯讀）。見檔頭。sheet_id 非 str 且非 None → `TypeError`；不合法 → `ValueError`。"""
    if sheet_id is not None and type(sheet_id) is not str:
        raise TypeError(f"sheet_id 必須是 str 或 None：{type(sheet_id).__name__}")
    if sheet_id is None or not sheet_id.strip():
        return empty_result(STATUS_NOT_BOUND)
    sid = sanitize_sheet_id(sheet_id)
    if not sid:
        # QA-B：有給值但不是合法 Sheet ID（例：發布連結 /d/e/…、"e"）＝ 呼叫端帶了壞的綁定，
        # 不是「沒綁定」⇒ Fail Loud（與 derive_portfolio_id 一致；DEC-083 B3 明確拒絕）。⛔ 不回顯原值。
        raise ValueError("read_strategy_classes: sheet_id 不是合法的 Google Sheet ID")
    try:
        values = _gsp.read_worksheet_values(STRATEGY_WORKSHEET_NAME, sheet_id=sid)
    except _gsp.SheetWorksheetMissingError:
        return empty_result(STATUS_WORKSHEET_MISSING)
    try:
        return parse_strategy_records(values, sheet_id=sid)
    except StrategySchemaMismatchError as exc:
        raise _gsp.SheetSchemaMismatchError(STRATEGY_WORKSHEET_NAME, STRATEGY_HEADERS) from exc
