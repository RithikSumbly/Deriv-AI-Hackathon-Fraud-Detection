"""
Evidence tab data: per-account DataFrames from anomaly_scores.csv or alert dict.

Used by the Streamlit Evidence tabs (Transactions, Geo, Identity, Network).
Deterministic and reproducible; no new models or fraud/legit labels.
"""
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ANOMALY_CSV = DATA_DIR / "anomaly_scores.csv"

# Thresholds for derived fields (explainable, no ML)
DOCUMENT_VERIFIED_KYC_THRESHOLD = 0.85
IDENTITY_RISK_HIGH = 0.7
IDENTITY_RISK_MEDIUM = 0.85
HIGH_RISK_VPN_PCT = 50
HIGH_RISK_COUNTRIES = 5


def _get_alert_row(account_id: str, alert: dict | None) -> dict | None:
    """
    Return the alert row for account_id: from optional alert dict, or by reading
    anomaly_scores.csv. Returns None if not found or CSV missing.
    """
    if alert is not None and alert.get("account_id") == account_id:
        return alert
    if not ANOMALY_CSV.exists():
        return None
    try:
        df = pd.read_csv(ANOMALY_CSV)
        if "account_id" not in df.columns:
            return None
        rows = df[df["account_id"] == account_id]
        if rows.empty:
            return None
        return rows.iloc[0].to_dict()
    except Exception:
        return None


def _no_data_df() -> pd.DataFrame:
    """Single-row DataFrame for missing data."""
    return pd.DataFrame([{"message": "No data available"}])


def get_transactions(account_id: str, alert: dict | None = None) -> pd.DataFrame:
    """
    Transaction summary for the account (90d). Dataset has 90d counts only; we do not invent 30d.
    Columns: deposit_count_90d, withdrawal_count_90d, deposits_vs_income_ratio,
    avg_deposit_amount, deposit_withdraw_cycle_days_avg.
    """
    row = _get_alert_row(account_id, alert)
    if row is None:
        return _no_data_df()
    num_dep = int(row.get("num_deposits_90d") or 0)
    num_wd = int(row.get("num_withdrawals_90d") or 0)
    total_dep = float(row.get("total_deposits_90d") or 0)
    ratio = row.get("deposits_vs_income_ratio")
    cycle = row.get("deposit_withdraw_cycle_days_avg")
    avg_dep = total_dep / max(1, num_dep) if num_dep else 0.0
    return pd.DataFrame([{
        "deposit_count_90d": num_dep,
        "withdrawal_count_90d": num_wd,
        "deposits_vs_income_ratio": float(ratio) if ratio is not None else None,
        "avg_deposit_amount": round(avg_dep, 2),
        "deposit_withdraw_cycle_days_avg": round(float(cycle), 2) if cycle is not None else None,
    }])


def get_geo_activity(account_id: str, alert: dict | None = None) -> pd.DataFrame:
    """
    Geo/VPN activity. high_risk_country_flag derived from vpn_usage_pct > 50 or
    countries_accessed_count > 5 (explainable rule).
    """
    row = _get_alert_row(account_id, alert)
    if row is None:
        return _no_data_df()
    countries = int(row.get("countries_accessed_count") or 0)
    vpn_pct = float(row.get("vpn_usage_pct") or 0)
    high_risk = (vpn_pct > HIGH_RISK_VPN_PCT) or (countries > HIGH_RISK_COUNTRIES)
    return pd.DataFrame([{
        "countries_accessed_count": countries,
        "vpn_usage_pct": round(vpn_pct, 1),
        "high_risk_country_flag": high_risk,
    }])


def get_identity_signals(account_id: str, alert: dict | None = None) -> pd.DataFrame:
    """
    Identity signals. document_verified = kyc_face_match_score >= 0.85.
    identity_risk_level: <0.7 High, 0.7–0.85 Medium, >=0.85 Low.
    """
    row = _get_alert_row(account_id, alert)
    if row is None:
        return _no_data_df()
    kyc = row.get("kyc_face_match_score")
    if kyc is None:
        return pd.DataFrame([{
            "kyc_face_match_score": None,
            "document_verified": False,
            "identity_risk_level": "Unknown",
        }])
    kyc_f = float(kyc)
    doc_verified = kyc_f >= DOCUMENT_VERIFIED_KYC_THRESHOLD
    if kyc_f < IDENTITY_RISK_HIGH:
        risk_level = "High"
    elif kyc_f < IDENTITY_RISK_MEDIUM:
        risk_level = "Medium"
    else:
        risk_level = "Low"
    return pd.DataFrame([{
        "kyc_face_match_score": round(kyc_f, 2),
        "document_verified": doc_verified,
        "identity_risk_level": risk_level,
    }])


def get_network_signals(account_id: str, alert: dict | None = None) -> pd.DataFrame:
    """Device and IP sharing counts (table, not graph)."""
    row = _get_alert_row(account_id, alert)
    if row is None:
        return _no_data_df()
    dev = int(row.get("device_shared_count") or 0)
    ip = int(row.get("ip_shared_count") or 0)
    return pd.DataFrame([{
        "device_shared_count": dev,
        "ip_shared_count": ip,
    }])
