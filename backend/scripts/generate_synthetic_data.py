#!/usr/bin/env python3
"""
Synthetic dataset for client-side fraud detection.

Schema (pandas-friendly):
- account_id (str): unique account identifier
- declared_income_annual (float): self-declared annual income, USD
- total_deposits_90d (float): sum of deposits in last 90 days, USD
- total_withdrawals_90d (float): sum of withdrawals in last 90 days, USD
- num_deposits_90d (int): count of deposit transactions
- num_withdrawals_90d (int): count of withdrawal transactions
- deposit_withdraw_cycle_days_avg (float): average days between deposit and next withdrawal (fast = fraud)
- vpn_usage_pct (float): % of sessions that used VPN, 0–100
- countries_accessed_count (int): distinct countries from which account was accessed
- device_id (str): primary device identifier (shared among fraud rings)
- ip_hash (str): hashed IP prefix for shared-IP detection
- account_age_days (int): days since account creation
- kyc_face_match_score (float): KYC face match confidence, 0–1
- is_fraud (bool): target — confirmed fraud (True) or legitimate (False)

Fraud patterns (why is_fraud=True is correlated with features):
1. Deposits far above declared income — fraudsters move illicit funds; legit users stay ~income-aligned.
2. Shared devices / IPs — fraud rings reuse devices and IPs; legit users mostly 1 device, 1–2 IPs.
3. VPN usage disproportionate — fraudsters hide location; legit users use VPN occasionally.
4. Faster deposit–withdraw cycles — fraudsters cycle money quickly; legit users hold longer.
5. Lower KYC face match — synthetic/borrowed IDs or poor-quality submissions.
"""
from pathlib import Path
import random
import numpy as np
import pandas as pd

RANDOM_SEED = 42
N_ACCOUNTS = 5_000
FRAUD_RATE = 0.05  # ~5% confirmed fraud
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_FILE = OUTPUT_DIR / "synthetic_fraud_dataset.csv"

# Fraud pattern parameters: small pools => sharing
N_FRAUD_DEVICES = 45
N_FRAUD_IPS = 80
N_LEGIT_DEVICES = 4500
N_LEGIT_IPS = 4800


def set_seed():
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)


def generate_accounts() -> pd.DataFrame:
    set_seed()
    n_fraud = int(N_ACCOUNTS * FRAUD_RATE)
    n_legit = N_ACCOUNTS - n_fraud

    # Pre-create shared pools for fraud (device_id, ip_hash)
    fraud_device_pool = [f"DEV-F-{i:04d}" for i in range(N_FRAUD_DEVICES)]
    fraud_ip_pool = [f"IP-F-{i:04d}" for i in range(N_FRAUD_IPS)]
    legit_device_pool = [f"DEV-L-{i:05d}" for i in range(N_LEGIT_DEVICES)]
    legit_ip_pool = [f"IP-L-{i:05d}" for i in range(N_LEGIT_IPS)]

    rows = []

    # --- Fraud accounts ---
    for i in range(n_fraud):
        declared_income = round(np.random.uniform(20_000, 80_000), 2)
        # Fraud: deposits 2–8x annual income in 90 days (impossible for declared income)
        income_mult = np.random.uniform(2.5, 8.0)
        total_deposits_90d = round(declared_income * (income_mult / 4), 2)  # ~quarter of year
        total_withdrawals_90d = round(total_deposits_90d * np.random.uniform(0.7, 0.98), 2)
        num_deposits_90d = int(np.random.randint(5, 35))
        num_withdrawals_90d = int(np.random.randint(4, 32))
        # Fast cycle: 1–6 days average
        deposit_withdraw_cycle_days_avg = round(np.random.uniform(1.2, 6.0), 2)
        vpn_usage_pct = round(np.random.uniform(55, 95), 2)
        countries_accessed_count = int(np.random.randint(3, 12))
        device_id = random.choice(fraud_device_pool)
        ip_hash = random.choice(fraud_ip_pool)
        account_age_days = int(np.random.uniform(14, 180))
        kyc_face_match_score = round(np.random.uniform(0.50, 0.88), 4)
        rows.append({
            "account_id": f"ACC-F-{i:05d}",
            "declared_income_annual": declared_income,
            "total_deposits_90d": total_deposits_90d,
            "total_withdrawals_90d": total_withdrawals_90d,
            "num_deposits_90d": num_deposits_90d,
            "num_withdrawals_90d": num_withdrawals_90d,
            "deposit_withdraw_cycle_days_avg": deposit_withdraw_cycle_days_avg,
            "vpn_usage_pct": vpn_usage_pct,
            "countries_accessed_count": countries_accessed_count,
            "device_id": device_id,
            "ip_hash": ip_hash,
            "account_age_days": account_age_days,
            "kyc_face_match_score": kyc_face_match_score,
            "is_fraud": True,
        })

    # --- Legitimate accounts ---
    for i in range(n_legit):
        declared_income = round(np.random.uniform(25_000, 120_000), 2)
        # Legit: 90d deposits within ~0.15–0.35 of annual income (quarterly-ish)
        frac_income = np.random.uniform(0.12, 0.35)
        total_deposits_90d = round(declared_income * frac_income, 2)
        total_withdrawals_90d = round(total_deposits_90d * np.random.uniform(0.5, 0.95), 2)
        num_deposits_90d = int(np.random.randint(2, 15))
        num_withdrawals_90d = int(np.random.randint(1, 12))
        # Slower cycle: 12–35 days
        deposit_withdraw_cycle_days_avg = round(np.random.uniform(12, 35), 2)
        vpn_usage_pct = round(np.random.uniform(2, 18), 2)
        countries_accessed_count = int(np.random.randint(1, 4))
        device_id = legit_device_pool[i % len(legit_device_pool)]
        ip_hash = legit_ip_pool[i % len(legit_ip_pool)]
        account_age_days = int(np.random.uniform(30, 800))
        kyc_face_match_score = round(np.random.uniform(0.88, 0.998), 4)
        rows.append({
            "account_id": f"ACC-L-{i:05d}",
            "declared_income_annual": declared_income,
            "total_deposits_90d": total_deposits_90d,
            "total_withdrawals_90d": total_withdrawals_90d,
            "num_deposits_90d": num_deposits_90d,
            "num_withdrawals_90d": num_withdrawals_90d,
            "deposit_withdraw_cycle_days_avg": deposit_withdraw_cycle_days_avg,
            "vpn_usage_pct": vpn_usage_pct,
            "countries_accessed_count": countries_accessed_count,
            "device_id": device_id,
            "ip_hash": ip_hash,
            "account_age_days": account_age_days,
            "kyc_face_match_score": kyc_face_match_score,
            "is_fraud": False,
        })

    df = pd.DataFrame(rows)
    # Shuffle so fraud/legit are interleaved
    df = df.sample(frac=1, random_state=RANDOM_SEED).reset_index(drop=True)
    return df


def main():
    df = generate_accounts()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)
    n_fraud = df["is_fraud"].sum()
    print(f"Wrote {len(df)} rows to {OUTPUT_FILE}")
    print(f"Fraud: {n_fraud} ({100 * n_fraud / len(df):.1f}%)")
    print("\nSchema (column → dtype):")
    print(df.dtypes.to_string())
    print("\nSample (first 3 rows):")
    print(df.head(3).to_string())


if __name__ == "__main__":
    main()
