"""
Alert queue for the fraud investigation dashboard.

Returns alerts sorted by risk descending. Each alert has:
- account_id, fraud_probability, risk_level (High/Medium/Low), one_line_explanation.
Uses backend/data/anomaly_scores.csv when present; otherwise mock data.
"""
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ANOMALY_CSV = DATA_DIR / "anomaly_scores.csv"


def _risk_level(prob: float) -> str:
    if prob >= 0.6:
        return "High"
    if prob >= 0.3:
        return "Medium"
    return "Low"


def _one_line_from_row(row) -> str:
    """Build a short AI-style explanation from a data row."""
    parts = []
    if row.get("vpn_usage_pct", 0) and float(row.get("vpn_usage_pct", 0)) > 50:
        parts.append("elevated VPN use")
    if row.get("deposits_vs_income_ratio", 0) and float(row.get("deposits_vs_income_ratio", 0)) > 1.5:
        parts.append("deposits vs income mismatch")
    if row.get("device_shared_count", 0) and int(row.get("device_shared_count", 0)) > 1:
        parts.append("shared device")
    if row.get("deposit_withdraw_cycle_days_avg", 100) and float(row.get("deposit_withdraw_cycle_days_avg", 100)) < 10:
        parts.append("rapid deposit-withdrawal cycle")
    if not parts:
        parts.append("anomaly vs normal behavior")
    return " ".join(parts[:3]).capitalize() + "."


def _risk_factors_from_row(row) -> list[str]:
    """Plain-language bullet list for the AI Explanation panel (no jargon)."""
    bullets = []
    if row.get("vpn_usage_pct", 0) and float(row.get("vpn_usage_pct", 0)) > 50:
        bullets.append("Most logins came from a hidden or private network (VPN), which can be used to hide location.")
    if row.get("deposits_vs_income_ratio", 0) and float(row.get("deposits_vs_income_ratio", 0)) > 1.5:
        bullets.append("Money going in is much higher than the stated income, which is unusual.")
    if row.get("device_shared_count", 0) and int(row.get("device_shared_count", 0)) > 1:
        bullets.append("This account shares a device with several other accounts, which is common in organised abuse.")
    if row.get("deposit_withdraw_cycle_days_avg", 100) and float(row.get("deposit_withdraw_cycle_days_avg", 100)) < 10:
        bullets.append("Money is being moved in and out very quickly instead of being held, which can indicate layering.")
    if row.get("kyc_face_match_score", 1) and float(row.get("kyc_face_match_score", 1)) < 0.85:
        bullets.append("Identity check (photo match) was weaker than usual.")
    if not bullets:
        bullets.append("Activity pattern differs from what we usually see for similar accounts.")
    return bullets[:6]


def get_alerts(limit: int = 50) -> list[dict]:
    """
    Return alerts sorted by risk descending (High first, then by fraud_probability desc).
    Each item: account_id, fraud_probability, anomaly_score, risk_level, one_line_explanation, risk_factors, timeline_events (optional).
    """
    if ANOMALY_CSV.exists():
        try:
            import pandas as pd
            df = pd.read_csv(ANOMALY_CSV)
            if "account_id" not in df.columns or "fraud_probability" not in df.columns:
                return _mock_alerts()
            default_timeline = _default_timeline_events()
            df = df.head(limit * 2)
            df["risk_level"] = df["fraud_probability"].apply(_risk_level)
            df["one_line_explanation"] = df.apply(_one_line_from_row, axis=1)
            df["risk_factors"] = df.apply(_risk_factors_from_row, axis=1)
            # Sort by risk descending: High first, then by fraud_probability desc
            risk_order = {"High": 0, "Medium": 1, "Low": 2}
            df["_risk_ord"] = df["risk_level"].map(risk_order)
            df = df.sort_values(by=["_risk_ord", "fraud_probability"], ascending=[True, False]).drop(columns=["_risk_ord"])
            rows = df.head(limit).to_dict("records")
            return [
                {
                    "account_id": r["account_id"],
                    "fraud_probability": float(r["fraud_probability"]),
                    "anomaly_score": float(r.get("anomaly_score", 0)),
                    "risk_level": r["risk_level"],
                    "one_line_explanation": r["one_line_explanation"],
                    "risk_factors": r["risk_factors"],
                    "timeline_events": default_timeline,
                }
                for r in rows
            ]
        except Exception:
            pass
    return _mock_alerts()


def _default_timeline_events() -> list[dict]:
    """Default chronological events for timeline (used when no account-specific timeline)."""
    return [
        {"timestamp": "2025-01-15 14:22", "event_type": "Login", "details": "IP 192.168.1.1", "suspicious": True},
        {"timestamp": "2025-01-15 14:23", "event_type": "Deposit", "details": "5,000", "suspicious": True},
        {"timestamp": "2025-01-15 14:45", "event_type": "Withdrawal", "details": "4,800", "suspicious": False},
        {"timestamp": "2025-01-16 09:00", "event_type": "Login", "details": "", "suspicious": False},
        {"timestamp": "2025-01-16 09:15", "event_type": "Deposit", "details": "15,000", "suspicious": True},
        {"timestamp": "2025-01-16 10:00", "event_type": "KYC attempt", "details": "document upload", "suspicious": True},
    ]


def _mock_alerts() -> list[dict]:
    timeline = _default_timeline_events()
    return [
        {"account_id": "ACC-F-00106", "fraud_probability": 0.72, "anomaly_score": 0.89, "risk_level": "High", "one_line_explanation": "Elevated VPN use, deposits vs income mismatch, shared device.", "risk_factors": ["Most logins came from a hidden or private network (VPN), which can be used to hide location.", "Money going in is much higher than the stated income, which is unusual.", "This account shares a device with several other accounts, which is common in organised abuse.", "Money is being moved in and out very quickly instead of being held, which can indicate layering."], "timeline_events": timeline},
        {"account_id": "ACC-F-00042", "fraud_probability": 0.65, "anomaly_score": 0.91, "risk_level": "High", "one_line_explanation": "Rapid deposit-withdrawal cycle, shared device, multiple countries.", "risk_factors": ["Money is being moved in and out very quickly instead of being held, which can indicate layering.", "This account shares a device with several other accounts, which is common in organised abuse.", "Logins from many different countries in a short time, which is unusual for a single user."], "timeline_events": timeline},
        {"account_id": "ACC-F-00088", "fraud_probability": 0.58, "anomaly_score": 0.85, "risk_level": "Medium", "one_line_explanation": "Deposits vs income mismatch, elevated VPN use.", "risk_factors": ["Money going in is much higher than the stated income, which is unusual.", "Most logins came from a hidden or private network (VPN), which can be used to hide location."], "timeline_events": timeline},
        {"account_id": "ACC-L-01251", "fraud_probability": 0.45, "anomaly_score": 0.38, "risk_level": "Medium", "one_line_explanation": "Anomaly vs normal behavior.", "risk_factors": ["Activity pattern differs from what we usually see for similar accounts."], "timeline_events": timeline},
        {"account_id": "ACC-L-02336", "fraud_probability": 0.22, "anomaly_score": 0.44, "risk_level": "Low", "one_line_explanation": "Slightly elevated anomaly score; within range.", "risk_factors": ["Some small differences from typical behavior; may be normal variation."], "timeline_events": timeline},
        {"account_id": "ACC-L-02403", "fraud_probability": 0.12, "anomaly_score": 0.18, "risk_level": "Low", "one_line_explanation": "Low risk; routine review.", "risk_factors": ["Routine check; no strong risk factors identified."], "timeline_events": timeline},
    ]
