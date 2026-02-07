"""
Fraud Investigation Dashboard — Main Streamlit layout.

Layout: page title at top | left sidebar (alert queue) | main area (case details).
Alert queue: risk badge, fraud %, one-line AI explanation; sorted by risk; select to load case.
Run: streamlit run app.py  (from project root: streamlit run frontend/app.py)
"""
import sys
from pathlib import Path

import streamlit as st

# Optional: pyvis for network graph (Network tab)
try:
    from pyvis.network import Network
    HAS_PYVIS = True
except ImportError:
    HAS_PYVIS = False


def _build_network_graph_html(
    account_id: str,
    devices: list[dict],
    ips: list[dict],
    height: int = 400,
) -> str | None:
    """
    Build an interactive network graph: center node = account, connected = devices & IPs.
    Highlights nodes linked to confirmed fraud. Hover for labels.
    Returns HTML string for st.components.v1.html, or None if pyvis not available.
    """
    if not HAS_PYVIS:
        return None
    net = Network(
        height=f"{height}px",
        width="100%",
        notebook=False,
        heading="",
        cdn_resources="remote",
    )
    net.barnes_hut(
        gravity=0.2,
        central_gravity=0.3,
        spring_length=150,
        spring_strength=0.05,
        damping=0.09,
    )
    # Center node: current account
    net.add_node(
        account_id,
        label=account_id,
        title=f"Current account\n{account_id}",
        color="#1a73e8",
        size=35,
        font={"size": 14},
    )
    # Device nodes (red if fraud-linked, else gray)
    for d in devices:
        nid = d.get("id", "?")
        fraud = d.get("fraud_linked", False)
        acc_count = d.get("accounts", 0)
        title = f"Device: {nid}\nAccounts: {acc_count}\n{'Linked to confirmed fraud' if fraud else 'No fraud link'}"
        net.add_node(
            nid,
            label=nid,
            title=title,
            color="#c62828" if fraud else "#78909c",
            size=25,
            font={"size": 12},
            shape="box",
        )
        net.add_edge(account_id, nid, title="uses device")
    # IP nodes (red if fraud-linked, else gray)
    for ip in ips:
        nid = ip.get("id", "?")
        fraud = ip.get("fraud_linked", False)
        acc_count = ip.get("accounts", 0)
        title = f"IP: {nid}\nAccounts: {acc_count}\n{'Linked to confirmed fraud' if fraud else 'No fraud link'}"
        net.add_node(
            nid,
            label=nid,
            title=title,
            color="#c62828" if fraud else "#78909c",
            size=25,
            font={"size": 12},
            shape="dot",
        )
        net.add_edge(account_id, nid, title="logged from")
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            tmp = f.name
        net.save_graph(tmp)
        html = Path(tmp).read_text()
        Path(tmp).unlink(missing_ok=True)
        return html
    except Exception:
        return None


# Backend: ensure project root is on path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.alerts import get_alerts

