# RetailSense — Task Backlog

**Version:** 1.0 (new in v2 doc set)
**Purpose:** The executable work breakdown. Every task has an ID, a dependency, and a verifiable done-condition.
**Related docs:** `phases.md` (why), this file (what and in what order)

---

## How to Use This File

- Work top to bottom; dependencies are stated explicitly
- A task is done when its **done-when** condition is verifiable by someone else, not when it feels finished
- 🔴 = blocking gate. Do not proceed past it on a failure — diagnose instead
- Estimates are for a single student working part-time

---

## Phase 0 — Setup (Week 0)

| ID | Task | Dep | Est | Done when |
|---|---|---|---|---|
| S-01 | Create repo, venv, pinned `requirements.txt`, directory skeleton per `stack.md` §3 | — | 2h | `pip install -r requirements.txt` succeeds clean; `pytest` collects 0 tests without error |
| S-02 | Download M5; inspect `sales_train_evaluation`, `calendar`, `sell_prices` | S-01 | 2h | Row counts and date ranges documented in README |
| S-03 | **Select item subset** (OQ1): 1 store, 20–50 items, min average daily volume, weather-sensitive categories over-represented | S-02 | 4h | `config/items_50.txt` committed with written selection rationale |
| S-04 | Extract and commit the subset | S-03 | 1h | Subset CSVs in `data/processed/`, under 10MB |
| S-05 | Define train/val/test splits, time-based, no overlap | S-04 | 2h | Split dates in `config/base.yaml`; boundaries asserted in a test |
| S-06 | Implement agent contract as Pydantic models (`src/agents/base.py`) | S-01 | 3h | `test_schema.py` passes: valid accepted, invalid rejected |
| S-07 | Store → lat/lon mapping for CA/TX/WI | S-02 | 1h | `config/stores.yaml` committed |
| S-08 | **Trends keyword mapping** (OQ2): map M5 departments to defensible search terms | S-02 | 4h | Mapping table committed with rationale per row — **or** a written decision to cut the Trend Agent |
| S-09 | LLM client wrapper, provider-agnostic, schema-validated | S-06 | 3h | Returns validated dict; retries once on schema failure; model read from config |

---

## Phase 1 — Forecasting Agents (Weeks 1–3)

### Data and features

| ID | Task | Dep | Est | Done when |
|---|---|---|---|---|
| D-01 | Data loader: subset → long format with `(date, store, item, sales, price, events)` | S-05 | 4h | Returns a tidy frame; row count asserted in a test |
| D-02 | Feature engineering: lags 1/7/14/28, rolling mean+std 7/28, DOW, week-of-year, price ratio, SNAP | D-01 | 6h | Feature frame builds for the full subset; no NaN in rows past the warmup window |
| D-03 | 🔴 **Leakage audit gate** (`src/data/leakage_audit.py`) | D-02 | 6h | For every feature column, max source timestamp < prediction timestamp; raises and aborts on violation |
| D-04 | `test_leakage.py`: no-future-features, actuals-isolated, weather-is-forecast | D-03 | 4h | All three pass; deliberately-leaked fixture fails as expected |
| D-05 | Naive anchor: 28-day same-DOW median | D-02 | 2h | Anchor computed for every `(t, store, item)`; unit-tested |

**D-03 is built before any agent.** An agent trained on leaked features must be discarded, and discovering that in week 8 costs the project far more than the six hours spent here.

### Agents

| ID | Task | Dep | Est | Done when |
|---|---|---|---|---|
| A-01 | Historical Agent: LightGBM train + predict | D-03 | 8h | Beats seasonal-naive on validation WAPE |
| A-02 | Historical confidence from out-of-fold residuals, volatility-bucketed | A-01 | 4h | Confidence varies across runs; not constant; range within [0.3, 0.95] |
| A-03 | Calendar Agent: learned event/DOW multipliers | D-02 | 6h | Multipliers computed from training split only; sanity-checked against known holidays |
| A-04 | Calendar Agent LLM layer + prompt v1 | A-03, S-09 | 5h | Emits valid schema; reasoning references actual event names |
| A-05 | Calendar confidence rules per `agent.md` §5.4 | A-04 | 2h | Confidence responds to event rarity and overlap |
| A-06 | Weather Agent skeleton on cached sample weather | D-05, S-09 | 6h | Produces anchor × (1+adj) with the clip applied |
| A-07 | Per-agent evaluation harness: MAE/WAPE/calibration curve | A-01, A-04 | 5h | One command produces the per-agent metrics table |
| A-08 | 🔴 **Pairwise forecast correlation check** | A-07 | 2h | No agent pair above ~0.95. **On failure: stop and redesign an agent** |

---

## Phase 2 — External Context (Weeks 4–5)

