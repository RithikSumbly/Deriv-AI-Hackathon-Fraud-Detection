#!/usr/bin/env python3
"""
Run the fraud detection pipeline on the unlabeled dataset.

1. Load unlabeled_fraud_dataset.csv and map columns to the schema expected by
   the trained fraud classifier and anomaly detector.
2. Run both models to get fraud_probability and anomaly_score per account.
3. Write backend/data/anomaly_scores.csv so the dashboard (alerts service) uses it.
4. Optionally compare with unlabeled_fraud_eval.json and print metrics.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
UNLABELED_CSV = DATA_DIR / "unlabeled_fraud_dataset.csv"
EVAL_JSON = DATA_DIR / "unlabeled_fraud_eval.json"
ANOMALY_OUTPUT = DATA_DIR / "anomaly_scores.csv"

# Same 13 features as train_fraud_classifier / train_anomaly_detector
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


def load_and_map_unlabeled(csv_path: Path) -> pd.DataFrame:
    """Load unlabeled CSV and map to classifier/anomaly feature schema."""
    df = pd.read_csv(csv_path)

    # Map to legacy schema (90d equivalents, annual income, etc.)
    df = df.assign(
        declared_income_annual=df["declared_monthly_income"] * 12,
        total_deposits_90d=df["avg_monthly_deposit"] * 3,
        total_withdrawals_90d=df["avg_monthly_withdrawal"] * 3,
        num_deposits_90d=(df["num_deposits_30d"] * 3).clip(1, 200).astype(int),
        num_withdrawals_90d=(df["num_withdrawals_30d"] * 3).clip(0, 200).astype(int),
        deposit_withdraw_cycle_days_avg=(df["deposit_withdraw_time_hours"] / 24).clip(0.1, 90),
        vpn_usage_pct=(df["vpn_login_ratio"] * 100).clip(0, 100),
        countries_accessed_count=df["countries_accessed"].apply(
            lambda s: len(json.loads(s)) if isinstance(s, str) else 1
        ),
        device_shared_count=df["shared_device_count"],
        ip_shared_count=df["shared_ip_count"],
        account_age_days=df["account_age_days"],
        kyc_face_match_score=df["face_match_score"],
        deposits_vs_income_ratio=df["deposit_income_ratio"],
    )
    return df


def run_classifier(df: pd.DataFrame, model_path: Path) -> np.ndarray:
    """Return fraud probability per row (positive class)."""
    import lightgbm as lgb
    model = lgb.Booster(model_file=str(model_path))
    X = df[FEATURE_COLS].astype(float)
    return model.predict(X)


def run_anomaly_detector(df: pd.DataFrame, model_path: Path, scaler_path: Path, config_path: Path) -> np.ndarray:
    """Return anomaly score in [0, 1] per row."""
    import joblib
    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    bounds = (0.0, 1.0)
    if config_path.exists():
        cfg = json.loads(config_path.read_text())
        b = cfg.get("anomaly_score_bounds", {})
        if "min" in b and "max" in b:
            bounds = (b["min"], b["max"])
    X = df[FEATURE_COLS].astype(float).values
    X_scaled = scaler.transform(X)
    raw = model.decision_function(X_scaled)
    shifted = -raw
    lo, hi = bounds
    if hi > lo:
        return np.clip((shifted - lo) / (hi - lo), 0.0, 1.0)
    return np.zeros(len(X))


def main() -> None:
    if not UNLABELED_CSV.exists():
        raise FileNotFoundError(f"Run generate_unlabeled_fraud_data.py first to create {UNLABELED_CSV}")

    print("Loading unlabeled dataset and mapping to model schema...")
    df = load_and_map_unlabeled(UNLABELED_CSV)
    X = df[FEATURE_COLS].astype(float)
    account_ids = df["account_id"].tolist()

    # Fraud classifier
    classifier_path = MODEL_DIR / "fraud_classifier.txt"
    if classifier_path.exists():
        print("Running fraud classifier...")
        fraud_probability = run_classifier(df, classifier_path)
    else:
        print("No fraud classifier found; using heuristic score from deposit_income_ratio and VPN.")
        fraud_probability = (
            np.clip(df["deposits_vs_income_ratio"] / 4.0, 0, 1) * 0.5
            + df["vpn_login_ratio"] * 0.3
            + (1 - df["face_match_score"]) * 0.2
        ).values

    # Anomaly detector
    anomaly_path = MODEL_DIR / "anomaly_detector.joblib"
    scaler_path = MODEL_DIR / "anomaly_scaler.joblib"
    config_path = MODEL_DIR / "config.json"
    if anomaly_path.exists() and scaler_path.exists():
        print("Running anomaly detector...")
        anomaly_score = run_anomaly_detector(df, anomaly_path, scaler_path, config_path)
    else:
        print("No anomaly model found; using normalized deposit_income_ratio as proxy.")
        anomaly_score = np.clip((df["deposits_vs_income_ratio"] - 0.5) / 2.0, 0, 1).values

    # Build output like existing anomaly_scores.csv (no is_fraud column for unlabeled)
    out = df[FEATURE_COLS].copy()
    out["anomaly_score"] = anomaly_score
    out["account_id"] = account_ids
    out["fraud_probability"] = np.clip(fraud_probability, 0, 1)
    # Reorder so account_id, fraud_probability, anomaly_score are easy to find
    cols = ["account_id", "fraud_probability", "anomaly_score"] + FEATURE_COLS
    out = out[[c for c in cols if c in out.columns]]
    out.to_csv(ANOMALY_OUTPUT, index=False)
    print(f"Wrote {ANOMALY_OUTPUT} ({len(out)} rows).")

    # Optional: eval vs ground truth
    if EVAL_JSON.exists():
        with open(EVAL_JSON) as f:
            eval_dict = json.load(f)
        y_true = np.array([int(eval_dict.get(aid, False)) for aid in account_ids])
        y_prob = out["fraud_probability"].values
        from sklearn.metrics import roc_auc_score, average_precision_score
        roc = roc_auc_score(y_true, y_prob)
        pr = average_precision_score(y_true, y_prob)
        print(f"\nEval (ground truth from {EVAL_JSON}):")
        print(f"  Fraud count (actual): {y_true.sum()}")
        print(f"  ROC-AUC: {roc:.4f}")
        print(f"  PR-AUC:  {pr:.4f}")
        pred_05 = (y_prob >= 0.5).astype(int)
        tp = ((pred_05 == 1) & (y_true == 1)).sum()
        fp = ((pred_05 == 1) & (y_true == 0)).sum()
        fn = ((pred_05 == 0) & (y_true == 1)).sum()
        print(f"  At 0.5 threshold: TP={tp}, FP={fp}, FN={fn}")

    print("\nYou can now run the dashboard: streamlit run frontend/app.py")
    return


if __name__ == "__main__":
    main()
