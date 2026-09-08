# RetailSense — System Architecture

**Version:** 2.0
**Related docs:** `prd.md`, `agent.md`, `design.md`, `stack.md`, `rules.md`

---

## 1. Architecture Summary

RetailSense is a sequential forecasting-and-decision pipeline with a conditional branch. Data flows one way; the only control-flow decision is whether disagreement clears the threshold τ.

```text
                        DATA SOURCES
                             │
        ┌────────────────┬───┴────────┬────────────────┐
        ▼                ▼            ▼                ▼
   M5 Sales         Open-Meteo   Google Trends    M5 Calendar
  (historical)      (weather)     (interest)       (events)
        │                │            │                │
        └────────────────┴──────┬─────┴────────────────┘
                                ▼
                    ┌───────────────────────┐
                    │ Data Integration Layer│  ← temporal joins, as-of alignment
                    └───────────┬───────────┘
                                ▼
                    ┌───────────────────────┐
                    │  Feature Engineering  │  ← lags, rolling stats, ANOMALIES
                    └───────────┬───────────┘
                                ▼
                    ┌───────────────────────┐
                    │  LEAKAGE AUDIT GATE   │  ← hard fail if any t+ field present
                    └───────────┬───────────┘
                                ▼
        ┌──────────────┬────────┴───────┬──────────────┐
        ▼              ▼                ▼              ▼
  Historical      Weather           Trend         Calendar
    Agent          Agent            Agent          Agent
  (XGBoost)     (LLM+rules)      (LLM+rules)    (LLM+rules)
        │              │                │              │
        └──────────────┴────────┬───────┴──────────────┘
                                ▼
                  Structured forecasts + confidence
                                │
                    ┌───────────▼───────────┐
                    │ Disagreement Analyzer │  D = normalized weighted variance
                    └───────────┬───────────┘
                                │
                  ┌─────────────┴─────────────┐
                  │ D < τ                     │ D ≥ τ
                  ▼                           ▼
          ┌───────────────┐           ┌───────────────┐
          │ Fast Consensus│           │  Critic Agent │
          │  (weighted)   │           └───────┬───────┘
          └───────┬───────┘                   ▼
                  │                   ┌───────────────┐
                  │                   │ 1 Revision    │
                  │                   │ Round         │
                  │                   └───────┬───────┘
                  │                           ▼
                  │                   ┌───────────────┐
                  │                   │ Re-consensus  │
                  │                   └───────┬───────┘
                  └─────────────┬─────────────┘
                                ▼
                    ┌───────────────────────┐
                    │ Final Forecast + PI   │
                    └───────────┬───────────┘
                                ▼
                    ┌───────────────────────┐
                    │ Inventory Policy      │  deterministic, rule-based
                    └───────────┬───────────┘
                                ▼
                   ┌────────────┼────────────┐
                   ▼            ▼            ▼
                RESTOCK       HOLD        REDUCE
                   └────────────┼────────────┘
                                ▼
                    ┌───────────────────────┐
                    │ Inventory Simulator   │  ← advances stock, applies lead time
                    └───────────┬───────────┘
                                ▼
                    ┌───────────────────────┐
                    │ Evaluation Store      │  ← SQLite; actuals revealed here
                    └───────────────────────┘
```

The **Leakage Audit Gate** is new in v2 and is the single most important structural addition. Data-leakage is the risk most likely to silently invalidate every result in the project; enforcing it as a pipeline stage rather than a coding convention makes violations impossible to miss.

---

## 2. Component Responsibilities

### 2.1 Data Integration Layer
Normalizes all inputs around `(prediction_timestamp, store_id, item_id)`. Responsible for as-of temporal joins, explicit missing-value markers, unit normalization, and store→lat/lon mapping for weather.

**Contract:** returns a single row per `(t, store, item)` containing only fields knowable at `t`.

### 2.2 Feature Engineering
Produces two classes of feature:
- **Level features** — lags, rolling means, price, promo flags
- **Anomaly features** — deviation of current context from its own historical norm

