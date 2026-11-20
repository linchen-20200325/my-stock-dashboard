"""tests/test_a_sec1110_revert_chain.py — A-SEC-1110(#1110)NAS 中繼站認證 fail closed + 502 脫敏 的還原鏈新頭節。

═══ 為什麼需要 ═══════════════════════════════════════════════════════════
`src/data/proxy/nas_server.py` 被 `tests/test_batch_z40.py` 以「新寫法 → 舊寫法」錨點還原成基底 `ba470b9b`
的 sha256（`test_reverted_source_equals_base_file[src/data/proxy/nas_server.py]`，並供其 `_nas_module(pre=True)`
的「修前」對照使用）。本批改動落在該檔，使舊還原體不再等於基底 ⇒ 在鏈頭**往前接一節**：
`i1208pr2_revert_for`（原鏈頭）開頭先呼叫本節的 `a_sec1110_revert_for`
（比照 `i1208_revert_for` 開頭先呼叫 `i1208pr2_revert_for` 的作法；⛔ 不動任何舊表與舊基底 sha、
不放寬任何斷言、不 skip）。有意識的接鏈，不是漏改。

基底 ＝ 本批開工前的 `535c1484`（origin/main）；`git show 535c1484:src/data/proxy/nas_server.py | sha256sum`
實算後寫死，測試不依賴 git。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

A_SEC1110_BASE_SHA = {
    'src/data/proxy/nas_server.py': '4809756ae8bfc5742ae86ef66a219a002c429f649a6255e61756773bdf92ed72',
}

_NEW_WARN = '''# v19.86 安全（第八份 review D）:未設 NAS_API_KEY 原為 `/proxy` `/api/fetch` 無認證
# 開放,任何人可把本機當跳板(SSRF)。A-SEC-1110(#1110):改為 fail closed ——
# 未設 NAS_API_KEY 時,受 _auth 保護的端點一律回 503(不得匿名放行);`/`(health)
# 維持原狀。此處仍於啟動時大聲警告。無論有無 key,下方 _assert_public_url 都會
# 封鎖內網/metadata 目標。
if not _API_KEY:
    print("=" * 72, flush=True)
    print("⚠️  [NAS 安全警告] NAS_API_KEY 未設定 — /proxy 與 /api/fetch 將一律"
          "回 503(fail closed,拒絕服務)!", flush=True)
    print("    請設定高強度金鑰後重啟,服務才會恢復:", flush=True)
    print('    export NAS_API_KEY="<高強度隨機字串>"', flush=True)
    print("=" * 72, flush=True)
'''
_OLD_WARN = '''# v19.86 安全（第八份 review D）:未設 NAS_API_KEY = `/proxy` `/api/fetch` 無認證
# 開放,任何人可把本機當跳板(SSRF)。此處大聲警告;硬性「未設 key 拒絕啟動」屬
# 部署行為變更,列 user 決定(見 PR 描述)。無論有無 key,下方 _assert_public_url
# 都會封鎖內網/metadata 目標,先堵住 SSRF 最危險面。
if not _API_KEY:
    print("=" * 72, flush=True)
    print("⚠️  [NAS 安全警告] NAS_API_KEY 未設定 — /proxy 與 /api/fetch 目前"
          "「無認證開放」!", flush=True)
    print("    任何知道本站網址者都可驅動本機發出 HTTP 請求。強烈建議:", flush=True)
    print('    export NAS_API_KEY="<高強度隨機字串>" 後重啟。', flush=True)
    print("    (SSRF 內網存取已由 _assert_public_url 封鎖,但認證仍應設定)", flush=True)
    print("=" * 72, flush=True)
'''
_NEW_AUTH = '''_PROXY_502_DETAIL = "中繼失敗"  # /proxy 502 對外固定文案(A-SEC-1110:禁含 URL/例外原文)


# ── 認證 ──────────────────────────────────────────────────────────────────
def _auth(x_api_key: str = Header(None)):
    # A-SEC-1110:未設 NAS_API_KEY ⇒ fail closed(503 固定文案,不得匿名放行)。
    if not _API_KEY:
        raise HTTPException(status_code=503,
                            detail="Service unavailable: server auth not configured")
    # key 已設:常數時間比對(hmac.compare_digest);以 utf-8 bytes 比,避免
    # 非 ASCII header 值使 compare_digest(str) 丟 TypeError;缺 header ⇒ 401。
    if not x_api_key or not hmac.compare_digest(
            x_api_key.encode("utf-8"), _API_KEY.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid API Key")
'''
_OLD_AUTH = '''# ── 認證 ──────────────────────────────────────────────────────────────────
def _auth(x_api_key: str = Header(None)):
    if _API_KEY and x_api_key != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
'''
_NEW_502 = '''        # A-SEC-1110:對外一律固定脫敏文案(不含 URL / 例外原文 / 內網 IP);詳情僅留上方 server log。
        raise HTTPException(status_code=502, detail=_PROXY_502_DETAIL)
'''
_OLD_502 = '''        raise HTTPException(status_code=502, detail=f'中繼失敗: {_e_px}')
'''

A_SEC1110_REVERT_PAIRS = {
    'src/data/proxy/nas_server.py': (
        ('import hmac\nimport ipaddress\n', 'import ipaddress\n'),
        (_NEW_WARN, _OLD_WARN),
        (_NEW_AUTH, _OLD_AUTH),
        (_NEW_502, _OLD_502),
    ),
}


def _rel(file_path) -> str:
    p = Path(file_path)
    return (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()


def a_sec1110_revert_for(file_path, code: str) -> str:
    """給模組 `__file__`（或 repo 相對路徑）與原始碼，換回 A-SEC-1110 之前的寫法（無 pair 則原樣；只套一次）。"""
    rel = _rel(file_path)
    pairs = A_SEC1110_REVERT_PAIRS.get(rel, ())
    if not pairs:
        return code
    counts = [code.count(new) for new, _old in pairs]
    if all(c == 0 for c in counts):
        return code          # 已被前一個掛點換回
    assert all(c == 1 for c in counts), (
        f"{rel} A-SEC-1110 還原組錨點漂移（各組出現次數 {counts}；應全 1 或全 0）—— 須重產還原組")
    for new, old in pairs:
        code = code.replace(new, old)
    return code


def test_a_sec1110_revert_is_exact_base_source():
    assert set(A_SEC1110_REVERT_PAIRS) == set(A_SEC1110_BASE_SHA)
    for rel in sorted(A_SEC1110_REVERT_PAIRS):
        code = a_sec1110_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == A_SEC1110_BASE_SHA[rel], rel


def test_a_sec1110_revert_is_idempotent():
    for rel in sorted(A_SEC1110_REVERT_PAIRS):
        once = a_sec1110_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert a_sec1110_revert_for(rel, once) == once, rel


def test_a_sec1110_link_is_reached_from_previous_head():
    """接鏈本身：原鏈頭 `i1208pr2_revert_for` 必須先套本節，否則 Z40 對 nas_server.py 的基底 sha 會紅。"""
    from tests.test_issue1208_pr2_revert_chain import i1208pr2_revert_for
    for rel in sorted(A_SEC1110_REVERT_PAIRS):
        code = (REPO / rel).read_text(encoding="utf-8")
        assert i1208pr2_revert_for(rel, code) == a_sec1110_revert_for(rel, code), rel
