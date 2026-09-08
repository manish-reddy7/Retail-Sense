# RetailSense — Product Requirements Document

**Version:** 2.0
**Status:** Scope frozen
**Document owner:** Project author (single-student capstone)
**Related docs:** `architecture.md`, `agent.md`, `design.md`, `stack.md`, `phases.md`, `tasks.md`, `rules.md`, `memory.md`

---

## 1. Product Overview

**Product:** RetailSense
**Full title:** *RetailSense: A Disagreement-Triggered Multi-Agent Framework for Real-Time Inventory Demand Forecasting and Restocking Decisions*

RetailSense is a hybrid forecasting and inventory decision-support system. Specialized agents independently forecast demand from different evidence sources — historical sales, weather, consumer search interest, and calendar events. An orchestrator measures how much those forecasts disagree. Low disagreement takes a fast consensus path. High disagreement triggers exactly one structured deliberation round before the final forecast is converted into a `RESTOCK` / `HOLD` / `REDUCE` decision.

**One sentence for a reviewer:**
> RetailSense measures disagreement between specialized forecasting agents and spends extra reasoning only when they conflict, then turns the resulting forecast into an inventory action.

---

## 2. Problem Statement

Retail inventory planners must commit to stock levels before demand is known. Historical sales patterns are the standard basis for that commitment, but demand shifts with weather, consumer interest, holidays, and events — conditions the historical pattern has not seen. When these signals conflict with history, the planner has no principled way to know whether to trust the baseline or the context.

The cost is two-sided and measurable:

```text
Understocked                    Overstocked
Demand = 1,000                  Demand =   600
Stock  =   600                  Stock  = 1,200
→ 400 lost sales                → 600 units held
→ lost margin, lost customer    → holding cost, markdown, waste
```

Existing multi-agent forecasting systems either always run expensive deliberation, or never do. Neither adapts reasoning effort to the situation. RetailSense addresses that gap.

---

## 3. Research Questions

### RQ1 — Primary
> Does disagreement-triggered deliberation among heterogeneous forecasting agents improve demand forecasting and inventory restocking decisions compared with statistical forecasting, single-agent forecasting, simple multi-agent consensus, and always-on deliberation?

### RQ2 — Mechanism validation (load-bearing)
> Does inter-agent disagreement correlate with actual forecast error strongly enough to serve as an actionable uncertainty signal?

### RQ3 — Efficiency
> Does selective deliberation achieve comparable or better accuracy than always-on deliberation at materially lower LLM cost and latency?

**RQ2 is the project's load-bearing assumption.** If disagreement does not predict error, selective triggering has no basis. RQ2 is therefore tested early (see `phases.md`, Phase 1.5) rather than discovered at the end. A negative RQ2 result is a publishable finding, not a project failure — see `rules.md` §5.

---

## 4. Goals

| # | Goal | How we know it succeeded |
|---|---|---|
| G1 | Specialized multi-agent forecasting | 3–4 agents each produce independent forecasts with confidence, each individually evaluated against ground truth |
| G2 | External-context adaptation | Context-aware forecast measurably differs from history-only forecast, with zero leakage violations in the audit |
| G3 | Calibrated disagreement triggering | Threshold τ selected on validation data by a documented rule, not by eye |
| G4 | Closed-loop inventory decisions | End-to-end replay produces actions and realized stockout/overstock outcomes |
| G5 | Rigorous comparative evaluation | All six arms run on identical data splits with multi-seed results |

---

## 5. Non-Goals

| # | Non-goal | Why out of scope |
|---|---|---|
| NG1 | Live proprietary retailer POS integration | No access; not required for the research question |
| NG2 | Multi-echelon supply-chain optimization | Separate research problem; multiplies complexity |
| NG3 | Reinforcement learning inventory control | Would take the entire timeline on its own |
| NG4 | Dynamic pricing | Changes the demand-generating process; confounds the experiment |
| NG5 | Donation / sustainability optimization | Worthy, but a different objective function |
| NG6 | 10+ agents | Disagreement becomes uninterpretable; cost explodes |
| NG7 | Multi-round deliberation | One round isolates the effect; N rounds is a follow-up study |

---

## 6. Target Users

