#!/usr/bin/env python3
"""scripts/risk_cap_wif_negative.py — VN1-STORE WIF 反向測試 R4／R5：換 token **必須被 Google STS 拒絕**。

依據：`docs/vnext/VN1_STORE_CREDENTIAL_SPEC.md` 第 5.2 節（R4：非 main 分支；R5：另一個 workflow 檔，在 main 上）。
WIF provider 的 attribute condition 釘了 repository_id、repository_owner_id、`ref`＝refs/heads/main、
`workflow_ref`＝`<repo>/.github/workflows/risk_cap_history_poc.yml@refs/heads/main`。

做什麼（刻意**不用** `google-github-actions/auth`：auth action 在 STS 被拒時只會讓 step 失敗，分不出「被條件拒絕」
與「設定錯誤／網路錯誤」；本腳本自己發與 auth action 相同的兩個請求，並**只在**看到 attribute condition 拒絕時判 PASS）：

1. 前置拒絕（exit 2，⛔ 不發任何請求）：
   - R4：`GITHUB_REF` 不得是 refs/heads/main；`GITHUB_WORKFLOW_REF` 必須是 PoC workflow 檔（同一個 workflow、只換分支）。
   - R5：`GITHUB_WORKFLOW_REF` 不得含 `/risk_cap_history_poc.yml@`；`GITHUB_REF` 必須是 refs/heads/main
     （只讓 `workflow_ref` 不符，隔離變因）。
   - 缺 `ACTIONS_ID_TOKEN_REQUEST_URL／TOKEN`（job 沒有 `id-token: write`）。
2. 向 GitHub 要 OIDC ID token，audience ＝ `https://iam.googleapis.com/<provider>`（與 auth action v3.0.0
   `src/main.ts` 的預設 `audience` 完全相同）。解碼 payload，只印**非機密** claim：ref、workflow_ref、
   repository_id、event_name；再以 claim 重驗前置條件（claim 不符 ⇒ exit 2、⛔ 不打 STS）。
3. POST `https://sts.googleapis.com/v1/token`（form-urlencoded，與 google-auth `oauth2/sts.py` 相同編碼；欄位與
   auth action `workload_identity_federation.ts#getToken` 相同）：grant_type＝token-exchange、
   subject_token_type＝jwt、requested_token_type＝access_token、audience＝`//iam.googleapis.com/<provider>`、
   scope＝cloud-platform。
4. 判定：
   - **PASS**：HTTP 4xx，且 JSON `error` ∈ {unauthorized_client, invalid_grant}，且 `error_description` 含
     "attribute condition"（不分大小寫）。Google STS 的實際格式（公開回報）：
     `{"error":"unauthorized_client","error_description":"The given credential is rejected by the attribute condition."}`。
   - **FAIL**：任何 2xx（換到了 token —— 大聲警告；⛔ 永不印 token）。
   - **INCONCLUSIVE**：其他一切（網路錯誤、5xx、其他 4xx、無法解析）—— ⛔ 永不當 PASS。

輸出只有：測試 ID、判定、HTTP 狀態碼、`error`、清洗過的 `error_description`、上述四個 claim。
⛔ 不印 OIDC token、STS 回應中的任何 token、請求 token。

結束碼：0 ＝ PASS；1 ＝ FAIL／INCONCLUSIVE；2 ＝ 前置條件被拒（REFUSED）。
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import quote

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_REFUSED = 2

PASS = "PASS"
FAIL = "FAIL"
INCONCLUSIVE = "INCONCLUSIVE"
REFUSED = "REFUSED"

#: 客戶設定的固定值（DEC-064 G1；不是 secret）。
WIF_PROVIDER = ("projects/847745640234/locations/global/workloadIdentityPools/"
                "stock-dashboard-github/providers/github-actions")
#: GitHub OIDC token 的 audience —— 與 google-github-actions/auth v3.0.0 預設相同（`https://iam.googleapis.com/${provider}`）。
OIDC_AUDIENCE = "https://iam.googleapis.com/" + WIF_PROVIDER
#: STS token exchange 的 audience —— 與 auth action 相同（`//iam.googleapis.com/${provider}`）。
STS_AUDIENCE = "//iam.googleapis.com/" + WIF_PROVIDER
STS_URL = "https://sts.googleapis.com/v1/token"
STS_FORM: Mapping[str, str] = {
    "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
    "audience": STS_AUDIENCE,
    "scope": "https://www.googleapis.com/auth/cloud-platform",
    "requested_token_type": "urn:ietf:params:oauth:token-type:access_token",
    "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
}
#: 本 repo 的數字 ID（規格 2.1；公開資訊）—— claim 不符 ⇒ 不是本 repo，測試沒有意義 ⇒ REFUSED。
EXPECTED_REPOSITORY_ID = "1241930464"
EXPECTED_REPOSITORY_OWNER_ID = "285537060"
MAIN_REF = "refs/heads/main"
POC_WORKFLOW_MARKER = "/risk_cap_history_poc.yml@"
#: STS 拒絕且屬 attribute condition 的 error 碼（Google STS 回 OAuth 2.0 錯誤格式）。
ATTRIBUTE_CONDITION_ERRORS: frozenset[str] = frozenset({"unauthorized_client", "invalid_grant"})
ATTRIBUTE_CONDITION_TEXT = "attribute condition"
#: 只印這幾個 claim（非機密）。
PRINT_CLAIMS: tuple[str, ...] = ("ref", "workflow_ref", "repository_id", "event_name")
HTTP_TIMEOUT_S = 20

HttpGet = Callable[[str, Mapping[str, str], int], "tuple[int, Any]"]
HttpPostForm = Callable[[str, Mapping[str, str], int], "tuple[int, Any]"]


@dataclass
class NegativeResult:
    test_id: str
    verdict: str
    message: str = ""
    http: int | None = None
    error: str = ""
    error_description: str = ""
    claims: dict[str, str] = field(default_factory=dict)

    @property
    def exit_code(self) -> int:
        return {PASS: EXIT_PASS, REFUSED: EXIT_REFUSED}.get(self.verdict, EXIT_FAIL)


# ══════════════════════════════════════════════════════════════════════
# 清洗（任何像 token 的字串一律遮蔽）
# ══════════════════════════════════════════════════════════════════════
_TOKENISH = (
    re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]*"),   # JWT
    re.compile(r"ya29\.[A-Za-z0-9_\-.]+"),                                # Google access token
    re.compile(r"[A-Za-z0-9_\-./+=]{32,}"),                               # 其他長串
)


def sanitize(text: Any, limit: int = 300, *, patterns: Sequence[re.Pattern[str]] = _TOKENISH) -> str:
    s = str(text or "")
    for rx in patterns:
        s = rx.sub("[REDACTED]", s)
    s = "".join(ch if ch.isprintable() else " " for ch in s)
    return s[:limit]


def sanitize_claim(text: Any) -> str:
    """OIDC claim（ref／workflow_ref…）本身是公開資訊、常含長路徑 ⇒ 只遮 JWT／access token 形狀，不遮長串。"""
    return sanitize(text, 200, patterns=_TOKENISH[:2])


# ══════════════════════════════════════════════════════════════════════
# 預設依賴（測試以假物件注入）
# ══════════════════════════════════════════════════════════════════════
def _http_get(url: str, headers: Mapping[str, str], timeout: int) -> tuple[int, Any]:
    import requests

    resp = requests.get(url, headers=dict(headers), timeout=timeout)
    try:
        return resp.status_code, resp.json()
    except ValueError:
        return resp.status_code, None


def _http_post_form(url: str, data: Mapping[str, str], timeout: int) -> tuple[int, Any]:
    import requests

    resp = requests.post(url, data=dict(data), timeout=timeout)
    try:
        return resp.status_code, resp.json()
    except ValueError:
        return resp.status_code, None


# ══════════════════════════════════════════════════════════════════════
# 前置條件
# ══════════════════════════════════════════════════════════════════════
def precondition_violation(test_id: str, ref: str, workflow_ref: str) -> str:
    """回傳違反原因（空字串 ＝ 符合）。env 與 OIDC claim 都用它驗。"""
    on_poc = POC_WORKFLOW_MARKER in workflow_ref
    if test_id == "R4":
        if ref == MAIN_REF or not ref:
            return "R4 必須從非 main 分支觸發（ref 是 main 或空白）"
        if not on_poc:
            return "R4 必須在 PoC workflow 檔（risk_cap_history_poc.yml）內執行"
        return ""
    if test_id == "R5":
        if on_poc or not workflow_ref:
            return "R5 不得在 PoC workflow 檔內執行（必須是另一個 workflow 檔）"
        if ref != MAIN_REF:
            return "R5 必須從 main 觸發（只讓 workflow_ref 不符，隔離變因）"
        return ""
    return f"未知的測試 {test_id!r}"


def decode_jwt_claims(jwt: str) -> dict[str, Any]:
    """只解 payload（不驗簽；只用來印非機密 claim 與重驗前置條件）。失敗 ⇒ ValueError（訊息固定）。"""
    parts = jwt.split(".")
    if len(parts) != 3:
        raise ValueError("not a JWT")
    seg = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(seg.encode("ascii")).decode("utf-8"))
    except Exception:  # noqa: BLE001
        raise ValueError("bad JWT payload") from None
    if not isinstance(payload, dict):
        raise ValueError("bad JWT payload")
    return payload


def classify_sts(http: int, body: Any) -> tuple[str, str, str]:
    """STS 回應 → (verdict, error, 清洗過的 error_description)。⛔ 永不回傳 token。"""
    if 200 <= http < 300:
        return FAIL, "", ""
    err = desc = ""
    if isinstance(body, dict):
        err = sanitize(body.get("error"), 64)
        desc = sanitize(body.get("error_description"))
    if (400 <= http < 500 and err in ATTRIBUTE_CONDITION_ERRORS
            and ATTRIBUTE_CONDITION_TEXT in desc.lower()):
        return PASS, err, desc
    return INCONCLUSIVE, err, desc


def run_negative(test_id: str, *, environ: Mapping[str, str] | None = None,
                 http_get: HttpGet = _http_get, http_post_form: HttpPostForm = _http_post_form) -> NegativeResult:
    env = os.environ if environ is None else environ
    bad = precondition_violation(test_id, env.get("GITHUB_REF", ""), env.get("GITHUB_WORKFLOW_REF", ""))
    if bad:
        return NegativeResult(test_id, REFUSED, f"{bad}（依環境變數）→ 拒絕，未發任何請求")
    req_url = env.get("ACTIONS_ID_TOKEN_REQUEST_URL", "")
    req_token = env.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")
    if not req_url or not req_token:
        return NegativeResult(test_id, REFUSED, "缺 ACTIONS_ID_TOKEN_REQUEST_URL／TOKEN（job 沒有 id-token: write）→ 拒絕")

    # 1. GitHub OIDC token（同 @actions/core getIDToken：URL 後接 &audience=）
    sep = "&" if "?" in req_url else "?"
    try:
        status, body = http_get(f"{req_url}{sep}audience={quote(OIDC_AUDIENCE, safe='')}",
                                {"Authorization": f"bearer {req_token}", "Accept": "application/json"},
                                HTTP_TIMEOUT_S)
    except Exception as e:  # noqa: BLE001 —— 只取類別名
        return NegativeResult(test_id, INCONCLUSIVE, f"向 GitHub 要 OIDC token 例外：{type(e).__name__}")
    jwt = body.get("value") if isinstance(body, dict) else None
    if status != 200 or not isinstance(jwt, str) or not jwt:
        return NegativeResult(test_id, INCONCLUSIVE, f"向 GitHub 要 OIDC token 失敗（HTTP {status}）", http=status)
    try:
        claims = decode_jwt_claims(jwt)
    except ValueError:
        return NegativeResult(test_id, INCONCLUSIVE, "OIDC token 無法解碼")
    shown = {k: sanitize_claim(claims.get(k, "")) for k in PRINT_CLAIMS}
    res_claims = dict(shown)

    # 2. 以 claim 重驗（claim 才是 STS 實際看到的值）
    bad = precondition_violation(test_id, str(claims.get("ref", "")), str(claims.get("workflow_ref", "")))
    if bad:
        return NegativeResult(test_id, REFUSED, f"{bad}（依 OIDC claim）→ 拒絕，未打 STS", claims=res_claims)
    if (str(claims.get("repository_id", "")) != EXPECTED_REPOSITORY_ID
            or str(claims.get("repository_owner_id", "")) != EXPECTED_REPOSITORY_OWNER_ID):
        return NegativeResult(test_id, REFUSED, "OIDC claim 的 repository_id／repository_owner_id 不是本 repo → 拒絕，未打 STS",
                              claims=res_claims)

    # 3. STS token exchange（應被拒）
    form = dict(STS_FORM)
    form["subject_token"] = jwt
    try:
        http, sbody = http_post_form(STS_URL, form, HTTP_TIMEOUT_S)
    except Exception as e:  # noqa: BLE001
        return NegativeResult(test_id, INCONCLUSIVE, f"STS 請求例外：{type(e).__name__}", claims=res_claims)
    finally:
        form.clear()
        jwt = ""
    verdict, err, desc = classify_sts(http, sbody)
    sbody = None
    msg = {PASS: "STS 以 attribute condition 拒絕（預期結果）",
           FAIL: "⚠️⚠️⚠️ STS 竟然發出了 token —— WIF attribute condition 沒擋住！立刻停下回報（token 未印出）",
           INCONCLUSIVE: "STS 回應不是 attribute condition 拒絕 —— 不能當通過"}[verdict]
    return NegativeResult(test_id, verdict, msg, http, err, desc, res_claims)


TAG = "[risk_cap_wif_negative]"


def format_result(r: NegativeResult) -> list[str]:
    lines = [f"{TAG} test={r.test_id}"]
    for k in PRINT_CLAIMS:
        if k in r.claims:
            lines.append(f"{TAG} claim.{k}={r.claims[k]}")
    lines.append(f"{TAG} {r.test_id} {r.verdict} http={r.http if r.http is not None else '-'} "
                 f"error={r.error or '-'} error_description={r.error_description or '-'}")
    if r.message:
        lines.append(f"{TAG} {r.message}")
    lines.append(f"{TAG} exit={r.exit_code}")
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="VN1-STORE WIF 反向測試（R4：非 main；R5：另一個 workflow 檔）")
    ap.add_argument("--test", required=True, choices=("R4", "R5"))
    args = ap.parse_args(argv)
    r = run_negative(args.test)
    for line in format_result(r):
        print(line)
    return r.exit_code


if __name__ == "__main__":
    sys.exit(main())
