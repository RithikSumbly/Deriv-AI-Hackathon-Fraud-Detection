"""
Alert Explanation Generator — LLM as Investigator Buddy.

Given fraud probability, anomaly score, top SHAP features, and network risk indicators,
produces:
  1. A concise explanation of why the alert was triggered
  2. A bullet list of key risk drivers
  3. A plain-English explanation for a junior analyst

Tone: Clear, evidence-based, no speculation.

Set OPENAI_API_KEY (or OPENAI_BASE_URL for a compatible endpoint) to use the LLM.
Otherwise returns a template-based explanation so demos work without an API key.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# -----------------------------------------------------------------------------
# Prompt template (load from prompts.json when available)
# -----------------------------------------------------------------------------
_PROMPTS_JSON = Path(__file__).resolve().parent.parent / "prompts" / "prompts.json"

def _load_system_prompt():
    if _PROMPTS_JSON.exists():
        try:
            with open(_PROMPTS_JSON) as f:
                return json.load(f).get("alert_explanation_system") or _DEFAULT_SYSTEM_PROMPT
        except Exception:
            pass
    return _DEFAULT_SYSTEM_PROMPT

_DEFAULT_SYSTEM_PROMPT = """You are a senior financial crime investigator. Your job is to explain fraud alerts in a way that is clear, evidence-based, and useful for human reviewers.

Rules:
- Use only the evidence provided. Do not speculate or add information not in the inputs.
- Be concise. No filler or hedging.
- Write so a junior analyst can understand and act on your explanation.
- Do not use jargon without a one-line plain-English clarification when needed."""

SYSTEM_PROMPT = _load_system_prompt()

USER_PROMPT_TEMPLATE = """Given the following alert inputs, produce exactly three outputs.

**Inputs:**
- Fraud probability score: {fraud_probability:.2%} (model estimate of fraud likelihood)
- Anomaly score: {anomaly_score:.2%} (how unusual this account is vs. normal behavior; high = more anomalous)
- Top SHAP drivers (features that most influenced the fraud score):
{shap_block}
- Network risk indicators:
{network_block}

