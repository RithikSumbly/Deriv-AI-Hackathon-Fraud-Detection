# Anomaly detection (Isolation Forest) — complement to fraud classifier

## Feature selection

- **Same 13 features as the fraud classifier**: `declared_income_annual`, `total_deposits_90d`, `total_withdrawals_90d`, `num_deposits_90d`, `num_withdrawals_90d`, `deposit_withdraw_cycle_days_avg`, `vpn_usage_pct`, `countries_accessed_count`, `device_shared_count`, `ip_shared_count`, `account_age_days`, `kyc_face_match_score`, `deposits_vs_income_ratio`.
- **Why**: One feature pipeline for both models; no target (`is_fraud`) is used in training. The anomaly model only sees non-fraud accounts, so it learns the distribution of “normal” behavior.
- **Preprocessing**: StandardScaler fitted on legit-only data; then Isolation Forest on the scaled features.

## How anomaly score differs from fraud probability

| | Fraud probability (classifier) | Anomaly score (Isolation Forest) |
|---|--------------------------------|----------------------------------|
| **What it is** | P(fraud \| features) from supervised learning | “How different is this account from normal?” (unsupervised) |
| **Training** | Uses both fraud and legit labels | Uses **only non-fraud** accounts (defines “normal”) |
| **High value means** | Model thinks it’s fraud | Account is unusual relative to legit distribution |
| **Can disagree when** | Novel fraud type → anomaly high, classifier may say legit | Rare but legitimate behavior → anomaly high, still legit |

So: **fraud probability** = “looks like known fraud”; **anomaly score** = “doesn’t look like normal,” which can catch new patterns the classifier never saw.

## When anomaly score should override classifier confidence

**Override (flag for human review / escalate)** when:

- **Anomaly score is HIGH** and **fraud probability is LOW**.

Example rule:

- `anomaly_score > 0.7` and `fraud_probability < 0.3` → treat as **“suspicious — review”** (don’t trust the classifier’s “legit” here).

**Reason**: The classifier only knows patterns it was trained on. Unusual but unlabeled fraud can get low fraud probability; the anomaly detector doesn’t use labels and will still mark the account as unusual. So in that zone (high anomaly, low fraud prob) we defer to human review.

**When both agree** (e.g. both high, or both low): use the classifier for the final fraud/legit decision; anomaly score adds supporting evidence.

## Runnable code

```bash
cd backend
pip install -r requirements.txt
# Optional: train classifier first for combined output
python scripts/train_fraud_classifier.py
python scripts/train_anomaly_detector.py
```

Outputs:

- `models/anomaly_detector.joblib` — fitted Isolation Forest
- `models/anomaly_scaler.joblib` — StandardScaler (legit-only fit)
- `models/config.json` — single file with `anomaly_feature_names`, `anomaly_score_bounds`, `feature_names`, `decision_threshold`
- `data/anomaly_scores.csv` — per-account anomaly (and fraud prob if classifier was run)

To **score new data** in code: load model, scaler, bounds and feature list; build the same 13 features; `scaler.transform(X)`; `model.decision_function(X_scaled)`; then `anomaly_score = -raw` normalized with the saved bounds and clipped to [0,1].
