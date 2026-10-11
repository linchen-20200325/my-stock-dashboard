"""shared/http_diag.py — 外部 HTTP 回應「診斷用 body 片段」的 L0 helper(批 Z39)。

用途:L1 fetcher 在「回應格式不對 / 解析 0 筆 / 例外」時,把 response body **前
`LOG_BODY_HEAD_CHARS` 字**印進 log 供排查(例:TPEx 改版 / 擋爬時回 HTML 錯誤頁)。

§資安:**只印 body**,不碰 headers / proxy URL / token;且一律先過
`shared.secret_scrub.scrub_secrets` + 本檔 `scrub_session_values`(Cookie / Set-Cookie 值、
JSESSIONID / sessionid 類 session 值;批 Z39 修正 QA N4)再截斷 —— 先截再洗可能把一段金鑰切成洗不到的半截。
為免對 MB 級 body 跑整套正則,先取前 `_SCRUB_WINDOW_CHARS` 字再洗、再截到 500。
純函式、零 I/O(只讀已拿到的 response 物件屬性),不 import streamlit。
"""
from __future__ import annotations

import re

from shared.secret_scrub import scrub_secrets

#: 診斷 log 印出的 body 字數上限(客戶 2026-10-11 Q-z28 診斷要求:前 500 字)。
LOG_BODY_HEAD_CHARS: int = 500
#: 洗秘密前先取的視窗(> LOG_BODY_HEAD_CHARS,避免洗前截斷把金鑰切半)。
_SCRUB_WINDOW_CHARS: int = 4000
#: 遮罩字樣(同 `shared.secret_scrub` 的 `***`,不加說明字)。
_MASK: str = "***"
#: 批 Z39 修正(QA N4):擋爬 / 錯誤頁常把 request / response header 回顯在 body 裡。
#: `Cookie:` / `Set-Cookie:` 整個值(到行尾或 HTML 標籤前)遮掉。
_COOKIE_HEADER_RE = re.compile(r"(?i)\b((?:set-)?cookie)(\s*[:=]\s*)[^\r\n<]*")
#: session id 類 `name=value`(JSESSIONID / sessionid / session_id / PHPSESSID /
#: ASP.NET_SessionId / connect.sid / sid)— 只遮值。
_SESSION_KV_RE = re.compile(
    r"(?i)\b((?:jsessionid|phpsessid|asp\.net_sessionid|connect\.sid|"
    r"session[_-]?id|sessid|sid))(\s*[=:]\s*)([^;&\s\"'<>,]+)")


#: 批 Z41(Z39 QA 殘留缺口):JSON / dict repr 內**帶引號的 key**(`{"Cookie": "a=b"}`、
#: `{'sessionid':'zzz'}`、`{"Set-Cookie": ["a=b", "c=d"]}`、`{"sid": 12345}`)—— 上面兩條要求 key 後
#: 直接接 `:`/`=`,遇到收尾引號就漏遮。值為字串 → 遮引號內;陣列(不巢狀)→ 遮整個 `[...]`;
#: 其他純量 → 遮到 `,` / `}` / `]` / 空白。
_JSON_SECRET_KEY_RE = re.compile(
    r"""(?i)(["'])((?:set-)?cookie|jsessionid|phpsessid|asp\.net_sessionid|connect\.sid|"""
    r"""session[_-]?id|sessid|sid)\1(\s*:\s*)"""
    r"""(?:(["'])(?:\\.|(?!\4)[^\\])*\4|\[[^\[\]]*\]|[^,}\]\s]+)""")


def _mask_json_secret(m) -> str:
    """JSON key 命中 → 保留 key 與引號樣式,值改 `"***"`(字串值沿用原引號)。"""
    q = m.group(4) or '"'
    return f"{m.group(1)}{m.group(2)}{m.group(1)}{m.group(3)}{q}{_MASK}{q}"


def scrub_session_values(text: str) -> str:
    """遮蔽 Cookie / Set-Cookie 值與 session id 類值(批 Z39 修正 QA N4;批 Z41 補 JSON 帶引號 key;純函式)。"""
    text = _JSON_SECRET_KEY_RE.sub(_mask_json_secret, text)
    text = _COOKIE_HEADER_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{_MASK}", text)
    return _SESSION_KV_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{_MASK}", text)


def scrubbed_body_head(resp) -> str:
    """response → 洗過秘密的 body 前 500 字。無 `.text` / 讀取失敗 → 說明字串(不炸)。"""
    if resp is None:
        return "<no response>"
    try:
        _text = resp.text
    except Exception as _e:  # noqa: BLE001 — 診斷 helper 不得讓 fetcher 多炸一次
        return f"<body 讀取失敗: {type(_e).__name__}>"
    if _text is None:
        return "<empty body>"
    if isinstance(_text, (bytes, bytearray)):
        _text = bytes(_text[:_SCRUB_WINDOW_CHARS]).decode("utf-8", "replace")
    return scrub_session_values(
        scrub_secrets(str(_text)[:_SCRUB_WINDOW_CHARS]))[:LOG_BODY_HEAD_CHARS]
