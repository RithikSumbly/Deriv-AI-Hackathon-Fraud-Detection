"""
Investigation Report Writer — Auto-documentation for compliance and regulators.

Given case summary, evidence points, and investigator conclusion, produce a formal
internal fraud investigation report with: Executive summary, Evidence reviewed,
Findings, Conclusion.

Tone: Formal, neutral, audit-ready. Use only the inputs; do not add new facts.
"""
from __future__ import annotations

import json
import os
from typing import Any

# -----------------------------------------------------------------------------
# Prompt
# -----------------------------------------------------------------------------

from pathlib import Path
_PROMPTS_JSON = Path(__file__).resolve().parent.parent / "prompts" / "prompts.json"

def _load_system_prompt():
    if _PROMPTS_JSON.exists():
        try:
            with open(_PROMPTS_JSON) as f:
                return json.load(f).get("report_writer_system") or _DEFAULT_SYSTEM_PROMPT
        except Exception:
            pass
    return _DEFAULT_SYSTEM_PROMPT

_DEFAULT_SYSTEM_PROMPT = """You are writing an internal fraud investigation report for the compliance team and regulators.

Rules:
- Audience: Compliance team and regulators. Write in a formal, neutral, audit-ready tone.
- Use ONLY the case summary, evidence points, and investigator conclusion provided. Do not add facts, inferences, or details not in the inputs.
- Structure the report with the exact section headings requested.
- No speculation. No informal language. Present the investigator's conclusion as stated."""

SYSTEM_PROMPT = _load_system_prompt()

USER_PROMPT_TEMPLATE = """Write an internal fraud investigation report using ONLY the following inputs. Do not add new facts.

**Case summary:**
{case_summary}

**Evidence points:**
{evidence_block}

**Investigator conclusion:**
{investigator_conclusion}

**Required output:** A report with exactly these four sections. Use formal, neutral language. Output valid JSON only, no other text:

{{
  "executive_summary": "2–4 sentences. High-level summary of the case and outcome for leadership and compliance.",
  "evidence_reviewed": "Bulleted or numbered list of the evidence that was reviewed, drawn only from the evidence points above.",
  "findings": "Structured summary of findings based on the evidence. Do not add conclusions here; state what was observed or verified.",
  "conclusion": "The investigator conclusion, stated formally and neutrally. Use the investigator conclusion provided above; do not rephrase beyond making it audit-appropriate."
}}"""


def _format_evidence(evidence_points: list[str] | list[dict]) -> str:
    if not evidence_points:
        return "(none provided)"
    lines = []
    for i, e in enumerate(evidence_points, 1):
        if isinstance(e, dict):
            lines.append(f"  {i}. {e.get('point', e.get('description', str(e)))}")
        else:
            lines.append(f"  {i}. {e}")
    return "\n".join(lines)


def _call_llm(prompt: str, system: str) -> str | None:
    from .llm_client import call_llm
    return call_llm(system, prompt, temperature=0.2)


def _template_report(
    case_summary: str,
    evidence_points: list[Any],
    investigator_conclusion: str,
) -> dict[str, str]:
    """Build report sections from inputs only. Formal, neutral, no new facts."""
    evidence_block = _format_evidence(evidence_points)
    exec_summary = (
        f"This report documents the investigation into the matter summarised below. "
        f"The evidence reviewed is set out in the following section; findings and the investigator conclusion are stated without addition of external facts. "
        f"Conclusion: {investigator_conclusion[:200]}{'...' if len(investigator_conclusion) > 200 else ''}"
    )
    evidence_reviewed = (
        "The following evidence was reviewed in the course of this investigation:\n\n" + evidence_block
    )
    findings = (
        "Findings are based solely on the evidence listed above. "
        "No further facts or inferences have been introduced. "
        "The investigator has assessed the evidence and reached the conclusion set out in the Conclusion section."
    )
    conclusion = (
        f"Investigator conclusion (stated formally for audit purposes): {investigator_conclusion}"
    )
    return {
        "executive_summary": exec_summary,
        "evidence_reviewed": evidence_reviewed,
        "findings": findings,
        "conclusion": conclusion,
    }


def write_investigation_report(
    case_summary: str,
    evidence_points: list[str] | list[dict[str, Any]],
    investigator_conclusion: str,
    *,
    use_llm: bool = True,
) -> dict[str, str]:
    """
    Produce an internal fraud investigation report for compliance and regulators.

    Args:
        case_summary: Brief description of the case.
        evidence_points: List of evidence items (strings or dicts with 'point' or 'description').
        investigator_conclusion: The investigator's conclusion as stated (will be used in Conclusion section).
        use_llm: If True and OPENAI_API_KEY set, use LLM; else use template.

    Returns:
        dict with keys: executive_summary, evidence_reviewed, findings, conclusion.
    """
    evidence_block = _format_evidence(evidence_points)
    prompt = USER_PROMPT_TEMPLATE.format(
        case_summary=case_summary or "(none provided)",
        evidence_block=evidence_block,
        investigator_conclusion=investigator_conclusion or "(none provided)",
    )

    if use_llm:
        raw = _call_llm(prompt, SYSTEM_PROMPT)
        if raw:
            text = raw.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            try:
                out = json.loads(text)
                required = ("executive_summary", "evidence_reviewed", "findings", "conclusion")
                if all(k in out for k in required):
                    return {k: str(out[k]) for k in required}
            except json.JSONDecodeError:
                pass
        # LLM required; no preset content
        msg = "Set OPENAI_API_KEY (or OPENAI_BASE_URL) to generate this report."
        return {
            "executive_summary": msg,
            "evidence_reviewed": msg,
            "findings": msg,
            "conclusion": msg,
        }

    return _template_report(case_summary, evidence_points, investigator_conclusion)