Anomaly features are what make context interpretable. An agent given `temp = 35°C` cannot reason; an agent given `temp = 35°C, seasonal_norm = 28°C, anomaly = +7°C (p95)` can.

### 2.3 Leakage Audit Gate
A hard gate, not a warning. For each feature column it asserts that the maximum source timestamp is strictly less than the prediction timestamp. Any violation raises and aborts the run. See `rules.md` §1.

### 2.4 Forecasting Agents
Four specialized agents, fully specified in **`agent.md`**. Summary:

| Agent | Evidence source | Implementation | Role |
|---|---|---|---|
| Historical | Sales history, price, promo | XGBoost/LightGBM | Quantitative backbone |
| Weather | Open-Meteo forecast + anomalies | Rule-based adjustment + LLM interpretation | Weather-driven deviation |
| Trend | Google Trends interest + delta | Rule-based adjustment + LLM interpretation | Consumer-interest shift |
| Calendar | M5 events, DOW, seasonality | Learned multipliers + LLM interpretation | Predictable calendar effects |

**Key design decision:** the three context agents produce a *forecast*, not a raw multiplier, so all four are comparable on the same scale and disagreement is well-defined. Each context agent anchors on a shared baseline and applies its own adjustment. See `agent.md` §4 for why this matters and what it costs.

### 2.5 Disagreement Analyzer
Collects the four structured outputs and computes D (§4 below). Routes to fast consensus or deliberation. It is deliberately stateless and pure — given the same agent outputs it always produces the same D and the same routing decision, which is what makes the mechanism reproducible and auditable.

### 2.6 Critic Agent
Activated only when D ≥ τ. Does **not** forecast. It classifies the conflict, names which agents are on which side, identifies the weakest assumption, and emits a structured challenge for each disagreeing agent. Full specification in `agent.md` §6 — including the conflict taxonomy, which was previously undefined and is the second most novel component after the trigger itself.

### 2.7 Deliberation Layer
Exactly one revision round. Each disagreeing agent receives: the critic's conflict report, the other agents' forecasts and stated key factors, and its own original output. It returns a revised forecast, a revised confidence, and a `changed_because` field. Agents may hold their position — refusing to move is a valid and informative outcome that must be logged.

### 2.8 Inventory Decision Layer
Deterministic and rule-based. Consumes final forecast, uncertainty, current stock, lead time, and safety stock; emits an action and an order quantity. The LLM has no write access to the order quantity (`rules.md` §4.3).

### 2.9 Evaluation Store
SQLite. The **only** component permitted to read actual future demand. Physically separating actuals into a store that agents cannot query is a structural leakage defense, not just a convention.

---

## 3. Agent Contract

Every forecasting agent returns:

```json
{
  "agent_id": "weather_agent",
  "run_id": "run_20250115_s1_i042",
  "forecast": 1150.0,
  "confidence": 0.82,
  "uncertainty": 0.18,
  "prediction_interval": [980, 1320],
  "key_factors": ["temperature anomaly +7C", "no precipitation"],
  "reasoning": "Sustained heat anomaly in p95 of seasonal distribution...",
  "abstained": false,
  "data_availability": {"weather": "complete", "trends": "n/a"},
  "latency_ms": 840,
  "tokens": {"in": 620, "out": 180}
}
```

Schema is enforced at the orchestrator boundary. Invalid output → one retry → recorded as `abstained: true` with the agent excluded from that run's consensus. **An abstaining agent is never treated as forecasting zero** (`rules.md` §2.7).

---

## 4. Disagreement Function

### 4.1 Definition

Confidence-weighted mean:

$$\bar{y}_c = \frac{\sum_i c_i y_i}{\sum_i c_i}$$

Confidence-weighted variance:

$$V = \frac{\sum_i c_i (y_i - \bar{y}_c)^2}{\sum_i c_i}$$

**Normalized disagreement** (v2 — this is the change that makes the score usable):

$$D = \frac{\sqrt{V}}{\bar{y}_c + \epsilon}$$

