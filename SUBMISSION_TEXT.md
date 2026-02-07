# Hackathon submission text

Copy-paste the fields below into the submission form.

---

## Submission Title * (5–50 characters)

**AI-Powered Fraud Detection & Investigation**

*(43 characters)*

---

## Short Description (summary) * (max 255 characters)

**Copy this (248 characters):**

An AI-powered fraud detection and investigation platform that combines multi-signal pattern detection (identity, transaction, geo, device), explainable alerts, and human-in-the-loop decisioning with LLM-assisted timelines, next-step recommendations, and regulatory report generation.

---

## Long Description (what is your idea?) * (min 100 words)

**Copy this (~165 words):**

Our idea is an AI-powered system that helps investigators detect and investigate client fraud while keeping humans in the loop and decisions explainable.

**The problem:** Fraud patterns are multi-faceted (identity, transactions, geography, devices) and constantly evolving. Investigators need clear explanations, prioritised alerts, and tools that learn from their decisions without replacing judgment.

**Our solution:** We built a live Streamlit dashboard that (1) flags accounts using a fraud classifier and an anomaly detector so both known and novel patterns are caught; (2) explains every alert in plain language with risk factors, confidence, and “why this account was flagged”; (3) gives investigators a coherent case view with timeline reconstruction, evidence tabs (transactions, geo, identity, network), and an interactive device/IP network graph; (4) suggests next steps via an LLM (recommendations only—no automated labels); (5) lets investigators confirm fraud, mark legit, or dismiss as false positive with a required reason, all stored in an audit trail; (6) generates regulatory-style investigation reports; and (7) exports investigator feedback so the model can be retrained periodically and improve from outcomes.

The system is designed so that investigator decisions are first-class signals: feedback, similarity matching (“similar to N confirmed fraud cases”), and the retraining pipeline plug in without changing how investigators work. We aim to reduce false positives, speed up investigations, and keep every decision auditable and explainable.