| ID | Task | Dep | Est | Done when |
|---|---|---|---|---|
| E-01 | Open-Meteo client using the **historical forecast archive** endpoint | S-07 | 5h | Returns the forecast issued at t-1 for t; a test asserts the observation endpoint is never called |
| E-02 | Weather snapshot cache to `data/external/weather/` | E-01 | 3h | Pipeline runs fully offline from committed snapshots |
| E-03 | Weather anomaly features vs. 30-day seasonal norm | E-02 | 4h | Anomaly columns present; distribution sanity-checked |
| E-04 | Learn per-category weather sensitivity coefficients on training split | E-03, A-01 | 6h | Coefficients + confidence intervals stored in config; documented |
| E-05 | Complete Weather Agent (rules + LLM, clipped) | E-04, A-06 | 5h | Schema-valid; confidence responds to horizon and staleness |
| E-06 | pytrends client with backoff and per-window snapshotting | S-08 | 6h | Never re-queries a cached window; retrieval timestamp stored |
| E-07 | 🔴 Trends leakage guard: window ends at t-1, snapshot immutable | E-06 | 3h | Test asserts no query window includes ≥ t |
| E-08 | Trend Agent (rules + LLM, clipped, structurally low confidence) | E-07 | 5h | Schema-valid; confidence typically below other agents |
| E-09 | Re-run full leakage audit with external signals | E-05, E-08 | 2h | Zero violations |
| E-10 | History-only vs. context-aware comparison | E-09 | 4h | Documented difference with a table |
| E-11 | Missing-signal handling verified end-to-end | E-09 | 3h | Agent abstains; D computed over remaining agents; **never zero-filled** |

---

## Phase 1.5 — RQ2 Smoke Test 🔴 (End of Week 5)

| ID | Task | Dep | Est | Done when |
|---|---|---|---|---|
| R-01 | Minimal disagreement function (normalized, 2 agents) | A-08 | 3h | Scale-invariance test passes |
| R-02 | Run both agents across the full validation split, log `(D, \|error\|)` | R-01, E-10 | 4h | Results table written to SQLite |
| R-03 | Compute Spearman ρ; quintile-bucket mean error | R-02 | 2h | ρ and the bucket table recorded |
| R-04 | Scatter plot with fitted trend | R-03 | 2h | Figure saved to `results/` |
| R-05 | 🔴 **Written go/pivot decision** committed to the repo | R-04 | 1h | Decision file states ρ, the rule applied, and the chosen path per `phases.md` Phase 1.5 |

**Do not skip R-05.** Writing the decision down before proceeding is what prevents an unconscious slide into assuming the mechanism works.

---

## Phase 3 — Disagreement and Deliberation (Weeks 6–10)

| ID | Task | Dep | Est | Done when |
|---|---|---|---|---|
| G-01 | Full normalized disagreement function, 4 agents, pure | R-05 | 4h | `test_disagreement.py` passes: scale invariance, identical→0, abstention handling |
| G-02 | Weighted consensus + prediction interval | G-01 | 4h | Interval width responds to spread and to mean uncertainty |
| G-03 | Build the full `(D, error)` validation dataset, 4 agents | G-02 | 5h | Complete table across the validation split |
| G-04 | 🔴 **τ calibration sweep** per `architecture.md` §4.3 | G-03 | 6h | Sweep curve saved; τ written to config **with its calibration run ID** |
| G-05 | Critic Agent: T1–T5 conflict taxonomy + prompt | G-04 | 10h | Classifies conflicts on held-out examples; emits valid `critic_reports` schema |
| G-06 | Per-agent challenge generation | G-05 | 5h | Challenges are agent-specific and reference that agent's stated factors |
| G-07 | `resolvable: false` → widen-interval branch | G-05, G-02 | 4h | Path is exercised and tested; interval widens by the configured factor |
| G-08 | Revision protocol with per-agent bounds (`agent.md` §7.4) | G-06 | 8h | Bounds enforced; `position_held` recorded |
| G-09 | Re-consensus over revised outputs using the same consensus function | G-08 | 2h | Identical function verified by test |
| G-10 | LangGraph wiring — thin wrapper only | G-09 | 6h | Graph runs end-to-end; agent logic remains callable without the graph |
| G-11 | Log initial + revised separately | G-08 | 3h | `agent_predictions` populated with both; single-query before/after works |
| G-12 | Hold-rate diagnostic per agent | G-11 | 2h | **If any agent's hold rate is ~0%, rewrite that deliberation prompt** |
| G-13 | 🔴 **Freeze all prompts**; tag the commit | G-12 | 1h | Prompts committed under `prompts/v1/`; git tag applied |
| G-14 | Compare fast-only / always-deliberate / selective on validation | G-13 | 5h | Three-way table with error, latency, and LLM calls |

---

## Phase 4 — Inventory Layer (Weeks 11–13)