D is a confidence-weighted coefficient of variation. It is scale-free, so a spread of 50 units on an item selling 100/day registers as high disagreement while the same spread on an item selling 5,000/day does not. The unnormalized variance in v1 would have made D almost entirely a function of item volume, and τ would have been meaningless across a mixed item set.

### 4.2 Routing

```text
D < τ   → fast consensus  (0 additional LLM calls)
D ≥ τ   → critic + 1 revision round  (1 + k additional LLM calls)
```

### 4.3 Threshold calibration — resolved

τ is **not** chosen by eye. Procedure, run on the validation split only:

1. For each validation run, record `(D, |error|)`.
2. Sweep τ over the empirical D quantiles from p50 to p95.
3. For each candidate τ, compute expected total cost:

$$\text{Cost}(\tau) = \underbrace{\text{WAPE}(\tau)}_{\text{accuracy}} + \lambda \cdot \underbrace{\text{trigger\_rate}(\tau)}_{\text{compute}}$$

4. Select the τ minimizing Cost, with λ documented and fixed in advance.
5. Report the full sweep curve, not just the winner.

This makes τ a defensible optimization result rather than a demo-tuning artifact, and it directly addresses the risk that a reviewer reads the threshold as post-hoc.

### 4.4 Known limitation — state this in the paper

D measures **spread, not correctness**. Four agents can agree confidently and be uniformly wrong, producing D ≈ 0 with large error. The mechanism can therefore only ever detect *disputed* uncertainty, never *shared blind spots*. The evaluation must report the low-D/high-error quadrant explicitly rather than letting the aggregate correlation hide it.

---

## 5. Real-Time Strategy

RetailSense is a **hybrid real-time decision system**:

| Component | Status |
|---|---|
| M5 sales | Real historical data, chronologically replayed |
| Weather | Live/current external API (as-of aligned) |
| Google Trends | Near-real-time external signal, snapshotted |
| Calendar | Known-in-advance data |
| Inventory state | Simulated |
| Replay clock | Simulated |
| Restocking decision | Generated by RetailSense |

It does **not** claim access to a retailer's private live POS feed. This phrasing is non-negotiable (`rules.md` §8).

---

## 6. Architecture Decision Records

### ADR-001: Hybrid ML + LLM rather than LLM-only forecasting

**Status:** Accepted

**Context.** The system needs both reliable point forecasts and the ability to reason about unusual context. LLMs are weak, high-variance numeric forecasters; gradient-boosted trees cannot interpret a heat wave they have never seen.

**Decision.** Numerical models provide the quantitative backbone. LLMs handle context interpretation, conflict analysis, deliberation, and explanation. The LLM never emits an unconstrained demand number as the primary forecast.

**Options considered.**

| Option | Complexity | Reliability | Research value |
|---|---|---|---|
| A: LLM-only forecasting | Low | Poor — high variance, poor calibration | Low — well-documented weakness |
| B: ML-only ensemble | Low | Good | Low — no agentic contribution |
| C: Hybrid (chosen) | Medium | Good | High — isolates the deliberation effect |

**Consequences.** Easier: results are stable and defensible; the LLM's contribution is isolated and measurable. Harder: two systems to maintain; context agents need a principled way to produce comparable forecasts (see `agent.md` §4). Revisit if: LLM numeric calibration improves substantially.

---

### ADR-002: One deliberation round in the MVP

**Status:** Accepted

**Context.** Multi-round deliberation could converge better, but each round multiplies cost, latency, and confounds.

**Decision.** Exactly one round.

**Consequences.** Easier: clean causal attribution — any change is attributable to a single intervention; bounded cost. Harder: cannot claim convergence properties. Revisit: as explicit future work (`prd.md` FR-15).

---

### ADR-003: Normalized (scale-free) disagreement score

**Status:** Accepted — supersedes the raw-variance formulation in v1

**Context.** Raw weighted variance scales with item volume, so a single τ cannot serve a mixed item set.

**Decision.** Use the confidence-weighted coefficient of variation (§4.1).

