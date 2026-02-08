# What's left (vs challenge PDF)

All **four pillars** and **constraints** from the brief are covered. The items below that were "optional" have been **implemented** where noted.

---

## ✅ Fully covered by the brief

- **1. Intelligent Detection & Pattern Discovery** — Multi-signal, behavioural anomaly, identity signals (KYC), sanctions/geo (VPN, countries), emerging patterns (anomaly detector), network analysis (graph + shared device/IP).
- **2. Explainable Alerts & Prioritisation** — Clear explanations, confidence + risk level, prioritisation (sort/filter), false positive dismissal + audit, "similar to N previously confirmed fraud cases" (similarity-based).
- **3. AI-Assisted Investigation** — Case view, timeline, evidence tabs, recommended next steps (LLM), cross-case (network graph).
- **4. Documentation & Learning** — Report generation (regulatory-style), continuous learning pipeline (feedback store + export for retrain).
- **Constraints** — Live demo, AI core, human-in-the-loop, explainable, no missed fraud (anomaly + classifier).

---

## ✅ Done (previously "optional")

| # | Item | Status |
|---|------|--------|
| 3 | **Prioritisation from outcomes** | ✅ **Done.** Sidebar sort includes "Outcome-informed (Learning)" — ranks by similarity to confirmed fraud + fraud prob. |
| 4 | **Knowledge capture (reusable patterns)** | ✅ **Done.** On case close (Confirm Fraud / Mark Legit / Dismiss as FP), LLM captures pattern → stored in feedback for similarity and retrain. |
| 30s copilot | **Investigation summary in ~30s** | ✅ **Done.** Orchestrator produces "30s summary"; "Run investigation to see summary" button in UI. |

---

## ⏳ Still optional / strengthen (not required for demo)

| # | Item | Current state | If you add it |
|---|------|----------------|----------------|
| 1 | **Evidence tabs use real data** | Transactions, Geo, Identity, Network tabs use **mock** tables | Populate from `anomaly_scores.csv` / alert (e.g. `vpn_usage_pct`, `countries_accessed_count`, `device_shared_count`, `kyc_face_match_score`, aggregates). |
| 2 | **Network graph from real data** | Graph uses **hardcoded** device/IP list | Pass per-account device/IP from backend or Neo4j into `_build_network_graph_html()`. |
| 5 | **Full auto-resolve with Reopen** | We have **suggestion** + manual dismiss with audit | Optional: when rule holds, auto-set status to False Positive, log `auto_resolved_false_positive`, show "Reopen case" in UI. |

---

## 🌟 "What would blow our minds" (stretch)

| Brief line | Status | Note |
|------------|--------|------|
| Pattern discovery: "Detected emerging behaviour cluster: **47 accounts** with similar transaction patterns" | Not built | Would need clustering (e.g. on anomaly/features), then surface "N accounts in this cluster" in UI. |
| Network revelation: "This account is part of a **23-account fraud ring** sharing 3 devices" | Not built | Would need graph analysis (e.g. connected components, device overlap) and a sentence generator. |
| Cross-domain intelligence: "Identity passed checks but **transaction + VPN + device match known fraud network**" | Partial | We have identity (KYC), VPN, device in one view; no single "match known fraud network" sentence. Could add when similarity to confirmed fraud is high. |
| **5x productivity** | Claim only | No measurement; you can state "designed to reduce time per case" in pitch. |

---

## Summary

- **Nothing required by the challenge is missing** for a solid demo.
- **Done:** Outcome-informed sort (3), knowledge capture on close (4), 30s investigation summary.
- **Still optional:** Real data in evidence/network (1–2), full auto-resolve + Reopen (5), and "blow our minds" stretch items.

Use **IMPLEMENTATION_STATUS.md** and the **judge one-liner** there when presenting.
