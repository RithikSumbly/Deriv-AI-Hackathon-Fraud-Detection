"""
Next-Step Advisor — Human-in-the-loop investigation suggestions.

Given risk indicators (e.g. high deposit-to-income, VPN, shared device, rapid withdrawals),
recommend the top 3 next investigative actions.

Rules: Do not make final decisions. Do not label as fraud. Focus on efficiency.
"""
from __future__ import annotations

import json
import os
from typing import Any

# -----------------------------------------------------------------------------
# Prompt (load from prompts.json when available)
# -----------------------------------------------------------------------------
from pathlib import Path
_PROMPTS_JSON = Path(__file__).resolve().parent.parent / "prompts" / "prompts.json"

def _load_system_prompt():
    if _PROMPTS_JSON.exists():
        try:
            with open(_PROMPTS_JSON) as f:
                return json.load(f).get("next_step_advisor_system") or _DEFAULT_SYSTEM_PROMPT
        except Exception:
            pass
    return _DEFAULT_SYSTEM_PROMPT

_DEFAULT_SYSTEM_PROMPT = """You are assisting a fraud investigator. Your role is to suggest efficient next steps—not to decide whether the case is fraud.

Rules:
- Do NOT make final decisions or conclusions.
- Do NOT label the case or the customer as fraud.
- Recommend only investigative actions (what to check, request, or verify next).
- Focus on efficiency: highest impact actions first, minimal redundancy.
- Be specific and actionable (e.g. "Request X", "Verify Y", "Review Z")."""

SYSTEM_PROMPT = _load_system_prompt()

USER_PROMPT_TEMPLATE = """Given these risk indicators for a case under review:

{indicators_block}

Recommend the **top 3 next investigative actions** (in order of efficiency). Each action should be one clear, actionable step. Output valid JSON only, no other text:

{{
  "next_steps": [
    "First action (most efficient to do next)",
    "Second action",
    "Third action"
  ],
  "rationale": "One short sentence on why these three (e.g. they address the main indicators with least effort)."
}}"""


def _format_indicators(indicators: list[str] | dict[str, Any]) -> str:
    if isinstance(indicators, dict):
        lines = [f"- {k}: {v}" for k, v in indicators.items()]
    else:
        lines = [f"- {x}" for x in indicators]
    return "\n".join(lines) if lines else "(none provided)"


def _call_llm(prompt: str, system: str) -> tuple[str | None, str | None]:
    """Returns (content, error_message). Error is set when LLM is unavailable or fails."""
    from .llm_client import call_llm_with_error
    return call_llm_with_error(system, prompt, temperature=0.2)


def _template_next_steps(indicators: list[str] | dict) -> dict[str, Any]:
    """Map common indicators to efficient next steps. No decisions, no fraud label."""
    if isinstance(indicators, dict):
        keys = set(k.lower() for k in indicators.keys())
    else:
        keys = set()
        for x in indicators or []:
            keys.update(str(x).lower().split())

    next_steps = []
    if any("deposit" in k or "income" in k or "ratio" in k for k in keys) or "high deposit-to-income ratio" in str(indicators).lower():
        next_steps.append("Verify declared income (employment letter, tax doc, or bank statement) to reconcile with deposit volume.")
    if any("vpn" in k for k in keys) or "vpn" in str(indicators).lower():
        next_steps.append("Review login geography vs. KYC address and payment rails; request confirmation of usual access locations.")
    if any("device" in k or "shared" in k or "network" in k for k in keys):
        next_steps.append("Expand device and IP graph: list all accounts linked by shared device/IP and flag any known fraud or SARs.")
    if any("withdrawal" in k or "rapid" in k for k in keys):
        next_steps.append("Review withdrawal timeline and beneficiaries; confirm purpose of funds and destination accounts.")

    # Pad to 3 if we have fewer
    defaults = [
        "Review full transaction history for the last 90 days for pattern consistency.",
        "Check whether KYC documents and face match are up to date and consistent with account behavior.",
        "Compare account tenure and activity level to peer segment for outliers.",
    ]
    for d in defaults:
        if len(next_steps) >= 3:
            break
        if d not in next_steps:
            next_steps.append(d)

    return {
        "next_steps": next_steps[:3],
        "rationale": "Suggested actions map to the risk indicators you provided; prioritize verification and graph review for efficiency. No conclusion on fraud—human decision required.",
    }


def recommend_next_steps(
    risk_indicators: list[str] | dict[str, Any],
    *,
    use_llm: bool = True,
) -> dict[str, Any]:
    """
    Recommend the top 3 next investigative actions given risk indicators.

    Args:
        risk_indicators: Either a list of strings (e.g. ["High deposit-to-income ratio", "VPN usage"])
            or a dict (e.g. {"deposit_to_income_ratio": 4.2, "vpn_usage_pct": 85}).
        use_llm: If True and API key set, use LLM; else use rule-based suggestions.

    Returns:
        dict with keys: next_steps (list of 3 strings), rationale (string).
    """
    indicators_block = _format_indicators(risk_indicators)
    prompt = USER_PROMPT_TEMPLATE.format(indicators_block=indicators_block)

    if use_llm:
        raw, err = _call_llm(prompt, SYSTEM_PROMPT)
        if err:
            return {
                "next_steps": [err],
                "rationale": "Fix the issue above (e.g. set GOOGLE_API_KEY or OPENAI_API_KEY in .env, or check key validity and network).",
            }
        if raw:
            text = raw.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            try:
                out = json.loads(text)
                if "next_steps" in out and isinstance(out["next_steps"], list):
                    out["next_steps"] = out["next_steps"][:3]
                    out.setdefault("rationale", "")
                    return out
            except json.JSONDecodeError:
                pass
        return {
            "next_steps": ["Set GOOGLE_API_KEY or OPENAI_API_KEY in .env to generate AI recommendations."],
            "rationale": "LLM is required for next-step suggestions.",
        }

    return _template_next_steps(risk_indicators)


# -----------------------------------------------------------------------------
# Example / CLI
# -----------------------------------------------------------------------------

EXAMPLE_INDICATORS = [
    "High deposit-to-income ratio",
    "VPN usage",
    "Shared device network",
    "Rapid withdrawals",
]


if __name__ == "__main__":
    import sys
    use_llm = "llm" in sys.argv
    out = recommend_next_steps(EXAMPLE_INDICATORS, use_llm=use_llm)
    print("--- Top 3 next investigative actions ---")
    for i, step in enumerate(out["next_steps"], 1):
        print(f"  {i}. {step}")
    print("\nRationale:", out["rationale"])
    if not use_llm:
        print("\n(Template suggestions; set OPENAI_API_KEY and run with 'llm' for LLM.)")
