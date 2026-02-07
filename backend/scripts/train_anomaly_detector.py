#!/usr/bin/env python3
"""
Unsupervised anomaly detection to complement the fraud classifier.

- Isolation Forest trained only on NON-FRAUD accounts (defines "normal").
- Outputs anomaly score per account (high = more anomalous / unusual).
- Explains: feature selection, anomaly vs fraud probability, when to override.

Run: python scripts/train_anomaly_detector.py

Requires: data and (optionally) trained classifier from train_fraud_classifier.py
for combined score comparison.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib

RANDOM_SEED = 42
DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "synthetic_fraud_dataset.csv"
MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
ANOMALY_MODEL_PATH = MODEL_DIR / "anomaly_detector.joblib"
SCALER_PATH = MODEL_DIR / "anomaly_scaler.joblib"
CONFIG_PATH = MODEL_DIR / "config.json"

# Same feature pipeline as fraud classifier (no target leakage; no is_fraud)
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


def load_and_prepare(data_path: Path) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """Load CSV, derive features (same as classifier). Returns X, y, df with account_id."""
    df = pd.read_csv(data_path)
    y = (df["is_fraud"] == True).astype(int)

    device_counts = df["device_id"].map(df["device_id"].value_counts())
    ip_counts = df["ip_hash"].map(df["ip_hash"].value_counts())
    df = df.assign(
        device_shared_count=device_counts.values,
        ip_shared_count=ip_counts.values,
        deposits_vs_income_ratio=df["total_deposits_90d"] / (df["declared_income_annual"] / 4 + 1e-6),
    )
    X = df[FEATURE_COLS].copy()
    return X, y, df[["account_id"]]


def train_on_legit_only(X_legit: np.ndarray) -> tuple[IsolationForest, StandardScaler]:
    """
    Fit scaler and Isolation Forest on legit accounts only.
    Contamination=0 (or small) since we assume training set is clean.
    """
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_legit)

    # contamination=0.05: allow 5% "outliers" in training to avoid overfitting to edge cases
    clf = IsolationForest(
        n_estimators=200,
        max_samples="auto",
        contamination=0.05,
        random_state=RANDOM_SEED,
        n_jobs=-1,
    )
    clf.fit(X_scaled)
    return clf, scaler


def anomaly_scores(
    model: IsolationForest,
    scaler: StandardScaler,
    X: np.ndarray,
    bounds: tuple[float, float] | None = None,
) -> np.ndarray:
    """
    Return anomaly score in [0, 1]: higher = more anomalous.
    sklearn's decision_function: positive = inlier, negative = outlier.
    We use -decision_function; if bounds (min, max) are provided, normalize to [0,1] with clip.
    """
    X_scaled = scaler.transform(X)
    raw = model.decision_function(X_scaled)  # higher = more normal
    shifted = -raw  # higher = more anomalous
    if bounds is not None:
        lo, hi = bounds
        if hi <= lo:
            return np.zeros_like(shifted)
        return np.clip((shifted - lo) / (hi - lo), 0.0, 1.0)
    # No bounds: use this batch's min/max (e.g. for one-off analysis)
    lo, hi = shifted.min(), shifted.max()
    if hi <= lo:
        return np.zeros_like(shifted)
    return (shifted - lo) / (hi - lo)


def main():
    print("Loading data...")
    X, y, meta = load_and_prepare(DATA_PATH)
    X_legit = X[y == 0].values
    n_legit, n_fraud = int((y == 0).sum()), int(y.sum())
    print(f"Training Isolation Forest on {n_legit} non-fraud accounts only (ignoring {n_fraud} fraud).")

    print("\n--- Feature selection ---")
    print(
        "Same 13 features as the classifier: income, deposits/withdrawals (amounts + counts),"
    )
    print(
        "deposit_withdraw_cycle_days_avg, vpn_usage_pct, countries_accessed_count,"
    )
    print(
        "device_shared_count, ip_shared_count, account_age_days, kyc_face_match_score,"
    )
    print("deposits_vs_income_ratio.")
    print(
        "No target (is_fraud) is used; we only learn the distribution of legit accounts."
    )
    print("Features are standardized (StandardScaler) before Isolation Forest.\n")

    print("Training (scaler + Isolation Forest on legit only)...")
    model, scaler = train_on_legit_only(X_legit)

    # Normalization bounds from LEGIT only so production scores are comparable
    X_legit_scaled = scaler.transform(X_legit)
    raw_legit = -model.decision_function(X_legit_scaled)
    score_min, score_max = float(raw_legit.min()), float(raw_legit.max())
    bounds = (score_min, score_max)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, ANOMALY_MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    config = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
    config["anomaly_feature_names"] = FEATURE_COLS
    config["anomaly_score_bounds"] = {"min": score_min, "max": score_max}
    CONFIG_PATH.write_text(json.dumps(config, indent=2))
    print(f"Saved: {ANOMALY_MODEL_PATH}, {SCALER_PATH}, {CONFIG_PATH}")

    # Score everyone using fixed bounds (legit-based)
    scores = anomaly_scores(model, scaler, X.values, bounds=bounds)
    X["anomaly_score"] = scores
    X["account_id"] = meta["account_id"].values
    X["is_fraud"] = y.values

    # Stats by label
    print("\n--- Anomaly score vs fraud (summary) ---")
    print("Legit accounts - anomaly score mean: {:.4f}, std: {:.4f}".format(scores[y == 0].mean(), scores[y == 0].std()))
    print("Fraud accounts - anomaly score mean: {:.4f}, std: {:.4f}".format(scores[y == 1].mean(), scores[y == 1].std()))

    print("\n--- How anomaly score differs from fraud probability ---")
    print(
        "• Fraud probability (classifier): P(fraud|features), learned from labeled fraud vs legit."
    )
    print(
        "• Anomaly score: 'How different is this account from normal?' No fraud labels used;"
    )
    print("  trained only on legit. High score = unusual with respect to legit distribution.")
    print(
        "• They can disagree: novel fraud → anomaly high, classifier may say legit. Rare legit → anomaly high, legit."
    )

    print("\n--- When anomaly score should override classifier confidence ---")
    print(
        "Override (flag for review / escalate) when: anomaly_score is HIGH and fraud_probability is LOW."
    )
    print(
        "  Example rule: if anomaly_score > 0.7 and fraud_probability < 0.3 → treat as 'suspicious, review'."
    )
    print(
        "  Reason: classifier may miss new fraud patterns; anomaly detector catches 'unusual' regardless of labels."
    )
    print(
        "  When both agree (e.g. both high): trust classifier for the final fraud/legit call; anomaly adds evidence."
    )

    # Combined example: load classifier if present and show one account with both scores
    try:
        import lightgbm as lgb
        clf_path = MODEL_DIR / "fraud_classifier.txt"
        if clf_path.exists() and CONFIG_PATH.exists():
            bst = lgb.Booster(model_file=str(clf_path))
            config = json.loads(CONFIG_PATH.read_text())
            thresh = config.get("decision_threshold", {}).get("threshold", 0.5)
            proba = bst.predict(X[FEATURE_COLS])
            X["fraud_probability"] = proba
            X["anomaly_override"] = (X["anomaly_score"] > 0.7) & (X["fraud_probability"] < 0.3)
            n_override = X["anomaly_override"].sum()
            print(f"\n--- Combined rule (anomaly_score > 0.7 and fraud_probability < 0.3) ---")
            print(f"Accounts flagged for review (override): {int(n_override)}")
            # One example where override triggers
            override = X[X["anomaly_override"]]
            if len(override) > 0:
                ex = override.iloc[0]
                print("\nExample account where anomaly overrides (flag for review):")
                print(json.dumps({
                    "account_id": ex["account_id"],
                    "fraud_probability": round(float(ex["fraud_probability"]), 4),
                    "anomaly_score": round(float(ex["anomaly_score"]), 4),
                    "recommendation": "Flag for review (high anomaly, low classifier confidence)",
                }, indent=2))
            # Save combined scores sample
            out_path = MODEL_DIR.parent / "data" / "anomaly_scores.csv"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            X.drop(columns=["anomaly_override"], errors="ignore").to_csv(out_path, index=False)
            print(f"\nFull scores (with fraud_probability if classifier present) saved to {out_path}")
    except Exception as e:
        print(f"\nClassifier not loaded (run train_fraud_classifier.py first for combined output): {e}")
        out_path = MODEL_DIR.parent / "data" / "anomaly_scores.csv"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        X.to_csv(out_path, index=False)
        print(f"Anomaly scores only saved to {out_path}")

    return model, scaler


def load_anomaly_pipeline():
    """Load saved model, scaler, feature names, and bounds from config.json."""
    model = joblib.load(ANOMALY_MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    config = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
    features = config.get("anomaly_feature_names", FEATURE_COLS)
    b = config.get("anomaly_score_bounds", {"min": 0.0, "max": 1.0})
    bounds = (b["min"], b["max"])
    return model, scaler, features, bounds


def score_accounts(X: pd.DataFrame, feature_cols: list[str] | None = None) -> np.ndarray:
    """
    Return anomaly score [0,1] for each row of X.
    X must contain the same feature columns (same order as feature_cols or FEATURE_COLS).
    """
    model, scaler, features, bounds = load_anomaly_pipeline()
    cols = feature_cols or features
    X_arr = X[cols].values
    return anomaly_scores(model, scaler, X_arr, bounds=bounds)


if __name__ == "__main__":
    main()
