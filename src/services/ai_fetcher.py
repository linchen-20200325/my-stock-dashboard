"""src/services/ai_fetcher.py — Gemini API 統一呼叫 wrapper(L3 service)。

A1 v18.386 深層拔毒:統一原本 5 處散落 Gemini call(ai_engine × 3 +
financial_health_engine × 1 + macro_state_locker × 1),retry/payload/timeout/
model fallback 邏輯集中。

caller 介面:
    text = post_gemini(api_key, prompt, ...)
    return None 表示所有 model 都失敗(caller 自決失敗 message / emoji header)。

範例:
    # ai_engine 戰情室(原 call 1)
    text = post_gemini(api_key, prompt, models=AI_MODELS_FULL,
                       retries_per_model=3, retry_after_parse=True, timeout=90)
    if text:
        return f"### 🧬 AI 戰情室\n\n{text}\n\n**model**: {used}"

    # financial_health(原 call 4)
    text = post_gemini(api_key, prompt, persona=_PERSONA, temperature=0.2,
                       max_tokens=1200, timeout=120,
                       models=FIN_HEALTH_MODELS, retries_per_model=1)
"""
from __future__ import annotations

import re
import time
from typing import Optional


_GEMINI_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/{api_ver}/models/{model}:generateContent"
)


def _build_payload(prompt: str, persona: Optional[str], temperature: float,
                   max_tokens: int,
                   extra_generation_config: Optional[dict] = None,
                   safety_settings: Optional[list] = None) -> dict:
    """組 Gemini request body(可選 systemInstruction / 額外 generationConfig / safetySettings)。"""
    gen_cfg = {"temperature": temperature, "maxOutputTokens": max_tokens}
    if extra_generation_config:
        gen_cfg.update(extra_generation_config)  # 如 topP, topK
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": gen_cfg,
    }
    if persona:
        body["systemInstruction"] = {"parts": [{"text": persona}]}
    if safety_settings:
        body["safetySettings"] = safety_settings
    return body


def _extract_text(result: dict) -> Optional[str]:
    """從 Gemini response 抽 text;若 finishReason==SAFETY 或無 text 回 None。"""
    cands = result.get("candidates", [])
    if not cands:
        return None
    cand0 = cands[0]
    parts = cand0.get("content", {}).get("parts", [])
    if parts and parts[0].get("text"):
        return parts[0]["text"]
    return None  # SAFETY block or empty


def _parse_retry_after(response, attempt: int) -> float:
    """429 retry-after parse;失敗回 exponential backoff(min 10s 上限)。"""
    try:
        err_msg = response.json().get("error", {}).get("message", "")
        m = re.search(r"Please retry in ([0-9.]+)s", err_msg)
        return min(10, float(m.group(1)) if m else (2 ** attempt) * 2)
    except Exception:
        return min(10, (2 ** attempt) * 2)


def post_gemini(
    api_key: str,
    prompt: str,
    *,
    models: list[str],
    persona: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    timeout: int = 90,
    retries_per_model: int = 3,
    retry_after_parse: bool = True,
    inter_model_sleep: float = 3.0,
    headers: Optional[dict] = None,
    extra_generation_config: Optional[dict] = None,
    safety_settings: Optional[list] = None,
) -> tuple[Optional[str], Optional[str]]:
    """統一 Gemini API call。

    回傳 (text, model_used):
        成功 → (text, model_name)
        全失敗 → (None, last_error_str)

    參數:
        models: model fallback list(依序嘗試)
        persona: 選填 systemInstruction text
        retry_after_parse: True → 429 解析 retry-after 等待;False → 直接 sleep(5)
        inter_model_sleep: 每切換 model 間隔(避速率限制)
    """
    import requests  # lazy import(測試 mock-friendly)

    headers = headers or {"Content-Type": "application/json"}
    payload = _build_payload(prompt, persona, temperature, max_tokens,
                              extra_generation_config=extra_generation_config,
                              safety_settings=safety_settings)
    last_error: Optional[str] = None

    for midx, model_name in enumerate(models):
        if midx > 0 and inter_model_sleep > 0:
            time.sleep(inter_model_sleep)
        try:
            api_ver = "v1beta" if (model_name.startswith("gemini-3") or "preview" in model_name) else "v1"
            url = _GEMINI_URL_TEMPLATE.format(api_ver=api_ver, model=model_name)

            for attempt in range(retries_per_model):
                if attempt > 0:
                    time.sleep(min(15, 3 * (2 ** attempt)))

                response = requests.post(
                    f"{url}?key={api_key}", headers=headers, json=payload, timeout=timeout,
                )

                if response.status_code == 200:
                    text = _extract_text(response.json())
                    if text:
                        return text, model_name
                    last_error = f"{model_name} HTTP 200 但回傳格式異常或 SAFETY block"
                    break  # 跳出 retry,切下個 model

                if response.status_code == 429:
                    if retry_after_parse:
                        wait_s = _parse_retry_after(response, attempt)
                    else:
                        wait_s = 5
                    last_error = f"{model_name} HTTP 429 (attempt {attempt+1}/{retries_per_model})"
                    time.sleep(wait_s)
                    continue  # retry 同 model

                # 暫時性 5xx(500/502/503/504,如 Gemini 過載 503)→ 退避重試同 model(同 429)
                if response.status_code in (500, 502, 503, 504):
                    last_error = f"{model_name} HTTP {response.status_code} (attempt {attempt+1}/{retries_per_model})"
                    time.sleep(min(15, 3 * (2 ** attempt)))
                    continue
                # 4xx(400/403/404 等)永久性設定/prompt 錯 → 跳下個 model(重試無用)
                last_error = f"{model_name} HTTP {response.status_code}: {response.text[:300]}"
                break

        except Exception as e:
            last_error = f"{model_name} Exception: {type(e).__name__}: {e}"
            continue

    return None, last_error
