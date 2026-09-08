# CLAUDE.md — RetailSense

Persistent context for Claude Code. Read automatically at session start.

---

## What this project is

RetailSense is a **research capstone**, not a product. It tests whether disagreement between specialized forecasting agents predicts forecast error, and whether triggering deliberation selectively on high-disagreement cases beats always deliberating or never deliberating.

The deliverable is **defensible experimental results**, not a polished app. A beautiful dashboard with unvalidated results is a failed project. An ugly script that produces an honest negative result is a successful one.

---

## Specification documents — read before implementing

The `docs/` folder is the specification. Do not invent behavior that contradicts it.

| Doc | Read when |
|---|---|
| `docs/memory.md` | Start here — orientation and the compact source of truth |
| `docs/tasks.md` | **Every session.** The task backlog with IDs, dependencies, done-conditions |
| `docs/agent.md` | Implementing or debugging any agent, the critic, or deliberation |
| `docs/architecture.md` | System structure, disagreement math, ADRs, failure modes |
| `docs/rules.md` | Any question of the form "am I allowed to..." |
| `docs/design.md` | Inventory policy math, DB schema, dashboard spec |
| `docs/stack.md` | Repo layout, dependencies, testing, what to do when something breaks |
| `docs/phases.md` | Timeline, gates, contingency |
| `docs/prd.md` | Requirements and acceptance criteria |

**Before starting any task, read the doc sections it references.** Do not work from memory of an earlier session.

---

## Working agreement

### Scope
- Implement **one task ID at a time** from `docs/tasks.md`. State which one you are starting.
- Do not implement tasks ahead of their dependencies.
- Do not add features, abstractions, config options, or error handling that no task asked for.
- If a task seems to need something outside its scope, say so and ask — do not silently expand.

### Before writing code
State briefly:
1. Which task ID this is
2. Which doc sections you read
3. Your approach in 2–3 sentences
4. Any assumption you had to make

If two approaches are defensible, name both and pick one explicitly rather than choosing silently.

### After writing code
1. Run the tests
2. State the done-condition from `tasks.md` and whether it is met
3. Stop. Do not roll into the next task unprompted.

### Changes to existing code
- Every changed line must trace to the current task ID
- Do not refactor, reformat, or "improve" adjacent code you happen to be near
- Match existing style even if you would write it differently
- If you notice unrelated dead code, mention it — do not delete it

### Simplicity
If a module is 200 lines and could be 50, rewrite it. No speculative flexibility. Ask: would a senior engineer call this overcomplicated?

---

## Non-negotiable rules

These come from `docs/rules.md`. Violating one invalidates results.

**Data integrity**
- No future-data leakage, ever. Every prediction uses only information available at the prediction timestamp.
- Weather comes from Open-Meteo's **historical forecast archive** — the forecast that was *issued*. Never the observation endpoint. Using observed weather feels like real data and is a direct leakage violation.
- Google Trends windows end at `t-1`, are snapshotted once with a retrieval timestamp, and are **never re-queried**. Trends renormalizes against the query window, so re-querying a past window injects future information.
- Actual demand lives only in the evaluation store. Agent-facing code has no read path to it.
- A missing or failed signal is recorded as missing. **Never zero-filled. Never forward-filled.**

**Agents**
- A failed or abstaining agent is **never converted to a zero forecast**. It is excluded from consensus and the run is flagged.
- Context agents anchor on the shared naive baseline (28-day same-DOW median), **never** on the Historical Agent's output.
- The LLM never produces the primary demand number and never sets the order quantity.
- Agent outputs are schema-validated at the orchestrator boundary. Invalid → one repair retry → abstain.

**Experiment integrity**
- τ is calibrated on the validation split by the documented sweep in `architecture.md` §4.3. Never by eye. Never on test data. Never adjusted after seeing test results.
- Prompts freeze at the start of Phase 3. A prompt change afterward invalidates every cross-arm comparison.
- No number affecting a result may be hardcoded. Config or nothing.
- No reported result comes from a notebook.
- No improvement is claimed without multi-seed evidence.

**If a rule and a deadline conflict, the rule wins.** Say so rather than quietly cutting a corner.

---

## Mandatory tests

Never skip these for time. They are the project's defense.

| Test | Asserts |
|---|---|
| `test_leakage.py::test_no_future_features` | No feature's source timestamp ≥ prediction timestamp |
| `test_leakage.py::test_actuals_isolated` | Agent code paths cannot read the actuals table |
| `test_leakage.py::test_weather_is_forecast` | The observation endpoint is never called |
| `test_disagreement.py::test_scale_invariance` | D unchanged when all forecasts scale by a constant |
| `test_disagreement.py::test_identical_forecasts` | Identical forecasts → D = 0 |
| `test_policy.py::test_determinism` | Same inputs → same action and quantity, always |
| `test_policy.py::test_llm_cannot_set_quantity` | No code path from LLM output to order quantity |
| `test_schema.py::test_invalid_agent_output` | Invalid output → abstain, never a zero forecast |

---

## Gates — stop and report on failure

Do not proceed past a failing gate. Diagnose and tell me.

| Gate | Task | Failure means |
|---|---|---|
| Leakage audit | D-03/D-04 | Nothing built on top of this is valid |
| Pairwise agent correlation < 0.95 | A-08 | Agents share an evidence space; disagreement is noise. Redesign an agent |
| RQ2 smoke test | R-05 | The core assumption may not hold. **Stop and discuss the pivot** — do not proceed as if it worked |
| τ calibration | G-04 | Trigger rate outside 10–30% means τ is miscalibrated. Rerun calibration; never hand-adjust |
| Hold rate per agent | G-12 | Near 0% means the deliberation prompt is coercive. Rewrite it |

---

## Commands

```bash
source .venv/bin/activate
pytest                              # all tests
pytest tests/test_leakage.py -v     # leakage suite
python -m src.data.leakage_audit --config config/base.yaml
python experiments/run_retailsense.py --config config/base.yaml --seed 42
streamlit run dashboard/app.py
```

---

## Things that are easy to get wrong here

1. **Reaching for the weather observation endpoint** because it is simpler and returns cleaner data. It is leakage.
2. **Zero-filling a missing signal** because it keeps the pipeline running. It silently biases every downstream metric.
3. **Anchoring context agents on the Historical Agent's forecast** because it is the better baseline. It correlates all forecasts by construction and collapses the disagreement score to near zero, which quietly destroys the entire research contribution.
4. **Nudging τ** to get a nicer-looking trigger rate. It makes the result indefensible.
5. **Writing a deliberation prompt that pressures agents to move.** If agents never hold their position, deliberation is measuring social compliance, not evidence.
6. **Building the dashboard early** because it is satisfying. It is Phase 5 for a reason.
