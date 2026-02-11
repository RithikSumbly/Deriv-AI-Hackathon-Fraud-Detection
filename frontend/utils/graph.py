"""Pyvis network graph helpers for the Network evidence tab."""
from pathlib import Path

try:
    from pyvis.network import Network
    HAS_PYVIS = True
except ImportError:
    HAS_PYVIS = False


def build_network_graph_html(
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


def short_node_label(full_label: str, max_chars: int = 10) -> str:
    """Shorten node label for display; full id remains in title (hover)."""
    if not full_label or len(full_label) <= max_chars:
        return full_label
    if full_label.startswith("ACC-"):
        return full_label[-8:] if len(full_label) > 8 else full_label
    if full_label.startswith("DEV-") or full_label.startswith("IP-"):
        return full_label[-6:] if len(full_label) > 6 else full_label
    return full_label[: max_chars - 2] + ".." if len(full_label) > max_chars else full_label


def build_network_graph_html_from_graph(graph: dict, height: int = 400) -> str | None:
    """
    Build interactive network from backend graph with fixed hierarchical layout:
    level 0 = primary account, level 1 = devices & IPs, level 2 = linked accounts.
    Physics disabled so the graph is stable and not jumbled.
    """
    if not HAS_PYVIS:
        return None
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    net = Network(
        height=f"{height}px",
        width="100%",
        notebook=False,
        heading="",
        cdn_resources="remote",
    )
    net.set_options(
        """
        {
          "layout": {
            "hierarchical": {
              "enabled": true,
              "direction": "UD",
              "levelSeparation": 120,
              "nodeSpacing": 100,
              "sortMethod": "directed"
            }
          },
          "physics": { "enabled": false }
        }
        """
    )
    for n in nodes:
        nid = n.get("id", "?")
        full_label = n.get("label", nid)
        ntype = n.get("type", "")
        title = f"{ntype}\n{full_label}"
        label = full_label if ntype == "primary_account" else short_node_label(full_label, 10)
        level = 0 if ntype == "primary_account" else (1 if ntype in ("device", "ip") else 2)
        if ntype == "primary_account":
            net.add_node(nid, label=label, title=title, color="#1a73e8", size=32, font={"size": 13}, level=level)
        elif ntype == "other_account":
            net.add_node(nid, label=label, title=title, color="#f57c00", size=18, font={"size": 10}, level=level)
        elif ntype == "device":
            net.add_node(nid, label=label, title=title, color="#78909c", size=20, font={"size": 10}, shape="box", level=level)
        else:
            net.add_node(nid, label=label, title=title, color="#78909c", size=20, font={"size": 10}, shape="dot", level=level)
    for e in edges:
        src = e.get("source")
        tgt = e.get("target")
        rel = e.get("relationship", "")
        if src and tgt:
            net.add_edge(src, tgt, title=rel)
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
