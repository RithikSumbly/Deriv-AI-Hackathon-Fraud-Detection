"""
Timeline Builder — Reconstruct an investigation timeline from unordered account events.

Input: Unordered events (logins, deposits, withdrawals, KYC attempts).
Output: Chronological timeline, highlighted suspicious sequences, human-readable narrative.

Rules: Do not add new facts. Use only the events provided.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

# -----------------------------------------------------------------------------
# Event schema and sorting
# -----------------------------------------------------------------------------

# Expected event keys: timestamp (ISO or YYYY-MM-DD HH:MM:SS), event_type, and optional details
EVENT_TYPES = ("login", "deposit", "withdrawal", "kyc_attempt", "kyc_completed", "logout", "password_change")


def _parse_ts(ev: dict) -> datetime:
    ts = ev.get("timestamp") or ev.get("ts") or ""
    if isinstance(ts, datetime):
        return ts
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(ts[:19].replace("Z", ""), fmt)
        except (ValueError, TypeError):
            continue
    return datetime.min


def build_chronological_timeline(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort events by timestamp ascending. Each event gets an index for reference."""
    out = []
    for i, ev in enumerate(sorted(events, key=_parse_ts)):
        e = dict(ev)
        e["_index"] = i + 1
        e["_parsed_ts"] = _parse_ts(ev)
        out.append(e)
    return out


# -----------------------------------------------------------------------------
# Suspicious sequence detection (rule-based; no new facts)
# -----------------------------------------------------------------------------


def _tag_suspicious_sequences(ordered: list[dict]) -> list[dict]:
    """
    Mark events that are part of suspicious patterns. Tags are added to events; no new facts.
    Patterns: rapid deposit-withdrawal, login then immediate deposit, KYC after large withdrawal, etc.
    """
    for i, ev in enumerate(ordered):
        ev = ev  # ref
        tags = list(ev.get("_suspicious_tags", []) or [])

        ts = _parse_ts(ev)
        etype = (ev.get("event_type") or "").lower()
        amount = ev.get("amount") or ev.get("value") or 0
        if isinstance(amount, str):
            try:
                amount = float(amount.replace(",", ""))
            except ValueError:
                amount = 0

        # Login then deposit within 1 "slot" (next event) — possible takeover or scripted
        if i + 1 < len(ordered):
            next_ev = ordered[i + 1]
            next_ts = _parse_ts(next_ev)
            next_type = (next_ev.get("event_type") or "").lower()
            delta_min = (next_ts - ts).total_seconds() / 60.0
            if etype == "login" and next_type == "deposit" and delta_min < 30:
                tags.append("login_immediately_followed_by_deposit")
            if etype == "deposit" and next_type == "withdrawal" and delta_min < 60:
                tags.append("deposit_immediately_followed_by_withdrawal")

        # Large deposit or withdrawal
        if etype == "deposit" and amount > 10000:
            tags.append("large_deposit")
        if etype == "withdrawal" and amount > 10000:
            tags.append("large_withdrawal")

        # KYC attempt after withdrawal (possible layering / identity delay)
        if etype == "kyc_attempt":
            prev_types = [ordered[j].get("event_type", "").lower() for j in range(i) if j >= 0]
            if "withdrawal" in prev_types[-5:]:
                tags.append("kyc_attempt_after_recent_withdrawal")

        # Many logins in short span (check last 5 events)
        if etype == "login":
            recent = [ordered[j] for j in range(max(0, i - 4), i + 1)]
            logins = sum(1 for r in recent if (r.get("event_type") or "").lower() == "login")
            if logins >= 3:
                tags.append("multiple_logins_in_short_period")

        if tags:
            ev["_suspicious_tags"] = tags
    return ordered


# -----------------------------------------------------------------------------
# Human-readable output (template or LLM)
# -----------------------------------------------------------------------------

TIMELINE_USER_PROMPT = """You are reconstructing an investigation timeline. Use ONLY the events and tags below. Do not add new facts or events.

**Chronological events** (each line = one event; [SUSPICIOUS: reason] if tagged):
{events_block}

**Task:** Produce a short, human-readable timeline narrative (bullet or numbered list). For each event, include time and what happened. Clearly mark any line that is part of a suspicious sequence with "[SUSPICIOUS: <reason>]". Keep it readable for investigators. Do not invent or assume anything not in the list."""


def _events_to_block(ordered: list[dict]) -> str:
    lines = []
    for ev in ordered:
        ts = ev.get("timestamp") or ev.get("ts") or "?"
        etype = ev.get("event_type") or "?"
        extra = ev.get("details") or ev.get("note") or ""
        if ev.get("amount") is not None:
            extra = f" amount={ev.get('amount')}" + (" " + extra if extra else "")
        tags = ev.get("_suspicious_tags") or []
        tag_str = " [SUSPICIOUS: " + "; ".join(tags) + "]" if tags else ""
        lines.append(f"  {ts} | {etype} | {extra}{tag_str}")
    return "\n".join(lines)


def _call_llm_timeline(prompt: str, system: str) -> str | None:
    from .llm_client import call_llm
    return call_llm(system, prompt, temperature=0.2)


