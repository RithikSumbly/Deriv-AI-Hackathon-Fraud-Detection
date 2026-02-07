# Fraud Investigation Dashboard (Streamlit)

Internal AI-powered fraud investigation dashboard. Investigator-first UX; explainability is the hero; human-in-the-loop.

## Run

Requires **OPENAI_API_KEY** (or OPENAI_BASE_URL) for AI explanations, next-step recommendations, and report generation. No preset/demo content is returned when the LLM is unavailable.

From **project root**:

```bash
pip install -r frontend/requirements-streamlit.txt
streamlit run frontend/app.py
```

From **frontend/**:

```bash
pip install -r requirements-streamlit.txt
streamlit run app.py
```

Open http://localhost:8501. Use the sidebar to select a case; open **Evidence → Network** for the interactive graph.

## Features

- **Overview**: Alert queue, open count, average scores (uses `backend/data/anomaly_scores.csv` when present; otherwise mock alert list).
- **Case detail & explainability**: Fraud probability, anomaly score, “Why this alert?” (concise explanation, risk drivers, junior analyst summary), SHAP table, network indicators.
- **Timeline**: Chronological events with suspicious-sequence tags.
- **Next steps**: Top 3 recommended investigative actions (no decisions, no fraud label).
- **Report**: Case summary, evidence, investigator conclusion → generate compliance/regulator-ready report (uses backend explainability when available).
- **Evidence → Network**: Pyvis network graph — center node = current account, connected nodes = devices & IPs, red = fraud-linked; hover for labels.

## Network graph (working example)

Uses **pyvis**. Center node = account; connected nodes = devices (box) and IPs (dot); fraud-linked nodes in red; hover shows labels.

```python
from pyvis.network import Network
import streamlit as st
from pathlib import Path
import tempfile

def build_network_html(account_id: str, devices: list[dict], ips: list[dict], height: int = 400) -> str:
    net = Network(height=f"{height}px", width="100%", notebook=False, cdn_resources="remote")
    net.add_node(account_id, label=account_id, title=f"Account: {account_id}", color="#1a73e8", size=35)
    for d in devices:
        nid, fraud = d.get("id", "?"), d.get("fraud_linked", False)
        net.add_node(nid, label=nid, title=f"Device: {nid}\n{'Fraud-linked' if fraud else 'OK'}", color="#c62828" if fraud else "#78909c", size=25, shape="box")
        net.add_edge(account_id, nid, title="uses device")
    for ip in ips:
        nid, fraud = ip.get("id", "?"), ip.get("fraud_linked", False)
        net.add_node(nid, label=nid, title=f"IP: {nid}\n{'Fraud-linked' if fraud else 'OK'}", color="#c62828" if fraud else "#78909c", size=25)
        net.add_edge(account_id, nid, title="logged from")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
        tmp = f.name
    net.save_graph(tmp)
    html = Path(tmp).read_text()
    Path(tmp).unlink(missing_ok=True)
    return html

# In your Streamlit app (e.g. in Network tab):
devices = [{"id": "DEV-F-0042", "fraud_linked": True}, {"id": "DEV-L-0001", "fraud_linked": False}]
ips = [{"id": "IP-F-0012", "fraud_linked": False}, {"id": "IP-F-0008", "fraud_linked": True}]
html = build_network_html(selected_id, devices, ips)
st.components.v1.html(html, height=420, scrolling=False)
```

## Tech

- Streamlit, Pandas, Pyvis (network graph). Minimal dependencies.
- Layout: `st.columns`, `st.expander`, `st.tabs`. Clean, serious, regulator-safe.
