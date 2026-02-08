# Product features — Fraud Investigation Dashboard

A single reference of all features in this product, derived from the codebase and docs. 

---

## 1. Detection (models)

| Feature | Description | Where |
|--------|-------------|--------|
| **Fraud classifier** | LightGBM binary classifier on 13 features; outputs fraud probability (0–1). Trained on labeled fraud/legit; F1-optimal threshold in `backend/models/config.json`. | `backend/models/`, `backend/scripts/train_fraud_classifier.py` |
| **Anomaly detector** | Isolation Forest on same 13 features; scaled with StandardScaler on legit-only data. Score 0–1; high = more unusual vs normal. | `backend/models/`, `backend/scripts/train_anomaly_detector.py` |
| **13 input features** | declared_income_annual, total_deposits_90d, total_withdrawals_90d, num_deposits_90d, num_withdrawals_90d, deposit_withdraw_cycle_days_avg, vpn_usage_pct, countries_accessed_count, device_shared_count, ip_shared_count, account_age_days, kyc_face_match_score, deposits_vs_income_ratio. | `backend/services/alerts.py` (FEATURE_COLS), `backend/models/FEATURE_IMPORTANCE.md` |
| **Risk level** | High / Medium / Low from composite = 0.5×fraud_probability + 0.5×anomaly_score; thresholds 0.5 and 0.3. Used for triage and ordering only, not automated enforcement. | `backend/services/alerts.py` (_risk_level) |
| **Alert queue source** | Alerts from `backend/data/anomaly_scores.csv` when present (from run_unlabeled_pipeline or similar); else mock list. Each alert has account_id, fraud_probability, anomaly_score, risk_level, one_line_explanation, risk_factors, feature_vector (when available). | `backend/services/alerts.py` (get_alerts) |

**Why LightGBM + Isolation Forest** — LightGBM is used for interpretable, tabular fraud patterns; Isolation Forest complements it by surfacing novel or rare behaviors not present in training labels.

---

## 2. Dashboard UI (Streamlit)

### 2.1 Layout and navigation

| Feature | Description |
|--------|-------------|
| **Hero** | Page title “Fraud Investigation Dashboard”, subtitle “Internal use · Human-in-the-loop”. |
| **Left sidebar** | Logo; API keys expander (Gemini, OpenAI); Filter & sort expander; four case lists (Alerts, Verified fraud, Legit, False positives); Select a case dropdowns; Selected case card (account, risk badge, fraud %, one-line explanation, outcome priority explanation when applicable). |
| **Main area** | Case header card (Account, Status, Risk score); Actions row; then case metrics, “Why this account was flagged”, 30s summary, Evidence tabs, Timeline, Next steps, Investigation report. |

### 2.2 Case header and actions

| Feature | Description |
|--------|-------------|
| **Case header card** | Account ID, Status (Under Review / Confirmed Fraud / Marked Legit / False Positive / More Info Requested), Risk score (%). |
| **Confirm Fraud** | Sets status to Confirmed Fraud; stores decision + snapshot + optional feature_vector; runs knowledge capture; logged for audit. |
| **Mark Legit** | Sets status to Marked Legit; same store + knowledge capture + audit. |
| **Request More Info** | Sets status to More Info Requested (no feedback write). |
| **Dismiss (false positive)** | Opens expander for required reason (dropdown + optional free text); on submit, stores False Positive with reason and feature_vector; audit. |
| **Next case →** | Moves selection to next case in the combined list (Alerts + Verified + Legit + False positives). |
| **Run investigation agents** | Runs full pipeline (transaction, identity, geo, network, outcome_similarity, orchestrator); caches result by account_id. |
| **Reopen case** | When status is closed (Fraud/Legit/False Positive), moves back to Under Review and logs “Reopened” in feedback. |

### 2.3 Filter and sort (sidebar)

| Feature | Description |
|--------|-------------|
| **Risk filter** | All / High / Medium / Low. |
| **Sort mode** | Risk (High → Low), Anomaly (High → Low), Outcome-informed (Learning). |
| **Risk order toggle** | High → Low / Low → High when sort is Risk. |
| **Anomaly order toggle** | High → Low / Low → High when sort is Anomaly. |
| **Outcome-informed sort** | Sorts by outcome_adjusted_priority DESC (then fraud_probability). Shows “Prioritised due to similarity with N confirmed fraud cases” or “De-prioritised due to historical false positives” in selected-case card and in main case view when applicable. |

### 2.4 Case metrics and explainability (main)

