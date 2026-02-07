# Fraud classifier — feature importance and explainability

## How the model works

- **Model**: LightGBM binary classifier.
- **Class imbalance**: Handled with `scale_pos_weight` = (number of legit) / (number of fraud).
- **Output**: Fraud **probability** per account; decision uses an F1-optimal threshold (saved in `models/config.json` under `decision_threshold`).
- **Explainability**: SHAP (TreeExplainer) for global feature importance and per-account drivers.

## Feature importance (what to expect)

| Feature | Meaning | Fraud signal |
|--------|--------|---------------|
| `deposits_vs_income_ratio` | 90d deposits / (annual income ÷ 4) | High → income mismatch → fraud |
| `deposit_withdraw_cycle_days_avg` | Avg days between deposit and withdrawal | Low (fast cycle) → fraud |
| `vpn_usage_pct` | % of sessions over VPN | High → fraud |
| `device_shared_count` | # accounts sharing same device_id | High → fraud ring |
| `ip_shared_count` | # accounts sharing same ip_hash | High → fraud ring |
| `kyc_face_match_score` | KYC face match 0–1 | Low → fraud |
| `countries_accessed_count` | # distinct countries | High → fraud |
| `account_age_days` | Days since signup | Often lower for fraud |
| Others | Declared income, deposit/withdrawal amounts and counts | Supporting signals |

Importance (gain) can vary by run; on this synthetic data one feature (e.g. VPN) may dominate because the data is highly separable.

## Example output for one account

The training script prints two examples: one high-risk (fraud) and one low-risk (legit). Each includes:

- `account_id`, `fraud_probability`, `predicted_label`, `actual_label`
- `decision_threshold_used` (F1-optimal threshold)
- `top_shap_drivers`: top 5 features by |SHAP| with value, SHAP effect, and direction (pushes toward FRAUD vs LEGIT)

Use these for human-in-the-loop: analysts see the score plus **why** (which features pushed the score up or down).