**Required outputs** (use this exact JSON structure; no other text):
{{
  "concise_explanation": "2–4 sentences stating why this alert was triggered, citing specific evidence from the inputs.",
  "key_risk_drivers": [
    "Bullet 1: one specific risk factor and the evidence (e.g. value or indicator)",
    "Bullet 2: ...",
    "Bullet 3: ..."
  ],
  "junior_analyst_summary": "2–3 plain-English sentences. What should the analyst look at first? What does the evidence suggest? No speculation—stick to what the numbers and indicators show."
}}"""


def _format_shap(drivers: list[dict[str, Any]]) -> str:
    if not drivers:
        return "  (none provided)"
    lines = []
    for d in drivers:
        f = d.get("feature", "?")
        v = d.get("value", "?")
        direction = d.get("direction", "")
        lines.append(f"  - {f}: value = {v}, {direction}")
    return "\n".join(lines)


def _format_network(indicators: dict[str, Any]) -> str:
    if not indicators:
        return "  (none provided)"
    return "\n".join(f"  - {k}: {v}" for k, v in indicators.items())


def _call_llm(prompt: str, system: str) -> str | None:
    """Call LLM (OpenAI or Google Gemini). Returns response content or None on failure."""
    from .llm_client import call_llm
    return call_llm(system, prompt, temperature=0.2)


def _template_fallback(
    fraud_probability: float,
    anomaly_score: float,
    top_shap_drivers: list[dict],
    network_risk_indicators: dict[str, Any],
) -> dict[str, Any]:
    """Evidence-based template when no LLM is available. No speculation."""
    drivers = []
    for d in top_shap_drivers[:5]:
        f = d.get("feature", "?")
        v = d.get("value", "?")
        direction = d.get("direction", "")
        drivers.append(f"{f} (value: {v}) {direction}.")
    network_bullets = [f"{k}: {v}" for k, v in (network_risk_indicators or {}).items()]
    conc = (
        f"This alert was triggered because the account has a fraud probability of {fraud_probability:.1%} "
        f"and an anomaly score of {anomaly_score:.1%}, indicating both model-based fraud likelihood and "
        f"unusual behavior relative to normal accounts. "
    )
    if drivers:
        conc += "The main drivers are: " + " ".join(drivers[:2]) + " "
    if network_bullets:
        conc += "Network indicators: " + "; ".join(network_bullets[:3]) + "."
    risk_list = []
    if fraud_probability >= 0.3:
        risk_list.append(f"Fraud probability {fraud_probability:.1%} exceeds typical review threshold.")
    if anomaly_score >= 0.6:
        risk_list.append(f"Anomaly score {anomaly_score:.1%} indicates high deviation from normal behavior.")
    for d in top_shap_drivers[:3]:
        risk_list.append(f"{d.get('feature', '?')} = {d.get('value', '?')} ({d.get('direction', '')})")
    for k, v in (network_risk_indicators or {}).items():
        risk_list.append(f"Network: {k} = {v}")
    junior = (
        f"For the junior analyst: This case was flagged by our models as higher risk. "
        f"Check the top risk drivers above; focus on any that push toward FRAUD. "
        f"If network indicators show shared device or IP with known fraud, treat as high priority. "
        f"Stick to the evidence listed—do not speculate beyond it."
    )
    return {
        "concise_explanation": conc,
        "key_risk_drivers": risk_list[:8],
        "junior_analyst_summary": junior,
    }


def generate_alert_explanation(
    fraud_probability: float,
    anomaly_score: float,
    top_shap_drivers: list[dict[str, Any]],
    network_risk_indicators: dict[str, Any] | None = None,
    *,
    use_llm: bool = True,
) -> dict[str, Any]:
    """
    Generate a three-part alert explanation: concise summary, risk drivers, junior analyst summary.

    Args:
        fraud_probability: Model fraud probability (0–1).
        anomaly_score: Anomaly score (0–1, high = more anomalous).
        top_shap_drivers: List of dicts with keys: feature, value, shap_effect, direction.
        network_risk_indicators: Optional dict e.g. device_shared_count, same_device_as_fraud, min_path_to_fraud.
        use_llm: If True and API key is set, use LLM; else use template fallback.

    Returns:
        dict with keys: concise_explanation, key_risk_drivers (list), junior_analyst_summary.
    """
    network_risk_indicators = network_risk_indicators or {}
    shap_block = _format_shap(top_shap_drivers)
    network_block = _format_network(network_risk_indicators)

    if use_llm:
        user_prompt = USER_PROMPT_TEMPLATE.format(
            fraud_probability=fraud_probability,
            anomaly_score=anomaly_score,
            shap_block=shap_block,
            network_block=network_block,
        )
        raw = _call_llm(user_prompt, SYSTEM_PROMPT)
        if raw:
            # Try to parse JSON from the response (handle markdown code blocks)
            text = raw.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            try:
                out = json.loads(text)
                if "concise_explanation" in out and "key_risk_drivers" in out and "junior_analyst_summary" in out:
                    return out
            except json.JSONDecodeError:
                pass
        # LLM required; no preset content
        msg = "Set OPENAI_API_KEY (or OPENAI_BASE_URL) to generate AI explanation."
        return {
            "concise_explanation": msg,
            "key_risk_drivers": [msg],
            "junior_analyst_summary": "LLM is required for this summary. No preset content is returned.",
        }

    return _template_fallback(
        fraud_probability,
        anomaly_score,
        top_shap_drivers,
        network_risk_indicators,
    )


# -----------------------------------------------------------------------------
# Example / CLI
# -----------------------------------------------------------------------------

EXAMPLE_INPUT = {
    "fraud_probability": 0.72,
    "anomaly_score": 0.89,
    "top_shap_drivers": [
        {"feature": "vpn_usage_pct", "value": 82.5, "shap_effect": 0.95, "direction": "pushes toward FRAUD"},
        {"feature": "deposits_vs_income_ratio", "value": 4.2, "shap_effect": 0.61, "direction": "pushes toward FRAUD"},
        {"feature": "deposit_withdraw_cycle_days_avg", "value": 3.1, "shap_effect": 0.44, "direction": "pushes toward FRAUD"},
        {"feature": "kyc_face_match_score", "value": 0.62, "shap_effect": 0.31, "direction": "pushes toward FRAUD"},
        {"feature": "device_shared_count", "value": 8, "shap_effect": 0.28, "direction": "pushes toward FRAUD"},
    ],
    "network_risk_indicators": {
        "device_shared_count": 8,
        "ip_shared_count": 5,
        "same_device_as_fraud": True,
        "same_ip_as_fraud": False,
        "min_path_to_fraud": 2,
    },
}


if __name__ == "__main__":
    import sys
    use_llm = "llm" in sys.argv
    out = generate_alert_explanation(
        EXAMPLE_INPUT["fraud_probability"],
        EXAMPLE_INPUT["anomaly_score"],
        EXAMPLE_INPUT["top_shap_drivers"],
        EXAMPLE_INPUT["network_risk_indicators"],
        use_llm=use_llm,
    )
    print("--- Concise explanation ---")
    print(out["concise_explanation"])
    print("\n--- Key risk drivers ---")
    for b in out["key_risk_drivers"]:
        print(f"  • {b}")
    print("\n--- Junior analyst summary ---")
    print(out["junior_analyst_summary"])
    if not use_llm:
        print("\n(Template fallback; set OPENAI_API_KEY and run with 'llm' to use LLM.)")