| Feature | Description |
|--------|-------------|
| **Case metrics row** | Fraud probability (%), Anomaly score (%), Risk level. |
| **One-line explanation** | From alert (model/rule-based); shown under metrics. |
| **Queue / outcome explanation** | Caption “Queue: Prioritised…” or “De-prioritised…” when outcome_priority_explanation is set and not neutral. |
| **Why this account was flagged** | When agents have run: Orchestrator key_drivers + investigation_summary, confidence (High/Medium/Low), priority (1–5). When no agents: risk_factors as bullets + confidence from fraud probability. |
| **Risk level and narrative consistency** | The likelihood phrase under the metrics (“High composite risk”, “Moderate…”, “Lower likelihood of real fraud”) and the confidence in “Why this account was flagged” are aligned with the displayed **Risk level**. When Risk level is High, the UI never shows “Lower likelihood of real fraud”; it shows “High composite risk” and, when fraud probability is low, explains that anomaly or network signals raised the composite risk. Confidence (when no orchestrator) is at least Medium when risk level is High, so “Low confidence / may be normal variation” is not shown for High-risk cases. |
| **30s Copilot Summary** | Short investigation_summary from Orchestrator when available; else button “Run investigation to see summary”. |

### 2.5 Evidence tabs

| Tab | Content |
|-----|--------|
| **Transactions** | Transaction agent output (anomaly score, short_explanation, detected_patterns); metrics (total deposits/withdrawals 90d, deposit count, avg cycle); **real** transaction summary table from backend (deposit_count_90d, withdrawal_count_90d, deposits_vs_income_ratio, avg_deposit_amount, deposit_withdraw_cycle_days_avg) via `get_transactions(account_id, alert)`. |
| **Access & Geo** | Geo agent output (geo_risk, explanation, indicators); metrics (countries, VPN %, distinct IPs, last login); **real** geo table (countries_accessed_count, vpn_usage_pct, high_risk_country_flag) via `get_geo_activity(account_id, alert)`. |
| **Identity** | Identity agent output (identity_risk, explanation, indicators); metrics (KYC face match, Doc verified, account age, declared income); **real** identity table (kyc_face_match_score, document_verified, identity_risk_level) via `get_identity_signals(account_id, alert)`. |
| **Network** | Network agent output (cluster_size, known_fraud_links, explanation, shared_signals); metrics (devices linked, accounts on same device, IPs linked); **real** device/IP table (device_shared_count, ip_shared_count) via `get_network_signals(account_id, alert)`. **Fraud ring flowchart** (Mermaid): shown only when the account has shared devices or IPs (i.e. is part of a fraud ring); built from same `get_account_network(account_id)` data; subgraphs for Selected account, Linked accounts, Shared devices, Shared IPs; capped at 6 linked accounts, 4 devices, 4 IPs for readability; uses streamlit-mermaid when installed, else HTML fallback + “View flowchart code” expander. **Interactive fraud ring graph** (pan/zoom): Pyvis hierarchical flowchart from `get_account_network(account_id)` — primary account, other accounts, devices, IPs; “No network links detected” when no edges. The flowchart block is omitted when there are no edges so the tab is not blank. |
| **Similar Cases** | Outcome similarity agent (fraud_likelihood, similar_confirmed_cases_count, explanation); fallback to `get_similar_confirmed_count(risk_level, feature_vector)` when agent errors; caption on outcome-informed sort. |

### 2.6 Timeline

| Feature | Description |
|--------|-------------|
| **Chronological events** | Events from alert timeline_events; sort by timestamp. |
| **Rule-based Mermaid diagram** | Flowchart of events; suspicious events highlighted (red border). |
| **Build timeline flow** | Button runs Visualization agent to produce AI-generated flowchart (spec → Mermaid via spec_to_mermaid); optional. |
| **Event list (text)** | Expandable list of timestamp, event_type, details, suspicious flag. |

### 2.7 Next steps and report

| Feature | Description |
|--------|-------------|
| **Recommended next steps** | Top 3 investigative actions from `recommend_next_steps(risk_factors/one_line_explanation)`; LLM or template; no decisions, no fraud label. |
| **Investigation report** | Button “Generate Investigation Report”; builds case context (account, status, scores, risk factors, timeline); calls `generate_regulatory_report(case_context)` (LLM); 4-section structure (Executive Summary, Evidence Reviewed, Findings, Conclusion & Recommendations). Report shown in expander; Regenerate button available. |

### 2.8 API keys (sidebar)

