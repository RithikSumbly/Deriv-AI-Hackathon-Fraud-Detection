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

from backend.agents import run_pipeline, run_knowledge_capture, run_visualization_agent
from backend.explainability.visualization_tool import spec_to_mermaid
from backend.services.alerts import get_alerts
from backend.services.feedback import add_decision, add_knowledge_pattern, get_similar_confirmed_count, has_false_positive_history

st.set_page_config(
    page_title="Fraud Investigation Dashboard",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------------------------------------------------------
# Global styles (smooth dark theme, refined cards, typography)
# -----------------------------------------------------------------------------
st.markdown("""
<style>
  /* Main content – gradient + subtle ambient depth */
  .stApp {
    background: radial-gradient(ellipse 90% 60% at 75% 15%, rgba(56, 139, 253, 0.035) 0%, transparent 50%),
                radial-gradient(ellipse 70% 50% at 15% 85%, rgba(46, 213, 115, 0.025) 0%, transparent 50%),
                linear-gradient(165deg, #0d1117 0%, #161b22 45%, #1c2128 100%);
    min-height: 100vh;
  }
  /* Sidebar – soft gradient, subtle border */
  [data-testid="stSidebar"] {
    background: linear-gradient(180deg, #161b22 0%, #1a1f26 50%, #21262d 100%);
    border-right: 1px solid rgba(48, 54, 61, 0.6);
  }
  [data-testid="stSidebar"] .stMarkdown { color: #e6edf3; }
  /* Cards – frosted feel, softer shadow, larger radius */
  .fraud-card {
    background: rgba(22, 27, 34, 0.88);
    border: 1px solid rgba(48, 54, 61, 0.7);
    border-radius: 16px;
    padding: 1.35rem 1.6rem;
    margin: 0.85rem 0;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.25), 0 1px 0 rgba(255, 255, 255, 0.03) inset;
    transition: box-shadow 0.2s ease, border-color 0.2s ease;
  }
  .fraud-card:hover { box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), 0 1px 0 rgba(255, 255, 255, 0.04) inset; }
  .fraud-card-title {
    font-size: 0.8rem; font-weight: 600; color: #8b949e;
    letter-spacing: 0.06em; text-transform: uppercase; margin-bottom: 0.5rem;
  }
  .fraud-metric-value { font-size: 1.75rem; font-weight: 700; letter-spacing: -0.02em; }
  /* Headers */
  h1, h2, h3 { color: #e6edf3 !important; font-weight: 600 !important; }
  .hero-title {
    font-size: 2rem; font-weight: 700; color: #e6edf3;
    letter-spacing: -0.03em; margin-bottom: 0.25rem !important;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
  }
  .hero-sub {
    font-size: 0.95rem; color: #8b949e; margin-bottom: 1.5rem !important;
    letter-spacing: 0.01em;
  }
  hr { border-color: rgba(48, 54, 61, 0.8) !important; opacity: 0.9; }
  /* Buttons – smooth radius, clear hover */
  .stButton > button {
    border-radius: 12px;
    font-weight: 600;
    transition: transform 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
  }
  .stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
  }
  .stButton > button:active { transform: translateY(0); }
  /* Primary (e.g. Risk toggle) – slightly lifted */
  .stButton > button[kind="primary"] {
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.25);
  }
  /* Metrics */
  [data-testid="stMetricValue"] { font-size: 1.4rem !important; font-weight: 700 !important; color: #e6edf3 !important; }
  [data-testid="stMetricLabel"] { color: #8b949e !important; }
  /* Tabs – pill style, more padding/gap so labels aren't cramped */
  .stTabs [data-baseweb="tab-list"] {
    background: rgba(33, 38, 45, 0.9);
    border-radius: 12px;
    padding: 10px 14px;
    gap: 12px;
    border: 1px solid rgba(48, 54, 61, 0.5);
  }
  .stTabs [data-baseweb="tab"] {
    background: transparent;
    border-radius: 10px;
    color: #8b949e;
    padding: 8px 16px;
    min-height: 2.5rem;
    transition: background 0.2s ease, color 0.2s ease;
  }
  .stTabs [aria-selected="true"] {
    background: rgba(48, 54, 61, 0.8) !important;
    color: #e6edf3 !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  }
  /* Space between tab bar and tab content */
  .stTabs [data-baseweb="tab-panel"] {
    padding-top: 1.25rem;
  }
  /* Expanders */
  .streamlit-expanderHeader {
    background: rgba(33, 38, 45, 0.8);
    border-radius: 10px;
    border: 1px solid rgba(48, 54, 61, 0.4);
  }
  /* DataFrames */
  .stDataFrame {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid rgba(48, 54, 61, 0.6);
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
  }
  /* Section labels – more space below so content isn't cramped */
  .section-label {
    font-size: 0.8rem; font-weight: 600; color: #8b949e;
    letter-spacing: 0.05em; text-transform: uppercase;
    margin-bottom: 0.85rem;
  }
  /* Selectbox / inputs – rounded, subtle border */
  .stSelectbox > div, [data-testid="stSelectbox"] > div {
    border-radius: 10px;
  }
  /* Block container – gentle padding */
  .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Page title (hero) — logo is in sidebar
# -----------------------------------------------------------------------------
st.markdown(
    '<p class="hero-title">🔍 Fraud Investigation Dashboard</p>'
    '<p class="hero-sub">Internal use · Human-in-the-loop</p>',
    unsafe_allow_html=True,
)

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

_logo_path = Path(__file__).resolve().parent / "logos" / "Gemini_Generated_Image_ayb0j7ayb0j7ayb0.png"
with st.sidebar:
    if _logo_path.exists():
        st.image(str(_logo_path), use_container_width=True)
        st.markdown("")  # spacing
    st.markdown(
        '<p style="font-size:1.1rem; font-weight:700; color:#e6edf3; margin-bottom:0.5rem;">Cases</p>'
        '<p style="font-size:0.8rem; color:#8b949e; margin-bottom:1rem;">Filter, sort, and select a case</p>',
        unsafe_allow_html=True,
    )
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
        false_positive_list = [aid for aid in all_ids if _get_case_status(aid) == "False Positive"]

        # Sort state (persist across reruns)
        if "sort_risk" not in st.session_state:
            st.session_state.sort_risk = "High → Low"
        if "sort_anomaly" not in st.session_state:
            st.session_state.sort_anomaly = "High → Low"

        def _toggle_risk():
            st.session_state.sort_risk = "Low → High" if st.session_state.sort_risk == "High → Low" else "High → Low"

        def _toggle_anomaly():
            st.session_state.sort_anomaly = "Low → High" if st.session_state.sort_anomaly == "High → Low" else "High → Low"

        # Filter and sort mode in expander
        if "sort_mode" not in st.session_state:
            st.session_state.sort_mode = "Risk (High → Low)"
        with st.expander("Filter & sort", expanded=False):
            filter_risk = st.selectbox("Risk filter", ["All", "High", "Medium", "Low"], index=0, key="filter_risk")
            if filter_risk != "All":
                alerts_list = [aid for aid in alerts_list if alert_by_id[aid].get("risk_level") == filter_risk]
            sort_mode = st.selectbox(
                "Sort by",
                ["Risk (High → Low)", "Anomaly (High → Low)", "Outcome-informed (Learning)"],
                index=["Risk (High → Low)", "Anomaly (High → Low)", "Outcome-informed (Learning)"].index(st.session_state.sort_mode),
                key="sort_mode_select",
            )
            st.session_state.sort_mode = sort_mode

        # Toggle buttons when sort is Risk or Anomaly
        risk_high_first = st.session_state.sort_risk == "High → Low"
        anom_high_first = st.session_state.sort_anomaly == "High → Low"
        tc1, tc2 = st.columns(2)
        with tc1:
            st.button(
                "↓ Risk" if risk_high_first else "↑ Risk",
                key="btn_risk_toggle",
                type="primary" if risk_high_first and st.session_state.sort_mode == "Risk (High → Low)" else "secondary",
                on_click=_toggle_risk,
                help="Risk: High→Low" if risk_high_first else "Risk: Low→High",
            )
        with tc2:
            st.button(
                "↓ Anomaly" if anom_high_first else "↑ Anomaly",
                key="btn_anom_toggle",
                type="primary" if anom_high_first and st.session_state.sort_mode == "Anomaly (High → Low)" else "secondary",
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
            if st.session_state.sort_mode == "Outcome-informed (Learning)":
                return sorted(
                    ids,
                    key=lambda aid: (
                        -get_similar_confirmed_count(
                            alert_by_id[aid].get("risk_level", "Low"),
                            feature_vector=alert_by_id[aid].get("feature_vector"),
                        ),
                        -alert_by_id[aid]["fraud_probability"],
                    ),
                )
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
        false_positive_list = _sort_alerts(false_positive_list)

        def _set_selected(which: str):
            key = f"dd_{which}"
            if st.session_state.get(key) and st.session_state[key] != _PLACEHOLDER:
                st.session_state.selected_alert_id = st.session_state[key]

        st.markdown('<p class="section-label" style="margin-top:0.5rem;">Select a case</p>', unsafe_allow_html=True)
        opts_alerts = alerts_list if alerts_list else [_PLACEHOLDER]
        idx_alerts = opts_alerts.index(st.session_state.get("selected_alert_id")) if st.session_state.get("selected_alert_id") in opts_alerts else 0
        st.selectbox("Alerts", options=opts_alerts, index=idx_alerts, key="dd_alerts", on_change=lambda: _set_selected("alerts"))
        opts_verified = verified_fraud_list if verified_fraud_list else [_PLACEHOLDER]
        idx_verified = opts_verified.index(st.session_state.get("selected_alert_id")) if st.session_state.get("selected_alert_id") in opts_verified else 0
        st.selectbox("Verified fraud", options=opts_verified, index=idx_verified, key="dd_verified", on_change=lambda: _set_selected("verified"))
        opts_legit = legit_list if legit_list else [_PLACEHOLDER]
        idx_legit = opts_legit.index(st.session_state.get("selected_alert_id")) if st.session_state.get("selected_alert_id") in opts_legit else 0
        st.selectbox("Legit", options=opts_legit, index=idx_legit, key="dd_legit", on_change=lambda: _set_selected("legit"))
        opts_fp = false_positive_list if false_positive_list else [_PLACEHOLDER]
        idx_fp = opts_fp.index(st.session_state.get("selected_alert_id")) if st.session_state.get("selected_alert_id") in opts_fp else 0
        st.selectbox("False positives", options=opts_fp, index=idx_fp, key="dd_fp", on_change=lambda: _set_selected("fp"))

        # Ordered list for Next case / Previous case navigation
        st.session_state.case_list = alerts_list + verified_fraud_list + legit_list + false_positive_list

        # Initial selection
        current = st.session_state.get("selected_alert_id")
        all_lists = alerts_list + verified_fraud_list + legit_list + false_positive_list
        if not current or current not in all_lists:
            first = (alerts_list or [])[0] if alerts_list else (verified_fraud_list or [])[0] if verified_fraud_list else (legit_list or [])[0] if legit_list else (false_positive_list or [])[0] if false_positive_list else None
            if first:
                st.session_state.selected_alert_id = first

        # Selected summary — compact card
        chosen = st.session_state.get("selected_alert_id")
        if chosen and chosen in alert_by_id:
            sel = alert_by_id[chosen]
            risk_color = {"High": "#c62828", "Medium": "#e65100", "Low": "#2e7d32"}.get(sel["risk_level"], "#37474f")
            expl = (sel.get("one_line_explanation") or "")[:60] + "…" if len(sel.get("one_line_explanation") or "") > 60 else (sel.get("one_line_explanation") or "")
            st.markdown(
                f'<div class="fraud-card" style="margin-top:1rem; padding:1rem;">'
                f'<p class="fraud-card-title">Selected case</p>'
                f'<p style="margin:0.35rem 0; font-size:0.95rem; color:#e6edf3;"><strong>{chosen}</strong></p>'
                f'<span style="background:{risk_color};color:white;padding:3px 8px;border-radius:6px;font-size:0.75rem;font-weight:600;">{sel["risk_level"]}</span> '
                f'<span style="font-size:0.9rem; color:#8b949e;">{sel["fraud_probability"]:.0%}</span>'
                f'<p style="margin:0.5rem 0 0; font-size:0.8rem; color:#8b949e; line-height:1.4;">{expl}</p>'
                f'</div>',
                unsafe_allow_html=True,
            )

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

    # ---------- Agent pipeline: run only when user clicks; cache by account_id ----------
    st.session_state.setdefault("agent_cache", {})
    agent_results = st.session_state.agent_cache.get(selected_id) or {}

    # ---------- Case header (card) ----------
    risk_pct = alert["fraud_probability"] * 100
    risk_color = "#c62828" if risk_pct >= 60 else "#e65100" if risk_pct >= 30 else "#2e7d32"
    if status == "Marked Legit":
        status_color = "#2e7d32"
        status_label = "Legit"
    elif status == "Confirmed Fraud":
        status_color = "#c62828"
        status_label = "Verified fraud"
    elif status == "False Positive":
        status_color = "#58a6ff"
        status_label = "False positive"
    else:
        status_color = "#e6edf3"
        status_label = status
    st.markdown(
        f'<div class="fraud-card" style="display:flex; align-items:center; flex-wrap:wrap; gap:2rem;">'
        f'<div><p class="fraud-card-title">Account</p><p style="margin:0; font-size:1.1rem; font-weight:600; color:#e6edf3;">{selected_id}</p></div>'
        f'<div><p class="fraud-card-title">Status</p><p style="margin:0; font-size:1rem; font-weight:600; color:{status_color};">{status_label}</p></div>'
        f'<div><p class="fraud-card-title">Risk score</p><p class="fraud-metric-value" style="color:{risk_color}; margin:0;">{risk_pct:.0f}%</p></div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<p class="fraud-card-title" style="margin-bottom:0.5rem;">Actions</p>', unsafe_allow_html=True)
    btn_col1, btn_col2, btn_col3, btn_col4, btn_next = st.columns(5)
    def _on_case_close(decision: str, reason: str = ""):
        add_decision(selected_id, decision, reason=reason, risk_level=alert["risk_level"], fraud_probability=alert["fraud_probability"], anomaly_score=alert.get("anomaly_score"), feature_vector=alert.get("feature_vector"))
        pattern = run_knowledge_capture(alert, decision, reason)
        if pattern and "_error" not in pattern:
            add_knowledge_pattern(selected_id, pattern)

    with btn_col1:
        if st.button("Confirm Fraud", key="btn_confirm_fraud"):
            st.session_state.case_status[selected_id] = "Confirmed Fraud"
            _on_case_close("Confirmed Fraud", "")
            st.rerun()
    with btn_col2:
        if st.button("Mark Legit", key="btn_mark_legit"):
            st.session_state.case_status[selected_id] = "Marked Legit"
            _on_case_close("Marked Legit", "")
            st.rerun()
    with btn_col3:
        if st.button("Request More Info", key="btn_more_info"):
            st.session_state.case_status[selected_id] = "More Info Requested"
            st.rerun()
    with btn_col4:
        if status != "False Positive" and st.button("Dismiss as false positive", key="btn_dismiss_fp", help="Mark as false positive and record reason for audit"):
            st.session_state.show_fp_reason = True
            st.rerun()
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
    # Run investigation agents (on demand)
    if st.button("Run investigation agents", key="btn_run_agents", help="Run Transaction, Identity, Geo, Network, Outcome Similarity and Orchestrator agents for this case"):
        with st.spinner("Running investigation agents…"):
            st.session_state.agent_cache[selected_id] = run_pipeline(alert, "alert_creation")
        st.rerun()
    if not agent_results:
        st.caption("Click **Run investigation agents** above to see AI risk summary, key drivers, and Evidence tab content.")
    # Dismiss as false positive: required reason (audit trail) — regulator-safe
    if st.session_state.get("show_fp_reason") and selected_id and status != "False Positive":
        with st.expander("Record reason for false positive (required for audit)", expanded=True):
            fp_reason_options = [
                "Expected income source",
                "Known customer behavior",
                "Temporary anomaly",
                "Other",
            ]
            fp_reason_choice = st.selectbox("Reason for dismissal (required)", options=fp_reason_options, key="fp_reason_dropdown")
            fp_reason_other = st.text_input("If Other, specify", key="fp_reason_other", placeholder="Free text")
            reason_for_audit = fp_reason_other.strip() if fp_reason_choice == "Other" else fp_reason_choice
            if st.button("Submit dismissal", key="btn_submit_fp"):
                if not reason_for_audit and fp_reason_choice == "Other":
                    st.warning("Please provide a reason (required for audit).")
                else:
                    _on_case_close("False Positive", reason_for_audit or fp_reason_choice)
                    st.session_state.case_status[selected_id] = "False Positive"
                    st.session_state.show_fp_reason = False
                    st.rerun()
    # Auto-resolve suggestion (conservative: low risk + historical FPs)
    prob, anom = alert["fraud_probability"], alert.get("anomaly_score") or 0
    low_risk = prob < 0.15 and anom < 0.3
    if low_risk and has_false_positive_history() and status not in ("False Positive", "Marked Legit", "Confirmed Fraud"):
        st.info("**Consider dismissing as false positive?** Pattern consistent with historical legitimate behavior. Use *Dismiss as false positive* to record reason for audit.")
    st.markdown("---")

    def _escape(s: str) -> str:
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    def _agent_error_message(err: str) -> str:
        """User-facing message for agent errors; rate-limit errors get a friendly line."""
        if not err:
            return "Unknown error"
        err_lower = err.lower()
        if any(x in err_lower or x in err for x in ("rate limit", "quota", "429", "resource exhausted")):
            return "Rate limit reached. Please try again in a minute."
        return err

    # ---------- Case metrics (compact row) ----------
    st.markdown(f'<p class="section-label">Case: {selected_id}</p>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Fraud probability", f"{alert['fraud_probability']:.0%}")
    with col2:
        st.metric("Anomaly score", f"{alert.get('anomaly_score', 0):.0%}")
    with col3:
        st.metric("Risk level", alert["risk_level"])
    st.markdown(
        f'<p style="font-size:0.9rem; color:#8b949e; margin-top:-0.5rem; margin-bottom:0.5rem;">{_escape(alert["one_line_explanation"] or "")}</p>',
        unsafe_allow_html=True,
    )
    # Predictive explanation (defensible, regulator-safe copy); use Outcome Similarity agent when available
    outcome_ag = agent_results.get("outcome_similarity") or {}
    if "_error" not in outcome_ag and outcome_ag.get("similar_confirmed_cases_count") is not None:
        similar_n = outcome_ag.get("similar_confirmed_cases_count", 0)
        similar_expl = outcome_ag.get("explanation") or ""
    else:
        similar_n = get_similar_confirmed_count(alert["risk_level"], feature_vector=alert.get("feature_vector"))
        similar_expl = ""
    risk_factors = alert.get("risk_factors") or [alert.get("one_line_explanation", "")]
    n_factors = len(risk_factors)
    pct = alert["fraud_probability"] * 100
    if pct >= 60:
        likelihood_phrase = "High likelihood of real fraud"
    elif pct >= 30:
        likelihood_phrase = "Moderate likelihood of real fraud"
    else:
        likelihood_phrase = "Lower likelihood of real fraud"
    similar_phrase = f" Behavioral pattern similar to {similar_n} previously confirmed fraud case{'s' if similar_n != 1 else ''}." if similar_n else " Similar to confirmed fraud patterns."
    if similar_expl:
        similar_phrase = f" {_escape(similar_expl)}"
    st.markdown(
        f'<p style="font-size:0.9rem; color:#c9d1d9; margin-bottom:1rem;">'
        f'<strong>{likelihood_phrase} ({pct:.0f}%).</strong> Based on <strong>{n_factors}</strong> independent risk signal{"s" if n_factors != 1 else ""}.'
        f'{similar_phrase}</p>',
        unsafe_allow_html=True,
    )

    # ---------- Why this account was flagged (card): Orchestrator when available ----------
    orch = agent_results.get("orchestrator") or {}
    if "_error" not in orch and (orch.get("investigation_summary") or orch.get("key_drivers")):
        bullets = orch.get("key_drivers") or []
        if orch.get("investigation_summary"):
            bullets = [orch["investigation_summary"]] + list(bullets)
        bullets_html = "<br>".join("• " + _escape(str(b)) for b in bullets) if bullets else _escape(orch.get("investigation_summary", ""))
        conf_val = orch.get("confidence")
        if conf_val is not None:
            try:
                c = float(conf_val)
                if c >= 0.6:
                    confidence_label, confidence_note, conf_color = "High confidence", "The model is fairly confident this case deserves review.", "#c62828"
                elif c >= 0.3:
                    confidence_label, confidence_note, conf_color = "Medium confidence", "The model sees notable risk; human review is recommended.", "#e65100"
                else:
                    confidence_label, confidence_note, conf_color = "Low confidence", "The model flagged this for completeness; may be normal variation.", "#2e7d32"
            except (TypeError, ValueError):
                confidence_label, confidence_note, conf_color = "Medium confidence", orch.get("investigation_summary") or "Human review recommended.", "#e65100"
        else:
            confidence_label, confidence_note, conf_color = "Medium confidence", orch.get("investigation_summary") or "Human review recommended.", "#e65100"
        priority = orch.get("priority")
        priority_line = f'<p style="margin-top:0.5rem; font-size:0.9rem; color:#8b949e;">Priority: {_escape(str(priority))} (1 = urgent, 5 = low)</p>' if priority is not None else ""
        st.markdown(
            f'<div class="fraud-card">'
            f'<p style="font-size:1.15rem; font-weight:600; color:#e6edf3; margin-bottom:0.75rem;">Why this account was flagged</p>'
            f'<div style="line-height:1.8; font-size:1rem; color:#c9d1d9;">{bullets_html}</div>'
            f'<p style="margin-top:1rem; margin-bottom:0.25rem; font-weight:600; color:{conf_color};">{confidence_label}</p>'
            f'<p style="margin:0; font-size:0.9rem; color:#8b949e;">{confidence_note}</p>'
            f'{priority_line}'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        risk_factors = alert.get("risk_factors") or [alert.get("one_line_explanation", "Activity was flagged for review.")]
        bullets_html = "<br>".join("• " + _escape(str(f)) for f in risk_factors)
        prob = alert["fraud_probability"]
        if prob >= 0.6:
            confidence_label, confidence_note, conf_color = "High confidence", "The model is fairly confident this case deserves review.", "#c62828"
        elif prob >= 0.3:
            confidence_label, confidence_note, conf_color = "Medium confidence", "The model sees notable risk; human review is recommended.", "#e65100"
        else:
            confidence_label, confidence_note, conf_color = "Low confidence", "The model flagged this for completeness; may be normal variation.", "#2e7d32"
        st.markdown(
            f'<div class="fraud-card">'
            f'<p style="font-size:1.15rem; font-weight:600; color:#e6edf3; margin-bottom:0.75rem;">Why this account was flagged</p>'
            f'<div style="line-height:1.8; font-size:1rem; color:#c9d1d9;">{bullets_html}</div>'
            f'<p style="margin-top:1rem; margin-bottom:0.25rem; font-weight:600; color:{conf_color};">{confidence_label}</p>'
            f'<p style="margin:0; font-size:0.9rem; color:#8b949e;">{confidence_note}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ---------- 30s Copilot Summary (one-glance summary below risk card) ----------
    if orch and "_error" not in orch and orch.get("investigation_summary"):
        copilot_text = (orch.get("investigation_summary") or "").strip()
        if len(copilot_text) > 200:
            copilot_text = copilot_text[:200].rsplit(" ", 1)[0] + "…"
        st.markdown(
            f'<p style="font-size:0.85rem; color:#8b949e; margin:0.5rem 0 1rem 0; line-height:1.5;">'
            f'<strong style="color:#c9d1d9;">30s summary:</strong> {_escape(copilot_text)}</p>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<p style="font-size:0.85rem; color:#8b949e; margin:0.5rem 0 1rem 0;">30s summary: Run investigation to see summary.</p>',
            unsafe_allow_html=True,
        )

    # ---------- Evidence (tabbed): fed by specialist agents ----------
    st.markdown('<p class="section-label" style="margin-top:1.75rem; margin-bottom:1rem;">Evidence</p>', unsafe_allow_html=True)
    tab_tx, tab_geo, tab_id, tab_net, tab_similar = st.tabs(["Transactions", "Access & Geo", "Identity", "Network", "Similar Cases"])
    tx_ag = agent_results.get("transaction") or {}
    geo_ag = agent_results.get("geo") or {}
    id_ag = agent_results.get("identity") or {}
    net_ag = agent_results.get("network") or {}
    with tab_tx:
        if "_error" in tx_ag:
            st.warning(f"Transaction agent unavailable: {_agent_error_message(tx_ag.get('_error', 'Unknown error'))}")
        else:
            if tx_ag.get("anomaly_score") is not None:
                st.metric("Behavior anomaly score", f"{float(tx_ag['anomaly_score']):.0%}")
            if tx_ag.get("short_explanation"):
                st.markdown(f"**Summary:** {_escape(str(tx_ag['short_explanation']))}")
            if tx_ag.get("detected_patterns"):
                st.markdown("**Detected patterns:**")
                for p in tx_ag["detected_patterns"] if isinstance(tx_ag["detected_patterns"], list) else [tx_ag["detected_patterns"]]:
                    st.markdown(f"- {_escape(str(p))}")
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Total deposits (90d)", f"£{alert.get('total_deposits_90d') or 125000:,.0f}")
            st.metric("Total withdrawals (90d)", f"£{alert.get('total_withdrawals_90d') or 118200:,.0f}")
        with c2:
            st.metric("Deposit count", alert.get("num_deposits_90d") or 12)
            st.metric("Avg cycle (days)", f"{float(alert.get('deposit_withdraw_cycle_days_avg') or 3.1):.1f}")
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
        if "_error" in geo_ag:
            st.warning(f"Geo/VPN agent unavailable: {_agent_error_message(geo_ag.get('_error', 'Unknown error'))}")
        else:
            if geo_ag.get("geo_risk"):
                st.metric("Geo/VPN risk", str(geo_ag["geo_risk"]))
            if geo_ag.get("explanation"):
                st.markdown(f"**Assessment:** {_escape(str(geo_ag['explanation']))}")
            if geo_ag.get("indicators"):
                st.markdown("**Indicators:**")
                for i in geo_ag["indicators"] if isinstance(geo_ag["indicators"], list) else [geo_ag["indicators"]]:
                    st.markdown(f"- {_escape(str(i))}")
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Countries (90d)", alert.get("countries_accessed_count") or 7)
            st.metric("VPN sessions %", f"{float(alert.get('vpn_usage_pct') or 82):.0f}%")
        with c2:
            st.metric("Distinct IPs", alert.get("ip_shared_count") or 5)
            st.metric("Last login", "2025-01-16 09:00")
        st.caption("Access by country")
        st.dataframe(
            [{"Country": "GB", "Sessions": 8}, {"Country": "NL", "Sessions": 12}, {"Country": "DE", "Sessions": 4}],
            use_container_width=True,
            hide_index=True,
        )
    with tab_id:
        if "_error" in id_ag:
            st.warning(f"Identity agent unavailable: {_agent_error_message(id_ag.get('_error', 'Unknown error'))}")
        else:
            if id_ag.get("identity_risk"):
                st.metric("Identity risk", str(id_ag["identity_risk"]))
            if id_ag.get("explanation"):
                st.markdown(f"**Assessment:** {_escape(str(id_ag['explanation']))}")
            if id_ag.get("indicators"):
                st.markdown("**Indicators:**")
                for i in id_ag["indicators"] if isinstance(id_ag["indicators"], list) else [id_ag["indicators"]]:
                    st.markdown(f"- {_escape(str(i))}")
        c1, c2 = st.columns(2)
        with c1:
            kyc = alert.get("kyc_face_match_score")
            st.metric("KYC face match", f"{float(kyc):.2f}" if kyc is not None else "0.62")
            st.metric("Doc verified", "Yes")
        with c2:
            st.metric("Account age (days)", alert.get("account_age_days") or 152)
            inc = alert.get("declared_income_annual")
            st.metric("Declared income", f"£{inc:,.0f}" if inc is not None else "£45,000")
        st.caption("Identity checks")
        st.dataframe(
            [{"Check": "ID document", "Result": "Pass"}, {"Check": "Face match", "Result": "Below threshold"}, {"Check": "Address", "Result": "Pass"}],
            use_container_width=True,
            hide_index=True,
        )
    with tab_net:
        if "_error" in net_ag:
            st.warning(f"Network agent unavailable: {_agent_error_message(net_ag.get('_error', 'Unknown error'))}")
        else:
            if net_ag.get("cluster_size") is not None:
                st.metric("Cluster size", str(net_ag["cluster_size"]))
            if net_ag.get("known_fraud_links") is not None:
                st.metric("Known fraud links", str(net_ag["known_fraud_links"]))
            if net_ag.get("explanation"):
                st.markdown(f"**Assessment:** {_escape(str(net_ag['explanation']))}")
            if net_ag.get("shared_signals"):
                st.markdown("**Shared signals:**")
                for s in net_ag["shared_signals"] if isinstance(net_ag["shared_signals"], list) else [net_ag["shared_signals"]]:
                    st.markdown(f"- {_escape(str(s))}")
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Devices linked", 1)
            st.metric("Accounts on same device", alert.get("device_shared_count") or 8)
        with c2:
            st.metric("IPs linked", alert.get("ip_shared_count") or 2)
            st.metric("Same device as fraud", "Yes")
        st.caption("Device & IP summary")
        st.dataframe(
            [{"Device ID": "DEV-F-0042", "Accounts": 8}, {"IP (hash)": "IP-F-0012", "Accounts": 4}],
            use_container_width=True,
            hide_index=True,
        )
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
    with tab_similar:
        outcome_ag = agent_results.get("outcome_similarity") or {}
        if "_error" in outcome_ag:
            similar_n = get_similar_confirmed_count(alert["risk_level"], feature_vector=alert.get("feature_vector"))
            st.warning(f"Outcome Similarity agent unavailable: {_agent_error_message(outcome_ag.get('_error', 'Unknown error'))}")
            st.markdown(f"**Similar confirmed cases (system):** {similar_n} previously confirmed fraud case{'s' if similar_n != 1 else ''} match this pattern.")
        else:
            if outcome_ag.get("fraud_likelihood") is not None:
                try:
                    st.metric("Fraud likelihood (outcome-based)", f"{float(outcome_ag['fraud_likelihood']):.0%}")
                except (TypeError, ValueError):
                    st.metric("Fraud likelihood (outcome-based)", str(outcome_ag["fraud_likelihood"]))
            if outcome_ag.get("similar_confirmed_cases_count") is not None:
                n = outcome_ag["similar_confirmed_cases_count"]
                st.metric("Similar confirmed cases", n)
            if outcome_ag.get("explanation"):
                st.markdown(f"**Assessment:** {_escape(str(outcome_ag['explanation']))}")
        st.caption("Similar confirmed cases inform the outcome-informed queue sort.")
    st.divider()

else:
    st.markdown(
        '<div class="fraud-card" style="text-align:center;"><p style="color:#8b949e; margin:0;">Select an alert from the sidebar to load case details.</p></div>',
        unsafe_allow_html=True,
    )

st.markdown("---")

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


st.markdown('<p class="section-label">Timeline</p>', unsafe_allow_html=True)
with st.expander("Chronological events", expanded=True):
    if selected_id:
        alert = alert_by_id.get(selected_id)
        events = (alert or {}).get("timeline_events") or []
        if events:
            st.session_state.setdefault("timeline_spec_cache", {})
            spec = st.session_state.timeline_spec_cache.get(selected_id)
            if st.button("Build timeline flow", key="btn_build_timeline", help="Run Visualization agent to build AI-generated flowchart from events"):
                with st.spinner("Building timeline flow…"):
                    st.session_state.timeline_spec_cache[selected_id] = run_visualization_agent(events)
                st.rerun()
            if spec and "_error" not in spec and spec.get("timeline") and spec.get("edges") is not None:
                mermaid_code = spec_to_mermaid(spec)
                st.markdown("**Chronological events** (AI-generated flow; risk = yellow, high risk = red)")
                st.components.v1.html(_mermaid_html(mermaid_code), height=400)
            else:
                mermaid_code = _mermaid_timeline(events)
                st.markdown("**Chronological events** (rule-based; suspicious events highlighted in red border)")
                st.components.v1.html(_mermaid_html(mermaid_code), height=400)
            with st.expander("Event list (text)", expanded=False):
                for ev in sorted(events, key=lambda e: e.get("timestamp", "")):
                    susp = " ⚠️ Suspicious" if ev.get("suspicious") else ""
                    st.markdown(f"- **{ev.get('timestamp', '')}** — {ev.get('event_type', '')} {ev.get('details', '')}{susp}")
        else:
            st.write("No timeline events for this case.")
    else:
        st.write("Select an alert to view the timeline.")

# ---------- Recommended Next Steps ----------
def _escape_html(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

st.markdown("---")
st.markdown(
    '<p class="section-label">Recommended next steps</p>'
    '<p style="font-size:0.9rem; color:#8b949e; margin-bottom:0.75rem;">Suggestions to support your investigation—you decide what to do next.</p>',
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
    steps = ["Select a case from the sidebar to see steps tailored to that alert."]
    rationale = ""
st.markdown(
    '<div class="fraud-card"><ol style="margin:0; padding-left:1.25rem; color:#c9d1d9; line-height:1.8;">'
    + "".join(f'<li style="margin-bottom:0.35rem;">{_escape_html(s)}</li>' for s in steps)
    + "</ol>"
    + (f'<p style="margin-top:0.75rem; margin-bottom:0; font-size:0.85rem; color:#8b949e;">{_escape_html(rationale)}</p>' if rationale else '')
    + "</div>",
    unsafe_allow_html=True,
)
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
    st.markdown('<p class="section-label">Investigation report</p>', unsafe_allow_html=True)
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

with st.expander("📄 Report", expanded=report_expanded):
    if not selected_id:
        st.markdown('<p style="color:#8b949e;">Select a case from the sidebar to generate an investigation report.</p>', unsafe_allow_html=True)
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
