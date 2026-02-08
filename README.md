# AI-Powered Client Fraud Detection & Investigation

**Human-in-the-loop fraud investigation platform** with multi-signal detection, explainable alerts, LLM-assisted case view, and continuous learning from investigator decisions.

---

## What’s important

| Area | What’s in place |
|------|------------------|
| **Detection** | Fraud classifier + anomaly detector; multi-signal (identity, transaction, geo, device/IP). |
| **Explainability** | “Why this account was flagged”, risk factors, confidence, risk level; 30s investigation summary. |
| **Investigation** | Case view, timeline (rule-based + AI flow), evidence tabs (Transactions, Geo, Identity, Network, Similar Cases), device/IP graph, recommended next steps (LLM). |
| **Decisions & audit** | Confirm Fraud / Mark Legit / Dismiss as false positive with **required reason**; every decision stored with snapshot and model version. |
| **Learning** | Similarity to “N confirmed fraud cases”; outcome-informed sort; knowledge capture on case close; feedback export for retrain. |
| **Reports** | Regulatory-style investigation report (LLM); 4-section structure. |

**Judge-safe one-liner:** *"We built a system where investigator decisions are first-class signals. Feedback, similarity matching, and retraining plug in without changing the investigation workflow."*

---

## Failure modes & safeguards

- **If an LLM agent fails:** The pipeline degrades gracefully. Each Evidence tab shows a warning for the failed agent and still displays model-only metrics (fraud probability, anomaly score, risk level, one-line explanation, risk factors). Other tabs and the Orchestrator can still run with partial specialist outputs.
- **If no API key:** The system falls back to model-only and template explanations. Alert explanation, report writer, next-step advisor, and timeline builder use template fallbacks so demos work without an LLM. The UI shows model scores and risk factors from the classifier and anomaly detector.
- **If signals conflict:** The Orchestrator is instructed to use cautious, regulator-safe language and not to treat any single signal as proof of fraud. Optional: the orchestrator prompt can be extended to explicitly require stating when specialist findings conflict (e.g. in key_drivers or investigation_summary).
- **Auto-resolve is conservative and reversible with audit log:** Only a suggestion is shown (“Consider dismissing as false positive?”) when pattern matches historical legitimate behavior; the investigator must click “Dismiss as false positive” and provide a **required** reason. Every decision (Confirm Fraud, Mark Legit, Dismiss as false positive) is stored in `backend/data/investigator_feedback.json` with account_id, decision, reason, timestamp, investigator_id, and model_version for audit. A **Reopen case** button moves a closed case (False Positive, Marked Legit, or Confirmed Fraud) back to Under Review; the reopen action is logged in the same feedback file for audit.

---

## Feature importance (detection signals)

The fraud classifier and anomaly detector use **13 features** per account. These drive both the score and the "why this account was flagged" explanations:

| Feature | Meaning | Fraud signal |
|--------|--------|---------------|
| `deposits_vs_income_ratio` | 90d deposits / (annual income ÷ 4) | High → income mismatch → fraud |
| `deposit_withdraw_cycle_days_avg` | Avg days between deposit and withdrawal | Low (fast cycle) → fraud |
| `vpn_usage_pct` | % of sessions over VPN | High → fraud |
| `device_shared_count` | # accounts sharing same device_id | High → fraud ring |
| `ip_shared_count` | # accounts sharing same ip_hash | High → fraud ring |
| `kyc_face_match_score` | KYC face match 0–1 | Low → fraud |
| `countries_accessed_count` | # distinct countries | High → fraud |
| `account_age_days` | Days since signup | Often lower for fraud |
| Others | Declared income, deposit/withdrawal amounts and counts | Supporting signals |

---

## Risk score and anomaly score

**Risk score (in the UI)**  
The case header **"Risk score"** is the **fraud probability** from the classifier, shown as a percentage (0–100%). For example, "Risk score 13%" means the classifier estimates a 13% likelihood of fraud based on patterns seen in training data.

**Fraud probability**  
- **Model:** LightGBM binary classifier on the 13 features (see table above).  
- **Output:** Probability of fraud per account (0–1). Trained on labeled fraud/legit; an F1-optimal decision threshold is stored in `backend/models/config.json`.  
- **Meaning:** "Looks like known fraud" — the model has seen similar patterns in training.  
- **Details:** See `backend/models/FEATURE_IMPORTANCE.md`.
- This score alone does not determine case outcomes; it is one input into investigator prioritisation and review.

**Anomaly score**  
- **Model:** Isolation Forest (unsupervised) on the same 13 features. Features are scaled with a StandardScaler fitted on legit-only data.  
- **Output:** Score 0–1 (bounds in `config.json`). High = more unusual relative to normal (legit) behavior.  
- **Meaning:** "Doesn’t look like normal" — can flag novel or rare patterns the classifier was not trained on.  
- **Details:** See `backend/models/ANOMALY_DETECTION_README.md`.
- High anomaly does not imply fraud by itself; it indicates deviation from historical norms and is reviewed in context.
- Anomaly detection helps surface emerging fraud patterns that the supervised classifier has not yet been trained on, reducing blind spots.

