# How the AI Agents Work and Are Called

A detailed description of the multi-agent fraud investigation system: agent definitions, execution flow, and how the frontend triggers and consumes results.

---

## 1. Overview

The system uses **seven LLM-based agents** for fraud investigation. Only one, the **Orchestrator**, is intended to “talk to the UI”; the rest are **specialists** whose outputs are merged by the Orchestrator. All agents are implemented as **single LLM calls** (system prompt + structured user message) that return **JSON**. The **agent runner** builds inputs, calls the LLM in a fixed order, parses JSON, and (on first case open) **caches** results per `account_id` so subsequent opens can reuse them.

---

## 2. Agent Definitions (`backend/agents/prompts.py`)

Each agent is defined by:

- A **system prompt** (role and task),
- A list of **output fields** (expected JSON keys).

They are registered in **`AGENTS`** and execution order is defined by **`ORDER_ON_ALERT_CREATION`**, **`ORDER_ON_CASE_OPEN`**, and **`ORDER_ON_CASE_CLOSE`**.

| Agent ID | Role | Output fields (expected JSON) |
|----------|------|--------------------------------|
| **transaction** | Transaction/behavior | `anomaly_score`, `detected_patterns`, `short_explanation` |
| **identity** | Identity risk | `identity_risk`, `indicators`, `explanation` |
| **geo** | Geo/VPN | `geo_risk`, `indicators`, `explanation` |
| **network** | Network/cluster | `cluster_size`, `known_fraud_links`, `shared_signals`, `explanation` |
| **outcome_similarity** | Similarity to past outcomes | `fraud_likelihood`, `similar_confirmed_cases_count`, `explanation` |
| **orchestrator** | Senior investigator (UI-facing) | `risk_level`, `confidence`, `key_drivers`, `priority`, `investigation_summary` |
| **knowledge_capture** | Case-close summary | `key_signals`, `behavioral_pattern`, `final_outcome`, `one_sentence_description` |

The Orchestrator is instructed to take the **combined specialist findings** and produce one summary, key drivers, confidence, and priority. The Knowledge Capture agent runs only **on case close** (Confirm Fraud / Mark Legit / Dismiss).

---

## 3. How Agents Are Called: The Runner (`backend/agents/runner.py`)

### 3.1 Single-Agent Run: `_run_agent(agent_id, user_message)`

- Looks up the agent in **`AGENTS`** to get `system_prompt` and `output_fields`.
- Calls **`call_llm_with_error(system, user_message)`** (one LLM request).
- Takes the raw text response and **parses JSON** (supports raw JSON or markdown code blocks) via **`_extract_json`**.
- Builds a result dict with the agent’s **output_fields** (and `_error` if something failed or the LLM said so).
- Returns `(parsed_output, error)`. On failure, `parsed_output` contains at least **`_error`** with the message.

So: **one agent = one LLM call + one JSON parse**. No tool use or multi-step reasoning.

### 3.2 Input Building (User Message per Agent)

The runner has a **`_build_*_user(alert, ...)`** for each agent. Each builds a **JSON string** from the current **alert** (and, where needed, extra data) and that string is the **user message** to the LLM.

- **Transaction:** `declared_income_annual`, deposit/withdrawal totals and counts, `deposit_withdraw_cycle_days_avg`, `deposits_vs_income_ratio`, `fraud_probability`, `anomaly_score`.
- **Identity:** `kyc_face_match_score`, `account_age_days`, `fraud_probability`.
- **Geo:** `vpn_usage_pct`, `countries_accessed_count`, `fraud_probability`.
- **Network:** `device_shared_count`, `ip_shared_count`, `fraud_probability`.
- **Outcome similarity:** `fraud_probability`, `risk_level`, **`similar_confirmed_cases_count_from_system`** (from **`get_similar_confirmed_count()`** in feedback), `one_line_explanation`.
- **Orchestrator:** **merged JSON of all five specialists’ outputs** (with `_error` keys stripped so the Orchestrator doesn’t see internal error fields).
- **Knowledge capture:** alert summary (e.g. `account_id`, `fraud_probability`, `risk_level`, `one_line_explanation`, `risk_factors`) plus **outcome** (e.g. Confirmed Fraud / Marked Legit / False Positive) and **reason**.