| Feature | Description |
|--------|-------------|
| **API keys expander** | Google (Gemini) and OpenAI API key inputs (password); override .env when set; caption that keys are not stored on server. |

---

## 3. Backend services

| Service | Purpose |
|--------|---------|
| **alerts** | `get_alerts(limit)` — load alerts from anomaly_scores.csv or mock; compute risk_level, one_line_explanation, risk_factors, feature_vector; **compute outcome_adjusted_priority** and outcome_priority_explanation per alert; return sorted by risk then fraud_probability. |
| **evidence** | `get_transactions`, `get_geo_activity`, `get_identity_signals`, `get_network_signals` — per-account DataFrames from anomaly_scores.csv or alert dict; “No data available” single-row DataFrame when missing. |
| **network** | `get_account_network(account_id)` — returns `{nodes, edges}` for Network tab. **Neo4j** when NEO4J_URI set and graph populated (run `backend/scripts/neo4j_load_network.py`); else **CSV fallback** from unlabeled + synthetic CSVs. Nodes: primary_account, other_account, device, ip; edges: uses device, logged from. |
| **feedback** | `add_decision`, `add_knowledge_pattern`, `get_decisions`, `get_similar_confirmed_count`, `get_similar_false_positive_count`, `has_false_positive_history`, `get_feedback_for_retrain` — store decisions (Confirmed Fraud, Marked Legit, False Positive, Reopened) with reason, timestamp, optional feature_vector; cosine-similarity counts for outcome-informed priority; feedback file for audit and retrain. |
| **priority** | `compute_outcome_adjusted_priority(alert)` — base = 0.5×prob + 0.5×anomaly; boost for similar confirmed fraud; reduction for similar false positives; clamp [0,1]; return score + explanation string for UI and audit. |

---

## 4. Agents (LLM pipeline)

| Agent | Role | Outputs | When run |
|-------|------|---------|----------|
| **transaction** | Transaction/behavior | anomaly_score, detected_patterns, short_explanation | On “Run investigation agents” (alert_creation) or from cache |
| **identity** | Identity risk | identity_risk, indicators, explanation | Same |
| **geo** | Geo/VPN | geo_risk, indicators, explanation | Same |
| **network** | Network/cluster | cluster_size, known_fraud_links, shared_signals, explanation | Same |
| **outcome_similarity** | Similarity to past outcomes | fraud_likelihood, similar_confirmed_cases_count, explanation | Same |
| **orchestrator** | Senior investigator (UI-facing) | risk_level, confidence, key_drivers, priority, investigation_summary; instructed to call out conflicting specialist signals in key_drivers/investigation_summary | After specialists (or from cache) |
| **knowledge_capture** | Case-close summary | key_signals, behavioral_pattern, final_outcome, one_sentence_description | On Confirm Fraud / Mark Legit / Dismiss |

Pipeline: specialists run in order; orchestrator gets merged specialist JSON; results cached by account_id. Graceful degradation: failed agents show warning in tab; model-only metrics and risk_factors still shown.

### Execution and caching semantics

Investigation agent outputs are **cached per account_id**. Re-running “Run investigation agents” reuses cached results unless explicitly cleared or the case state changes. This prevents unnecessary recomputation and keeps investigator views stable during a review session. Caching is in session state (`agent_cache`); timeline visualization spec is also cached per account (`timeline_spec_cache`). So: clicking “Run investigation agents” twice on the same case does not re-call the LLM; the UI stays fast and consistent.

---

## 5. Explainability modules

| Module | Purpose |
|--------|---------|
| **alert_explanation** | Generate concise explanation, key risk drivers, junior analyst summary from fraud prob, anomaly, SHAP-style drivers, network indicators; LLM or template fallback. |
| **timeline_builder** | Chronological timeline, suspicious-sequence tags, human-readable narrative from event list. |
| **next_step_advisor** | Top 3 next investigative actions from risk indicators; no decisions. |
| **report_writer** | Regulatory-style report: executive summary, evidence reviewed, findings, conclusion; from case summary + evidence points + investigator conclusion. |
| **visualization_tool** | `spec_to_mermaid(spec)` — convert timeline spec (nodes/edges) to Mermaid flowchart for UI. |

**Negative evidence** — The absence of expected fraud signals (e.g. no shared devices, low anomaly, strong KYC match) is treated as contextual evidence and may lower priority or confidence, but never auto-dismisses a case. The UI shows “No network links detected” when the graph has no edges; the orchestrator and risk factors can reflect “clean” identity or low anomaly as part of the overall picture.

---

## 6. Data and scripts