**Risk level (High / Medium / Low)**  
Used for sorting and display. It combines both scores:

- **Composite** = 0.5 × fraud_probability + 0.5 × anomaly_score  
- **High** if composite ≥ 0.5  
- **Medium** if composite ≥ 0.3  
- **Low** otherwise  

So a high anomaly score can raise the risk level even when fraud probability is moderate, and both scores feed into prioritisation in the dashboard. Risk level is used for **triage and ordering**, not automated enforcement.

---

## Quick start

```bash
# Clone and enter project
cd "deriv AI hackathon"

# Python 3.10+; create venv and install
pip install -r requirements.txt
pip install -r frontend/requirements-streamlit.txt

# Copy env and set at least one LLM key (Gemini or OpenAI)
cp .env.example .env
# Edit .env: GOOGLE_API_KEY=... or OPENAI_API_KEY=...

# Run dashboard (from project root)
streamlit run frontend/app.py
```

Open **http://localhost:8501** (or the URL Streamlit prints). Select a case in the sidebar, then **Run investigation agents** to run the full pipeline and see the 30s summary, key drivers, and Evidence tabs.

---

## Project structure

```
deriv AI hackathon/
├── frontend/
│   ├── app.py                    # Streamlit dashboard (main UI)
│   ├── requirements-streamlit.txt
│   └── logos/                     # Sidebar logo
├── backend/
│   ├── agents/                   # Multi-agent pipeline (LLM)
│   │   ├── runner.py             # run_pipeline, run_knowledge_capture, run_visualization_agent
│   │   ├── prompts.py            # AGENTS, ORDER_*, system prompts & output schemas
│   │   ├── AGENTS_ARCHITECTURE.md
│   │   └── MAPPING.md
│   ├── explainability/           # Alert explanation, timeline, next steps, report
│   │   ├── llm_client.py         # Single LLM entrypoint (Gemini/OpenAI)
│   │   ├── alert_explanation.py
│   │   ├── timeline_builder.py
│   │   ├── next_step_advisor.py
│   │   ├── report_writer.py
│   │   └── visualization_tool.py # Mermaid spec from visualization agent
│   ├── services/
│   │   ├── alerts.py             # get_alerts() — anomaly_scores.csv / mock
│   │   └── feedback.py           # add_decision, add_knowledge_pattern, get_similar_confirmed_count
│   ├── models/                   # anomaly_detector.joblib, fraud_classifier, config
│   ├── data/                     # anomaly_scores.csv, investigator_feedback.json, etc.
│   └── scripts/                  # train_*, feedback_retrain.py, generate_*, run_unlabeled_pipeline
├── scripts/                      # e.g. generate_slides.py
├── .env.example
├── IMPLEMENTATION_STATUS.md      # Demo checklist & judge one-liner
├── WHATS_LEFT.md                 # Optional/stretch vs brief
└── SUBMISSION_TEXT.md            # Hackathon submission copy
```

---

## Agent pipelines and structure

### High-level flow

Only the **Orchestrator** talks to the UI; **specialists** run in sequence and their outputs are merged into one summary, key drivers, and 30s investigation summary.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Alert (from get_alerts) → run_pipeline(alert, "alert_creation")         │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
    ┌─────────────────────────────────┼─────────────────────────────────┐
    ▼                                 ▼                                 ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌─────────────────────┐
│ Transaction   │  │ Identity      │  │ Geo / VPN     │  │ Network       │  │ Outcome Similarity   │
│ (behavior)   │→ │ (KYC, face)   │→ │ (countries,   │→ │ (device/IP    │→ │ (similar confirmed  │
│               │  │               │  │  VPN)         │  │  shared)      │  │  cases count)        │
└───────────────┘  └───────────────┘  └───────────────┘  └───────────────┘  └─────────────────────┘
                                                                                      │
                                                                                      ▼
                                                                            ┌─────────────────────┐
                                                                            │ Orchestrator        │
                                                                            │ (Senior Investigator)│
                                                                            │ → risk_level,        │
                                                                            │   key_drivers,       │
                                                                            │   investigation_    │
                                                                            │   summary (30s)      │
                                                                            └─────────────────────┘
