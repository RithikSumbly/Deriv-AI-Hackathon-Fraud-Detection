"""Mermaid timeline and HTML helpers for Timeline tab and report."""


def mermaid_timeline(events: list[dict]) -> str:
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


def mermaid_html(mermaid_code: str) -> str:
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


def escape_html(s: str) -> str:
    """Escape HTML special characters for safe display."""
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
