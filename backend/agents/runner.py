"""
Agent runner: runs specialist agents and orchestrator in order, parses outputs.
Used by the dashboard to drive risk explanation and Evidence tabs.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Literal

from backend.agents.prompts import (
    AGENTS,
    ORDER_ON_ALERT_CREATION,
    ORDER_ON_CASE_OPEN,
    ORDER_ON_CASE_CLOSE,
)
from backend.explainability.llm_client import call_llm_with_error


def _extract_json(text: str | None) -> dict | None:
    """Extract a JSON object from LLM response (handles markdown code blocks and common LLM slips)."""
    if not text or not text.strip():
        return None
    text = text.strip()

    def try_parse(raw: str) -> dict | None:
        if not raw:
            return None
        raw = raw.strip()
        # Remove trailing commas before } or ] (common LLM mistake)
        raw = re.sub(r",\s*([}\]])", r"\1", raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    parsed = try_parse(text)
    if parsed:
        return parsed
    # Try ```json ... ``` or ``` ... ```
    for pattern in (r"```(?:json)?\s*([\s\S]*?)\s*```", r"\{[\s\S]*\}"):
        match = re.search(pattern, text)
        if match:
            raw = match.group(1).strip() if match.lastindex else match.group(0)
            parsed = try_parse(raw)
            if parsed:
                return parsed
    # Try first { to last } (outermost object)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        parsed = try_parse(text[start : end + 1])
        if parsed:
            return parsed
    return None


def _build_transaction_user(alert: dict) -> str:
    """Structured input for Transaction/Behavior agent."""
    data = {
        "declared_income_annual": alert.get("declared_income_annual"),
        "total_deposits_90d": alert.get("total_deposits_90d"),
        "total_withdrawals_90d": alert.get("total_withdrawals_90d"),
        "num_deposits_90d": alert.get("num_deposits_90d"),
        "num_withdrawals_90d": alert.get("num_withdrawals_90d"),
        "deposit_withdraw_cycle_days_avg": alert.get("deposit_withdraw_cycle_days_avg"),
        "deposits_vs_income_ratio": alert.get("deposits_vs_income_ratio"),
        "fraud_probability": alert.get("fraud_probability"),
        "anomaly_score": alert.get("anomaly_score"),
    }
    return json.dumps(data, indent=2)


def _build_identity_user(alert: dict) -> str:
    """Structured input for Identity agent."""
    data = {
        "kyc_face_match_score": alert.get("kyc_face_match_score"),
        "account_age_days": alert.get("account_age_days"),
        "fraud_probability": alert.get("fraud_probability"),
    }
    return json.dumps(data, indent=2)


def _build_geo_user(alert: dict) -> str:
    """Structured input for Geo/VPN agent."""
    data = {
        "vpn_usage_pct": alert.get("vpn_usage_pct"),
        "countries_accessed_count": alert.get("countries_accessed_count"),
        "fraud_probability": alert.get("fraud_probability"),
    }
    return json.dumps(data, indent=2)


def _build_network_user(alert: dict) -> str:
    """Structured input for Network agent."""
    data = {
        "device_shared_count": alert.get("device_shared_count"),
        "ip_shared_count": alert.get("ip_shared_count"),
        "fraud_probability": alert.get("fraud_probability"),
    }
    return json.dumps(data, indent=2)


def _build_outcome_similarity_user(alert: dict, similar_count: int) -> str:
    """Structured input for Outcome Similarity agent."""
    data = {
        "fraud_probability": alert.get("fraud_probability"),
        "risk_level": alert.get("risk_level"),
        "similar_confirmed_cases_count_from_system": similar_count,
        "one_line_explanation": alert.get("one_line_explanation"),
    }
    return json.dumps(data, indent=2)


def _build_orchestrator_user(specialist_outputs: dict[str, Any]) -> str:
    """Merged specialist findings for Orchestrator."""
    return json.dumps(specialist_outputs, indent=2)


def _build_knowledge_capture_user(alert: dict, outcome: str, reason: str) -> str:
    """Input for Knowledge Capture on case close."""
    summary = {
        "account_id": alert.get("account_id"),
        "fraud_probability": alert.get("fraud_probability"),
        "risk_level": alert.get("risk_level"),
        "one_line_explanation": alert.get("one_line_explanation"),
        "risk_factors": alert.get("risk_factors"),
        "final_outcome": outcome,
        "reason": reason,
    }
    return json.dumps(summary, indent=2)


def _build_visualization_user(events: list[dict]) -> str:
    """Input for Visualization agent: raw timeline events (timestamp, event_type, details, suspicious)."""
    return json.dumps(events, indent=2)


def _run_agent(agent_id: str, user_message: str) -> tuple[dict[str, Any], str | None]:
    """
    Run one agent: LLM call + parse. Returns (parsed_output, error).
    On success parsed_output has agent's output_fields; on failure has _error key.
    """
    agent = AGENTS.get(agent_id)
    if not agent:
        return ({"_error": f"Unknown agent: {agent_id}"}, None)
    system = agent["system_prompt"]
    output_fields = agent.get("output_fields") or []
    text, err = call_llm_with_error(system, user_message)
    if err or not text:
        return ({"_error": err or "No response"}, err)
    parsed = _extract_json(text)
    if not parsed:
        return ({"_error": "Could not parse JSON", "_raw": text[:500]}, "Parse error")
    # Normalize keys and ensure expected fields exist
    out = {}
    for f in output_fields:
        if f in parsed:
            out[f] = parsed[f]
        else:
            out[f] = None
    if "_error" in parsed:
        out["_error"] = parsed["_error"]
    return (out, None)


def run_pipeline(
    alert: dict,
    mode: Literal["alert_creation", "case_open"],
    *,
    cached_specialists: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Run the agent pipeline. Returns dict with keys: transaction, identity, geo,
    network, outcome_similarity, orchestrator. Each value is the agent's parsed
    output (or dict with _error).

    - alert_creation: run ORDER_ON_ALERT_CREATION (all specialists then orchestrator).
    - case_open: run only orchestrator using cached_specialists (or empty if None).
    """
    result: dict[str, Any] = {
        "transaction": {},
        "identity": {},
        "geo": {},
        "network": {},
        "outcome_similarity": {},
        "orchestrator": {},
    }

    if mode == "alert_creation":
        delay = max(0.0, float(os.environ.get("AGENT_CALL_DELAY_SECONDS", "6")))

        # Specialists in order (no orchestrator yet)
        result["transaction"], _ = _run_agent(
            "transaction", _build_transaction_user(alert)
        )
        if delay > 0:
            time.sleep(delay)
        result["identity"], _ = _run_agent("identity", _build_identity_user(alert))
        if delay > 0:
            time.sleep(delay)
        result["geo"], _ = _run_agent("geo", _build_geo_user(alert))
        if delay > 0:
            time.sleep(delay)
        result["network"], _ = _run_agent("network", _build_network_user(alert))
        if delay > 0:
            time.sleep(delay)

        # Outcome similarity: need similar count from feedback
        try:
            from backend.services.feedback import get_similar_confirmed_count
            similar_count = get_similar_confirmed_count(
                alert.get("risk_level", "Low"),
                feature_vector=alert.get("feature_vector"),
            )
        except Exception:
            similar_count = 0
        result["outcome_similarity"], _ = _run_agent(
            "outcome_similarity",
            _build_outcome_similarity_user(alert, similar_count),
        )
        if delay > 0:
            time.sleep(delay)

        # Orchestrator with merged specialist outputs (no _error keys in payload)
        specialist_merge = {
            k: {kk: vv for kk, vv in v.items() if kk != "_error"}
            for k, v in result.items()
            if k != "orchestrator"
        }
        result["orchestrator"], _ = _run_agent(
            "orchestrator", _build_orchestrator_user(specialist_merge)
        )
        return result

    if mode == "case_open":
        specialists = cached_specialists or {}
        for k in ("transaction", "identity", "geo", "network", "outcome_similarity"):
            result[k] = specialists.get(k, {})
        specialist_merge = {
            k: {kk: vv for kk, vv in v.items() if kk != "_error"}
            for k, v in result.items()
            if k != "orchestrator"
        }
        result["orchestrator"], _ = _run_agent(
            "orchestrator", _build_orchestrator_user(specialist_merge)
        )
        return result

    return result


def run_knowledge_capture(alert: dict, outcome: str, reason: str) -> dict[str, Any]:
    """
    Run Knowledge Capture agent on case close. Returns pattern dict with
    key_signals, behavioral_pattern, final_outcome, one_sentence_description (or _error).
    """
    user_msg = _build_knowledge_capture_user(alert, outcome, reason)
    out, _ = _run_agent("knowledge_capture", user_msg)
    return out


def run_visualization_agent(events: list[dict]) -> dict[str, Any]:
    """
    Run Visualization agent on raw timeline events. Returns flow spec
    { "timeline": [ { "id", "label", "type" }, ... ], "edges": [ [from_id, to_id], ... ] } or { "_error": "..." }.
    """
    user_msg = _build_visualization_user(events)
    out, _ = _run_agent("visualization", user_msg)
    return out