Alert data (including the 13 raw feature columns) comes from **`get_alerts()`** in `backend/services/alerts.py`; the runner only reads the alert dict (and feedback for similar count).

### 3.3 Pipeline: `run_pipeline(alert, mode, cached_specialists=...)`

Two modes:

**`mode="alert_creation"`** (first time this case is opened):

1. **Optional pacing:** If **`AGENT_CALL_DELAY_SECONDS`** > 0, the runner sleeps that many seconds **after** each specialist call to spread requests (e.g. for rate limits).
2. Run specialists **in order**: **transaction → identity → geo → network → outcome_similarity.** For each: build user message from `alert` (and for outcome_similarity, from `get_similar_confirmed_count`), call **`_run_agent`**, store result in a dict keyed by agent id.
3. Build **specialist_merge**: all five specialists’ outputs, with `_error` keys removed.
4. Run **orchestrator** with user message = **`_build_orchestrator_user(specialist_merge)`** (the merged JSON).
5. Return a dict: `{ "transaction": {...}, "identity": {...}, "geo": {...}, "network": {...}, "outcome_similarity": {...}, "orchestrator": {...} }`.

So on “alert creation” the agents are **called sequentially** in that order; the Orchestrator is called **once**, after all five specialists.

**`mode="case_open"`** (later opens of the same case, when cache exists):

- Fill **transaction, identity, geo, network, outcome_similarity** from **`cached_specialists`** (no LLM calls).
- Build **specialist_merge** from that cached data.
- Run **only the orchestrator** with that merge as user message.
- Return the same shape of dict (cached specialists + new orchestrator result).

So “case open” does **one LLM call** (Orchestrator only); the frontend currently uses the **full cached result** and does not re-run the pipeline on every open, so in practice it may not call `run_pipeline(..., "case_open", cached_specialists=...)` at all unless you add that path.

### 3.4 Knowledge Capture: `run_knowledge_capture(alert, outcome, reason)`

- Builds user message with **`_build_knowledge_capture_user(alert, outcome, reason)`**.
- Calls **`_run_agent("knowledge_capture", user_msg)`** (one LLM call).
- Returns the parsed pattern dict (or dict with `_error`).

This is **only** invoked from the frontend when the user closes a case (see below).

---

## 4. LLM Layer (`backend/explainability/llm_client.py`)

- **Entry point:** **`call_llm_with_error(system, user)`** (and **`call_llm`** which just returns the text).
- **Provider choice:** If **`GOOGLE_API_KEY`** (or an OpenAI key that looks like a Google key) is set, the client uses **Gemini**; otherwise it uses an **OpenAI-compatible** client (**`OPENAI_API_KEY`** / **`OPENAI_BASE_URL`**).
- **Rate limits:** If the error looks like a rate limit (429, “quota”, “resource exhausted”, “rpm”, “tpm”, etc.), the client **retries** with exponential backoff (2s, 4s, 8s), up to **`LLM_RATE_LIMIT_RETRIES`** (default 3). So every agent call (and any other use of this client) gets that behavior.

So: **every agent call is exactly one call to `call_llm_with_error(system_prompt, user_message)`**, with no extra tool or chain logic inside the client.

---

## 5. When the Frontend Triggers Which Pipeline

- **On first open of a case (selected alert):**  
  - Frontend checks **`st.session_state.agent_cache`** for `selected_id`.  
  - If **missing**, it calls **`run_pipeline(alert, "alert_creation")`** (with a spinner), then stores the returned dict in **`agent_cache[selected_id]`**.  
  - So the **first time** you open that case, **six LLM calls** run in sequence (five specialists + one orchestrator).

