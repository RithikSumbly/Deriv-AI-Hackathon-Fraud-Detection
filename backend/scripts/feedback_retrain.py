#!/usr/bin/env python3
"""
Continuous learning: build a training dataset from investigator feedback and optionally retrain.

1. Load decisions from backend/data/investigator_feedback.json (via feedback service).
2. Join with backend/data/anomaly_scores.csv to get features for each account_id.
3. Export backend/data/feedback_training_data.csv (features + label) for retraining.
4. Optionally run a retrain step (e.g. combine with existing synthetic data and retrain classifier).

Run from project root:
  python backend/scripts/feedback_retrain.py           # export only
  python backend/scripts/feedback_retrain.py --retrain # export and retrain (if enough data)
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add backend to path
BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

DATA_DIR = BACKEND / "data"
MODEL_DIR = BACKEND / "models"
FEATURE_COLS = [
    "declared_income_annual",
    "total_deposits_90d",
    "total_withdrawals_90d",
    "num_deposits_90d",
    "num_withdrawals_90d",
    "deposit_withdraw_cycle_days_avg",
    "vpn_usage_pct",
    "countries_accessed_count",
    "device_shared_count",
    "ip_shared_count",
    "account_age_days",
    "kyc_face_match_score",
    "deposits_vs_income_ratio",
]


def main() -> None:
    from services.feedback import get_feedback_for_retrain

    feedback = get_feedback_for_retrain()
    if not feedback:
        print("No investigator feedback found. Confirm Fraud / Mark Legit / Dismiss as false positive to build training data.")
        return

    import pandas as pd

    anomaly_path = DATA_DIR / "anomaly_scores.csv"
    if not anomaly_path.exists():
        print("anomaly_scores.csv not found. Run the pipeline first to score accounts.")
        return

    scores = pd.read_csv(anomaly_path)
    if "account_id" not in scores.columns:
        print("anomaly_scores.csv must have account_id column.")
        return

    # Build label table from feedback (one row per account: latest decision)
    by_account: dict[str, int] = {}
    for r in feedback:
        aid = r.get("account_id")
        if aid is None:
            continue
        by_account[aid] = int(r["label"])

    account_ids = list(by_account.keys())
    scores_sub = scores[scores["account_id"].isin(account_ids)].copy()
    if scores_sub.empty:
        print("No feedback account_ids found in anomaly_scores.csv.")
        return

    missing = set(account_ids) - set(scores_sub["account_id"].tolist())
    if missing:
        print(f"Warning: {len(missing)} feedback accounts not in anomaly_scores: {list(missing)[:5]}...")

    scores_sub["is_fraud"] = scores_sub["account_id"].map(by_account)
    out_cols = ["account_id", "is_fraud"] + [c for c in FEATURE_COLS if c in scores_sub.columns]
    missing_feat = [c for c in FEATURE_COLS if c not in scores_sub.columns]
    if missing_feat:
        print(f"Warning: missing feature columns in anomaly_scores.csv: {missing_feat}")
    export_df = scores_sub[out_cols].copy()
    out_path = DATA_DIR / "feedback_training_data.csv"
    export_df.to_csv(out_path, index=False)
    print(f"Exported {len(export_df)} rows to {out_path}")

    retrain = "--retrain" in sys.argv
    if retrain and len(export_df) >= 10:
        print("Retrain requested and enough samples; run train_fraud_classifier with feedback_training_data or combined dataset.")
        # Optional: call trainer with feedback_training_data.csv or merge with synthetic and train
        # from train_fraud_classifier import load_and_prepare, train, ...
        # For now we only export; user can merge feedback_training_data with synthetic and run train_fraud_classifier manually.
    elif retrain:
        print("Need at least 10 feedback samples to retrain. Current:", len(export_df))


if __name__ == "__main__":
    main()
