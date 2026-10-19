#!/usr/bin/env python3
"""scripts/risk_cap_wif_auth_check.py — VN1-STORE「WIF auth-only」：只驗證 GitHub Actions 換得到 writer 身分。

依據：DEC-064 G1（writer＝GitHub OIDC＋Google Workload Identity Federation impersonate `risk-cap-writer`，
⛔ 禁止 writer JSON key）；`docs/vnext/VN1_STORE_CREDENTIAL_SPEC.md` 第 6 節第 1～4 點。
⛔ production 寫入**仍未核准**（DEC-063）—— 本腳本**完全不碰任何 Google Sheet**。

做什麼
------
1. 前置拒絕（exit 2，⛔ 不發任何網路請求）：
   - `GOOGLE_APPLICATION_CREDENTIALS` 沒設／檔案讀不到／不是 JSON；
   - 憑證檔 `type` 不是 `external_account`（`service_account` ＝ writer JSON key ⇒ DEC-064 G1 禁止）；
   - 憑證要 impersonate 的 SA 不是 `--expect-sa`。
   只讀 `type` 一個欄位；⛔ 永不印出檔案內容（內含 GitHub OIDC 請求 token）。
2. `google.auth.default(scopes=[userinfo.email])` → `creds.refresh(Request())`：
   走 STS token exchange（GitHub OIDC subject token → federated token）＋ IAM Credentials
   `generateAccessToken`（impersonate writer SA）。scope 刻意只開 `userinfo.email`
   （最小權限；⛔ 刻意**不**要 `spreadsheets`）。
3. 把 access token 以 **POST form body**（⛔ 不放 URL）送 `https://oauth2.googleapis.com/tokeninfo`，
   核對 `email` ＝ 預期 SA、`email_verified`、`expires_in` > 0、scope 不含試算表／雲端硬碟。

輸出（只有這些）：PASS／FAIL、impersonate 到的 email、project_id（有才印）、token 剩餘壽命（約略秒數）、
失敗時的 stage 與例外**類別名**。⛔ 不印 token、⛔ 不印例外訊息（可能夾帶 token 或憑證細節）、
⛔ 不寫任何檔案、⛔ 不 import gspread、⛔ 不呼叫任何 Sheets／Drive API。

結束碼：0 ＝ PASS；1 ＝ FAIL（換身分或驗證身分失敗）；2 ＝ 設定被拒（沒試著換身分）。

用法（只在 `.github/workflows/risk_cap_history_poc.yml` 的 `wif_auth_only` job 內有意義）::

    python scripts/risk_cap_wif_auth_check.py --expect-sa risk-cap-writer@<project>.iam.gserviceaccount.com
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

EXIT_PASS = 0
EXIT_FAIL_AUTH = 1
EXIT_REFUSED_CONFIG = 2

#: ADC 憑證檔路徑的環境變數（`google-github-actions/auth` 以 `create_credentials_file` 匯出）。
GAC_ENV_VAR = "GOOGLE_APPLICATION_CREDENTIALS"
#: 唯一接受的憑證檔類型（WIF 產生的短效 federation 設定檔）。
ALLOWED_CREDENTIAL_TYPE = "external_account"
#: 最小權限驗證 scope：只夠 tokeninfo 回 email。⛔ 不含 spreadsheets／drive／cloud-platform。
VERIFY_SCOPES: tuple[str, ...] = ("https://www.googleapis.com/auth/userinfo.email",)
TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
#: tokeninfo 回的 scope 若含這些字樣 ⇒ token 權限比要求的大 ⇒ FAIL（最小權限守衛）。
FORBIDDEN_SCOPE_MARKERS: tuple[str, ...] = ("spreadsheets", "drive", "cloud-platform")
HTTP_TIMEOUT_S = 20

STAGE_LOAD = "load_credentials"
STAGE_STS = "sts_exchange"          # 含取得 GitHub OIDC subject token
STAGE_IMPERSONATION = "impersonation"
STAGE_REFRESH = "refresh"           # refresh 失敗但分不出是哪一段
STAGE_TOKENINFO = "tokeninfo"

#: 每個 stage 一句固定的人話（⛔ 永不拼接例外訊息）。
STAGE_MESSAGES: Mapping[str, str] = {
    STAGE_LOAD: "載入 ADC 憑證失敗（google.auth.default）",
    STAGE_STS: "STS token exchange 失敗（GitHub OIDC token 未取得、或 WIF provider／attribute condition 拒絕）",
    STAGE_IMPERSONATION: "impersonate writer SA 失敗（generateAccessToken 被拒：workloadIdentityUser 綁定／API 啟用）",
    STAGE_REFRESH: "取得 access token 失敗（無法判定是 STS 還是 impersonation 階段）",
    STAGE_TOKENINFO: "tokeninfo 驗證身分失敗",
}

DefaultFn = Callable[[Sequence[str]], "tuple[Any, str | None]"]
RequestFactory = Callable[[], Any]
PostFn = Callable[[str, Mapping[str, str], int], "tuple[int, Any]"]


class ConfigRefused(Exception):
    """設定不合格 ⇒ 不嘗試換身分（exit 2）。`message` 為固定文字，⛔ 不含檔案內容。"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class AuthCheckResult:
    """一次檢查的結論（全部欄位都可以印；⛔ 沒有 token 欄位）。"""

    exit_code: int
    stage: str = ""
    error_class: str = ""
    message: str = ""
    email: str = ""
    project_id: str = ""
    lifetime_s: int | None = None
    scope: str = ""


