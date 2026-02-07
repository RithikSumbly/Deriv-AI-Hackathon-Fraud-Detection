"""
Multi-agent fraud investigation platform.

- Orchestrator (senior investigator): only agent that talks to the UI; merges specialist findings.
- Specialists: Transaction, Identity, Geo/VPN, Network, Outcome Similarity, Knowledge Capture.

Prompts and output schemas: backend.agents.prompts (AGENTS dict).
See README.md for architecture and mapping.
"""
from .prompts import (
    AGENTS,
    ORDER_ON_ALERT_CREATION,
    ORDER_ON_CASE_OPEN,
    ORDER_ON_CASE_CLOSE,
)
from .runner import run_pipeline, run_knowledge_capture, run_visualization_agent

__all__ = [
    "AGENTS",
    "ORDER_ON_ALERT_CREATION",
    "ORDER_ON_CASE_OPEN",
    "ORDER_ON_CASE_CLOSE",
    "run_pipeline",
    "run_knowledge_capture",
    "run_visualization_agent",
]
