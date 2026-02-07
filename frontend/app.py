"""
Fraud Investigation Dashboard — Main Streamlit layout.

Layout: page title at top | left sidebar (alert queue) | main area (case details).
Alert queue: risk badge, fraud %, one-line AI explanation; sorted by risk; select to load case.
Run: streamlit run app.py  (from project root: streamlit run frontend/app.py)
"""
import sys
from pathlib import Path

# Load .env from project root so OPENAI_API_KEY / GOOGLE_API_KEY are set for LLM calls
ROOT = Path(__file__).resolve().parent.parent
_env_file = ROOT / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_file, override=True)
    except ImportError:
        pass

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
# Load alerts (fetch more so sort/filter have enough to work with)
# -----------------------------------------------------------------------------
_alerts_raw = get_alerts(limit=500)
alert_by_id = {a["account_id"]: a for a in _alerts_raw}

# -----------------------------------------------------------------------------
# Session state: selected alert, case status, investigator decision
# All state persists across button clicks and reruns.
# -----------------------------------------------------------------------------
if "case_status" not in st.session_state:
    st.session_state.case_status = {}  # account_id -> "Under Review" | "Confirmed Fraud" | "Marked Legit" | "More Info Requested"
# selected_alert_id is owned by the sidebar radio widget; we only read it (use .get so first run works)

# Investigator decision = case status for the selected case (single source of truth)
def _get_case_status(account_id: str) -> str:
    return st.session_state.case_status.get(account_id, "Under Review")

# -----------------------------------------------------------------------------
# Left sidebar: 3 dropdowns (Alerts, Verified fraud, Legit) — cases move when status changes
# -----------------------------------------------------------------------------
_PLACEHOLDER = "— No cases —"

with st.sidebar:
    st.markdown("### Cases")
    st.markdown("")  # spacing
    if not _alerts_raw:
        st.warning("No alerts.")
        alerts_list = []
        verified_fraud_list = []
        legit_list = []
        st.session_state.case_list = []
    else:
        # Partition by investigator decision
        all_ids = [a["account_id"] for a in _alerts_raw]
        alerts_list = [aid for aid in all_ids if _get_case_status(aid) in ("Under Review", "More Info Requested")]
        verified_fraud_list = [aid for aid in all_ids if _get_case_status(aid) == "Confirmed Fraud"]
        legit_list = [aid for aid in all_ids if _get_case_status(aid) == "Marked Legit"]

        # Sort state (persist across reruns)
        if "sort_risk" not in st.session_state:
            st.session_state.sort_risk = "High → Low"
        if "sort_anomaly" not in st.session_state:
            st.session_state.sort_anomaly = "High → Low"

        def _toggle_risk():
            st.session_state.sort_risk = "Low → High" if st.session_state.sort_risk == "High → Low" else "High → Low"

        def _toggle_anomaly():
            st.session_state.sort_anomaly = "Low → High" if st.session_state.sort_anomaly == "High → Low" else "High → Low"

        # Filter in expander
        with st.expander("Filter & sort", expanded=False):
            filter_risk = st.selectbox("Risk filter", ["All", "High", "Medium", "Low"], index=0, key="filter_risk")
            if filter_risk != "All":
                alerts_list = [aid for aid in alerts_list if alert_by_id[aid].get("risk_level") == filter_risk]

        # Toggle buttons always visible: click to flip ↓ ↔ ↑
        risk_high_first = st.session_state.sort_risk == "High → Low"
        anom_high_first = st.session_state.sort_anomaly == "High → Low"
        tc1, tc2 = st.columns(2)
        with tc1:
            st.button(
                "↓ Risk" if risk_high_first else "↑ Risk",
                key="btn_risk_toggle",
                type="primary" if risk_high_first else "secondary",
                on_click=_toggle_risk,
                help="Risk: High→Low" if risk_high_first else "Risk: Low→High",
            )
        with tc2:
            st.button(
                "↓ Anomaly" if anom_high_first else "↑ Anomaly",
                key="btn_anom_toggle",
                type="primary" if anom_high_first else "secondary",
                on_click=_toggle_anomaly,
                help="Anomaly: High→Low" if anom_high_first else "Anomaly: Low→High",
            )
        risk_order = st.session_state.sort_risk
        anomaly_order = st.session_state.sort_anomaly

        risk_ord_high = {"High": 0, "Medium": 1, "Low": 2}
        risk_ord_low = {"Low": 0, "Medium": 1, "High": 2}
        def _sort_alerts(ids: list) -> list:
            if not ids:
                return ids
            risk_ord = risk_ord_high if risk_order == "High → Low" else risk_ord_low
            prob_sign = -1 if risk_order == "High → Low" else 1
            anom_sign = -1 if anomaly_order == "High → Low" else 1
            return sorted(
                ids,
                key=lambda aid: (
                    risk_ord.get(alert_by_id[aid]["risk_level"], 3),
                    prob_sign * alert_by_id[aid]["fraud_probability"],
                    anom_sign * alert_by_id[aid].get("anomaly_score", 0),
                ),
            )
        alerts_list = _sort_alerts(alerts_list)
        verified_fraud_list = _sort_alerts(verified_fraud_list)
        legit_list = _sort_alerts(legit_list)

        def _set_selected(which: str):
            key = f"dd_{which}"
            if st.session_state.get(key) and st.session_state[key] != _PLACEHOLDER:
                st.session_state.selected_alert_id = st.session_state[key]

        # Case lists (main focus)
        st.caption("Select a case")
        opts_alerts = alerts_list if alerts_list else [_PLACEHOLDER]
        idx_alerts = opts_alerts.index(st.session_state.get("selected_alert_id")) if st.session_state.get("selected_alert_id") in opts_alerts else 0
        st.selectbox("Alerts", options=opts_alerts, index=idx_alerts, key="dd_alerts", on_change=lambda: _set_selected("alerts"))
        opts_verified = verified_fraud_list if verified_fraud_list else [_PLACEHOLDER]
        idx_verified = opts_verified.index(st.session_state.get("selected_alert_id")) if st.session_state.get("selected_alert_id") in opts_verified else 0
        st.selectbox("Verified fraud", options=opts_verified, index=idx_verified, key="dd_verified", on_change=lambda: _set_selected("verified"))
        opts_legit = legit_list if legit_list else [_PLACEHOLDER]
        idx_legit = opts_legit.index(st.session_state.get("selected_alert_id")) if st.session_state.get("selected_alert_id") in opts_legit else 0
        st.selectbox("Legit", options=opts_legit, index=idx_legit, key="dd_legit", on_change=lambda: _set_selected("legit"))

        # Ordered list for Next case / Previous case navigation
        st.session_state.case_list = alerts_list + verified_fraud_list + legit_list

        # Initial selection
        current = st.session_state.get("selected_alert_id")
        if not current or current not in (alerts_list + verified_fraud_list + legit_list):
            first = (alerts_list or [])[0] if alerts_list else (verified_fraud_list or [])[0] if verified_fraud_list else (legit_list or [])[0] if legit_list else None
            if first:
                st.session_state.selected_alert_id = first

        # Selected summary — compact
        chosen = st.session_state.get("selected_alert_id")
        if chosen and chosen in alert_by_id:
            sel = alert_by_id[chosen]
            st.divider()
            risk_color = {"High": "#c62828", "Medium": "#e65100", "Low": "#2e7d32"}.get(sel["risk_level"], "#37474f")
            st.markdown(
                f"<span style='font-size:0.85rem;'>Selected</span> "
                f"<span style='background:{risk_color};color:white;padding:2px 6px;border-radius:4px;font-size:0.75rem;'>{sel['risk_level']}</span> "
                f"<span style='font-size:0.85rem;'>{sel['fraud_probability']:.0%}</span>",
                unsafe_allow_html=True,
            )
            expl = (sel.get("one_line_explanation") or "")[:55] + "…" if len(sel.get("one_line_explanation") or "") > 55 else (sel.get("one_line_explanation") or "")
            st.caption(expl)

    alerts = _alerts_raw  # for rest of app (metrics etc.)
    alert_options = [a["account_id"] for a in _alerts_raw]

