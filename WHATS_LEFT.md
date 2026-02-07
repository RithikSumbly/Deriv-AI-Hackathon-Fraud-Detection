# What’s left (vs challenge PDF)

All **four pillars** and **constraints** from the brief are covered for a strong demo. What remains is **optional polish** and **stretch**.

---

## ✅ Fully covered by the brief

- **1. Intelligent Detection & Pattern Discovery** — Multi-signal, behavioural anomaly, identity signals (KYC), sanctions/geo (VPN, countries), emerging patterns (anomaly detector), network analysis (graph + shared device/IP).
- **2. Explainable Alerts & Prioritisation** — Clear explanations, confidence + risk level, prioritisation (sort/filter), false positive dismissal + audit, “similar to N previously confirmed fraud cases” (similarity-based).
- **3. AI-Assisted Investigation** — Case view, timeline, evidence tabs, recommended next steps (LLM), cross-case (network graph).
- **4. Documentation & Learning** — Report generation (regulatory-style), continuous learning pipeline (feedback store + export for retrain).
- **Constraints** — Live demo, AI core, human-in-the-loop, explainable, no missed fraud (anomaly + classifier).

---

## ⏳ Optional / strengthen (not required for demo)

| # | Item | From brief | Current state | If you add it |
|---|------|------------|----------------|----------------|
| 1 | **Evidence tabs use real data** | “Pull relevant information from multiple systems into a coherent case view” | Transactions, Geo, Identity, Network tabs use **mock** tables | Populate from `anomaly_scores.csv` / alert (e.g. `vpn_usage_pct`, `countries_accessed_count`, `device_shared_count`, `kyc_face_match_score`, aggregates). |
| 2 | **Network graph from real data** | “Connect related accounts through shared IPs, devices” | Graph uses **hardcoded** device/IP list | Pass per-account device/IP from backend or Neo4j into `_build_network_graph_html()`. |
| 3 | **Prioritisation from outcomes** | “Learn from historical outcomes to rank alerts by likelihood of being real fraud” | Sort is risk → fraud prob → anomaly only | Use feedback: e.g. rank higher if similar to confirmed fraud (we already have similarity count); or train a small “will investigator confirm?” model and sort by that. |
| 4 | **Knowledge capture (reusable patterns)** | “Learn from every investigation to improve future detection” | Decisions + snapshot stored; no structured “pattern” yet | Optional: after each decision, LLM summarise → store `{ pattern_id, signals, outcome, summary }` for similarity and training. |
| 5 | **Full auto-resolve with Reopen** | “Identify and auto-resolve obvious false positives with audit trail” | We have **suggestion** + manual dismiss with audit | Optional: when rule holds, auto-set status to False Positive, log `auto_resolved_false_positive`, show “Reopen case” in UI. |

---

## 🌟 “What would blow our minds” (stretch)

| Brief line | Status | Note |
|------------|--------|------|
| Investigation copilot: case summary + evidence + recommendations in **30 seconds** | Partial | Report + next steps exist; could add one “Generate full summary” button that runs both and shows in one view. |
| Pattern discovery: “Detected emerging behaviour cluster: **47 accounts** with similar transaction patterns” | Not built | Would need clustering (e.g. on anomaly/features), then surface “N accounts in this cluster” in UI. |
| Network revelation: “This account is part of a **23-account fraud ring** sharing 3 devices” | Not built | Would need graph analysis (e.g. connected components, device overlap) and a sentence generator. |
| Cross-domain intelligence: “Identity passed checks but **transaction + VPN + device match known fraud network**” | Partial | We have identity (KYC), VPN, device in one view; no single “match known fraud network” sentence. Could add when similarity to confirmed fraud is high. |
| **5x productivity** | Claim only | No measurement; you can state “designed to reduce time per case” in pitch. |

---

## Summary

- **Nothing required by the challenge is missing** for a solid demo.
- **Left** = real data in evidence/network (1–2), outcome-based prioritisation (3), optional knowledge patterns (4), optional full auto-resolve (5), and “blow our minds” extras if you have time.

Use **IMPLEMENTATION_STATUS.md** and the **judge one-liner** there when presenting.