**Consequences.** Easier: one τ across all items; cross-item comparability. Harder: unstable for very-low-volume items where the denominator approaches zero — mitigated by the ε term and by filtering items below a minimum average daily volume during subset selection.

---

### ADR-004: SQLite over Postgres

**Status:** Accepted

**Context.** Single-user experimental workload; reproducibility and portability matter more than concurrency.

**Decision.** SQLite for the evaluation store.

**Consequences.** Easier: zero setup, file-level reproducibility, database ships with the repo. Harder: no concurrent writers — parallel experiment runs must write to separate DB files and be merged.

---

### ADR-005: LangGraph for orchestration

**Status:** Accepted, with a caveat

**Context.** The pipeline needs conditional branching (the τ decision) and state passing between agents.

**Decision.** LangGraph, because conditional edges map directly onto the disagreement branch and the graph is inspectable.

**Consequences.** Easier: the routing logic is declarative and visualizable, which is useful for the paper figure. Harder: framework churn is a real risk on a 16-week timeline. **Mitigation:** all agent logic lives in plain Python functions with the framework used only as a thin orchestration wrapper, so the system remains runnable if LangGraph is dropped. This is a deliberate hedge — do not let framework abstractions leak into agent code.

---

### ADR-006: Evaluation store is the sole holder of ground truth

**Status:** Accepted

**Context.** Leakage is the dominant experimental risk and discipline alone is insufficient.

**Decision.** Actual future demand exists only in the evaluation store. Agent-facing code paths have no read access to it. The audit gate enforces this structurally.

**Consequences.** Easier: leakage becomes an architectural impossibility rather than a review burden. Harder: slightly more plumbing for evaluation joins.

---

## 7. Failure Modes and Handling

| Failure | Detection | Handling |
|---|---|---|
| Weather API unavailable | HTTP error / timeout | Fall back to cached snapshot; mark `data_availability: degraded`; agent lowers confidence |
| Trends rate-limited | 429 | Use last snapshot with staleness flag; if stale beyond threshold, agent abstains |
| Agent returns invalid JSON | Schema validation | One retry with a repair prompt; then abstain and log |
| Agent abstains | `abstained: true` | Excluded from consensus; D computed over remaining agents; run flagged |
| Fewer than 2 agents available | Count check | Run marked incomplete; no deliberation possible; logged separately |
| LLM timeout during deliberation | Timeout | Keep pre-deliberation forecast; log `deliberation_failed` |
| D undefined (single agent) | Guard | Skip routing; fast path by definition |

**Universal rule:** a failed agent never becomes a zero forecast (`rules.md` §2.7). Silent zero-filling would bias every downstream metric.

---

## 8. Data Flow Timing

```text
t-1  │ Ingest weather forecast for t, Trends snapshot, calendar for t
     │ Build features from sales ≤ t-1
     │ ── LEAKAGE GATE ──
     │ Run 4 agents → compute D → route → final forecast
     │ Apply inventory policy → emit action
     │ Advance simulator (place order, start lead-time clock)
─────┼──────────────────────────────────────────────────────────
 t   │ Reveal actual demand (evaluation store only)
     │ Apply demand to inventory; record stockout/overstock
     │ Log run row with realized error
```

---

## 9. Component Interfaces

Kept narrow so each layer is independently replaceable (`prd.md` NFR: modularity).

```python
# Every forecasting agent
def forecast(features: FeatureRow, context: Context) -> AgentOutput: ...

# Deliberation-capable agents
def revise(original: AgentOutput, critique: CriticReport,
           peers: list[AgentOutput]) -> AgentOutput: ...

# Disagreement — pure function, no side effects
def disagreement(outputs: list[AgentOutput]) -> float: ...

# Consensus
def consensus(outputs: list[AgentOutput]) -> Forecast: ...

# Inventory policy — deterministic
def decide(forecast: Forecast, state: InventoryState) -> Decision: ...
```

Any of these five can be swapped without touching the others. That is what allows the ablation studies in `phases.md` Phase 5 to run as configuration changes rather than code rewrites.