| Persona | What they need from RetailSense |
|---|---|
| Retail inventory planner | A stock action with a stated risk and a reason |
| Store manager | A quick read on whether tomorrow is unusual |
| Supply-chain analyst | Traceable evidence behind each recommendation |
| Researcher / evaluator | Reproducible experiments and honest metrics |

---

## 7. User Stories

**Forecasting**
- As an inventory planner, I want to select a product, store, and horizon so that I get a demand forecast for a specific decision I have to make.
- As an inventory planner, I want to see each agent's forecast and confidence so that I understand what evidence drives the number.
- As a store manager, I want a plain-language reason when the system flags unusual conditions so that I can sanity-check it against what I know about my store.

**Deliberation transparency**
- As an analyst, I want to see whether disagreement was high or low so that I know how much the system trusted its own consensus.
- As an analyst, I want to see the pre- and post-deliberation forecasts side by side so that I can judge whether deliberation actually changed anything.
- As an analyst, I want the critic's conflict summary so that disagreement is interpretable rather than just a number.

**Inventory action**
- As a planner, I want a `RESTOCK` / `HOLD` / `REDUCE` recommendation with an order quantity so that I can act without doing the arithmetic myself.
- As a planner, I want the stockout risk stated so that I can override the system when my risk tolerance differs.

**Evaluation**
- As a researcher, I want every run logged with its configuration so that I can reproduce any reported number.
- As a researcher, I want to plot disagreement against realized error so that I can test RQ2 directly.
- As an evaluator, I want baseline arms run on the identical split so that comparisons are fair.

---

## 8. Requirements

### 8.1 Must-Have (P0)

**FR-01 — Chronological historical replay**
The system replays M5 sales in date order and hides all demand at or after the prediction timestamp until the forecast is committed.

*Acceptance criteria*
- [ ] Given a prediction at date `t`, when any agent requests features, then no field derived from data at or after `t` is returned
- [ ] A leakage audit script runs over the feature matrix and exits non-zero on any violation
- [ ] Actual demand for `t` is written to the evaluation store only after the forecast row is committed

**FR-02 — External signal ingestion**
The system ingests weather, search interest, and calendar data aligned to the prediction timestamp.

*Acceptance criteria*
- [ ] Weather uses the forecast that would have been available at `t`, not the observed outcome
- [ ] Google Trends values are snapshotted with a retrieval date and never silently revised (see `rules.md` §1.8)
- [ ] Missing signals are recorded as explicitly missing, never zero-filled

**FR-03 — Specialized agent forecasting**
Each agent returns the shared schema defined in `agent.md` §3.

*Acceptance criteria*
- [ ] All agent outputs validate against the JSON schema before entering the orchestrator
- [ ] A schema-invalid output is retried once, then recorded as an agent failure — never coerced to zero demand
- [ ] Each agent is independently evaluable against ground truth

**FR-04 — Disagreement calculation**
The orchestrator computes a normalized, confidence-weighted disagreement score.

*Acceptance criteria*
- [ ] Score is scale-free so that high-volume and low-volume items are comparable
- [ ] Score is computed and logged for every run, including low-disagreement runs
- [ ] Score is reproducible from the logged agent outputs alone

**FR-05 — Conditional deliberation**
Below τ, fast consensus. At or above τ, one critic + revision round.

*Acceptance criteria*
- [ ] τ is loaded from configuration, never hardcoded in logic
- [ ] Deliberation runs at most one round per forecast
- [ ] Trigger decision and τ value are logged on every run

**FR-06 — Final forecast with uncertainty**
The system produces a point forecast and an uncertainty range after consensus or deliberation.

**FR-07 — Inventory decision**
The system converts forecast, uncertainty, current stock, lead time, and safety stock into `RESTOCK` / `HOLD` / `REDUCE` plus an order quantity computed by the policy, not by the LLM.

*Acceptance criteria*
- [ ] Order quantity is a deterministic function of policy inputs
- [ ] Given identical inputs, the same action is always produced
- [ ] The LLM cannot alter the order quantity

**FR-08 — Full traceability**
Every run logs agent forecasts (initial and revised), confidence, disagreement, deliberation status, critic output, final forecast, inventory state, action, actual demand, latency, and token cost.

### 8.2 Nice-to-Have (P1)

