"""
Pure renderer: converts a flow spec (timeline + edges) from the Visualization Agent
into Mermaid flowchart code. No LLM; no decisions; deterministic styling.
"""
from __future__ import annotations


def _escape_label(label: str) -> str:
    """Escape node label for Mermaid (brackets, quotes, etc.)."""
    if not label:
        return "Event"
    s = str(label).replace("]", " ").replace("[", " ").replace('"', "'").replace("\n", " ")
    s = s.replace("<", " ").replace(">", " ").replace("{", " ").replace("}", " ")
    return s.strip() or "Event"


def _sanitize_id(node_id: str) -> str:
    """Ensure node id is safe for Mermaid (alphanumeric, underscore)."""
    if not node_id:
        return "n"
    out = "".join(c if c.isalnum() or c == "_" else "_" for c in str(node_id))
    return out or "n"


def spec_to_mermaid(spec: dict) -> str:
    """
    Convert a flow spec from the Visualization Agent into Mermaid flowchart TB.

    Input: dict with "timeline" (list of { "id", "label", "type" }) and "edges" (list of [from_id, to_id]).
    type is "normal" | "risk" | "high_risk". Output uses classDef for risk and high_risk styling.
    """
    if not spec:
        return "flowchart TB\n  A[No events]"
    timeline = spec.get("timeline")
    edges = spec.get("edges")
    if not timeline or not isinstance(timeline, list):
        return "flowchart TB\n  A[No events]"
    if not edges or not isinstance(edges, list):
        edges = []

    lines = ["flowchart TB"]
    risk_ids = []
    high_risk_ids = []
    id_map = {}  # original id -> sanitized id

    for node in timeline:
        if not isinstance(node, dict):
            continue
        orig_id = node.get("id") or "n"
        nid = _sanitize_id(orig_id)
        id_map[str(orig_id)] = nid
        label = _escape_label(node.get("label") or "Event")
        node_type = (node.get("type") or "normal").lower()
        lines.append(f'  {nid}["{label}"]')
        if node_type == "high_risk":
            high_risk_ids.append(nid)
        elif node_type == "risk":
            risk_ids.append(nid)

    for pair in edges:
        if isinstance(pair, (list, tuple)) and len(pair) >= 2:
            a = id_map.get(str(pair[0]), _sanitize_id(str(pair[0])))
            b = id_map.get(str(pair[1]), _sanitize_id(str(pair[1])))
            lines.append(f"  {a} --> {b}")

    if risk_ids:
        lines.append("  classDef risk fill:#fff9c4,stroke:#f9a825,stroke-width:2px")
        lines.append("  class " + ",".join(risk_ids) + " risk")
    if high_risk_ids:
        lines.append("  classDef high_risk fill:#ffcdd2,stroke:#c62828,stroke-width:2px")
        lines.append("  class " + ",".join(high_risk_ids) + " high_risk")

    return "\n".join(lines)