# ══════════════════════════════════════════════════════════════════════
# 預設依賴（測試以假物件注入）
# ══════════════════════════════════════════════════════════════════════
def _default_fn(scopes: Sequence[str]) -> tuple[Any, str | None]:
    import google.auth

    return google.auth.default(scopes=list(scopes))


def _request_factory() -> Any:
    import google.auth.transport.requests

    return google.auth.transport.requests.Request()


def _http_post(url: str, data: Mapping[str, str], timeout: int) -> tuple[int, Any]:
    """POST form body（`data=`，⛔ 不放 query string）。回 (HTTP status, 解析後 JSON 或 None)。"""
    import requests

    resp = requests.post(url, data=dict(data), timeout=timeout)
    try:
        body = resp.json()
    except ValueError:
        body = None
    return resp.status_code, body


# ══════════════════════════════════════════════════════════════════════
# 各段
# ══════════════════════════════════════════════════════════════════════
def check_credentials_file(environ: Mapping[str, str]) -> str:
    """確認 ADC 憑證檔是 WIF 的 `external_account`。回傳檔案路徑；不合格 ⇒ `ConfigRefused`。

    ⛔ 只讀 `type` 欄位，⛔ 錯誤訊息不含檔案內容或解析錯誤原文。
    """
    path = environ.get(GAC_ENV_VAR, "")
    if not path:
        raise ConfigRefused(f"{GAC_ENV_VAR} 未設定（auth step 沒有產生 ADC 憑證檔）→ 拒絕")
    try:
        with open(path, encoding="utf-8") as fh:
            info = json.load(fh)
    except OSError:
        raise ConfigRefused(f"{GAC_ENV_VAR} 指向的檔案讀不到 → 拒絕") from None
    except ValueError:
        raise ConfigRefused(f"{GAC_ENV_VAR} 指向的檔案不是合法 JSON → 拒絕") from None
    cred_type = info.get("type") if isinstance(info, dict) else None
    if cred_type == "service_account":
        raise ConfigRefused("憑證檔是 service_account JSON key —— writer JSON key 依 DEC-064 G1 禁止；"
                            "只接受 WIF 產生的 external_account 憑證 → 拒絕")
    if cred_type != ALLOWED_CREDENTIAL_TYPE:
        raise ConfigRefused(f"憑證檔類型不是 {ALLOWED_CREDENTIAL_TYPE}（只接受 WIF 短效憑證）→ 拒絕")
    return path


#: STS 段（取 GitHub OIDC subject token ＋ token exchange）在 google-auth 內的函式名。
_STS_FRAME_NAMES: frozenset[str] = frozenset({"retrieve_subject_token", "get_subject_token", "exchange_token"})


def classify_refresh_failure(exc: BaseException, fallback: str) -> str:
    """依 traceback 經過的模組判定失敗在哪一段（⛔ 不看例外訊息）。

    google-auth 的 impersonation 路徑是「impersonated_credentials.refresh → 來源 external_account 憑證
    refresh（取 subject token ＋ STS exchange）→ generateAccessToken」，所以：
    經過 STS／subject token 程式 ⇒ `sts_exchange`；只經過 impersonated_credentials ⇒ `impersonation`。
    """
    frames: list[tuple[str, str]] = []
    tb = exc.__traceback__
    while tb is not None:
        code = tb.tb_frame.f_code
        frames.append((code.co_filename.replace("\\", "/"), code.co_name))
        tb = tb.tb_next
    # ⚠️ 不能用「經過 identity_pool.py」判 STS：url 型 external_account 的 refresh 本身就定義在該檔，
    #   impersonation 失敗的 traceback 也會經過它（2026-10-19 以真 google-auth 2.62 實測抓到）。
    if any(f.endswith("/oauth2/sts.py") or name in _STS_FRAME_NAMES for f, name in frames):
        return STAGE_STS
    if any(f.endswith("/auth/impersonated_credentials.py") for f, _ in frames):
        return STAGE_IMPERSONATION
    return fallback


def _fail(stage: str, exc: BaseException | None = None, *, email: str = "", project_id: str = "",
          extra: str = "") -> AuthCheckResult:
    msg = STAGE_MESSAGES[stage] + (f"：{extra}" if extra else "")
    return AuthCheckResult(exit_code=EXIT_FAIL_AUTH, stage=stage,
                           error_class=type(exc).__name__ if exc is not None else "",
                           message=msg, email=email, project_id=project_id)


