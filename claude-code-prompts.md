# RetailSense — Claude Code Prompts

Copy-paste prompts for driving implementation. Use the setup prompt once, then the session prompt repeatedly.

---

## 0. Repo setup (do this first, outside Claude Code)

```bash
mkdir retailsense && cd retailsense
git init
mkdir docs
# copy the 9 spec docs into docs/
# copy CLAUDE.md into the repo ROOT (not docs/)
git add . && git commit -m "docs: specification v2"
```

`CLAUDE.md` must be at the root. Claude Code reads it automatically every session, which is why the durable rules live there and not in the prompt.

---

## 1. Session-one prompt

Paste this to start.

```
This is RetailSense, a research capstone building a multi-agent demand
forecasting system. The full specification is in docs/ — nine markdown
files. CLAUDE.md at the root has the working agreement and the
non-negotiable rules.

Before writing any code:

1. Read docs/memory.md for orientation, then docs/tasks.md for the
   backlog, then docs/stack.md for the repo layout and dependencies.

2. Tell me back, in your own words and in under 200 words:
   - What the research question is and which assumption is load-bearing
   - What the disagreement score measures and what it does NOT measure
   - The three leakage hazards you must avoid
   - Why context agents anchor on a naive baseline rather than on the
     Historical Agent

3. Flag anything in the specification that is ambiguous, internally
   inconsistent, or that you think is a bad idea. I would rather hear
   this now than discover it in week 10. Do not be diplomatic about it.

Do not write code yet. After I confirm your understanding, we start
with task S-01.
```

Step 3 matters. A summary you agree with tells you little; an objection tells you whether the spec is actually implementable.

---

## 2. Per-task prompt

The workhorse. Use for every task.

```
Next task: [TASK-ID] from docs/tasks.md.

Read the doc sections that task references before starting.

Then:
1. State the task ID, its done-condition, and its dependencies
2. State your approach in 2-3 sentences and any assumption you made
3. Implement it — only it
4. Run the tests
5. Report whether the done-condition is met

Do not start the next task. Stop after step 5.
```

---

## 3. Gate prompts

### Leakage audit (after D-03/D-04)

```
Before we go further: audit the entire pipeline for future-data leakage.

Check every path by which information from time >= t could reach a
forecast for t:
- Feature engineering (lags, rolling windows, boundary conditions)
- The weather client — confirm we call the historical FORECAST archive,
  never the observation endpoint
- The Trends client — confirm windows end at t-1 and snapshots are
  never re-queried
- Train/val/test split boundaries
- Any join that could pull a future row

For each, show me the code path and your verdict. Then write a
deliberately-leaked test fixture and confirm the audit catches it.

Be adversarial. Assume leakage exists and find it.
```

### Agent independence (A-08)

```
Run the pairwise correlation check across all agent forecasts on the
validation split.

Report the full correlation matrix. For any pair above 0.90, explain
what evidence they share and whether that sharing is structural
(the naive anchor) or a design error.

Per docs/rules.md §2.2, any pair above ~0.95 means one agent must be
cut or redesigned. Do not proceed to Phase 2 until this is resolved —
tell me your recommendation.
```

### RQ2 smoke test (R-05) — the important one

```
Run Phase 1.5, the RQ2 smoke test, per docs/phases.md.

Two agents only. No critic, no deliberation, no inventory layer.

1. Run across the full validation split, logging (D, |error|) per run
2. Compute Spearman rho
3. Bucket D into quintiles, tabulate mean absolute error per bucket
4. Plot the scatter with fitted trend
5. Apply the decision rule in docs/phases.md Phase 1.5

Then STOP and report. Do not proceed to Phase 3 regardless of the
result — I need to make the go/pivot call myself.

Report the number you actually got. If rho is weak, say so plainly.
An honest negative here is far more valuable than a result massaged
toward what the project hoped for.
```

### τ calibration (G-04)

```
Calibrate tau per docs/architecture.md §4.3.

Validation split only. Sweep over empirical D quantiles p50 to p95,
compute WAPE(tau) + lambda * trigger_rate(tau) at each point, select
the minimum, and save the full sweep curve.

Write tau to config with its calibration run ID.

If the selected tau produces a trigger rate outside the 10-30% band,
do not adjust it by hand. Report the anomaly and we will diagnose why.
```

---

## 4. Review prompt

Run at the end of each phase.

```
Phase [N] is complete. Review it before we move on.

1. Every task in this phase — is its done-condition actually met, or
   just approximately met?
2. Any rule in CLAUDE.md we violated or bent?
3. Any place where you zero-filled, defaulted, or silently handled a
   failure that should have been an abstention?
4. Any hardcoded number that affects a result and should be in config?
5. Any code that is more complex than the task required?
6. What would a skeptical examiner attack first?

Be direct about anything that is fragile. I would rather fix it now.
```

---

## 5. Results-integrity prompt

Use in Phase 5, before writing anything up.

```
Before I write up results, stress-test them.

1. Is every reported number reproducible from a committed config
   and seed?
2. Are all arms on identical splits with the identical inventory
   simulator?
3. Is the error before/after deliberation computed on the DELIBERATED
   SUBSET only, not averaged across all runs?
4. Quantify the low-disagreement/high-error quadrant explicitly —
   how often do agents agree confidently and get it wrong?
5. Is any claimed improvement smaller than the across-seed variance?
6. Did we touch the test set more than once?

For each, give me the answer and the evidence. If any result does not
hold up, say so — I would rather cut a claim than defend one that
falls apart under questioning.
```

---

## 6. Habits that make this work

**Start each session with `/clear` and name the task.** Context from an unrelated task makes Claude Code drift toward patterns from the previous problem.

**Ask for the objection, not the summary.** "What's wrong with this approach?" surfaces more than "does this look right?"

**When it wants to build ahead, stop it.** Enthusiasm for the dashboard in week 3 is the most likely source of schedule slip in this project.

**Commit per task ID.** `git commit -m "A-02: historical agent confidence from OOF residuals"` makes the backlog and the history line up, which matters when you write the methods section four months from now.

**When a gate fails, do not prompt your way past it.** A failing correlation check or a weak rho is information about the project, not an obstacle to the session.