def _template_timeline(ordered: list[dict]) -> str:
    """Human-readable timeline from events only; no new facts."""
    lines = ["**Chronological timeline**", ""]
    for ev in ordered:
        ts = ev.get("timestamp") or ev.get("ts") or "?"
        etype = (ev.get("event_type") or "?").lower().replace("_", " ")
        amount = ev.get("amount")
        part = f"- **{ts}** — {etype}"
        if amount is not None:
            part += f" (amount: {amount})"
        tags = ev.get("_suspicious_tags") or []
        if tags:
            part += f"  \n  → *Suspicious: {', '.join(tags)}*"
        lines.append(part)
    lines.append("")
    lines.append("*Timeline built from provided events only. No new facts added.*")
    return "\n".join(lines)


from pathlib import Path
_PROMPTS_JSON = Path(__file__).resolve().parent.parent / "prompts" / "prompts.json"

def _load_system_prompt():
    if _PROMPTS_JSON.exists():
        try:
            with open(_PROMPTS_JSON) as f:
                return json.load(f).get("timeline_builder_system") or _DEFAULT_SYSTEM_PROMPT_TIMELINE
        except Exception:
            pass
    return _DEFAULT_SYSTEM_PROMPT_TIMELINE

_DEFAULT_SYSTEM_PROMPT_TIMELINE = """You are reconstructing an investigation timeline for financial crime review.

Rules:
- Use ONLY the events and tags provided. Do not add new facts, events, or interpretations beyond what is in the list.
- Output a clear, chronological, human-readable timeline (bullets or numbers).
- Clearly highlight any event that is marked as suspicious, using the exact reason tag given.
- Keep it readable for human investigators. Be concise."""

SYSTEM_PROMPT_TIMELINE = _load_system_prompt()


def build_timeline(
    events: list[dict[str, Any]],
    *,
    use_llm: bool = False,
) -> dict[str, Any]:
    """
    Build a chronological investigation timeline and highlight suspicious sequences.

    Args:
        events: List of event dicts. Each should have:
            - timestamp (ISO or "YYYY-MM-DD HH:MM:SS")
            - event_type (e.g. login, deposit, withdrawal, kyc_attempt)
            - optional: amount, details, note
        use_llm: If True and OPENAI_API_KEY set, use LLM for narrative; else template.

    Returns:
        dict with:
            - chronological_events: list of events sorted by time (with _index, _suspicious_tags)
            - suspicious_sequences: list of { "event_index", "tags", "timestamp", "event_type" }
            - human_readable: string (template or LLM narrative)
    """
    ordered = build_chronological_timeline(events)
    ordered = _tag_suspicious_sequences(ordered)

    suspicious_sequences = []
    for ev in ordered:
        tags = ev.get("_suspicious_tags") or []
        if tags:
            suspicious_sequences.append({
                "event_index": ev.get("_index"),
                "timestamp": ev.get("timestamp") or ev.get("ts"),
                "event_type": ev.get("event_type"),
                "tags": tags,
            })

    if use_llm:
        events_block = _events_to_block(ordered)
        prompt = TIMELINE_USER_PROMPT.format(events_block=events_block)
        narrative = _call_llm_timeline(prompt, SYSTEM_PROMPT_TIMELINE)
        human_readable = narrative if narrative else "Set OPENAI_API_KEY (or OPENAI_BASE_URL) to generate narrative timeline. No preset content."
    else:
        human_readable = _template_timeline(ordered)

    # Strip internal keys for JSON-friendly output if needed
    out_events = []
    for ev in ordered:
        e = {k: v for k, v in ev.items() if not k.startswith("_")}
        e["_index"] = ev.get("_index")
        e["_suspicious_tags"] = ev.get("_suspicious_tags")
        out_events.append(e)

    return {
        "chronological_events": out_events,
        "suspicious_sequences": suspicious_sequences,
        "human_readable": human_readable,
    }


# -----------------------------------------------------------------------------
# Example
# -----------------------------------------------------------------------------

EXAMPLE_EVENTS = [
    {"timestamp": "2025-01-15 14:22:00", "event_type": "login", "details": "IP 192.168.1.1"},
    {"timestamp": "2025-01-15 14:23:12", "event_type": "deposit", "amount": 5000},
    {"timestamp": "2025-01-15 14:45:00", "event_type": "withdrawal", "amount": 4800},
    {"timestamp": "2025-01-16 09:00:00", "event_type": "login"},
    {"timestamp": "2025-01-16 09:15:00", "event_type": "deposit", "amount": 15000},
    {"timestamp": "2025-01-16 10:00:00", "event_type": "kyc_attempt", "details": "document upload"},
]


if __name__ == "__main__":
    import sys
    result = build_timeline(EXAMPLE_EVENTS, use_llm=("llm" in sys.argv))
    print(result["human_readable"])
    print("\n--- Suspicious sequences ---")
    for s in result["suspicious_sequences"]:
        print(f"  Event #{s['event_index']} ({s['timestamp']}): {s['tags']}")
    if "llm" not in sys.argv:
        print("\n(Template output; set OPENAI_API_KEY and run with 'llm' for LLM narrative.)")
