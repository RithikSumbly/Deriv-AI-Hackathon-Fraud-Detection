#!/usr/bin/env python3
"""
LightGBM fraud classifier for the synthetic client-side fraud dataset.

- Binary classification (fraud / not fraud)
- Class imbalance handled via scale_pos_weight
- Outputs fraud probability per account
- SHAP explainability for feature importance and per-account explanations

Run: python scripts/train_fraud_classifier.py
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import lightgbm as lgb
import shap
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    average_precision_score,
    f1_score,
)

RANDOM_SEED = 42
DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "synthetic_fraud_dataset.csv"
MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
MODEL_PATH = MODEL_DIR / "fraud_classifier.txt"
CONFIG_PATH = MODEL_DIR / "config.json"


def load_and_prepare(data_path: Path) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    """Load CSV, derive features, return X, y, feature_names."""
    df = pd.read_csv(data_path)

    # Target
    y = (df["is_fraud"] == True).astype(int)  # 1 = fraud, 0 = legit

    # Shared device/IP counts (interpretable proxy for "same device/IP")
    device_counts = df["device_id"].map(df["device_id"].value_counts())
    ip_counts = df["ip_hash"].map(df["ip_hash"].value_counts())
    df = df.assign(
        device_shared_count=device_counts.values,
        ip_shared_count=ip_counts.values,
    )

    # Ratio: 90d deposits vs quarter of declared income (high => income mismatch)
    df["deposits_vs_income_ratio"] = df["total_deposits_90d"] / (
        df["declared_income_annual"] / 4 + 1e-6
    )

    feature_cols = [
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
    X = df[feature_cols].copy()
    X.columns = [c for c in feature_cols]
    return X, y, list(X.columns)


def train(
    X: pd.DataFrame,
    y: pd.Series,
    feature_names: list[str],
) -> lgb.Booster:
    """Train LightGBM with class imbalance handling; return booster."""
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    scale_pos_weight = n_neg / max(n_pos, 1)

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=RANDOM_SEED
    )

    train_data = lgb.Dataset(X_train, label=y_train, feature_name=feature_names)
    val_data = lgb.Dataset(X_val, label=y_val, reference=train_data, feature_name=feature_names)

    params = {
        "objective": "binary",
        "metric": "auc",
        "boosting_type": "gbdt",
        "num_leaves": 31,
        "learning_rate": 0.05,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "verbose": -1,
        "seed": RANDOM_SEED,
        "scale_pos_weight": scale_pos_weight,  # handle ~5% fraud
    }

    callbacks = [lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)]
    model = lgb.train(
        params,
        train_data,
        num_boost_round=500,
        valid_sets=[val_data],
        callbacks=callbacks,
    )
    return model


def explain_with_shap(model: lgb.Booster, X: pd.DataFrame, feature_names: list[str], n_sample: int = 500):
    """SHAP TreeExplainer; return explainer and values on a sample (for speed)."""
    X_sample = X.sample(n=min(n_sample, len(X)), random_state=RANDOM_SEED)
    explainer = shap.TreeExplainer(model, data=X_sample, feature_perturbation="interventional")
    shap_values = explainer.shap_values(X_sample)
    return explainer, shap_values, X_sample


def feature_importance_explanation(importance: dict) -> str:
    """Human-readable feature importance explanation."""
    lines = [
        "Feature importance (gain):",
        "  - Higher gain = feature is used more often in splits and to separate fraud vs legit.",
        "  - deposits_vs_income_ratio: deposits far above declared income (strong fraud signal).",
        "  - deposit_withdraw_cycle_days_avg: fast cycles (low days) → more fraud.",
        "  - vpn_usage_pct: high VPN % → more fraud.",
        "  - device_shared_count / ip_shared_count: many accounts on same device/IP → fraud ring.",
        "  - kyc_face_match_score: lower score → more fraud.",
        "  - countries_accessed_count: more countries → more fraud.",
        "",
        "Sorted importance (gain):",
    ]
    for name, gain in sorted(importance.items(), key=lambda x: -x[1]):
        lines.append(f"  {name}: {gain:.2f}")
    return "\n".join(lines)


def example_account_output(
    account_id: str,
    fraud_prob: float,
    is_fraud_actual: bool,
    shap_values_one: np.ndarray,
    feature_names: list[str],
    feature_values_one: np.ndarray,
    decision_threshold: float = 0.5,
) -> dict:
    """Build example output for one account (probability + top SHAP drivers)."""
    # Top 5 drivers (by absolute SHAP value) for this prediction
    order = np.argsort(np.abs(shap_values_one))[::-1][:5]
    top_drivers = [
        {
            "feature": feature_names[i],
            "value": round(float(feature_values_one[i]), 4),
            "shap_effect": round(float(shap_values_one[i]), 4),
            "direction": "pushes toward FRAUD" if shap_values_one[i] > 0 else "pushes toward LEGIT",
        }
        for i in order
    ]
    return {
        "account_id": account_id,
        "fraud_probability": round(fraud_prob, 4),
        "predicted_label": "fraud" if fraud_prob >= decision_threshold else "legit",
        "actual_label": "fraud" if is_fraud_actual else "legit",
        "decision_threshold_used": decision_threshold,
        "top_shap_drivers": top_drivers,
    }


def main():
    print("Loading data...")
    X, y, feature_names = load_and_prepare(DATA_PATH)
    print(f"Features: {feature_names}")
    print(f"Class balance: fraud={y.sum()}, legit={len(y) - y.sum()}")

    print("\nTraining LightGBM (class imbalance via scale_pos_weight)...")
    model = train(X, y, feature_names)

    # Threshold that maximizes F1 (compute before saving config)
    proba = model.predict(X)
    thresholds = np.linspace(0.05, 0.95, 19)
    best_t = 0.5
    best_f1 = 0.0
    for t in thresholds:
        f1 = f1_score(y, (proba >= t).astype(int), zero_division=0)
        if f1 > best_f1:
            best_f1, best_t = f1, t
    pred = (proba >= best_t).astype(int)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model.save_model(str(MODEL_PATH))
    config = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
    config["feature_names"] = feature_names
    config["decision_threshold"] = {"threshold": float(best_t)}
    CONFIG_PATH.write_text(json.dumps(config, indent=2))
    print(f"Model saved to {MODEL_PATH}")

    # Metrics
    print(f"\nDecision threshold (F1-optimal): {best_t:.2f}")
    print("\n--- Metrics (full dataset) ---")
    print(classification_report(y, pred, target_names=["legit", "fraud"], zero_division=0))
    print("Confusion matrix:\n", confusion_matrix(y, pred))
    print(f"ROC-AUC: {roc_auc_score(y, proba):.4f}")
    print(f"PR-AUC:  {average_precision_score(y, proba):.4f}")

    # Feature importance (gain)
    importance = dict(zip(feature_names, model.feature_importance(importance_type="gain")))
    print("\n--- Feature importance explanation ---")
    print(feature_importance_explanation(importance))

    # SHAP (on sample for speed)
    print("\nComputing SHAP (sample)...")
    explainer, shap_values, X_sample = explain_with_shap(model, X, feature_names)
    # shap_values for binary is the positive class (fraud)
    if isinstance(shap_values, list):
        shap_values = shap_values[1]

    # Example: one account predicted as fraud (high proba) and one as legit (low proba)
    df_full = pd.read_csv(DATA_PATH)
    df_full = df_full.assign(
        device_shared_count=df_full["device_id"].map(df_full["device_id"].value_counts()).values,
        ip_shared_count=df_full["ip_hash"].map(df_full["ip_hash"].value_counts()).values,
        deposits_vs_income_ratio=(
            df_full["total_deposits_90d"] / (df_full["declared_income_annual"] / 4 + 1e-6)
        ),
    )
    X_full = df_full[feature_names]
    proba_full = model.predict(X_full)
    # Pick example fraud: highest fraud probability among any account
    idx_fraud = np.argmax(proba_full)
    # Pick example legit: lowest fraud probability among legit-only
    legit_mask = y == 0
    idx_legit = np.where(legit_mask)[0][np.argmin(proba_full[legit_mask])]

    # SHAP for those two rows (use explainer on full X for those positions)
    shap_two = explainer.shap_values(X_full.iloc[[idx_fraud, idx_legit]])
    if isinstance(shap_two, list):
        shap_two = shap_two[1]

    ex_fraud = example_account_output(
        account_id=df_full.iloc[idx_fraud]["account_id"],
        fraud_prob=float(proba_full[idx_fraud]),
        is_fraud_actual=bool(y.iloc[idx_fraud]),
        shap_values_one=shap_two[0],
        feature_names=feature_names,
        feature_values_one=X_full.iloc[idx_fraud].values,
        decision_threshold=best_t,
    )
    ex_legit = example_account_output(
        account_id=df_full.iloc[idx_legit]["account_id"],
        fraud_prob=float(proba_full[idx_legit]),
        is_fraud_actual=bool(y.iloc[idx_legit]),
        shap_values_one=shap_two[1],
        feature_names=feature_names,
        feature_values_one=X_full.iloc[idx_legit].values,
        decision_threshold=best_t,
    )

    print("\n--- Example output: FRAUD account ---")
    print(json.dumps(ex_fraud, indent=2))
    print("\n--- Example output: LEGIT account ---")
    print(json.dumps(ex_legit, indent=2))
    return model


if __name__ == "__main__":
    main()
