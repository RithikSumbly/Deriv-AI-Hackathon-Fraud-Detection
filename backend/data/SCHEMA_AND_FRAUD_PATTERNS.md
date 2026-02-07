# Synthetic fraud dataset — schema and fraud patterns

## Pandas-friendly schema

| Column | Type | Description |
|--------|------|-------------|
| `account_id` | str | Unique account identifier |
| `declared_income_annual` | float | Self-declared annual income (USD) |
| `total_deposits_90d` | float | Sum of deposits in last 90 days (USD) |
| `total_withdrawals_90d` | float | Sum of withdrawals in last 90 days (USD) |
| `num_deposits_90d` | int | Count of deposit transactions |
| `num_withdrawals_90d` | int | Count of withdrawal transactions |
| `deposit_withdraw_cycle_days_avg` | float | Avg days between deposit and next withdrawal |
| `vpn_usage_pct` | float | % of sessions using VPN (0–100) |
| `countries_accessed_count` | int | Distinct countries from which account was accessed |
| `device_id` | str | Primary device identifier |
| `ip_hash` | str | Hashed IP prefix (for shared-IP detection) |
| `account_age_days` | int | Days since account creation |
| `kyc_face_match_score` | float | KYC face match confidence (0–1) |
| `is_fraud` | bool | **Target**: confirmed fraud (True) or legitimate (False) |

## Fraud patterns (why `is_fraud=True` is predictable)

1. **Deposits far above declared income**  
   Fraud accounts deposit 2–8× their declared annual income within 90 days (illicit fund movement). Legit accounts stay within ~12–35% of annual income in 90 days.

2. **Shared devices and IPs**  
   Fraud accounts share a small pool of `device_id` and `ip_hash` values (many accounts per device/IP). Legit accounts use a large pool (mostly one device, one or few IPs per account).

3. **VPN usage disproportionate**  
   Fraud: 55–95% of sessions over VPN. Legit: 2–18%. Used to hide location and evade geo-checks.

4. **Faster deposit–withdraw cycles**  
   Fraud: average 1.2–6 days between deposit and withdrawal (quick cycling). Legit: 12–35 days (normal holding behavior).

5. **Lower KYC face match score**  
   Fraud: 0.50–0.88 (synthetic/borrowed IDs or poor submissions). Legit: 0.88–0.998.

6. **More countries accessed**  
   Fraud: 3–12 distinct countries. Legit: 1–4. Reflects access from multiple regions/VPN endpoints.

## Usage

```bash
cd backend
pip install -r requirements.txt
python scripts/generate_synthetic_data.py
```

Output: `backend/data/synthetic_fraud_dataset.csv` (5,000 rows, ~5% fraud).
