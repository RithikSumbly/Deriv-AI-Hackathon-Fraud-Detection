# Alert Explanation Generator (LLM = Investigator Buddy)

Act as a **senior financial crime investigator**: given model and network evidence, produce clear, evidence-based explanations for alerts.

## Inputs

- **Fraud probability score** — Model’s P(fraud).
- **Anomaly score** — How unusual the account is vs. normal (0–1).
- **Top SHAP features** — List of `{feature, value, shap_effect, direction}` (e.g. "pushes toward FRAUD").
- **Network risk indicators** — e.g. `device_shared_count`, `ip_shared_count`, `same_device_as_fraud`, `same_ip_as_fraud`, `min_path_to_fraud`.

## Outputs

1. **Concise explanation** — 2–4 sentences on why the alert was triggered, citing evidence.
2. **Key risk drivers** — Bullet list of specific risk factors and evidence.
3. **Junior analyst summary** — Plain-English: what to look at first, what the evidence suggests; no speculation.

**Tone:** Clear, evidence-based, no speculation.

## Usage

### From code

```python
from explainability import generate_alert_explanation

out = generate_alert_explanation(
    fraud_probability=0.72,
    anomaly_score=0.89,
    top_shap_drivers=[
        {"feature": "vpn_usage_pct", "value": 82.5, "shap_effect": 0.95, "direction": "pushes toward FRAUD"},
        {"feature": "deposits_vs_income_ratio", "value": 4.2, "shap_effect": 0.61, "direction": "pushes toward FRAUD"},
    ],
    network_risk_indicators={
        "device_shared_count": 8,
        "same_device_as_fraud": True,
        "min_path_to_fraud": 2,
    },
)

print(out["concise_explanation"])
print(out["key_risk_drivers"])
print(out["junior_analyst_summary"])
```

### CLI (from `backend/`)

```bash
# Template-based explanation (no API key)
python explainability/alert_explanation.py

# Use LLM (set OPENAI_API_KEY or OPENAI_BASE_URL)
python explainability/alert_explanation.py llm
```

### Environment (for LLM)

- `OPENAI_API_KEY` — API key for OpenAI or compatible endpoint.
- `OPENAI_BASE_URL` — Optional; use for local/compatible endpoints.
- `OPENAI_MODEL` — Optional; default `gpt-4o-mini`.

If no API key is set, the module returns a **template-based** explanation so demos work without an LLM.

## Timeline Builder

Reconstruct an investigation timeline from **unordered account events** (logins, deposits, withdrawals, KYC attempts).

- **Input:** List of events with `timestamp`, `event_type`, and optional `amount`, `details`.
- **Output:** Chronological timeline, suspicious sequences (rule-based tags), and a human-readable narrative. **Do not add new facts.**

```python
from explainability import build_timeline

events = [
    {"timestamp": "2025-01-15 14:22:00", "event_type": "login"},
    {"timestamp": "2025-01-15 14:23:12", "event_type": "deposit", "amount": 5000},
    {"timestamp": "2025-01-15 14:45:00", "event_type": "withdrawal", "amount": 4800},
]
result = build_timeline(events)
# result["chronological_events"], result["suspicious_sequences"], result["human_readable"]
```

CLI: `python explainability/timeline_builder.py` (add `llm` to use LLM narrative). Suspicious patterns: login→deposit within 30 min, deposit→withdrawal within 60 min, large amounts, KYC after recent withdrawal, multiple logins in short period.

---

## Next-Step Advisor (human-in-the-loop)

Given risk indicators (e.g. high deposit-to-income ratio, VPN usage, shared device network, rapid withdrawals), recommend the **top 3 next investigative actions**. Rules: do not make final decisions; do not label as fraud; focus on efficiency.

```python
from explainability import recommend_next_steps

out = recommend_next_steps([
    "High deposit-to-income ratio",
    "VPN usage",
    "Shared device network",
    "Rapid withdrawals",
])
# out["next_steps"] (list of 3 strings), out["rationale"]
```

CLI: `python explainability/next_step_advisor.py` (add `llm` for LLM suggestions).

---

## Investigation Report Writer (compliance / regulators)

Write an **internal fraud investigation report** for the compliance team and regulators.

**Input:** Case summary, evidence points (list), investigator conclusion.  
**Output sections:** Executive summary, Evidence reviewed, Findings, Conclusion.  
**Tone:** Formal, neutral, audit-ready. Use only the inputs; do not add new facts.

```python
from explainability import write_investigation_report, report_to_markdown

report = write_investigation_report(
    case_summary="Account flagged for elevated fraud probability; review focused on income consistency and device sharing.",
    evidence_points=[
        "Fraud probability 0.72; anomaly score 0.89.",
        "Deposits exceed declared income (ratio 4.2x).",
        "Device shared with 8 accounts; same device as one confirmed fraud case.",
    ],
    investigator_conclusion="Evidence supports escalation to SAR. No final determination of fraud; recommend filing and monitoring.",
)
# report["executive_summary"], report["evidence_reviewed"], report["findings"], report["conclusion"]
md = report_to_markdown(report)  # single audit-ready document
```

CLI: `python explainability/report_writer.py` (add `llm` for LLM-generated report).

---

## Files

- `explainability/alert_explanation.py` — Alert explanation (SHAP + network → narrative).
- `explainability/timeline_builder.py` — Timeline reconstruction and suspicious-sequence tags.
- `explainability/next_step_advisor.py` — Next-step investigative suggestions (no decisions, no fraud label).
- `explainability/report_writer.py` — Investigation report (executive summary, evidence, findings, conclusion) for compliance/regulators.
- `prompts/prompts.json` — All system prompts (alert_explanation_system, next_step_advisor_system, report_writer_system, timeline_builder_system).
