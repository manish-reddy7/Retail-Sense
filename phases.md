# RetailSense — Implementation Phases

**Version:** 2.0
**Timeline:** 16 weeks, single student
**Related docs:** `tasks.md` (executable backlog), `prd.md`, `rules.md`

---

## Timeline Overview

```text
Week  0     Phase 0  — Scope freeze and setup
Weeks 1–3   Phase 1  — Specialized forecasting agents
Weeks 4–5   Phase 2  — External context integration
Week  5     Phase 1.5 — ⚠ RQ2 SMOKE TEST (go/no-go gate)
Weeks 6–10  Phase 3  — Disagreement + deliberation
Weeks 11–13 Phase 4  — Inventory decision layer
Weeks 14–16 Phase 5  — Evaluation, paper, demo, hardening
```

### What changed from v1 and why

The v1 plan placed the first test of RQ2 — does disagreement actually predict error? — inside Phase 3, finishing week 10. That is the project's load-bearing assumption, and discovering it is weak with six weeks left would leave no room to adapt.

**Phase 1.5 moves that test to week 5**, using only two agents and a cheap proxy. It costs about three days. If the relationship is strong, the rest of the plan proceeds with confidence. If it is weak, there are eleven weeks left to pivot the framing toward *characterizing when disagreement is and is not informative* — which remains a publishable contribution. This is the highest-value change in the v2 document set.

---

## Phase 0 — Scope Freeze and Setup

**Duration:** 2–3 days (week 0)

### Work
- Freeze title, research questions, scope boundaries
- Select M5 subset: **1 store, 20–50 items**, filtered to items with sufficient volume that a normalized disagreement score is stable, and biased toward weather-sensitive categories (resolves `prd.md` OQ1)
- Build the store → lat/lon mapping for weather
- Draft the Trends keyword mapping table (resolves OQ2, or triggers the Trend Agent cut early)
- Set up repo, venv, pinned requirements, config structure
- Define and implement the agent output schema (Pydantic)
- Create time-based train/validation/test splits

### Exit criteria
- [ ] Repo initialized, dependencies pinned and installing cleanly
- [ ] M5 subset extracted and committed
- [ ] Splits defined and documented; no overlap
- [ ] Agent contract implemented and schema-tested
- [ ] OQ1 and OQ2 resolved or the Trend Agent formally cut

---

## Phase 1 — Specialized Multi-Agent Forecasting

**Duration:** Weeks 1–3

### Goal
Four agents producing independent, individually-evaluated forecasts on a shared contract.

### Work
1. M5 loading, cleaning, feature engineering (lags, rolling stats, price, promo)
2. **Build the leakage audit gate first** — before any agent, so no agent is ever built on leaked features
3. Historical Agent (LightGBM) with residual-based confidence
4. Naive anchor for context agents (`agent.md` §4)
5. Calendar Agent (learned multipliers + LLM interpretation) — built before Weather because M5 calendar data needs no external API
6. Weather Agent skeleton against cached sample weather
7. LLM client wrapper, prompt v1 for each agent
8. Evaluate every agent independently

### Exit criteria
- [ ] ≥ 3 agents produce schema-valid forecasts on the validation split
- [ ] Per-agent MAE/WAPE recorded
- [ ] Confidence calibration curve plotted per agent — no agent reports near-constant confidence
- [ ] **Pairwise forecast correlation computed** — no pair above ~0.95 (validates evidence separation, `agent.md` §9)
- [ ] Leakage audit passes on the full feature matrix

**Gate:** if two agents correlate above 0.95, stop and redesign one before proceeding. Building a disagreement mechanism on agents that see the same evidence measures nothing.

---

## Phase 2 — External Context Integration

**Duration:** Weeks 4–5

### Goal
Live/current external signals flowing in, timestamp-aligned, leak-free.

### Work
- Open-Meteo integration using the **historical forecast archive**, not observations (`rules.md` §1.3)
- Learn per-category weather sensitivity coefficients on the training split
- Build anomaly features (current vs. own seasonal norm) for weather and trends
- pytrends integration with per-window snapshotting and backoff
- Snapshot all external data to `data/external/` and commit
- Compare history-only vs. context-aware forecasts
- Re-run the leakage audit with external signals present

### Exit criteria
- [ ] Weather and Trends aligned to prediction timestamps
- [ ] All external data snapshotted, committed, reproducible offline
- [ ] Zero leakage violations with external signals included
- [ ] Context-aware vs. history-only comparison documented
- [ ] Missing-signal handling verified: agents abstain, never zero-fill

---

## Phase 1.5 — RQ2 Smoke Test ⚠ GO/NO-GO GATE

**Duration:** 2–3 days, end of week 5
**This is the most important gate in the project.**

### Goal
Answer, cheaply and early: *does disagreement between agents correlate with forecast error at all?*

### Work
1. Take the two agents already working (Historical + Calendar, or + Weather if ready)
2. Run them across the full validation split — no critic, no deliberation, no inventory layer
3. For every run, log `(D, |error|)`
4. Compute Spearman ρ between D and |error|
5. Bucket D into quintiles and tabulate mean absolute error per bucket
6. Plot the scatter with the fitted trend

### Decision rule

| Result | Interpretation | Action |
|---|---|---|
| ρ ≥ 0.3, monotone across buckets | Mechanism is sound | Proceed to Phase 3 as planned |
| 0.15 ≤ ρ < 0.3 | Weak but present | Proceed, but add a third agent before calibrating τ, and pre-register the weak-signal framing |
| ρ < 0.15 | Mechanism assumption not supported | **Pivot the framing** (see below). Do not proceed as if it worked |

