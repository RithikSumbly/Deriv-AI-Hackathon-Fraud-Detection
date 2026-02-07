"""
Shared LLM client: OpenAI-compatible API or Google Gemini.

Uses OPENAI_API_KEY + OPENAI_BASE_URL for OpenAI, or GOOGLE_API_KEY for Gemini.
Google API keys (AIza...) work with GOOGLE_API_KEY; the app will use Gemini.
"""
from __future__ import annotations

import os


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

    Returns (response_text, error_message). On success: (text, None). On failure: (None, error_string).
    When no API key is set, error_string is "Set GOOGLE_API_KEY or OPENAI_API_KEY in .env".
    """
    # 1) Google Gemini: GOOGLE_API_KEY, or OPENAI_API_KEY if it looks like Google (AIza...)
    google_key = (
        os.environ.get("GOOGLE_API_KEY")
        or _maybe_google_key(os.environ.get("OPENAI_API_KEY"))
    )
    if google_key:
        out, err = _call_gemini(system, user, google_key, temperature)
        if out is not None:
            return (out, None)
        return (None, err or "Set GOOGLE_API_KEY or OPENAI_API_KEY in .env")

    # 2) OpenAI-compatible (OpenAI or proxy)
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL")
    if not api_key and not base_url:
        return (None, "Set GOOGLE_API_KEY or OPENAI_API_KEY in .env")
    out, err = _call_openai(system, user, api_key, base_url, temperature)
    if out is not None:
        return (out, None)
    return (None, err or "OpenAI/LLM request failed.")


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
        model_name = os.environ.get("GOOGLE_MODEL", "gemini-2.5-flash")
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
