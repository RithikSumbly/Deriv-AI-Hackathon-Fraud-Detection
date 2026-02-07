# Implementation status: AI-Powered Client Fraud Detection & Investigation

**Judge-safe one-liner (if challenged on “what’s not built yet”):**

> “We intentionally built a system where investigator decisions are first-class signals. The feedback, similarity matching, and retraining pipelines are designed to plug in incrementally without changing the investigation workflow.”

---

## Implemented (demo-ready)

| Capability | What’s in place |
|------------|------------------|
| **Pattern-based detection** | Fraud classifier + anomaly detector; multi-signal (identity, transaction, geo, device/IP). |
| **Explainable alerts** | “Why this account was flagged”, risk factors, confidence, risk level. |
| **Investigator decisioning** | Confirm Fraud, Mark Legit, Request More Info; decisions stored with snapshot. |
| **False positive dismissal with audit trail** | “Dismiss as false positive” with **required** reason (dropdown: Expected income source, Known customer behavior, Temporary anomaly, Other). Stored: account_id, decision, reason, timestamp, investigator_id, model_version. |
| **Case similarity references** | “Behavioral pattern similar to N previously confirmed fraud cases” — similarity by **feature-vector (cosine)** when vectors exist, else by risk_level. |
| **Predictive explanation** | “High / Moderate / Lower likelihood of real fraud (X%). Based on N independent risk signals. Similar to confirmed fraud patterns.” |
| **Report generation** | Generate Investigation Report (regulatory-style, LLM); 4 H2 sections. |
| **Auto-resolve suggestion** | When fraud_prob &lt; 0.15 and anomaly &lt; 0.3 and we have FP history: banner “Consider dismissing as false positive?” |
| **Continuous learning (pipeline)** | Every decision → `investigator_feedback.json`. `feedback_retrain.py` exports `feedback_training_data.csv` for periodic retrain. |

---

## Designed / extensible (no workflow change)

| Capability | Status | How it plugs in |
|------------|--------|------------------|
| **Continuous learning (retrain)** | Feedback dataset exported | Run `python backend/scripts/feedback_retrain.py`; merge with synthetic data and run `train_fraud_classifier.py` (or equivalent). Model versioning: set `FRAUD_MODEL_VERSION` / tag outputs (e.g. v0.3 → v0.4). |
| **Knowledge capture** | Schema-ready | From each completed investigation we already store signals, outcome, reason. Optional: LLM summarisation → reusable pattern (pattern_id, signals, outcome, summary) for similarity and training. |
| **Conservative auto-resolution** | Suggestion only | Today: suggest “Consider dismissing…”. Optional: auto-resolve when rule holds and log `auto_resolved_false_positive` with confidence and “Reopen case” in UI. |

---

## Stored per decision (audit)

Each investigator action is logged with:

- `account_id`, `decision`, `reason`, `timestamp`
- `investigator_id` (env `INVESTIGATOR_ID` or `"demo"`)
- `model_version` (env `FRAUD_MODEL_VERSION` or `"v0.3"`)
- Snapshot: `risk_level`, `fraud_probability`, `anomaly_score`
- For Confirmed Fraud: `feature_vector` (for similarity-based “matches N”)

File: `backend/data/investigator_feedback.json`.
