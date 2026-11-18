"""OneBrain OB-1 離線測試用 FakeProvider（不是測試檔，不會被收集；**僅限 tests/ 使用**）。

模式：`echo`（回規則式草稿）、`timeout`／`rate_limit`／`unavailable`／`invalid_response`（raise 對應 ProviderError）、
`boom`（raise 非 ProviderError 的 RuntimeError）、`payload`（原樣回傳任意物件，用來餵偽造／垃圾輸出）。
無網路、無時鐘、無 sleep；`calls` 為呼叫計數。
"""
from __future__ import annotations

from typing import Any

from shared.onebrain_provider import ProviderError, ProviderErrorKind, ProviderRequest
from src.services.decision_digest_summary import compose_rule_draft

MODE_ECHO = "echo"
MODE_BOOM = "boom"
MODE_PAYLOAD = "payload"
ERROR_MODES = tuple(k.value for k in ProviderErrorKind)
ALL_MODES = (MODE_ECHO, MODE_BOOM, MODE_PAYLOAD, *ERROR_MODES)


class FakeProvider:
    def __init__(self, mode: str = MODE_ECHO, payload: Any = None) -> None:
        if mode not in ALL_MODES:
            raise ValueError(f"未知 FakeProvider 模式：{mode!r}")
        self.mode, self.payload, self.calls = mode, payload, 0
        self.requests: list = []

    def propose_summary(self, request: ProviderRequest):
        self.calls += 1
        self.requests.append(request)
        if self.mode == MODE_ECHO:
            return compose_rule_draft(request.digest)
        if self.mode in ERROR_MODES:
            raise ProviderError(ProviderErrorKind(self.mode), "fake")
        if self.mode == MODE_BOOM:
            raise RuntimeError("fake boom")
        return self.payload
