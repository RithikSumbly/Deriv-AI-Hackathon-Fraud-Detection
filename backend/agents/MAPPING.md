# Mapping: Agents → Streamlit Components

How the multi-agent design maps to the real UI and when each agent runs.

## Main layout

```
┌──────────────────────────────┐
│ Fraud Alert Queue            │
│ (Outcome-informed priority)  │
└──────────────┬───────────────┘
               │ click alert
┌──────────────▼───────────────┐
│ Investigation Dashboard       │
│ ──────────────────────────── │
│ Orchestrator Summary          │
│ Key Drivers                   │
│ Confidence + Priority         │
│ [30s Copilot Summary]         │
│                               │
│ Tabs:                          │
│  - Transactions                │
│  - Identity                    │
│  - Geo / VPN                   │
│  - Network                     │
│  - Similar Cases                │
│                               │
│ Actions:                       │
│ [Confirm Fraud]                │
│ [Mark Legit]                   │
│ [Dismiss as False Positive]    │
└──────────────────────────────┘
```

## Component ↔ Agent mapping

| UI Component | Agent |
|--------------|--------|
| Alert queue sorting | Outcome Learning Agent |
| Risk explanation (summary, drivers, confidence, priority) | Orchestrator |
| Transaction tab | Behavior Agent |
| Identity tab | Identity Agent |
| Geo tab | Geo/VPN Agent |
| Network tab | Network Agent |
| “Similar cases” line | Outcome + Knowledge |
| Case close buttons (Confirm Fraud / Mark Legit / Dismiss) | Knowledge Capture |

## Agent execution order

Execution order matters for latency and believability.

### On alert creation

Run once when an alert is created (or when we first load it for the queue):

1. **Behavior Agent** — transaction/behavior analysis
2. **Identity Agent** — identity verification risk
3. **Geo/VPN Agent** — geographic and VPN risk
4. **Network Agent** — shared devices/IPs (can be cached / precomputed)
5. **Outcome Similarity Agent** — similarity to historical outcomes
6. **Orchestrator Agent** — merge specialist outputs → summary, key drivers, confidence, priority

### On case open

When the user clicks an alert and opens the investigation dashboard:

- **Re-run Orchestrator only** (fast path using cached specialist outputs).

### On case close

When the user clicks **Confirm Fraud**, **Mark Legit**, or **Dismiss as False Positive**:

1. **Knowledge Capture Agent** — summarize investigation into a reusable pattern (key signals, behavioral pattern, final outcome, one-sentence description).
2. **Store outcome** — persist decision + pattern (e.g. in investigator_feedback and a knowledge store).
3. **Update similarity index** — so future alerts can use “similar cases” and outcome-informed priority.

This keeps the system feeling alive: new outcomes feed back into sorting and similarity.
