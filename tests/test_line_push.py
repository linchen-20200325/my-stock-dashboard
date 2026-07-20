# -*- coding: utf-8 -*-
"""tests/test_line_push.py — L1 LINE 推播 sender 守衛(morning_brief 早報用)。

守 src/data/notify/line_push.push_line:
- 正常送出:打對 URL / Bearer header / body(to + messages[type=text])
- 缺 token/user id → RuntimeError;空訊息 → ValueError(§1 不亂送)
- 失敗重試(HTTP 非 200 / 網路例外),最終仍敗 → raise(§1 Fail Loud,cron 紅燈)
- 訊息 > 5000 字切多則;單次 push > 5 則分批

三個最容易出錯的輸入(§6):
1. 缺 secrets(本機/忘了設)→ 明確 raise,不靜默吞
2. 超長早報(> 5000)→ 切段不可掉字、不可超 LINE 上限
3. LINE 暫時 5xx → 重試而非一次就死
"""
from __future__ import annotations

import pytest

from src.data.notify import line_push as lp
from src.data.notify.line_push import push_line, _chunk_text


class _Resp:
    def __init__(self, status=200, text="{}"):
        self.status_code = status
        self.text = text


def _recorder(responses):
    """回傳一個假 requests.post,依序吐 responses(Exception 則 raise),並記錄呼叫。"""
    seq = list(responses)
    calls = []

    def _post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json})
        r = seq.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    _post.calls = calls
    return _post


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """重試退避 sleep mock 掉,測試不真的等。"""
    monkeypatch.setattr(lp.time, "sleep", lambda *_a, **_k: None)


# ══════════════════════════════════════════════════════════════
# 正常送出
# ══════════════════════════════════════════════════════════════
def test_success_posts_correct_payload(monkeypatch):
    post = _recorder([_Resp(200)])
    monkeypatch.setattr(lp.requests, "post", post)
    n = push_line("早安,測試", token="TOK", to="U123")
    assert n == 1
    assert len(post.calls) == 1
    c = post.calls[0]
    assert c["url"] == "https://api.line.me/v2/bot/message/push"
    assert c["headers"]["Authorization"] == "Bearer TOK"
    assert c["json"]["to"] == "U123"
    assert c["json"]["messages"] == [{"type": "text", "text": "早安,測試"}]


def test_reads_token_from_env(monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "ENVTOK")
    monkeypatch.setenv("LINE_USER_ID", "ENVU")
    post = _recorder([_Resp(200)])
    monkeypatch.setattr(lp.requests, "post", post)
    push_line("hi")
    assert post.calls[0]["headers"]["Authorization"] == "Bearer ENVTOK"
    assert post.calls[0]["json"]["to"] == "ENVU"


# ══════════════════════════════════════════════════════════════
# 拒送(§1 不亂送)
# ══════════════════════════════════════════════════════════════
def test_missing_token_raises(monkeypatch):
    monkeypatch.delenv("LINE_CHANNEL_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("LINE_USER_ID", raising=False)
    with pytest.raises(RuntimeError, match="缺 token"):
        push_line("hi")


def test_empty_text_raises():
    with pytest.raises(ValueError):
        push_line("   ", token="T", to="U")


# ══════════════════════════════════════════════════════════════
# 重試(§1 Fail Loud)
# ══════════════════════════════════════════════════════════════
def test_retry_then_success(monkeypatch):
    post = _recorder([_Resp(500, "err"), _Resp(500, "err"), _Resp(200)])
    monkeypatch.setattr(lp.requests, "post", post)
    push_line("hi", token="T", to="U", retry=3)
    assert len(post.calls) == 3          # 兩次失敗 + 第三次成功


def test_network_exception_retried(monkeypatch):
    post = _recorder([ConnectionError("boom"), _Resp(200)])
    monkeypatch.setattr(lp.requests, "post", post)
    push_line("hi", token="T", to="U", retry=3)
    assert len(post.calls) == 2


def test_retry_exhausted_raises(monkeypatch):
    post = _recorder([_Resp(500, "e"), _Resp(500, "e"), _Resp(500, "e")])
    monkeypatch.setattr(lp.requests, "post", post)
    with pytest.raises(RuntimeError, match="推播失敗"):
        push_line("hi", token="T", to="U", retry=3)
    assert len(post.calls) == 3


# ══════════════════════════════════════════════════════════════
# 切段 / 分批
# ══════════════════════════════════════════════════════════════
def test_chunk_prefers_newline():
    text = "A" * 4990 + "\n" + "B" * 20      # 換行落在 5000 窗口內
    chunks = _chunk_text(text, size=5000)
    assert chunks[0] == "A" * 4990           # 在換行處切,不含 \n
    assert chunks[1] == "B" * 20


def test_long_text_split_into_multiple_messages(monkeypatch):
    post = _recorder([_Resp(200)])
    monkeypatch.setattr(lp.requests, "post", post)
    n = push_line("X" * 12000, token="T", to="U")   # 無換行 → 硬切 5000*2 + 2000 = 3 則
    assert n == 3
    assert len(post.calls) == 1                      # 3 ≤ 5 → 單次 push
    msgs = post.calls[0]["json"]["messages"]
    assert len(msgs) == 3
    assert all(len(m["text"]) <= 5000 for m in msgs)


def test_over_five_chunks_batched(monkeypatch):
    post = _recorder([_Resp(200), _Resp(200)])
    monkeypatch.setattr(lp.requests, "post", post)
    n = push_line("Y" * 30000, token="T", to="U")   # 6 則 → 分 2 次 push(5 + 1)
    assert n == 6
    assert len(post.calls) == 2
    assert len(post.calls[0]["json"]["messages"]) == 5
    assert len(post.calls[1]["json"]["messages"]) == 1