- **FR-09** Streamlit dashboard with main, explainability, and evaluation views
- **FR-10** Disagreement-vs-error calibration plot generated automatically per experiment
- **FR-11** Always-on deliberation control arm
- **FR-12** MLflow experiment tracking beyond flat-file logging

### 8.3 Future Considerations (P2)

- **FR-13** Second dataset (Corporación Favorita) validation
- **FR-14** Synthetic disruption stress tests (injected demand shocks)
- **FR-15** Multi-round adaptive deliberation
- **FR-16** Learned rather than rule-based inventory policy

P2 items are not built, but the architecture must not foreclose them — hence the modular agent contract and the pluggable inventory policy interface.

---

## 9. Success Metrics

### Leading indicators (visible within days of a working pipeline)
| Metric | Target |
|---|---|
| Agents producing schema-valid output | ≥ 99% of runs |
| Leakage audit violations | 0 |
| Deliberation trigger rate | 10–30% of runs (outside this band, τ is likely miscalibrated) |
| Spearman ρ between disagreement and absolute error | ≥ 0.3 for the mechanism to be considered actionable |

### Lagging indicators (end-of-project results)
| Metric | Success | Stretch |
|---|---|---|
| WAPE vs best single baseline | Comparable (within 2%) | 5%+ better |
| Stockout rate vs XGBoost baseline | Comparable | Lower at equal or lower holding cost |
| LLM calls vs always-on deliberation | ≥ 50% reduction | ≥ 70% reduction |
| Error reduction on deliberated subset | Any consistent improvement | Statistically significant across seeds |

**Reporting rule:** no improvement is claimed without multi-seed or statistical evidence (`rules.md` §5.6).

---

## 10. Non-Functional Requirements

| NFR | Requirement |
|---|---|
| Reproducibility | Any reported number regenerates from a committed config + fixed seed |
| No leakage | Enforced by automated audit, not by discipline alone |
| Explainability | Every action exposes structured evidence and, if deliberated, the conflict reason |
| Latency awareness | Fast path and deliberation path timed separately on every run |
| Modularity | Agents, disagreement function, inventory policy, and evaluation are independently swappable |
| Cost control | Token spend logged per run; total project LLM budget capped (see `stack.md` §7) |
| Feasibility | Full scope buildable by one student in 16 weeks |

---

## 11. Open Questions

| # | Question | Owner | Blocking? |
|---|---|---|---|
| OQ1 | Which M5 store/item subset (target: 1 store, 20–50 items, high-volume, weather-sensitive categories) | Author | **Yes** — blocks Phase 1 |
| OQ2 | Google Trends keyword mapping for M5 categories (M5 items are anonymized) | Author | **Yes** — blocks Trend Agent |
| OQ3 | Final LLM provider and model tier | Author | No — interface is provider-agnostic |
| OQ4 | Safety stock formula: fixed multiple vs. service-level-based (z·σ·√L) | Author | No — resolve by Phase 4 |
| OQ5 | Lead time: fixed 3 days vs. stochastic | Author | No — start fixed |

OQ2 is the sharpest practical risk: M5 item IDs are anonymized, so Trends keywords must be inferred from department/category labels. If a defensible mapping cannot be built, the Trend Agent is the first cut (`phases.md`, Contingency).

---

## 12. Timeline

16 weeks, single student. See `phases.md` for the full breakdown and `tasks.md` for the executable backlog.

```text
Weeks 1–3    Specialized forecasting agents
Weeks 4–5    External context integration
Week  5      ⚠ RQ2 SMOKE TEST — go/no-go on the core mechanism
Weeks 6–10   Disagreement + deliberation
Weeks 11–13  Inventory decision layer
Weeks 14–16  Evaluation, paper, demo, hardening
```

The week-5 smoke test is a deliberate schedule change from the original plan. It tests RQ2 with only two agents and a cheap proxy, so that a weak disagreement-error relationship is discovered with 11 weeks remaining rather than 6.

---

## 13. Explicitly Not Claimed

RetailSense does not claim to have invented demand forecasting, weather-aware forecasting, multi-agent systems, LLM time-series forecasting, or inventory optimization. The contribution is **calibrated disagreement-triggered selective deliberation and its empirical evaluation**. See `rules.md` §8.
