"""
Alert queue for the fraud investigation dashboard.

Returns alerts sorted by risk descending. Each alert has:
- account_id, fraud_probability, risk_level (High/Medium/Low), one_line_explanation.
Uses backend/data/anomaly_scores.csv when present; otherwise mock data.
"""
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ANOMALY_CSV = DATA_DIR / "anomaly_scores.csv"

# Same 13 features as classifier/anomaly pipeline (for similarity-based "matches N confirmed cases")
FEATURE_COLS = [
    "declared_income_annual", "total_deposits_90d", "total_withdrawals_90d",
    "num_deposits_90d", "num_withdrawals_90d", "deposit_withdraw_cycle_days_avg",
    "vpn_usage_pct", "countries_accessed_count", "device_shared_count", "ip_shared_count",
    "account_age_days", "kyc_face_match_score", "deposits_vs_income_ratio",
]


def _risk_level(prob: float, anomaly: float = 0) -> str:
    """Use combined score so anomaly_score can lift risk when fraud_prob is conservative."""
    composite = 0.5 * prob + 0.5 * (anomaly if anomaly is not None else 0)
    if composite >= 0.5:
        return "High"
    if composite >= 0.3:
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
            df = df.head(limit * 4)
            df["risk_level"] = df.apply(
                lambda r: _risk_level(float(r["fraud_probability"]), float(r.get("anomaly_score", 0))),
                axis=1,
            )
            df["one_line_explanation"] = df.apply(_one_line_from_row, axis=1)
            df["risk_factors"] = df.apply(_risk_factors_from_row, axis=1)
            # Sort by risk descending: High first, then by fraud_probability desc
            risk_order = {"High": 0, "Medium": 1, "Low": 2}
            df["_risk_ord"] = df["risk_level"].map(risk_order)
            df = df.sort_values(by=["_risk_ord", "fraud_probability"], ascending=[True, False]).drop(columns=["_risk_ord"])
            rows = df.head(limit).to_dict("records")
            def _vec(r):
                try:
                    return [float(r.get(c, 0)) for c in FEATURE_COLS if c in r]
                except (TypeError, ValueError):
                    return None
            return [
                {
                    "account_id": r["account_id"],
                    "fraud_probability": float(r["fraud_probability"]),
                    "anomaly_score": float(r.get("anomaly_score", 0)),
                    "risk_level": r["risk_level"],
                    "one_line_explanation": r["one_line_explanation"],
                    "risk_factors": r["risk_factors"],
                    "timeline_events": default_timeline,
                    "feature_vector": _vec(r) if all(c in r for c in FEATURE_COLS) else None,
                    **{c: r.get(c) for c in FEATURE_COLS},
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
    # Mock alerts: no feature_vector (similarity falls back to risk_level); raw features absent/None for agents
    def _m(account_id, prob, anom, level, expl, factors):
        base = {"account_id": account_id, "fraud_probability": prob, "anomaly_score": anom, "risk_level": level, "one_line_explanation": expl, "risk_factors": factors, "timeline_events": timeline, "feature_vector": None}
        for c in FEATURE_COLS:
            base[c] = None
        return base
    return [
        _m("ACC-F-00106", 0.72, 0.89, "High", "Elevated VPN use, deposits vs income mismatch, shared device.", ["Most logins came from a hidden or private network (VPN), which can be used to hide location.", "Money going in is much higher than the stated income, which is unusual.", "This account shares a device with several other accounts, which is common in organised abuse.", "Money is being moved in and out very quickly instead of being held, which can indicate layering."]),
        _m("ACC-F-00042", 0.65, 0.91, "High", "Rapid deposit-withdrawal cycle, shared device, multiple countries.", ["Money is being moved in and out very quickly instead of being held, which can indicate layering.", "This account shares a device with several other accounts, which is common in organised abuse.", "Logins from many different countries in a short time, which is unusual for a single user."]),
        _m("ACC-F-00088", 0.58, 0.85, "Medium", "Deposits vs income mismatch, elevated VPN use.", ["Money going in is much higher than the stated income, which is unusual.", "Most logins came from a hidden or private network (VPN), which can be used to hide location."]),
        _m("ACC-L-01251", 0.45, 0.38, "Medium", "Anomaly vs normal behavior.", ["Activity pattern differs from what we usually see for similar accounts."]),
        _m("ACC-L-02336", 0.22, 0.44, "Low", "Slightly elevated anomaly score; within range.", ["Some small differences from typical behavior; may be normal variation."]),
        _m("ACC-L-02403", 0.12, 0.18, "Low", "Low risk; routine review.", ["Routine check; no strong risk factors identified."]),
    ]