- **On later opens of the same case:**  
  - **`agent_results = agent_cache.get(selected_id)`** is used; no new pipeline run unless you explicitly call **`run_pipeline(alert, "case_open", cached_specialists=...)`** and replace the cached orchestrator.

- **On case close (Confirm Fraud / Mark Legit / Dismiss as False Positive):**  
  - Frontend calls **`_on_case_close(decision, reason)`**, which:  
    - Calls **`add_decision(...)`** (persists the decision).  
    - Calls **`run_knowledge_capture(alert, decision, reason)`** (one LLM call).  
    - If the returned pattern has no **`_error`**, calls **`add_knowledge_pattern(selected_id, pattern)`** to attach the pattern to the feedback record.

So in total:

- **First open of a case:** 6 agent calls (5 specialists + orchestrator).  
- **Case close:** 1 agent call (knowledge_capture).  
- **Later opens:** 0 agent calls unless you add a “case_open” path that re-runs only the orchestrator.

---

## 6. How the UI Uses Agent Results

- **Risk block (“Why this account was flagged”):** Uses **`agent_results["orchestrator"]`** when present and no `_error`: `investigation_summary`, `key_drivers`, `confidence`, `priority`. Else fallback to rule-based `risk_factors` and probability.
- **30s Copilot Summary:** Short line from **orchestrator `investigation_summary`** (truncated).
- **Predictive line (likelihood + similar cases):** Uses **`agent_results["outcome_similarity"]`** when present (`similar_confirmed_cases_count`, `explanation`); else **`get_similar_confirmed_count()`** and default copy.
- **Evidence tabs:**  
  - **Transactions:** **transaction** agent (`anomaly_score`, `short_explanation`, `detected_patterns`).  
  - **Access & Geo:** **geo** agent (`geo_risk`, `indicators`, `explanation`).  
  - **Identity:** **identity** agent (`identity_risk`, `indicators`, `explanation`).  
  - **Network:** **network** agent (`cluster_size`, `known_fraud_links`, `shared_signals`, `explanation`).  
  - **Similar Cases:** **outcome_similarity** agent (`fraud_likelihood`, `similar_confirmed_cases_count`, `explanation`), with fallback to **`get_similar_confirmed_count()`** if the agent failed.

If any agent returns **`_error`**, the UI shows a warning (e.g. “Transaction agent unavailable: …”) and, for rate-limit-like errors, a friendlier “Rate limit reached. Please try again in a minute.”

---

## 7. End-to-End Flow (Summary)

```
User selects case (first time)
  → Frontend: cache miss for account_id
  → run_pipeline(alert, "alert_creation")
       → Build transaction user message from alert
       → _run_agent("transaction", user_msg)  → call_llm_with_error → parse JSON
       → [optional delay]
       → Same for identity, geo, network
       → get_similar_confirmed_count(alert) → build outcome_similarity user msg
       → _run_agent("outcome_similarity", user_msg)
       → specialist_merge = { transaction, identity, geo, network, outcome_similarity } (no _error)
       → _run_agent("orchestrator", specialist_merge as JSON)
  → Store result in agent_cache[account_id]
  → Render risk block, 30s summary, predictive line, Evidence tabs from agent_results

User closes case (Confirm Fraud / Mark Legit / Dismiss)
  → add_decision(...)
  → run_knowledge_capture(alert, outcome, reason)
       → _run_agent("knowledge_capture", user_msg built from alert + outcome + reason)
  → add_knowledge_pattern(account_id, pattern) if no _error
```

So: **agents are “called” by the runner’s `_run_agent`**, which uses **one LLM call per agent** via **`call_llm_with_error`**, with inputs built from the **alert** (and feedback for outcome_similarity, and specialist merge for orchestrator). The frontend triggers **alert_creation** once per case (on first open) and **knowledge_capture** once per case close, and otherwise reads from **agent_cache**.
