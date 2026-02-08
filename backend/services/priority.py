"""
Outcome-adjusted priority for alert ordering.

Uses past investigator outcomes (similar confirmed fraud, similar false positives)
to re-rank alerts. Deterministic and explainable; no retraining.
Score and explanation are attached to each alert for audit.
"""
from __future__ import annotations

from backend.services.feedback import get_similar_confirmed_count, get_similar_false_positive_count

# Auditable constants for priority formula
PRIORITY_BOOST_PER_CONFIRMED = 0.05
PRIORITY_REDUCTION_PER_FP = 0.05
PRIORITY_CAP_CONFIRMED = 5
PRIORITY_CAP_FP = 5
FP_THRESHOLD = 2  # Apply reduction only when similar_fp >= 2


def compute_outcome_adjusted_priority(alert: dict) -> dict:
    """
    Compute priority score and explanation from base scores and outcome similarity.

    - base = 0.5 * fraud_probability + 0.5 * anomaly_score
    - Boost if similar_confirmed_count > 0
    - Reduce if similar_false_positive_count >= FP_THRESHOLD

    Returns dict with outcome_adjusted_priority (float in [0,1]) and
    outcome_priority_explanation (str for UI). Suitable for audit (attach to alert snapshot).
    """
    prob = float(alert.get("fraud_probability") or 0)
    anomaly = float(alert.get("anomaly_score") or 0)
    base = 0.5 * prob + 0.5 * anomaly

    risk_level = alert.get("risk_level") or "Low"
    feature_vector = alert.get("feature_vector")

    similar_confirmed = get_similar_confirmed_count(risk_level, feature_vector=feature_vector)
    similar_fp = get_similar_false_positive_count(risk_level, feature_vector=feature_vector)

    boost = 0.0
    if similar_confirmed > 0:
        boost = PRIORITY_BOOST_PER_CONFIRMED * min(similar_confirmed, PRIORITY_CAP_CONFIRMED)

    reduction = 0.0
    if similar_fp >= FP_THRESHOLD:
        reduction = PRIORITY_REDUCTION_PER_FP * min(similar_fp, PRIORITY_CAP_FP)

    outcome_adjusted_priority = max(0.0, min(1.0, base + boost - reduction))

    parts = []
    if similar_confirmed > 0:
        parts.append(f"Prioritised due to similarity with {similar_confirmed} confirmed fraud case{'s' if similar_confirmed != 1 else ''}.")
    if similar_fp >= FP_THRESHOLD:
        parts.append("De-prioritised due to historical false positives.")
    if not parts:
        parts.append("No outcome-based adjustment.")

    outcome_priority_explanation = " ".join(parts)

    return {
        "outcome_adjusted_priority": outcome_adjusted_priority,
        "outcome_priority_explanation": outcome_priority_explanation,
    }
