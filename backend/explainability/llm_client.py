"""
Shared LLM client: OpenAI-compatible API or Google Gemini.

Uses OPENAI_API_KEY + OPENAI_BASE_URL for OpenAI, or GOOGLE_API_KEY for Gemini.
Google API keys (AIza...) work with GOOGLE_API_KEY; the app will use Gemini.
Retries on rate-limit errors (429, quota, RPM/TPM) with exponential backoff.
Daily-quota errors are not retried (clear message returned).
"""
from __future__ import annotations

import os
import re
import time


def _is_rate_limit_error(err: str | None) -> bool:
    """True if the error message indicates a rate limit or quota exhaustion."""
    if not err:
        return False
    err_lower = err.lower()
    return (
        "429" in err
        or "rate limit" in err_lower
        or "quota" in err_lower
        or "resource exhausted" in err_lower
        or "rate_limit_exceeded" in err_lower
        or "insufficient_quota" in err_lower
        or "too many requests" in err_lower
        or "rpm" in err_lower
        or "tpm" in err_lower
    )


def _is_daily_quota_error(err: str | None) -> bool:
    """True if the error is a daily quota limit (retrying won't help until next day)."""
    if not err:
        return False
    err_lower = err.lower()
    return (
        "perday" in err_lower
        or "per day" in err_lower
        or "daily" in err_lower
        or "free_tier_requests" in err_lower
        or "requestsperday" in err_lower
    )


def _parse_retry_after_ms(err: str | None) -> float | None:
    """If the error says 'retry in X ms', return X (seconds). Otherwise None."""
    if not err:
        return None
    match = re.search(r"retry\s+in\s+([\d.]+)\s*ms", err, re.I)
    if match:
        try:
            return float(match.group(1)) / 1000.0
        except ValueError:
            pass
    return None


def call_llm(system: str, user: str, *, temperature: float = 0.2) -> str | None:
    """Returns response text or None. Use call_llm_with_error to get failure reason."""
    content, _ = call_llm_with_error(system, user, temperature=temperature)
    return content


def call_llm_with_error(
    system: str, user: str, *, temperature: float = 0.2
) -> tuple[str | None, str | None]:
    """
    Call an LLM with system and user message. Supports OpenAI and Google Gemini.

    - If GOOGLE_API_KEY is set: use Google Gemini (google-generativeai).
    - Else if OPENAI_API_KEY or OPENAI_BASE_URL is set: use OpenAI client.

    On rate-limit errors (429, quota, RPM/TPM), retries with exponential backoff.
    LLM_RATE_LIMIT_RETRIES (default 3) controls max attempts; backoff 2s, 4s, 8s.

    Returns (response_text, error_message). On success: (text, None). On failure: (None, error_string).
    """
    google_key = (
        os.environ.get("GOOGLE_API_KEY")
        or _maybe_google_key(os.environ.get("OPENAI_API_KEY"))
    )
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL")
    if google_key:
        pass
    elif not api_key and not base_url:
        return (None, "Set GOOGLE_API_KEY or OPENAI_API_KEY in .env")
    max_retries = max(1, int(os.environ.get("LLM_RATE_LIMIT_RETRIES", "3")))
    last_err: str | None = None
    for attempt in range(max_retries):
        if google_key:
            out, last_err = _call_gemini(system, user, google_key, temperature)
            if last_err is None:
                last_err = "Set GOOGLE_API_KEY or OPENAI_API_KEY in .env" if out is None else None
        else:
            out, last_err = _call_openai(system, user, api_key, base_url, temperature)
            if out is None and last_err is None:
                last_err = "OpenAI/LLM request failed."
        if out is not None:
            return (out, None)
        if not _is_rate_limit_error(last_err):
            return (None, last_err or "Unknown error")
        if _is_daily_quota_error(last_err):
            return (
                None,
                "Daily API quota reached (free tier). Try again tomorrow or check your plan: https://ai.google.dev/gemini-api/docs/rate-limits",
            )
        if attempt < max_retries - 1:
            retry_sec = _parse_retry_after_ms(last_err)
            if retry_sec is not None and retry_sec > 0:
                time.sleep(min(retry_sec, 60.0))
            else:
                time.sleep(2 ** (attempt + 1))
    return (None, last_err or "Rate limit exceeded after retries.")


def _maybe_google_key(key: str | None) -> str | None:
    """Treat OpenAI API key as Google key if it looks like one (AIza...)."""
    if not key or not key.strip():
        return None
    if key.strip().startswith("AIza"):
        return key.strip()
    return None


def _call_gemini(
    system: str, user: str, api_key: str, temperature: float
) -> tuple[str | None, str | None]:
    """Call Google Gemini. Returns (text, None) on success, (None, error_message) on failure."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model_name = os.environ.get("GOOGLE_MODEL", "gemini-2.5-flash-lite")
        prompt = f"{system}\n\n---\n\n{user}" if system else (user or "(no user message)")
        try:
            model = genai.GenerativeModel(model_name, system_instruction=system)
            response = model.generate_content(user or "(no user message)")
        except TypeError:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
        if response and response.text:
            return (response.text.strip(), None)
        return (None, "Gemini returned no text.")
    except Exception as e:
        return (None, str(e).strip() or "Gemini API error.")


def _call_openai(
    system: str, user: str, api_key: str | None, base_url: str | None, temperature: float
) -> tuple[str | None, str | None]:
    """Call OpenAI or an OpenAI-compatible endpoint. Returns (text, None) or (None, error)."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key or "not-needed", base_url=base_url or None)
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system or ""},
                {"role": "user", "content": user or ""},
            ],
            temperature=temperature,
        )
        return ((resp.choices[0].message.content or "").strip(), None)
    except Exception as e:
        return (None, str(e).strip() or "OpenAI API error.")