| Item | Purpose |
|------|---------|
| **anomaly_scores.csv** | Per-account scores and 13 features; used by alerts and evidence when present. |
| **unlabeled_fraud_dataset.csv** | Account, device_id, ip_address, behavioral columns; used by run_unlabeled_pipeline and by network (CSV fallback) and neo4j_load_network. |
| **synthetic_fraud_dataset.csv** | Account, device_id, ip_hash, is_fraud, etc.; used by network (CSV/Neo4j load) and neo4j_graph_features. |
| **investigator_feedback.json** | All decisions + reason, timestamp, investigator_id, model_version, optional feature_vector and knowledge_pattern; audit and similarity/priority. |
| **neo4j_load_network.py** | One-time/startup: load unlabeled + synthetic CSVs into Neo4j (Account.account_id, Device.device_id, IP.ip_id, USES_DEVICE, LOGGED_FROM). |
| **feedback_retrain.py** | Export feedback for retraining; join with anomaly_scores; labels from decision. |
| **run_unlabeled_pipeline.py** | Score unlabeled dataset; write anomaly_scores.csv. |

**Data freshness** — Scores and evidence reflect the latest available batch data (from anomaly_scores.csv or pipelines). The UI does not claim real-time monitoring; timestamps are shown where applicable (e.g. decision timestamp, event timestamps in timeline).

---

## 7. Optional / configuration

| Feature | Description |
|--------|-------------|
| **Neo4j** | Optional. Set NEO4J_URI (and user/password); run `python -m backend.scripts.neo4j_load_network` to populate graph; Network tab then uses Neo4j for get_account_network; otherwise CSV fallback. |
| **LLM keys** | GOOGLE_API_KEY or OPENAI_API_KEY (or set in sidebar). Without keys, template/fallback explanations and reports; agents can still run if keys set in UI. |
| **AGENT_CALL_DELAY_SECONDS** | Optional pacing between agent calls. |
| **INVESTIGATOR_ID, FRAUD_MODEL_VERSION** | Stored with each decision for audit. |
| **streamlit-mermaid** | Optional. When installed, the Network tab uses it to render the fraud ring flowchart (Mermaid). Without it, the app falls back to HTML iframe + expander with flowchart code. |

**Model version traceability** — Each investigator decision stores the fraud model version (and investigator_id) active at decision time, enabling post-hoc analysis of model performance drift and audit review.

**Feature vectors** — When available (from anomaly_scores.csv or the scoring pipeline), a normalized 13-dimensional feature vector is attached to each alert and can be stored with investigator decisions (Confirmed Fraud, False Positive, Marked Legit). When unavailable (e.g. mock alerts), similarity and outcome-informed prioritisation fall back to risk-level–based heuristics (e.g. same risk_level bucket). So: “what if vectors are missing?” is handled by design; the system still orders and explains, with coarser similarity.

---

## 8. Safeguards and compliance

- **No single signal as proof of fraud** — orchestrator and copy are cautious; conflict between specialists can be called out.
- **Scores do not auto-decide** — risk score and anomaly are inputs to prioritisation and review; risk level is for triage and ordering, not automated enforcement.
- **False positive dismissal** — required reason (dropdown + optional text); stored for audit.
- **Reopen case** — moves case back to Under Review; action logged.
- **All decisions** — stored with snapshot and model version in investigator_feedback.json for audit and retrain.

**Access control (out of scope)** — Authentication, role-based access control, and investigator permissions are out of scope for this prototype but assumed in a production deployment.

---

## 9. File map (key entry points)

| Path | Role |
|------|------|
| `frontend/app.py` | Streamlit dashboard; single entry `streamlit run frontend/app.py`. |
| `backend/services/alerts.py` | get_alerts, risk_level, one_line_explanation, risk_factors, outcome_adjusted_priority. |
| `backend/services/evidence.py` | get_transactions, get_geo_activity, get_identity_signals, get_network_signals. |
| `backend/services/network.py` | get_account_network (Neo4j or CSV). |
| `backend/services/feedback.py` | add_decision, get_similar_confirmed_count, get_similar_false_positive_count, etc. |
| `backend/services/priority.py` | compute_outcome_adjusted_priority. |
| `backend/agents/runner.py` | run_pipeline, run_knowledge_capture, run_visualization_agent. |
| `backend/agents/prompts.py` | Agent system prompts and output schemas. |
| `backend/explainability/*.py` | Alert explanation, timeline, next steps, report, visualization_tool. |

This document lists the features as implemented; for “how to run” and “what’s important” summaries, see README.md.