# Use session state for selected case everywhere (persists across reruns)
selected_id = st.session_state.get("selected_alert_id")

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
        # Status: green for Legit, red for Verified fraud, default for Under Review / More Info
        if status == "Marked Legit":
            status_color = "#2e7d32"
            status_label = "Legit"
        elif status == "Confirmed Fraud":
            status_color = "#c62828"
            status_label = "Verified fraud"
        else:
            status_color = "inherit"
            status_label = status
        st.markdown(
            f"**Status**  \n<span style='color:{status_color}; font-weight:600;'>{status_label}</span>",
            unsafe_allow_html=True,
        )
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
        btn_col1, btn_col2, btn_col3, btn_next = st.columns([1, 1, 1, 1])
        with btn_col1:
            if st.button("Confirm Fraud", key="btn_confirm_fraud"):
                st.session_state.case_status[selected_id] = "Confirmed Fraud"
        with btn_col2:
            if st.button("Mark Legit", key="btn_mark_legit"):
                st.session_state.case_status[selected_id] = "Marked Legit"
        with btn_col3:
            if st.button("Request More Info", key="btn_more_info"):
                st.session_state.case_status[selected_id] = "More Info Requested"
        with btn_next:
            case_list = st.session_state.get("case_list") or []
            if case_list and len(case_list) > 0:
                try:
                    idx = case_list.index(selected_id)
                    next_idx = (idx + 1) % len(case_list)
                    next_id = case_list[next_idx]
                except ValueError:
                    next_id = case_list[0] if case_list else selected_id
                if st.button("Next case →", key="btn_next_case", help="Go to next case in list"):
                    st.session_state.selected_alert_id = next_id
                    st.rerun()
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
    def _escape(s: str) -> str:
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    st.markdown(
        '<p style="font-size:1.35rem; font-weight:600; color:#e8e8e8; margin-bottom:0.5rem;">Why this account was flagged</p>',
        unsafe_allow_html=True,
    )
    st.markdown("")  # spacing
    risk_factors = alert.get("risk_factors") or [alert.get("one_line_explanation", "Activity was flagged for review.")]
    bullets_html = "<br>".join("• " + _escape(str(f)) for f in risk_factors)
    st.markdown(
        f'<div style="line-height:1.85; font-size:1.05rem; margin:0.5rem 0; color:#e0e0e0;">{bullets_html}</div>',
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
        f'<p style="margin:0; font-size:0.95rem; color:#b0b0b0;">{confidence_note}</p>',
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