st.set_page_config(
    page_title="Fraud Investigation Dashboard",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------------------------------------------------------
# Page title (top)
# -----------------------------------------------------------------------------
st.title("Fraud Investigation Dashboard")
st.caption("Internal use. Human-in-the-loop.")

# -----------------------------------------------------------------------------
# Load alerts once (used by sidebar and main)
# -----------------------------------------------------------------------------
alerts = get_alerts(limit=50)
alert_by_id = {a["account_id"]: a for a in alerts}
alert_options = [a["account_id"] for a in alerts]

# -----------------------------------------------------------------------------
# Session state: selected alert, case status, investigator decision
# All state persists across button clicks and reruns.
# -----------------------------------------------------------------------------
if "case_status" not in st.session_state:
    st.session_state.case_status = {}  # account_id -> "Under Review" | "Confirmed Fraud" | "Marked Legit" | "More Info Requested"
if "selected_alert_id" not in st.session_state:
    st.session_state.selected_alert_id = alert_options[0] if alert_options else None
# Keep selected_alert_id valid when alert list changes or when options load
if alert_options and (st.session_state.selected_alert_id not in alert_options):
    st.session_state.selected_alert_id = alert_options[0]
if not alert_options:
    st.session_state.selected_alert_id = None

# Investigator decision = case status for the selected case (single source of truth)
def _get_case_status(account_id: str) -> str:
    return st.session_state.case_status.get(account_id, "Under Review")

# -----------------------------------------------------------------------------
# Left sidebar: alert queue (bound to session_state.selected_alert_id)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("Alert queue")
    if not alerts:
        st.warning("No alerts.")
    else:
        def badge_md(risk: str) -> str:
            color = {"High": "#c62828", "Medium": "#e65100", "Low": "#2e7d32"}.get(risk, "#37474f")
            return f'<span style="background:{color};color:white;padding:2px 6px;border-radius:4px;font-size:0.75rem;font-weight:600;">{risk}</span>'

        def format_option(account_id: str) -> str:
            a = alert_by_id[account_id]
            prob_pct = f"{a['fraud_probability']:.0%}"
            line = (a["one_line_explanation"] or "")[:50] + ("…" if len(a.get("one_line_explanation", "") or "") > 50 else "")
            return f"{a['risk_level']} | {prob_pct} | {line}"

        # Radio writes to session_state.selected_alert_id so selection persists on any button click
        chosen = st.radio(
            "Select case (click to load)",
            options=alert_options,
            format_func=format_option,
            index=alert_options.index(st.session_state.selected_alert_id) if st.session_state.selected_alert_id in alert_options else 0,
            key="selected_alert_id",
            label_visibility="collapsed",
        )
        st.session_state.selected_alert_id = chosen

        if chosen:
            sel = alert_by_id[chosen]
            st.divider()
            st.markdown("**Selected alert**")
            st.markdown(badge_md(sel["risk_level"]) + f" **{sel['fraud_probability']:.0%}** fraud probability", unsafe_allow_html=True)
            st.caption(sel["one_line_explanation"])
            st.metric("Open alerts", len([a for a in alerts if a.get("risk_level") == "High"]))

# Use session state for selected case everywhere (persists across reruns)
selected_id = st.session_state.selected_alert_id

# -----------------------------------------------------------------------------
# Main area: case header + case details (live for selected alert)
# -----------------------------------------------------------------------------
if selected_id:
    alert = alert_by_id[selected_id]
    status = _get_case_status(selected_id)

    # ---------- Case header section ----------
    st.subheader("Case header")
    header_col1, header_col2, header_col3 = st.columns([2, 1, 2])
    with header_col1:
        st.markdown(f"**Account ID**  \n{selected_id}")
        st.markdown(f"**Status**  \n{status}")
    with header_col2:
        # Risk score with color indicator (0-100 scale)
        risk_pct = alert["fraud_probability"] * 100
        if risk_pct >= 60:
            color = "#c62828"
        elif risk_pct >= 30:
            color = "#e65100"
        else:
            color = "#2e7d32"
        st.markdown(
            f'**Risk score**  \n<span style="color:{color};font-weight:700;font-size:1.5rem;">{risk_pct:.0f}%</span>',
            unsafe_allow_html=True,
        )
    with header_col3:
        st.markdown("**Actions**")
        btn_col1, btn_col2, btn_col3 = st.columns(3)
        with btn_col1:
            if st.button("Confirm Fraud", key="btn_confirm_fraud"):
                st.session_state.case_status[selected_id] = "Confirmed Fraud"
        with btn_col2:
            if st.button("Mark Legit", key="btn_mark_legit"):
                st.session_state.case_status[selected_id] = "Marked Legit"
        with btn_col3:
            if st.button("Request More Info", key="btn_more_info"):
                st.session_state.case_status[selected_id] = "More Info Requested"
    st.divider()

    # ---------- Case details ----------
    st.header(f"Case: {selected_id}")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Fraud probability", f"{alert['fraud_probability']:.0%}")
    with col2:
        st.metric("Anomaly score", f"{alert.get('anomaly_score', 0):.0%}")
    with col3:
        st.metric("Risk level", alert["risk_level"])
    st.caption(f"AI summary: {alert['one_line_explanation']}")

    # ---------- AI Explanation panel (most readable section) ----------
    st.divider()
    st.markdown("---")
    st.markdown(
        '<p style="font-size:1.35rem; font-weight:600; color:#1a1a1a; margin-bottom:0.5rem;">Why this account was flagged</p>',
        unsafe_allow_html=True,
    )
    st.markdown("")  # spacing
    risk_factors = alert.get("risk_factors") or [alert.get("one_line_explanation", "Activity was flagged for review.")]
    bullets_html = "<br>".join(f"• {f}" for f in risk_factors).replace("<", "&lt;").replace(">", "&gt;")
    st.markdown(
        f'<div style="line-height:1.85; font-size:1.05rem; margin:0.5rem 0;">{bullets_html}</div>',
        unsafe_allow_html=True,
    )
    st.markdown("")
    # Confidence level indicator (plain language, no jargon)
    prob = alert["fraud_probability"]
    if prob >= 0.6:
        confidence_label = "High confidence"
        confidence_note = "The model is fairly confident this case deserves review."
        conf_color = "#c62828"
    elif prob >= 0.3:
        confidence_label = "Medium confidence"
        confidence_note = "The model sees notable risk; human review is recommended."
        conf_color = "#e65100"
    else:
        confidence_label = "Low confidence"
        confidence_note = "The model flagged this for completeness; may be normal variation."
        conf_color = "#2e7d32"
    st.markdown(
        f'<p style="margin-top:1rem; margin-bottom:0.25rem; font-weight:600; color:{conf_color};">{confidence_label}</p>'
        f'<p style="margin:0; font-size:0.95rem; color:#555;">{confidence_note}</p>',
        unsafe_allow_html=True,
    )
    st.markdown("---")
    st.divider()

    # ---------- Evidence (tabbed) ----------
    st.subheader("Evidence")
    tab_tx, tab_geo, tab_id, tab_net = st.tabs(["Transactions", "Access & Geo", "Identity", "Network"])
    with tab_tx:
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Total deposits (90d)", "£125,000")
            st.metric("Total withdrawals (90d)", "£118,200")
        with c2:
            st.metric("Deposit count", 12)
            st.metric("Avg cycle (days)", 3.1)
        st.caption("Last 5 transactions")
        st.dataframe(
            [
                {"Date": "2025-01-16", "Type": "Deposit", "Amount": 15000, "Status": "Completed"},
                {"Date": "2025-01-15", "Type": "Withdrawal", "Amount": 4800, "Status": "Completed"},
                {"Date": "2025-01-15", "Type": "Deposit", "Amount": 5000, "Status": "Completed"},
                {"Date": "2025-01-14", "Type": "Withdrawal", "Amount": 3200, "Status": "Completed"},
                {"Date": "2025-01-12", "Type": "Deposit", "Amount": 8000, "Status": "Completed"},
            ],
            use_container_width=True,
            hide_index=True,
        )
    with tab_geo:
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Countries (90d)", 7)
            st.metric("VPN sessions %", 82)
        with c2:
            st.metric("Distinct IPs", 5)
            st.metric("Last login", "2025-01-16 09:00")
        st.caption("Access by country")
        st.dataframe(
            [{"Country": "GB", "Sessions": 8}, {"Country": "NL", "Sessions": 12}, {"Country": "DE", "Sessions": 4}],
            use_container_width=True,
            hide_index=True,
        )
    with tab_id:
        c1, c2 = st.columns(2)
        with c1:
            st.metric("KYC face match", "0.62")
            st.metric("Doc verified", "Yes")
        with c2:
            st.metric("Account age (days)", 152)
            st.metric("Declared income", "£45,000")
        st.caption("Identity checks")
        st.dataframe(
            [{"Check": "ID document", "Result": "Pass"}, {"Check": "Face match", "Result": "Below threshold"}, {"Check": "Address", "Result": "Pass"}],
            use_container_width=True,
            hide_index=True,
        )
    with tab_net:
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Devices linked", 1)
            st.metric("Accounts on same device", 8)
        with c2:
            st.metric("IPs linked", 2)
            st.metric("Same device as fraud", "Yes")
        st.caption("Device & IP summary")
        st.dataframe(
            [{"Device ID": "DEV-F-0042", "Accounts": 8}, {"IP (hash)": "IP-F-0012", "Accounts": 4}],
            use_container_width=True,
            hide_index=True,
        )
        # Network graph: center = account, connected = devices & IPs, highlight fraud-linked
        st.markdown("**Network graph** (hover for labels)")
        net_html = _build_network_graph_html(
            account_id=selected_id,
            devices=[{"id": "DEV-F-0042", "accounts": 8, "fraud_linked": True}],
            ips=[{"id": "IP-F-0012", "accounts": 4, "fraud_linked": False}, {"id": "IP-F-0008", "accounts": 2, "fraud_linked": True}],
        )
        if net_html:
            st.components.v1.html(net_html, height=420, scrolling=False)
        else:
            st.caption("Install pyvis for interactive graph: pip install pyvis")
    st.divider()

else:
    st.info("Select an alert from the sidebar to load case details.")

st.divider()

# ---------- Timeline (Mermaid diagram) ----------
def _mermaid_timeline(events: list[dict]) -> str:
    """Build Mermaid flowchart TB from chronological events; highlight suspicious nodes."""
    if not events:
        return "flowchart TB\n  A[No events]"
    # Sort by timestamp
    sorted_events = sorted(events, key=lambda e: e.get("timestamp", ""))
    lines = ["flowchart TB"]
    suspicious_ids = []
    for i, ev in enumerate(sorted_events):
        node_id = f"E{i}"
        ts = ev.get("timestamp", "")[:16]
        etype = (ev.get("event_type") or "Event").replace('"', "'")
        details = (ev.get("details") or "").replace('"', "'")[:20]
        label = f"{ts} {etype}" + (f" {details}" if details else "")
        # Mermaid node: E0["label"] — escape so label does not break diagram or HTML
        safe_label = label.replace("]", " ").replace('"', "'").replace("<", " ").replace(">", " ").replace("{", " ").replace("}", " ")
        lines.append(f'  {node_id}["{safe_label}"]')
        if ev.get("suspicious"):
            suspicious_ids.append(node_id)
    for i in range(len(sorted_events) - 1):
        lines.append(f"  E{i} --> E{i + 1}")
    if suspicious_ids:
        lines.append("  classDef suspicious fill:#ffebee,stroke:#c62828,stroke-width:2px")
        lines.append("  class " + ",".join(suspicious_ids) + " suspicious")
    return "\n".join(lines)


def _mermaid_html(mermaid_code: str) -> str:
    """Return HTML that loads Mermaid.js and renders the diagram (UMD bundle for iframe)."""
    return (
        '<div class="mermaid" style="min-height:200px;">'
        + mermaid_code
        + """</div>
<script src="https://cdn.jsdelivr.net/npm/mermaid@9/dist/mermaid.min.js"></script>
<script>
  mermaid.initialize({ startOnLoad: true, theme: 'neutral' });
</script>"""
    )


with st.expander("Timeline", expanded=True):
    if selected_id:
        alert = alert_by_id.get(selected_id)
        events = (alert or {}).get("timeline_events") or []
        if events:
            mermaid_code = _mermaid_timeline(events)
            st.markdown("**Chronological events** (suspicious events highlighted in red border)")
            st.components.v1.html(_mermaid_html(mermaid_code), height=400)
            with st.expander("Event list (text)", expanded=False):
                for ev in sorted(events, key=lambda e: e.get("timestamp", "")):
                    susp = " ⚠️ Suspicious" if ev.get("suspicious") else ""
                    st.markdown(f"- **{ev.get('timestamp', '')}** — {ev.get('event_type', '')} {ev.get('details', '')}{susp}")
        else:
            st.write("No timeline events for this case.")
    else:
        st.write("Select an alert to view the timeline.")

# ---------- Recommended Next Steps (investigator-assist) ----------
st.markdown("---")
st.markdown(
    '<p style="font-size:1.1rem; font-weight:600; color:#37474f; margin-bottom:0.25rem;">Recommended next steps</p>'
    '<p style="font-size:0.9rem; color:#607d8b; margin-bottom:0.75rem;">Suggestions to support your investigation—you decide what to do next.</p>',
    unsafe_allow_html=True,
)
if selected_id:
    alert = alert_by_id.get(selected_id)
    try:
        from backend.explainability.next_step_advisor import recommend_next_steps
        indicators = alert.get("risk_factors") or [alert.get("one_line_explanation", "")]
        out = recommend_next_steps(indicators, use_llm=True)
        steps = out.get("next_steps", [])
        rationale = out.get("rationale", "")
    except Exception:
        steps = ["Unable to load recommendations. Set OPENAI_API_KEY and retry."]
        rationale = ""
else:
    steps = [
        "Select a case from the sidebar to see steps tailored to that alert.",
    ]
    rationale = ""
for i, step in enumerate(steps, 1):
    st.markdown(f"{i}. {step}")
if rationale:
    st.caption(rationale)
st.markdown("---")

# ---------- Investigation Report (generate on demand, display in expander) ----------
if "investigation_report" not in st.session_state:
    st.session_state.investigation_report = None
if "investigation_report_account" not in st.session_state:
    st.session_state.investigation_report_account = None

def _build_case_context(account_id: str, alert: dict, status: str) -> str:
    """Build a single text block of case data for the regulatory report generator."""
    lines = [
        f"Account ID: {account_id}",
        f"Case status: {status}",
        f"Fraud probability: {alert.get('fraud_probability', 0):.0%}",
        f"Risk level: {alert.get('risk_level', 'N/A')}",
        f"Anomaly score: {alert.get('anomaly_score', 0):.0%}",
        f"One-line explanation: {alert.get('one_line_explanation', '')}",
        "",
        "Risk factors:",
    ]
    for f in alert.get("risk_factors") or []:
        lines.append(f"  - {f}")
    events = alert.get("timeline_events") or []
    if events:
        lines.append("")
        lines.append("Timeline events:")
        for e in events:
            ts = e.get("timestamp", "")
            typ = e.get("event_type", "")
            details = e.get("details", "")
            susp = " [suspicious]" if e.get("suspicious") else ""
            lines.append(f"  - {ts} | {typ} | {details}{susp}")
    lines.append("")
    lines.append("Evidence types available on dashboard: transaction history (last 5), access by country, VPN %, KYC/identity checks, device and IP network graph. Use only what is stated above or explicitly marked as available.")
    return "\n".join(lines)

report_expanded = False
if selected_id:
    alert_for_report = alert_by_id.get(selected_id)
    has_report = (
        st.session_state.investigation_report is not None
        and st.session_state.investigation_report_account == selected_id
    )
    if st.button("Generate Investigation Report", key="btn_generate_report"):
        case_context = _build_case_context(
            selected_id, alert_for_report, _get_case_status(selected_id)
        )
        with st.spinner("Generating report..."):
            try:
                from backend.explainability.report_writer import generate_regulatory_report
                report_md = generate_regulatory_report(case_context, use_llm=True)
                st.session_state.investigation_report = report_md
                st.session_state.investigation_report_account = selected_id
                report_expanded = True
            except Exception as e:
                st.error(f"Report generation failed: {e}")
        st.rerun()
    report_expanded = report_expanded or has_report
else:
    has_report = False
    report_expanded = False

with st.expander("Report", expanded=report_expanded):
    if not selected_id:
        st.write("Select a case from the sidebar to generate an investigation report.")
    elif st.session_state.investigation_report and st.session_state.investigation_report_account == selected_id:
        st.markdown(st.session_state.investigation_report)
        if st.button("Regenerate report", key="btn_regenerate_report"):
            case_context = _build_case_context(
                selected_id, alert_by_id[selected_id], _get_case_status(selected_id)
            )
            with st.spinner("Regenerating report..."):
                try:
                    from backend.explainability.report_writer import generate_regulatory_report
                    st.session_state.investigation_report = generate_regulatory_report(case_context, use_llm=True)
                    st.session_state.investigation_report_account = selected_id
                except Exception as e:
                    st.error(f"Report generation failed: {e}")
            st.rerun()
    else:
        st.write("Click **Generate Investigation Report** (above) to create a structured report: Executive Summary, Evidence Reviewed, Findings, Conclusion & Recommendations.")