def report_to_markdown(report: dict[str, str]) -> str:
    """Turn the report dict into a single markdown document (audit-ready)."""
    return """# Internal Fraud Investigation Report

## Executive Summary
{executive_summary}

## Evidence Reviewed
{evidence_reviewed}

## Findings
{findings}

## Conclusion
{conclusion}

---
*Report generated for compliance and regulatory purposes. Based on case summary, evidence points, and investigator conclusion provided. No new facts added.*
""".format(**report)


# -----------------------------------------------------------------------------
# Regulatory-ready investigation report (single markdown, 4 H2 sections)
# -----------------------------------------------------------------------------

REGULATORY_REPORT_SYSTEM = """You are a Senior Financial Crime Investigator and Compliance Auditor. Your task is to generate a formal, regulatory-ready investigation report based ONLY on the provided case data.

**Tone Guidelines:**
* Professional, objective, and factual.
* Do not use conversational language (no "I think" or "We found").
* Use active voice where possible (e.g., "Analysis revealed..." instead of "It was revealed by analysis...").
* Do not hallucinate facts. If evidence is missing, state that it is missing.

**Required Output Structure:**
You must generate a report using Markdown formatting with exactly these four H2 headers:

## 1. Executive Summary
* A concise (3-5 sentences) overview of the investigation. State the subject (user/account ID), the trigger event (why it was flagged), the final determination (e.g., Confirmed Fraud, Suspicious Activity, or False Positive), and the primary reason for that determination.

## 2. Evidence Reviewed
* A bulleted list of the specific data points, documents, and systems reviewed during this investigation. (e.g., "Transaction logs dated [Date range]", "Identity document [Type]", "Device fingerprint analysis logs", "Linked account network graph").

## 3. Findings
* A detailed narrative connecting the evidence to the suspicious activity. Use paragraphs to explain the patterns.
* Must include: reference specific high-risk transactions (amounts, dates); explain connections to other flagged accounts (network analysis); highlight anomalies in behavior (e.g., IP inconsistencies, velocity); mention any failed verification checks.

## 4. Conclusion & Recommendations
* The final verdict and actionable next steps.
* Must include: clear statement of risk level (High/Medium/Low); final action taken or recommended (e.g., "Account closure recommended," "Elevate to SAR filing team," "Mark as benign").
Output only the markdown report. Do not wrap in code blocks or add text before or after the report."""

REGULATORY_REPORT_USER_TEMPLATE = """**Input Case Data:**
---BEGIN DATA---
{case_context_data}
---END DATA---

Generate the investigation report using the required structure. Use only the data above; state when evidence is missing."""


def generate_regulatory_report(case_context_data: str, *, use_llm: bool = True) -> str:
    """
    Generate a structured, regulatory-ready investigation report in Markdown.

    Args:
        case_context_data: Full case context as a single text block (account, scores, evidence, timeline, etc.).
        use_llm: If True and OPENAI_API_KEY (or OPENAI_BASE_URL) set, use LLM; else return template fallback.

    Returns:
        Markdown string with exactly four H2 sections: Executive Summary, Evidence Reviewed, Findings, Conclusion & Recommendations.
    """
    prompt = REGULATORY_REPORT_USER_TEMPLATE.format(case_context_data=case_context_data or "(No case data provided.)")
    if use_llm:
        raw = _call_llm(prompt, REGULATORY_REPORT_SYSTEM)
        if raw:
            text = raw.strip()
            # Remove surrounding code blocks if present
            if text.startswith("```"):
                lines = text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines)
            if "## 1. Executive Summary" in text or "## 1. Executive summary" in text:
                return text
        # LLM required; no preset content
        return _llm_required_report_message()
    return _regulatory_report_fallback(case_context_data)


def _llm_required_report_message() -> str:
    """When use_llm=True but LLM is unavailable; no preset content."""
    return """# Investigation Report

## 1. Executive Summary
Set OPENAI_API_KEY (or OPENAI_BASE_URL) to generate this report. No preset content is returned.

## 2. Evidence Reviewed
LLM is required for report generation.

## 3. Findings
LLM is required for report generation.

## 4. Conclusion & Recommendations
LLM is required for report generation.
"""


def _regulatory_report_fallback(case_context_data: str) -> str:
    """Template fallback only when use_llm=False (e.g. CLI)."""
    return _llm_required_report_message()


# -----------------------------------------------------------------------------
# Example / CLI
# -----------------------------------------------------------------------------

EXAMPLE_INPUT = {
    "case_summary": "Account flagged for elevated fraud probability and anomaly score. Review focused on deposit-to-income consistency, device/IP sharing, and transaction timeline.",
    "evidence_points": [
        "Fraud probability score 0.72; anomaly score 0.89.",
        "Deposits in 90d significantly exceed declared annual income (ratio 4.2x quarterly equivalent).",
        "VPN usage 82% of sessions; KYC face match score 0.62.",
        "Device shared with 8 other accounts; same device as one confirmed fraud case.",
        "Rapid deposit-withdrawal cycles (avg 3.1 days). Timeline reviewed; no additional red flags.",
    ],
    "investigator_conclusion": "Evidence supports escalation to SAR. No final determination of fraud; recommend filing and continued monitoring.",
}


if __name__ == "__main__":
    import sys
    use_llm = "llm" in sys.argv
    inp = EXAMPLE_INPUT
    report = write_investigation_report(
        inp["case_summary"],
        inp["evidence_points"],
        inp["investigator_conclusion"],
        use_llm=use_llm,
    )
    print(report_to_markdown(report))
    if not use_llm:
        print("(Template report; set OPENAI_API_KEY and run with 'llm' for LLM-generated report.)")
