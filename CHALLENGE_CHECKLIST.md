# Challenge checklist: AI-Powered Client Fraud Detection & Investigation

Based on the challenge brief and current codebase.

---

## ✅ Done

### 1. Intelligent Detection & Pattern Discovery
| Requirement | Status | Where |
|-------------|--------|--------|
| Multi-signal detection (identity, transaction, geo, account) | ✅ | 13 features in classifier + anomaly; `alerts.py` risk_factors (VPN, income, device, cycle, KYC) |
| Behavioural anomaly detection | ✅ | Isolation Forest anomaly detector; deposits vs income, rapid cycles |
| Identity fraud signals | ✅ | `kyc_face_match_score` and risk factors in alerts |
| Sanctions & geographic risk | ✅ | VPN %, countries in features and explanations |
| Emerging pattern discovery | ✅ | Unsupervised anomaly detector (catches novel patterns classifier misses) |
| Network analysis (shared IPs, devices) | ✅ | Neo4j design + pyvis network graph in dashboard; device/IP shared counts in data |

### 2. Explainable Alerts & Prioritisation
| Requirement | Status | Where |
|-------------|--------|--------|
| Clear human-readable explanations | ✅ | "Why this account was flagged" + one_line_explanation + risk_factors (plain language) |
| Confidence scoring with reasoning | ✅ | Fraud probability %, anomaly %, risk level (High/Medium/Low) + confidence note in UI |
| Prioritisation (risk order) | ✅ | Sort by risk then fraud prob; filter by risk level; ↓ Risk / ↓ Anomaly toggles |

### 3. AI-Assisted Investigation
| Requirement | Status | Where |
|-------------|--------|--------|
| Coherent case view | ✅ | Dashboard: case header, metrics, evidence tabs (Transactions, Geo, Identity, Network) |
| Timeline reconstruction | ✅ | Mermaid timeline from `timeline_events`; suspicious events highlighted |
| Evidence synthesis | ✅ | Tabs show transactions, geo/VPN, KYC, device/IP; risk factors + AI summary |
| Investigation suggestions | ✅ | "Recommended next steps" (LLM) + rationale |
| Cross-case connections | ✅ | Network graph (device/IP), "Accounts on same device", "Same device as fraud" in Evidence |

### 4. Documentation & Learning
| Requirement | Status | Where |
|-------------|--------|--------|
| Automated report generation | ✅ | "Generate Investigation Report" → regulatory report (4 H2 sections, LLM) |
| Regulatory explanations | ✅ | Report writer: Executive Summary, Evidence Reviewed, Findings, Conclusion & Recommendations |

### 5. Constraints
| Constraint | Status |
|------------|--------|
| Must demo live | ✅ Streamlit app |
| AI must add value | ✅ Gemini/OpenAI for next steps, report, explanations |
| Human in the loop | ✅ Investigator confirms Fraud / Legit / Request More Info; AI recommends only |
| Explainable decisions | ✅ Every alert has reasoning; confidence and risk factors shown |
| No missed fraud | ✅ Anomaly detector flags unusual even when classifier says low; combined risk level |

---

## ⏳ Partially done / Could strengthen

| Item | Current state | Possible improvement |
|------|----------------|---------------------|
| **False positive handling** | ✅ Implemented | "Dismiss as false positive" button → optional reason → stored in `backend/data/investigator_feedback.json` (audit trail). Fourth queue: False positives. |
| **Contextual comparison** | ✅ Implemented | "Pattern similar to N confirmed fraud cases" (same risk_level) in UI; N from investigator feedback. |
| **Intelligent prioritisation from outcomes** | Sort is risk/fraud/anomaly only | Re-rank alerts by "likelihood of real fraud" using investigator decisions (e.g. model that learns from Confirm Fraud / Mark Legit). |
| **Evidence data** | Evidence tabs use **mock** data (fixed tables) | Wire tabs to real per-account data from backend/CSV (transactions, countries, KYC, device/IP from anomaly_scores or Neo4j). |
| **Network data** | Graph uses **hardcoded** device/IP list | Populate from Neo4j or from anomaly_scores/backend so graph reflects real shared devices/IPs. |

---

## ❌ Not done (from challenge)

| Requirement | Notes |
|-------------|--------|
| **Continuous learning** | ✅ Pipeline in place | Investigator decisions (Confirm Fraud, Mark Legit, False Positive) stored in `investigator_feedback.json`. `python backend/scripts/feedback_retrain.py` exports `feedback_training_data.csv` from feedback + anomaly_scores; use with or merge into classifier training for periodic retrain. |
| **Knowledge capture** | ✅ Same pipeline | Every decision (with optional reason) is logged; feedback_retrain builds training dataset for future retrain. |
| **Auto-resolve false positives with audit trail** | ✅ Implemented | "Dismiss as false positive" → reason (optional) → saved to investigator_feedback.json with timestamp. |
| **Predictive explanation** | ✅ In UI | Line: "X% model-estimated likelihood of fraud based on Y risk factors. Pattern similar to N confirmed fraud cases." (N from feedback by risk_level). |

---

## Quick wins before demo

1. **Evidence tabs** — Replace mock tables with real fields from `alert` / `anomaly_scores.csv` (e.g. `vpn_usage_pct`, `countries_accessed_count`, `device_shared_count`, `kyc_face_match_score`, transaction aggregates) so the case view is coherent and data-driven.
2. **Network graph** — If you have device/IP per account in data or Neo4j, pass that into `_build_network_graph_html()` instead of hardcoded lists.
3. **One “Likely false positive” cue** — When risk is Low and anomaly is low, show a short line: "Consider quick review; pattern may be benign" and optionally a "Dismiss as false positive" action with a reason (stored for audit).
4. **One slide or sentence on “What would blow our minds”** — e.g. "Anomaly detector finds novel patterns; report is audit-ready; next steps are LLM-driven; we can add learning from outcomes next."

---

## Summary

| Category | Done | Partial | Not done |
|----------|------|--------|----------|
| Detection & pattern discovery | 6/6 | 0 | 0 |
| Explainable alerts & prioritisation | 3/5 | 2 | 0 |
| AI-assisted investigation | 5/5 | 0 (evidence data mock) | 0 |
| Documentation & learning | 2/4 | 0 | 2 (continuous learning, knowledge capture) |
| Constraints | 5/5 | — | — |

**Overall:** The live demo already covers detection, explainability, case view, timeline, next steps, and regulatory report. The main gaps are **learning from outcomes**, **false-positive handling with audit trail**, and **using real evidence/network data** instead of mocks in the UI.