| ID | Task | Dep | Est | Done when |
|---|---|---|---|---|
| I-01 | Inventory simulator: stock, on-order pipeline, lead time, demand application | G-14 | 8h | Multi-day replay conserves units; no negative stock without a recorded stockout |
| I-02 | Safety stock from prediction interval (resolves OQ4) | I-01, G-02 | 4h | Wider interval → higher safety stock, verified |
| I-03 | Reorder point + RESTOCK/HOLD/REDUCE logic | I-02 | 5h | Matches the worked example in `design.md` §5.3 exactly |
| I-04 | Order quantity as a pure function | I-03 | 3h | `test_policy.py::test_determinism` passes |
| I-05 | 🔴 `test_llm_cannot_set_quantity` | I-04 | 2h | Passes; no code path exists from LLM output to quantity |
| I-06 | Cost model: holding, stockout, total | I-03 | 4h | Costs computed per run and aggregated |
| I-07 | Apply the identical simulator to all six arms | I-06 | 4h | Same simulator object used by every experiment script |
| I-08 | End-to-end test-split replay | I-07 | 6h | Runs unattended to completion; all tables populated |

---

## Phase 5 — Evaluation and Package (Weeks 14–16)

### Week 14 — arms

| ID | Task | Dep | Est | Done when |
|---|---|---|---|---|
| V-01 | ARIMA / seasonal-naive arm | I-08 | 5h | Metrics logged to `evaluation_results` |
| V-02 | XGBoost arm | I-08 | 3h | Logged |
| V-03 | Single-agent arm | I-08 | 4h | Logged |
| V-04 | Weighted consensus arm (no deliberation) | I-08 | 3h | Logged |
| V-05 | Always-on deliberation arm | I-08 | 4h | Logged with full LLM cost |
| V-06 | RetailSense arm | I-08 | 4h | Logged |
| V-07 | Multi-seed reruns (≥ 3 seeds per arm) | V-01…V-06 | 8h | Variance reported per arm |

### Week 15 — analysis

| ID | Task | Dep | Est | Done when |
|---|---|---|---|---|
| V-08 | Ablation: drop one agent at a time | V-07 | 6h | Table of per-agent contribution |
| V-09 | Ablation: vary τ across the sweep | V-07 | 4h | Performance-vs-τ curve |
| V-10 | Ablation: revise without the critic | V-07 | 4h | Isolates the critic's contribution — this is what shows the critic is not decorative |
| V-11 | Disagreement-error calibration analysis | V-07 | 5h | Spearman ρ, quintile table, scatter |
| V-12 | 🔴 **Low-D/high-error quadrant analysis** | V-11 | 3h | Explicitly quantified and reported (`architecture.md` §4.4) |
| V-13 | Statistical testing across seeds | V-07 | 4h | No improvement claimed without it (`rules.md` §5.6) |
| V-14 | Cost/latency analysis for RQ3 | V-05, V-06 | 3h | Selective vs. always-on call counts and latency |

### Week 16 — package

| ID | Task | Dep | Est | Done when |
|---|---|---|---|---|
| P-01 | Streamlit main view | V-06 | 6h | Renders a live run per `design.md` §7.1 |
| P-02 | Explainability view | P-01 | 5h | Shows critic report and before/after with `position_held` |
| P-03 | Evaluation view | P-01, V-11 | 5h | Includes the RQ2 scatter and the τ sweep curve |
| P-04 | Paper figures and tables | V-13 | 8h | All figures regenerate from committed scripts |
| P-05 | **Limitations section, written first** | V-12 | 4h | Covers D-measures-spread-not-correctness, anchor coupling, Trends proxy, single dataset, single horizon |
| P-06 | README with reproduction instructions | P-04 | 3h | A clean clone reproduces one reported number end-to-end |
| P-07 | Final reproducibility audit (`stack.md` §8) | P-06 | 3h | Every checklist item ticked |

**P-05 is scheduled before the results section is finalized.** Writing limitations while results are still being interpreted keeps the framing honest, rather than retrofitting caveats around a conclusion already committed to.

---

## Standing Rules for Every Task

Derived from the karpathy coding guidelines, applied throughout:

1. **Simplest thing that works.** No speculative abstraction. If a module is 200 lines and could be 50, rewrite it.
2. **Surgical changes.** Each edit traces to a specific task ID. Don't improve adjacent code while passing through.
3. **Verifiable done-conditions.** "Add the disagreement function" → "scale-invariance test passes." If you cannot write the check, the task is not defined yet.
4. **Surface assumptions.** When a choice has two defensible options, write both in the commit message and pick one explicitly.
5. **Commit config with results.** A number without its config is not a result.
6. **Never silently zero-fill.** Missing evidence → abstention → logged. This is the failure mode most likely to quietly corrupt every metric in the project.
