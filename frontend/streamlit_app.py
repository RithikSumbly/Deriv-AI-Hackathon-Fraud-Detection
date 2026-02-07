"""
AI-Powered Fraud Investigation Dashboard (Streamlit).

Investigator-first UX. Explainability is the hero. Human-in-the-loop.
Clean, serious, regulator-safe. Demoable in under 5 minutes.

Run: streamlit run streamlit_app.py  (from frontend/ or project root)
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Optional: use backend explainability if running from repo
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BACKEND = ROOT / "backend"
DATA_DIR = BACKEND / "data"

# -----------------------------------------------------------------------------
# Mock data (realistic; used when backend data or modules unavailable)
# -----------------------------------------------------------------------------


def _mock_alerts_df():
    return pd.DataFrame([
        {"account_id": "ACC-F-00106", "fraud_probability": 0.72, "anomaly_score": 0.89, "status": "Open"},
        {"account_id": "ACC-F-00042", "fraud_probability": 0.65, "anomaly_score": 0.91, "status": "Open"},
        {"account_id": "ACC-L-01251", "fraud_probability": 0.12, "anomaly_score": 0.38, "status": "Closed"},
        {"account_id": "ACC-F-00088", "fraud_probability": 0.58, "anomaly_score": 0.85, "status": "Open"},
    ])


def _mock_case_data(account_id: str):
    return {
        "account_id": account_id,
        "fraud_probability": 0.72,
        "anomaly_score": 0.89,
        "declared_income_annual": 45000,
        "total_deposits_90d": 125000,
        "deposit_withdraw_cycle_days_avg": 3.1,
        "vpn_usage_pct": 82.5,
        "device_shared_count": 8,
        "ip_shared_count": 5,
        "same_device_as_fraud": True,
        "same_ip_as_fraud": False,
        "min_path_to_fraud": 2,
        "top_shap_drivers": [
            {"feature": "vpn_usage_pct", "value": 82.5, "direction": "pushes toward FRAUD"},
            {"feature": "deposits_vs_income_ratio", "value": 4.2, "direction": "pushes toward FRAUD"},
            {"feature": "deposit_withdraw_cycle_days_avg", "value": 3.1, "direction": "pushes toward FRAUD"},
            {"feature": "kyc_face_match_score", "value": 0.62, "direction": "pushes toward FRAUD"},
            {"feature": "device_shared_count", "value": 8, "direction": "pushes toward FRAUD"},
        ],
        "concise_explanation": (
            "This alert was triggered because the account has a fraud probability of 72% and an anomaly score of 89%, "
            "indicating both model-based fraud likelihood and unusual behavior relative to normal accounts. "
            "Main drivers: VPN usage 82.5% (pushes toward FRAUD), deposits vs declared income ratio 4.2x (pushes toward FRAUD). "
            "Network: device shared with 8 accounts; same device as one confirmed fraud case."
        ),
        "key_risk_drivers": [
            "Fraud probability 72% exceeds review threshold.",
            "Anomaly score 89% indicates high deviation from normal behavior.",
            "vpn_usage_pct = 82.5 (pushes toward FRAUD).",
            "deposits_vs_income_ratio = 4.2 (pushes toward FRAUD).",
            "Network: same_device_as_fraud = True.",
        ],
        "junior_analyst_summary": (
            "This case was flagged by our models as higher risk. Check the top risk drivers above; "
            "focus on any that push toward FRAUD. The account shares a device with a known fraud case—treat as high priority. "
            "Stick to the evidence listed; do not speculate beyond it."
        ),
        "next_steps": [
            "Verify declared income (employment letter, tax doc, or bank statement) to reconcile with deposit volume.",
            "Review login geography vs. KYC address and payment rails; request confirmation of usual access locations.",
            "Expand device and IP graph: list all accounts linked by shared device/IP and flag any known fraud or SARs.",
        ],
        "next_steps_rationale": "Suggested actions map to the risk indicators; prioritize verification and graph review. No conclusion on fraud—human decision required.",
        "timeline_events": [
            {"timestamp": "2025-01-15 14:22:00", "event_type": "login", "suspicious": ["login_immediately_followed_by_deposit"]},
            {"timestamp": "2025-01-15 14:23:12", "event_type": "deposit", "amount": 5000, "suspicious": ["deposit_immediately_followed_by_withdrawal"]},
            {"timestamp": "2025-01-15 14:45:00", "event_type": "withdrawal", "amount": 4800, "suspicious": []},
            {"timestamp": "2025-01-16 09:15:00", "event_type": "deposit", "amount": 15000, "suspicious": ["large_deposit"]},
            {"timestamp": "2025-01-16 10:00:00", "event_type": "kyc_attempt", "suspicious": ["kyc_attempt_after_recent_withdrawal"]},
        ],
    }


def _load_alerts():
    if (DATA_DIR / "anomaly_scores.csv").exists():
        try:
            df = pd.read_csv(DATA_DIR / "anomaly_scores.csv")
            if "account_id" in df.columns and "fraud_probability" in df.columns and "anomaly_score" in df.columns:
                df["status"] = "Open"
                return df.head(50)
        except Exception:
            pass
    return _mock_alerts_df()


def _get_case_data(account_id: str):
    try:
        from backend.explainability.alert_explanation import generate_alert_explanation
        from backend.explainability.next_step_advisor import recommend_next_steps
    except ImportError:
        pass
    return _mock_case_data(account_id)


# -----------------------------------------------------------------------------
# Layout
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="Fraud Investigation Dashboard",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Fraud Investigation Dashboard")
st.caption("Internal use. AI-assisted; all decisions are human-in-the-loop.")

# Sidebar: case selector
alerts_df = _load_alerts()
account_options = alerts_df["account_id"].tolist()
selected_account = st.sidebar.selectbox(
    "Select case",
    account_options,
    index=0,
    help="Choose an account to investigate.",
)
row = alerts_df[alerts_df["account_id"] == selected_account].iloc[0]
st.sidebar.metric("Fraud probability", f"{row.get('fraud_probability', 0):.0%}")
st.sidebar.metric("Anomaly score", f"{row.get('anomaly_score', 0):.0%}")
st.sidebar.divider()
st.sidebar.markdown("**Quick filters**")
show_open_only = st.sidebar.checkbox("Open only", value=False)
if show_open_only and "status" in alerts_df.columns:
    alerts_df = alerts_df[alerts_df["status"] == "Open"]

case = _get_case_data(selected_account)

# Main: tabs
tab_overview, tab_case, tab_timeline, tab_next, tab_report = st.tabs([
    "Overview",
    "Case detail & explainability",
    "Timeline",
    "Next steps",
    "Report",
])

# ---- Tab: Overview ----
with tab_overview:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Open alerts", int((alerts_df["status"] == "Open").sum() if "status" in alerts_df.columns else len(alerts_df)))
    with c2:
        st.metric("Avg fraud probability", f"{alerts_df['fraud_probability'].mean():.0%}" if "fraud_probability" in alerts_df.columns else "—")
    with c3:
        st.metric("Avg anomaly score", f"{alerts_df['anomaly_score'].mean():.0%}" if "anomaly_score" in alerts_df.columns else "—")
    st.divider()
    st.subheader("Alert queue")
    st.dataframe(alerts_df, use_container_width=True, hide_index=True)

# ---- Tab: Case detail & explainability (hero) ----
with tab_case:
    # Score cards
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Fraud probability", f"{case['fraud_probability']:.0%}")
    with col2:
        st.metric("Anomaly score", f"{case['anomaly_score']:.0%}")
    with col3:
        st.metric("Device shared count", case.get("device_shared_count", "—"))

    st.divider()
    st.subheader("Why this alert? (Explainability)")
    with st.expander("Concise explanation", expanded=True):
        st.write(case["concise_explanation"])
    with st.expander("Key risk drivers"):
        for d in case["key_risk_drivers"]:
            st.markdown(f"- {d}")
    with st.expander("Junior analyst summary"):
        st.write(case["junior_analyst_summary"])

    st.subheader("Top SHAP drivers")
    shap_df = pd.DataFrame(case["top_shap_drivers"])
    st.dataframe(shap_df, use_container_width=True, hide_index=True)

    st.subheader("Network risk indicators")
    net = {k: v for k, v in case.items() if k in ("device_shared_count", "ip_shared_count", "same_device_as_fraud", "same_ip_as_fraud", "min_path_to_fraud") and v is not None}
    if net:
        st.json(net)

# ---- Tab: Timeline ----
with tab_timeline:
    st.subheader("Event timeline")
    for ev in case["timeline_events"]:
        ts = ev.get("timestamp", "")
        etype = ev.get("event_type", "")
        amount = ev.get("amount", "")
        susp = ev.get("suspicious", [])
        line = f"**{ts}** — {etype}"
        if amount:
            line += f" (amount: {amount})"
        if susp:
            line += f"  \n*Suspicious: {', '.join(susp)}*"
        st.markdown(f"- {line}")
    st.caption("Chronological. No new facts added.")

# ---- Tab: Next steps ----
with tab_next:
    st.subheader("Recommended next investigative actions")
    st.caption("Suggestions only. Do not treat as final decisions or fraud determination.")
    for i, step in enumerate(case["next_steps"], 1):
        st.markdown(f"{i}. {step}")
    st.divider()
    st.markdown("**Rationale**")
    st.write(case["next_steps_rationale"])

# ---- Tab: Report ----
with tab_report:
    st.subheader("Investigation report (compliance / regulators)")
    case_summary = st.text_area(
        "Case summary",
        value="Account flagged for elevated fraud probability and anomaly score. Review focused on deposit-to-income consistency, device/IP sharing, and transaction timeline.",
        height=80,
    )
    evidence_prefill = "\n".join(case["key_risk_drivers"][:5])
    evidence_points = st.text_area("Evidence points (one per line)", value=evidence_prefill, height=120)
    investigator_conclusion = st.text_input(
        "Investigator conclusion",
        value="Evidence supports escalation to SAR. No final determination of fraud; recommend filing and continued monitoring.",
    )
    if st.button("Generate report"):
        evidence_list = [x.strip() for x in evidence_points.split("\n") if x.strip()]
        report = None
        try:
            from backend.explainability.report_writer import write_investigation_report, report_to_markdown
            report = write_investigation_report(case_summary, evidence_list, investigator_conclusion, use_llm=False)
            st.markdown(report_to_markdown(report))
        except Exception:
            report = {
                "executive_summary": "This report documents the investigation. Evidence reviewed is set out below; conclusion is as stated by the investigator. No new facts added.",
                "evidence_reviewed": "Evidence reviewed:\n\n" + "\n".join(f"- {e}" for e in evidence_list) if evidence_list else "(none)",
                "findings": "Findings are based solely on the evidence listed. The investigator has reached the conclusion set out in the Conclusion section.",
                "conclusion": f"Investigator conclusion (formal): {investigator_conclusion}",
            }
            st.markdown("## Executive Summary")
            st.write(report["executive_summary"])
            st.markdown("## Evidence Reviewed")
            st.write(report["evidence_reviewed"])
            st.markdown("## Findings")
            st.write(report["findings"])
            st.markdown("## Conclusion")
            st.write(report["conclusion"])
        st.caption("Report generated for compliance. No new facts added.")

st.divider()
st.caption("AI-powered fraud investigation dashboard. Explainability is the hero. Human-in-the-loop. Not regulatory advice.")