```

- **On “Run investigation agents” (first time for a case):** run **alert_creation** → all 5 specialists in order, then Orchestrator. Results cached per `account_id`.
- **On later case open:** use cached specialists and run only **Orchestrator** (mode **case_open**).

### Agent registry (order and roles)

| Order | Agent ID | Role | Main outputs |
|-------|----------|------|--------------|
| 1 | `transaction` | Transaction/behavior | `anomaly_score`, `detected_patterns`, `short_explanation` |
| 2 | `identity` | Identity risk | `identity_risk`, `indicators`, `explanation` |
| 3 | `geo` | Geo/VPN | `geo_risk`, `indicators`, `explanation` |
| 4 | `network` | Network/cluster | `cluster_size`, `known_fraud_links`, `shared_signals`, `explanation` |
| 5 | `outcome_similarity` | Similarity to past outcomes | `fraud_likelihood`, `similar_confirmed_cases_count`, `explanation` |
| 6 | `orchestrator` | Senior investigator (UI-facing) | `risk_level`, `confidence`, `key_drivers`, `priority`, `investigation_summary` |

**On case close** (Confirm Fraud / Mark Legit / Dismiss as false positive):

| Agent ID | When | Main outputs |
|----------|------|--------------|
| `knowledge_capture` | After investigator decision | `key_signals`, `behavioral_pattern`, `final_outcome`, `one_sentence_description` → stored in feedback |

**Timeline flow (optional):**

| Agent ID | When | Main outputs |
|----------|------|--------------|
| `visualization` | On “Build timeline flow” | `timeline` (nodes), `edges` → converted to Mermaid via `visualization_tool.spec_to_mermaid()` |

### Where it’s implemented

- **Runner:** `backend/agents/runner.py` — `run_pipeline(alert, "alert_creation" | "case_open")`, `run_knowledge_capture(alert, outcome, reason)`, `run_visualization_agent(events)`.
- **Prompts & order:** `backend/agents/prompts.py` — `AGENTS`, `ORDER_ON_ALERT_CREATION`, `ORDER_ON_CASE_OPEN`, `ORDER_ON_CASE_CLOSE`.
- **LLM:** `backend/explainability/llm_client.py` — single entrypoint used by runner and explainability modules (Gemini or OpenAI via `.env`).

---

## Backend in short

- **agents:** Multi-agent pipeline; specialists → orchestrator; knowledge capture on close; visualization agent for timeline.
- **explainability:** Alert explanation, timeline builder, next-step advisor, report writer, Mermaid visualization tool; all use `llm_client`.
- **services:** `alerts.get_alerts()` (CSV or mock); `feedback.add_decision`, `add_knowledge_pattern`, `get_similar_confirmed_count` (audit + similarity).
- **data:** `anomaly_scores.csv`, `investigator_feedback.json`, optional synthetic/unlabeled datasets.
- **models:** Anomaly detector and fraud classifier used to score alerts; see `backend/models/*.md` and `backend/scripts/train_*.py`.

---

## Frontend (dashboard)

- **Layout:** Hero title | left sidebar (cases, filter/sort, select case) | main area (case summary, actions, case details, “Why flagged”, 30s summary, Evidence tabs, Timeline, Next steps, Report).
- **Entry:** `frontend/app.py`; run with `streamlit run frontend/app.py` from project root.
- **Actions:** Confirm Fraud, Mark Legit, Request More Info, Dismiss as false positive (with required reason), Next case, Run investigation agents, Run investigation to see summary (when no 30s summary yet).

---

## Data and continuous learning

- **Alerts:** From `backend/data/anomaly_scores.csv` (or mock); 13 feature columns + `fraud_probability`, `anomaly_score`, `risk_level`, `one_line_explanation`, etc.
- **Feedback:** Each decision → `backend/data/investigator_feedback.json` (account_id, decision, reason, timestamp, investigator_id, model_version, snapshot, optional feature_vector and knowledge pattern).
- **Retrain:** `python backend/scripts/feedback_retrain.py` exports feedback for periodic retraining; merge with synthetic data and run `train_fraud_classifier.py` (or equivalent).

---

## Docs and references

| Doc | Purpose |
|-----|---------|
| **IMPLEMENTATION_STATUS.md** | Demo checklist, judge one-liner, what’s implemented vs designed. |
| **WHATS_LEFT.md** | Done (outcome sort, knowledge capture, 30s summary) vs still optional / stretch. |
| **SUBMISSION_TEXT.md** | Hackathon submission title, short and long description. |
| **backend/agents/AGENTS_ARCHITECTURE.md** | How agents are called, input building, pipeline modes. |
| **backend/agents/MAPPING.md** | Mapping of brief to agents and UI. |
| **backend/explainability/README.md** | Explainability modules. |
| **backend/models/*.md** | Anomaly and classifier notes. |

---

## Environment (.env)

Copy `.env.example` to `.env`. Important:

- **LLM:** Set `GOOGLE_API_KEY` (Gemini) or `OPENAI_API_KEY` (OpenAI). Optional: `GOOGLE_MODEL`, `OPENAI_MODEL`, `OPENAI_BASE_URL`.
- **Optional:** `AGENT_CALL_DELAY_SECONDS` (e.g. 6) to pace agent calls; `INVESTIGATOR_ID`, `FRAUD_MODEL_VERSION` for audit trail.

See `.env.example` for full list.
