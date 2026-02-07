#!/usr/bin/env python3
"""
Generate a realistic synthetic UNLABELED dataset for testing AI-powered fraud detection.

No column in the output indicates fraud. Fraud is only inferable from patterns,
anomalies, and network signals. Returns a pandas DataFrame and an optional
evaluation dict (account_id -> fraud_flag) for benchmarking only.

Hidden fraud logic (comments only; not in data):
- ~5–8% of accounts are fraudulent; fraud clusters (≥10) share device_id and ip_address.
- Fraud: higher deposit_income_ratio, faster deposit_withdraw_time_hours, higher
  vpn_login_ratio, more high_risk_country_access, lower KYC/face scores, elevated
  shared_device_count / shared_ip_count / linked_account_count.
- Legit users may trigger 1–2 risk indicators (edge cases: high ratio, high VPN,
  fast cycle, weak KYC, high-risk country). Subtle fraud avoids obvious thresholds
  via distribution variance (e.g. 2 strong + 1 moderate signal).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

# -----------------------------------------------------------------------------
# Config (fraud rate and cluster structure are HIDDEN from the dataset)
# -----------------------------------------------------------------------------
RANDOM_SEED = 42
N_ACCOUNTS = 10_000
# Hidden fraud rate: ~5–8% (not stated in data). We use ~6.5%.
FRAUD_RATE = 0.065
# At least 10 hidden fraud clusters: shared device_id and ip_address pools used by fraud rings
N_FRAUD_CLUSTER_DEVICES = 12
N_FRAUD_CLUSTER_IPS = 18
# Legit users get mostly unique or lightly shared devices/IPs
N_LEGIT_DEVICE_POOL = 8500
N_LEGIT_IP_POOL = 9000

# Countries: a few high-risk for access patterns
HIGH_RISK_COUNTRIES = {"XX", "YY", "ZZ"}  # fictional codes
ALL_COUNTRIES = list("GB US DE FR NL IN SG AU CA ES IT BR MX".split()) + list(HIGH_RISK_COUNTRIES)


def _set_seed() -> None:
    np.random.seed(RANDOM_SEED)


def _hidden_fraud_assignment(n: int) -> tuple[np.ndarray, list[str], list[str], np.ndarray]:
    """
    Internally assign fraud vs legit and assign cluster devices/IPs.
    Returns: (is_fraud bool array, list device_ids, list ip_addresses, cluster_id per account).
    Fraud clusters: groups of fraud accounts share the same device_id and ip_address.
    """
    n_fraud = int(round(n * FRAUD_RATE))
    n_legit = n - n_fraud
    is_fraud = np.zeros(n, dtype=bool)
    fraud_ix = np.random.choice(n, size=n_fraud, replace=False)
    is_fraud[fraud_ix] = True

    # At least 10 fraud clusters: each cluster has a shared device and shared IP
    n_clusters = max(10, n_fraud // 50)
    cluster_devices = [f"DEV-C{i:02d}" for i in range(n_clusters)]
    cluster_ips = [f"IP-C{i:02d}" for i in range(n_clusters)]

    device_ids = [None] * n
    ip_addresses = [None] * n
    cluster_id = np.full(n, -1, dtype=int)

    fraud_indices = np.where(is_fraud)[0]
    np.random.shuffle(fraud_indices)
    for i, idx in enumerate(fraud_indices):
        c = i % n_clusters
        cluster_id[idx] = c
        device_ids[idx] = cluster_devices[c]
        # Same cluster often shares IP; sometimes 2 clusters share an IP (overlap)
        ip_addresses[idx] = cluster_ips[c] if np.random.rand() < 0.85 else cluster_ips[(c + 1) % n_clusters]

    # Legit: mostly unique device/IP; some sharing (e.g. family) to create edge cases
    legit_device_pool = [f"DEV-L{i:05d}" for i in range(N_LEGIT_DEVICE_POOL)]
    legit_ip_pool = [f"IP-L{i:05d}" for i in range(N_LEGIT_IP_POOL)]
    for idx in np.where(~is_fraud)[0]:
        # Most legit get unique; ~5% share a device (e.g. same household)
        if np.random.rand() < 0.95:
            device_ids[idx] = np.random.choice(legit_device_pool)
            ip_addresses[idx] = np.random.choice(legit_ip_pool)
        else:
            d = np.random.choice(legit_device_pool)
            device_ids[idx] = d
            ip_addresses[idx] = np.random.choice(legit_ip_pool)

    return is_fraud, device_ids, ip_addresses, cluster_id


def _derive_network_counts(
    device_ids: list[str],
    ip_addresses: list[str],
    is_fraud: np.ndarray,
) -> tuple[list[int], list[int], list[int]]:
    """Compute shared_device_count, shared_ip_count, linked_account_count from device/IP lists."""
    from collections import Counter
    dev_counts = Counter(device_ids)
    ip_counts = Counter(ip_addresses)
    shared_device_count = [dev_counts[d] - 1 for d in device_ids]  # others sharing this device
    shared_ip_count = [ip_counts[ip] - 1 for ip in ip_addresses]
    # Linked: same device or same IP
    linked = []
    for i in range(len(device_ids)):
        ld = dev_counts[device_ids[i]] - 1
        li = ip_counts[ip_addresses[i]] - 1
        linked.append(ld + li)  # simple proxy for "linked accounts"
    return shared_device_count, shared_ip_count, linked


def generate_unlabeled_fraud_dataset() -> tuple[pd.DataFrame, dict[str, bool]]:
    """
    Generate 10,000-account unlabeled dataset. Fraud is only detectable via patterns.
    Returns: (DataFrame with no fraud column, eval_dict mapping account_id -> fraud_flag).
    """
    _set_seed()
    n = N_ACCOUNTS

    # ----- Hidden state (never written to the dataset) -----
    # is_fraud: which accounts are fraudulent (for eval only). cluster_id used to correlate
    # device_id and ip_address within fraud rings so shared_device_count / shared_ip_count
    # and linked_account_count emerge as network signals (no explicit fraud label).
    is_fraud, device_ids, ip_addresses, cluster_id = _hidden_fraud_assignment(n)

    # ----- Account IDs -----
    account_ids = [f"ACC-{i:06d}" for i in range(n)]

    # ----- Account profile -----
    # Hidden fraud logic: fraud accounts tend to be younger (shorter account_age_days) and
    # declare lower monthly income; no column labels this—only correlation with behavior.
    account_age_days = np.where(
        is_fraud,
        np.random.lognormal(mean=5.5, sigma=1.2, size=n).astype(int).clip(1, 2000),
        np.random.lognormal(mean=6.0, sigma=1.0, size=n).astype(int).clip(30, 2500),
    )
    country_of_registration = np.random.choice(ALL_COUNTRIES, size=n)

    # Declared income: fraud often under-declares or uses modest declared income
    declared_monthly_income = np.random.lognormal(mean=8.5, sigma=0.6, size=n).clip(800, 25000)
    if is_fraud.any():
        declared_monthly_income[is_fraud] = np.random.lognormal(mean=8.0, sigma=0.5, size=is_fraud.sum()).clip(800, 12000)

    # ----- Behavioral signals -----
    # Hidden: fraud tends to have high deposit_income_ratio, fast deposit_withdraw_time_hours,
    # and high num_deposits/withdrawals; legit may have 1–2 of these (edge cases added below).
    deposit_income_ratio = np.ones(n)
    deposit_income_ratio[~is_fraud] = np.random.lognormal(mean=0.0, sigma=0.4, size=(~is_fraud).sum()).clip(0.2, 3.0)
    deposit_income_ratio[is_fraud] = np.random.lognormal(mean=0.8, sigma=0.5, size=is_fraud.sum()).clip(1.2, 8.0)
    # Some legit edge cases: high ratio (e.g. savings, bonus) but other signals clean
    legit_high_ratio_ix = np.random.choice(np.where(~is_fraud)[0], size=min(80, (~is_fraud).sum()), replace=False)
    deposit_income_ratio[legit_high_ratio_ix] = np.random.uniform(2.0, 4.0, size=len(legit_high_ratio_ix))

    avg_monthly_deposit = (declared_monthly_income * deposit_income_ratio).round(2)
    avg_monthly_withdrawal = np.where(
        is_fraud,
        avg_monthly_deposit * np.random.uniform(0.85, 1.02, size=n),  # fraud: withdraw most of what they deposit
        avg_monthly_deposit * np.random.uniform(0.3, 0.9, size=n),
    ).round(2)

    num_deposits_30d = np.where(
        is_fraud,
        np.random.poisson(8, size=n) + np.random.randint(2, 12, size=n),
        np.random.poisson(4, size=n) + np.random.randint(0, 5, size=n),
    ).clip(1, 50)
    num_withdrawals_30d = np.where(
        is_fraud,
        num_deposits_30d + np.random.randint(-2, 3, size=n),
        np.random.poisson(3, size=n) + np.random.randint(0, 4, size=n),
    ).clip(0, 50)

    # deposit_withdraw_time_hours: fraud = faster (layering); legit = slower
    deposit_withdraw_time_hours = np.where(
        is_fraud,
        np.random.exponential(24, size=n).clip(0.5, 72),
        np.random.lognormal(mean=3.5, sigma=1.2, size=n).clip(24, 720),
    ).round(1)
    # Edge case: some legit with fast cycle (day traders, etc.)
    fast_legit_ix = np.random.choice(np.where(~is_fraud)[0], size=min(50, (~is_fraud).sum()), replace=False)
    deposit_withdraw_time_hours[fast_legit_ix] = np.random.uniform(12, 48, size=len(fast_legit_ix))

    net_flow_ratio = (avg_monthly_deposit - avg_monthly_withdrawal) / (avg_monthly_deposit + 1e-6)
    net_flow_ratio = np.clip(net_flow_ratio, -1, 1).round(3)

    # ----- Access & device signals -----
    num_logins_30d = np.random.poisson(20, size=n) + np.random.randint(0, 30, size=n)
    # Hidden: fraud has higher vpn_login_ratio and more high_risk_country_access; some legit
    # have high VPN or high-risk access (edge cases) so thresholds are not trivial.
    vpn_login_ratio = np.random.beta(2, 8, size=n).round(3)
    vpn_login_ratio[is_fraud] = np.random.beta(5, 2, size=is_fraud.sum()).round(3).clip(0.3, 0.98)
    # Some legit with high VPN (remote workers)
    vpn_legit_ix = np.random.choice(np.where(~is_fraud)[0], size=min(120, (~is_fraud).sum()), replace=False)
    vpn_login_ratio[vpn_legit_ix] = np.random.uniform(0.5, 0.9, size=len(vpn_legit_ix))

    # countries_accessed: list of country codes (stored as JSON string for CSV). Fraud often accesses more countries and high-risk jurisdictions.
    high_risk_list = list(HIGH_RISK_COUNTRIES)
    countries_accessed = []
    high_risk_country_access = np.zeros(n, dtype=bool)
    for i in range(n):
        n_countries = np.random.poisson(2) + 1 if not is_fraud[i] else np.random.poisson(4) + 2
        n_countries = min(n_countries, len(ALL_COUNTRIES))
        chosen = np.random.choice(ALL_COUNTRIES, size=n_countries, replace=False).tolist()
        # Hidden: fraud has ~40% chance of including a high-risk country; legit ~2%
        if is_fraud[i] and np.random.rand() < 0.4:
            chosen.append(np.random.choice(high_risk_list))
        elif not is_fraud[i] and np.random.rand() < 0.02:
            chosen.append(np.random.choice(high_risk_list))
        chosen = list(dict.fromkeys(chosen))
        countries_accessed.append(json.dumps(chosen))
        high_risk_country_access[i] = any(h in chosen for h in high_risk_list)
    # Edge case: some legit with high-risk country (e.g. expat, travel)
    high_risk_legit = np.random.choice(np.where(~is_fraud)[0], size=min(60, (~is_fraud).sum()), replace=False)
    for ix in high_risk_legit:
        lst = json.loads(countries_accessed[ix])
        if not any(h in lst for h in high_risk_list):
            lst.append(np.random.choice(high_risk_list))
            countries_accessed[ix] = json.dumps(lst)
            high_risk_country_access[ix] = True

    # ----- Identity verification -----
    # Hidden: fraud has lower kyc_doc_score and face_match_score and more selfie_liveness_pass=False;
    # a few legit have weak KYC (edge case) so identity alone is not a perfect signal.
    kyc_doc_score = np.random.beta(8, 2, size=n).round(3)
    kyc_doc_score[is_fraud] = np.random.beta(4, 4, size=is_fraud.sum()).round(3).clip(0.3, 0.95)
    face_match_score = np.random.beta(9, 2, size=n).round(3)
    face_match_score[is_fraud] = np.random.beta(3, 4, size=is_fraud.sum()).round(3).clip(0.25, 0.88)
    selfie_liveness_pass = np.random.binomial(1, 0.97, size=n).astype(bool)
    selfie_liveness_pass[is_fraud] = np.random.binomial(1, 0.72, size=is_fraud.sum()).astype(bool)
    # Legit with weak KYC (edge case)
    weak_kyc_ix = np.random.choice(np.where(~is_fraud)[0], size=min(40, (~is_fraud).sum()), replace=False)
    face_match_score[weak_kyc_ix] = np.random.uniform(0.5, 0.75, size=len(weak_kyc_ix))

    # ----- Network indicators -----
    # Hidden: fraud clusters share device_id and ip_address so shared_device_count,
    # shared_ip_count, and linked_account_count are elevated for fraud; legit mostly 0–1.
    # At least 10 clusters created in _hidden_fraud_assignment; no label in data.
    shared_device_count, shared_ip_count, linked_account_count = _derive_network_counts(
        device_ids, ip_addresses, is_fraud
    )

    # ----- Build DataFrame (NO fraud column) -----
    df = pd.DataFrame({
        "account_id": account_ids,
        "declared_monthly_income": declared_monthly_income,
        "account_age_days": account_age_days,
        "country_of_registration": country_of_registration,
        "avg_monthly_deposit": avg_monthly_deposit,
        "avg_monthly_withdrawal": avg_monthly_withdrawal,
        "deposit_income_ratio": deposit_income_ratio,
        "num_deposits_30d": num_deposits_30d,
        "num_withdrawals_30d": num_withdrawals_30d,
        "deposit_withdraw_time_hours": deposit_withdraw_time_hours,
        "net_flow_ratio": net_flow_ratio,
        "num_logins_30d": num_logins_30d,
        "vpn_login_ratio": vpn_login_ratio,
        "countries_accessed": countries_accessed,
        "high_risk_country_access": high_risk_country_access,
        "device_id": device_ids,
        "ip_address": ip_addresses,
        "kyc_doc_score": kyc_doc_score,
        "face_match_score": face_match_score,
        "selfie_liveness_pass": selfie_liveness_pass,
        "shared_device_count": shared_device_count,
        "shared_ip_count": shared_ip_count,
        "linked_account_count": linked_account_count,
    })

    eval_dict = {aid: bool(flag) for aid, flag in zip(account_ids, is_fraud)}
    return df, eval_dict


def main() -> None:
    out_dir = Path(__file__).resolve().parent.parent / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    df, eval_dict = generate_unlabeled_fraud_dataset()
    df.to_csv(out_dir / "unlabeled_fraud_dataset.csv", index=False)
    eval_path = out_dir / "unlabeled_fraud_eval.json"
    with open(eval_path, "w") as f:
        json.dump(eval_dict, f, indent=0)
    print(f"Saved {len(df)} rows to {out_dir / 'unlabeled_fraud_dataset.csv'}")
    print(f"Saved eval dict ({sum(eval_dict.values())} fraud) to {eval_path}")
    return


if __name__ == "__main__":
    main()
