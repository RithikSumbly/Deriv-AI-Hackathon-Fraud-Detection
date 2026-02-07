"""
Investigator feedback store: decisions (Confirm Fraud, Mark Legit, Dismiss as false positive)
with reason and timestamp for audit trail and continuous learning.

Stored in backend/data/investigator_feedback.json.
Supports similarity-based "matches N confirmed cases" via stored feature vectors.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FEEDBACK_FILE = DATA_DIR / "investigator_feedback.json"
MODEL_VERSION = os.environ.get("FRAUD_MODEL_VERSION", "v0.3")


def _load() -> list[dict]:
    if not FEEDBACK_FILE.exists():
        return []
    try:
        with open(FEEDBACK_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def _save(records: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(FEEDBACK_FILE, "w") as f:
        json.dump(records, f, indent=2)


def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Cosine similarity in [0, 1] (assume non-negative features)."""
    if len(a) != len(b) or len(a) == 0:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a < 1e-9 or norm_b < 1e-9:
        return 0.0
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))


def add_decision(
    account_id: str,
    decision: str,
    reason: str = "",
    *,
    risk_level: str | None = None,
    fraud_probability: float | None = None,
    anomaly_score: float | None = None,
    feature_vector: list[float] | None = None,
    investigator_id: str | None = None,
    model_version: str | None = None,
) -> None:
    """
    Append one investigator decision for audit and future retrain.
    decision: "Confirmed Fraud" | "Marked Legit" | "False Positive"
    When decision is Confirmed Fraud and feature_vector is provided, it is stored for similarity matching.
    """
    records = _load()
    inv_id = investigator_id or os.environ.get("INVESTIGATOR_ID", "demo")
    rec = {
        "account_id": account_id,
        "decision": decision,
        "reason": (reason or "").strip(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "risk_level": risk_level,
        "fraud_probability": fraud_probability,
        "anomaly_score": anomaly_score,
        "investigator_id": inv_id,
        "model_version": model_version or MODEL_VERSION,
    }
    if decision == "Confirmed Fraud" and feature_vector and len(feature_vector) > 0:
        rec["feature_vector"] = feature_vector
    records.append(rec)
    _save(records)


def add_knowledge_pattern(account_id: str, pattern: dict) -> None:
    """
    Attach a knowledge-capture pattern to the most recent decision for this account.
    pattern should have keys such as key_signals, behavioral_pattern, final_outcome, one_sentence_description.
    """
    records = _load()
    for i in range(len(records) - 1, -1, -1):
        if records[i].get("account_id") == account_id:
            records[i]["knowledge_pattern"] = pattern
            _save(records)
            return
    # No decision found for this account; append a minimal record so pattern is not lost (edge case)
    rec = {
        "account_id": account_id,
        "decision": "(pattern only)",
        "reason": "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "knowledge_pattern": pattern,
    }
    records.append(rec)
    _save(records)


def get_decisions(account_id: str | None = None) -> list[dict]:
    """Return all feedback records, optionally filtered by account_id."""
    records = _load()
    if account_id is not None:
        records = [r for r in records if r.get("account_id") == account_id]
    return records


def get_latest_decision(account_id: str) -> dict | None:
    """Return the most recent decision for this account, or None."""
    decisions = get_decisions(account_id)
    if not decisions:
        return None
    return max(decisions, key=lambda r: r.get("timestamp", ""))


def get_similar_confirmed_count(
    risk_level: str,
    *,
    feature_vector: list[float] | None = None,
    similarity_threshold: float = 0.7,
) -> int:
    """
    Count previously confirmed fraud cases similar to this one.
    - If feature_vector is provided and we have stored vectors: use cosine similarity (>= threshold).
    - Else: fall back to same risk_level (behavioral bucket).
    UI copy: "Behavioral pattern similar to N previously confirmed fraud cases."
    """
    records = _load()
    confirmed = [r for r in records if r.get("decision") == "Confirmed Fraud"]
    if not confirmed:
        return 0
    # Similarity-based when we have current vector and stored vectors
    if feature_vector and len(feature_vector) > 0:
        stored = [r.get("feature_vector") for r in confirmed if isinstance(r.get("feature_vector"), list)]
        if stored and len(stored[0]) == len(feature_vector):
            return sum(1 for sv in stored if _cosine_sim(feature_vector, sv) >= similarity_threshold)
    # Fallback: same risk_level
    return sum(1 for r in confirmed if r.get("risk_level") == risk_level)


def get_confirmed_fraud_count() -> int:
    """Total number of Confirmed Fraud decisions (for display)."""
    records = _load()
    return sum(1 for r in records if r.get("decision") == "Confirmed Fraud")


def has_false_positive_history() -> bool:
    """True if any investigator has dismissed a case as false positive (for auto-resolve suggestion)."""
    records = _load()
    return any(r.get("decision") == "False Positive" for r in records)


def get_feedback_for_retrain() -> list[dict]:
    """
    Return feedback records with decision and snapshot for retraining.
    Label: 1 = Confirmed Fraud, 0 = Marked Legit or False Positive.
    """
    records = _load()
    out = []
    for r in records:
        decision = r.get("decision", "")
        if decision == "Confirmed Fraud":
            label = 1
        elif decision in ("Marked Legit", "False Positive"):
            label = 0
        else:
            continue
        out.append({
            "account_id": r.get("account_id"),
            "label": label,
            "reason": r.get("reason"),
            "timestamp": r.get("timestamp"),
            "risk_level": r.get("risk_level"),
            "fraud_probability": r.get("fraud_probability"),
            "anomaly_score": r.get("anomaly_score"),
        })
    return out