def _parse_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def run_check(expected_sa: str, *, environ: Mapping[str, str] | None = None,
              default_fn: DefaultFn = _default_fn, request_factory: RequestFactory = _request_factory,
              post_fn: PostFn = _http_post) -> AuthCheckResult:
    """執行整個檢查並回結論。所有外部依賴可注入；⛔ 回傳值與任何輸出都不含 token。"""
    env = os.environ if environ is None else environ
    if not expected_sa:
        return AuthCheckResult(exit_code=EXIT_REFUSED_CONFIG, stage="config",
                               message="--expect-sa 不得為空 → 拒絕")
    try:
        check_credentials_file(env)
    except ConfigRefused as e:
        return AuthCheckResult(exit_code=EXIT_REFUSED_CONFIG, stage="config", message=e.message)

    try:
        creds, project_id = default_fn(VERIFY_SCOPES)
    except Exception as e:  # noqa: BLE001 —— 只取類別名，⛔ 不印訊息
        return _fail(classify_refresh_failure(e, STAGE_LOAD), e)
    project = str(project_id or "")

    if hasattr(creds, "service_account_email"):
        sa_in_file = getattr(creds, "service_account_email", None)
        if sa_in_file != expected_sa:
            return AuthCheckResult(
                exit_code=EXIT_REFUSED_CONFIG, stage="config", project_id=project,
                message="憑證檔要 impersonate 的 SA 與 --expect-sa 不符（或沒有設定 impersonation）→ 拒絕")

    try:
        creds.refresh(request_factory())
    except Exception as e:  # noqa: BLE001
        return _fail(classify_refresh_failure(e, STAGE_REFRESH), e, project_id=project)

    token = getattr(creds, "token", None)
    if not token or not isinstance(token, str):
        return _fail(STAGE_REFRESH, project_id=project, extra="refresh 後沒有 access token")

    try:
        status, body = post_fn(TOKENINFO_URL, {"access_token": token}, HTTP_TIMEOUT_S)
    except Exception as e:  # noqa: BLE001
        return _fail(STAGE_TOKENINFO, e, project_id=project, extra="請求失敗")
    if status != 200 or not isinstance(body, dict):
        return _fail(STAGE_TOKENINFO, project_id=project, extra=f"HTTP {status}")

    email = str(body.get("email") or "")
    if email != expected_sa:
        return _fail(STAGE_TOKENINFO, email=email, project_id=project, extra="email 與 --expect-sa 不符")
    if str(body.get("email_verified")).lower() != "true":
        return _fail(STAGE_TOKENINFO, email=email, project_id=project, extra="email_verified 不是 true")
    lifetime = _parse_int(body.get("expires_in"))
    if lifetime is None or lifetime <= 0:
        return _fail(STAGE_TOKENINFO, email=email, project_id=project, extra="expires_in 不是正數")
    scope = str(body.get("scope") or "")
    if any(m in scope for m in FORBIDDEN_SCOPE_MARKERS):
        return _fail(STAGE_TOKENINFO, email=email, project_id=project,
                     extra="token scope 超出最小權限（含試算表／雲端硬碟／cloud-platform）")
    return AuthCheckResult(exit_code=EXIT_PASS, email=email, project_id=project, lifetime_s=lifetime,
                           scope=scope)


def format_result(result: AuthCheckResult) -> list[str]:
    """結論 → 輸出行（只含可公開的欄位）。"""
    tag = "[risk_cap_wif_auth_check]"
    if result.exit_code == EXIT_PASS:
        lines = [f"{tag} PASS：GitHub OIDC → WIF STS exchange → impersonation 成功",
                 f"{tag} impersonated_email={result.email}"]
        if result.project_id:
            lines.append(f"{tag} project_id={result.project_id}")
        lines.append(f"{tag} token_lifetime=~{result.lifetime_s}s")
        lines.append(f"{tag} token_scope={result.scope}")
        lines.append(f"{tag} 未讀寫任何 Google Sheet（auth-only）")
        return lines
    label = "REFUSED" if result.exit_code == EXIT_REFUSED_CONFIG else "FAIL"
    lines = [f"{tag} {label}：stage={result.stage}"]
    if result.error_class:
        lines.append(f"{tag} error_class={result.error_class}")
    lines.append(f"{tag} {result.message}")
    if result.email:
        lines.append(f"{tag} tokeninfo_email={result.email}")
    if result.project_id:
        lines.append(f"{tag} project_id={result.project_id}")
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="VN1-STORE WIF auth-only：驗證換得到 writer SA 身分（不碰 Sheet）")
    ap.add_argument("--expect-sa", required=True, help="預期 impersonate 的 service account email")
    args = ap.parse_args(argv)
    result = run_check(args.expect_sa)
    for line in format_result(result):
        print(line)
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