### Pivot plan if ρ < 0.15
The project does not stop. It reframes to: *"Under what conditions does inter-agent disagreement carry information about forecast error, and when does it not?"*

That still requires the full system to be built, still yields all the comparative baselines, and produces an honest negative or conditional result — which `rules.md` §5.7 already commits to reporting. What it changes is the paper's claim and the emphasis of the evaluation: characterization rather than improvement. Discovering this at week 5 with eleven weeks left is the entire reason this phase exists.

### Exit criteria
- [ ] ρ computed and recorded with the scatter plot
- [ ] Quintile table produced
- [ ] Explicit written go/pivot decision committed to the repo

---

## Phase 3 — Disagreement Detection and Deliberation

**Duration:** Weeks 6–10

### Goal
The main research contribution, implemented and calibrated.

### Work
1. Implement the normalized disagreement function (pure, tested for scale invariance)
2. Build the full `(D, error)` validation dataset with all four agents
3. **Calibrate τ** by the documented sweep procedure (`architecture.md` §4.3) — never by eye
4. Implement the Critic Agent with the full T1–T5 conflict taxonomy (`agent.md` §6)
5. Implement the one-round deliberation protocol with per-agent revision bounds
6. Implement the `resolvable: false` → widen-interval branch
7. Log initial and revised forecasts separately; track hold rate per agent
8. **Freeze all prompts** — from this point, prompt changes invalidate cross-arm comparison
9. Compare fast-path-only, always-deliberate, and selective modes

### Exit criteria
- [ ] τ selected by documented procedure; sweep curve saved
- [ ] Deliberation trigger rate lands in the 10–30% band
- [ ] Error before/after deliberation reported **on the deliberated subset only**
- [ ] Latency and LLM-call delta measured between paths
- [ ] Hold rate per agent recorded and non-zero (if 0%, the deliberation prompt is coercive — rewrite it)
- [ ] All prompts frozen and committed

---

## Phase 4 — Closed-Loop Inventory Decision

**Duration:** Weeks 11–13

### Goal
Forecasts become actions with realized business outcomes.

### Work
- Inventory simulator: stock tracking, lead-time order pipeline, demand application
- Safety stock from the prediction interval (resolves OQ4)
- Reorder-point policy and RESTOCK/HOLD/REDUCE logic
- Cost model: holding, stockout, total
- **Apply the identical simulator to every arm** (`rules.md` §4.5) — a different policy per arm would confound the comparison entirely
- Log every action and realized result

### Exit criteria
- [ ] End-to-end replay runs on the test split without manual intervention
- [ ] Stockout rate, overstock units, and total cost computed per arm
- [ ] Policy determinism test passes
- [ ] LLM-cannot-set-quantity test passes

---

## Phase 5 — Evaluation and Publication Package

**Duration:** Weeks 14–16

### Work

**Week 14 — run all arms**
1. ARIMA / seasonal-naive baseline
2. XGBoost baseline
3. Single-agent baseline
4. Multi-agent weighted consensus, no deliberation
5. Always-on deliberation control
6. RetailSense (selective deliberation)

All on identical splits, multiple seeds.

**Week 15 — analysis and ablations**
- Ablations: remove one agent at a time; vary τ; disable the critic (revise without conflict analysis)
- Disagreement-error calibration analysis, including the **low-D/high-error quadrant** (`architecture.md` §4.4)
- Statistical testing across seeds
- Cost/latency analysis for RQ3

**Week 16 — package**
- Streamlit dashboard, three views
- Paper figures and tables
- Limitations and future work
- README and reproduction instructions

### Exit criteria
- [ ] All six arms reported on identical splits with multi-seed variance
- [ ] RQ1, RQ2, RQ3 each answered explicitly — including negatively if that is the result
- [ ] Ablations completed
- [ ] Working demo
- [ ] Reproducible from committed configs
- [ ] Limitations section written before the results section is finalized

---

## Contingency Plan

If the schedule slips, cut in this order:

```text
1. Google Trends / Trend Agent        ← most fragile, least essential
2. Second dataset                      ← already deferred
3. Always-on deliberation control arm  ← weakens RQ3 only
4. Ablation studies (keep at least one)
5. Dashboard polish (keep the evaluation view)
```

**Never cut:**
```text
Historical forecasting → disagreement detection → selective deliberation → honest evaluation
```

That chain is the project. Everything else is supporting evidence.

### Additional rules under time pressure
- Do not add a second dataset before the primary experiment is complete
- Do not add RL, dynamic pricing, or extra agents
- Do not skip the leakage audit to save time — an unaudited result is worth nothing
- Do not skip multi-seed runs; a single-seed improvement is not a result

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Disagreement does not predict error | Medium | **Critical** | Phase 1.5 gate at week 5; documented pivot |
| Data leakage invalidates results | Medium | **Critical** | Audit gate in the pipeline; isolated actuals; automated tests |
| Agents too correlated → D meaningless | Medium | High | Pairwise correlation gate at end of Phase 1 |
| pytrends breaks or rate-limits | High | Low | Snapshots; abstention; first to cut |
| Trends keyword mapping indefensible | Medium | Medium | Resolve in Phase 0; cut the agent early if not |
| LLM cost overrun | Low | Medium | Response caching, dev slice, budget cap in config |
| τ lands outside a sensible trigger band | Medium | Medium | Sweep procedure with cost function; report the curve |
| Deliberation changes nothing | Medium | Medium | Track hold rate; a null result is reportable |
| LangGraph churn | Low | Medium | Agent logic is framework-independent (ADR-005) |
| Scope creep | Medium | High | Frozen non-goals; contingency order |
