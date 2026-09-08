# RetailSense — Engineering and Research Rules

**Version:** 2.0
**Status:** Binding. A rule here overrides convenience, deadline pressure, and a better-looking result.

---

## 1. Data Integrity Rules

1. **No future-data leakage.** Every prediction uses only information available at the prediction timestamp. This is the project's single most important rule.
2. Actual future sales are revealed only after the forecast row is committed, and used only for evaluation.
3. **Weather must come from the forecast that was issued, not the weather that occurred.** Use Open-Meteo's historical *forecast* archive. Using observed weather is leakage even though it feels like "real data."
4. Google Trends is a **demand proxy**, never actual sales.
5. M5 is U.S. retail data. Never describe it as Indian retail ground truth.
6. All external data must be timestamp-aligned to the forecast horizon.
7. Missing or unavailable signals are handled explicitly. **Never zero-filled, never forward-filled from the future.**
8. **Trends snapshots are immutable.** Google Trends normalizes against the queried window, so re-querying a past window later yields values informed by data that did not exist then. Query once with a window ending at t-1, snapshot with the retrieval timestamp, never re-query. This is the subtlest leakage path in the project.
9. **The leakage audit is a pipeline gate, not a review step.** It runs automatically and aborts on violation.
10. Actual demand lives only in the evaluation store. Agent-facing code has no read access to it.

---

## 2. Agent Rules

1. Agents have clearly defined, non-overlapping responsibilities.
2. **Agents must not share an evidence space.** Verified by pairwise correlation at the end of Phase 1. Two agents above ~0.95 correlation means one must be cut or redesigned — their disagreement is noise, and a mechanism built on it measures nothing.
3. Every agent returns forecast, confidence, key factors, uncertainty, and a prediction interval on the shared schema.
4. Numerical models provide the quantitative backbone.
5. LLMs handle context interpretation, conflict analysis, deliberation, and explanation — **not free-form numeric forecasting.**
6. All agent outputs are schema-validated at the orchestrator boundary before use.
7. **A failed or abstaining agent is never converted to a zero forecast.** It is excluded from consensus and the run is flagged.
8. Confidence must be a real signal. An agent reporting near-constant confidence has a broken confidence derivation and flattens the disagreement score.
9. Context agents anchor on the shared naive baseline, never on the Historical Agent's output — anchoring on Historical would correlate all four forecasts by construction and collapse D.
10. Agents do not see peer *reasoning* before deliberation, only peer forecasts and key factors. This prevents anchoring cascades.

---

## 3. Deliberation Rules

1. Deliberation is **conditional**, not always-on. This is the whole thesis.
2. **τ is calibrated on validation data by the documented sweep procedure** (`architecture.md` §4.3), never chosen because it produces an appealing demo, and never adjusted after seeing test results.
3. τ is stored in config with a pointer to the calibration run that produced it.
4. The MVP permits exactly one deliberation round.
5. The critic identifies and classifies the conflict before any agent revises.
6. Initial and revised predictions are logged separately.
7. The system records whether deliberation improved, worsened, or did not change the forecast.
8. **Holding position is a valid outcome.** An agent that always moves is capitulating, not deliberating. Hold rate is tracked per agent; a rate near zero means the prompt is coercive and must be rewritten.
9. **`resolvable: false` must be implemented.** When disagreement reflects irreducible uncertainty, the correct response is a wider interval, not a moved point forecast. Forcing every deliberation to produce movement manufactures the appearance of a working mechanism.
10. **Prompts are frozen at the start of Phase 3.** A prompt change mid-evaluation invalidates every cross-arm comparison made before it.

---

## 4. Inventory Rules

1. Inventory decisions use a transparent, rule-based policy.
2. The MVP uses forecast, uncertainty, lead time, safety stock, and current stock.
3. **The LLM must not be able to set or influence the order quantity.** Enforced by test, not by convention.
4. Final actions are exactly one of `RESTOCK`, `HOLD`, `REDUCE`.
5. **The identical simulator and policy apply to every experimental arm.** A different policy per arm would confound the entire comparison.
6. Order quantity is deterministic: identical inputs always produce identical output.

---

## 5. Evaluation Rules

1. Always compare against meaningful baselines: statistical (ARIMA/seasonal-naive), ML (XGBoost), single-agent, non-deliberative consensus, and always-on deliberation.
2. Report multiple forecast metrics — MAE, RMSE, and sMAPE/WAPE.
3. Inventory evaluation must include business outcomes: stockout rate, overstock, holding cost, total cost.
4. Measure disagreement against realized forecast error, and report the **low-disagreement/high-error quadrant** explicitly. Aggregate correlation can hide the shared-blind-spot failure mode.
5. Measure deliberation frequency, latency, and LLM call count.
6. **Never claim improvement without multi-seed or statistical evidence.** An improvement smaller than run-to-run variance is not an improvement.
7. **If deliberation does not help, report that.** A rigorous negative result is a contribution; a manufactured positive is misconduct.
8. Error before/after deliberation is reported **on the deliberated subset only**. Averaging over all runs dilutes the effect and misrepresents what the mechanism does.
9. Test-split results are computed once, at the end. No iterating against the test set.

---

## 6. Scope Rules

1. Start with 3–4 forecasting agents plus one critic. The roster is frozen at 5.
2. One retail benchmark for the MVP.
3. A second dataset only after the primary pipeline is complete and stable.
4. No reinforcement learning, dynamic pricing, donation optimization, or multi-echelon supply chain in the core MVP.
5. A feature is added only if it serves a research question, a measurable evaluation, or a required demo capability.
6. **Any scope addition requires a scope removal or an explicit timeline extension.** Not both silently absorbed.
7. Good ideas that are out of scope go to a parking lot in `memory.md`, not into the build.

---

## 7. Engineering Rules

1. **Simplest thing that works.** No abstraction for single-use code, no configurability that was not requested.
2. **Surgical changes.** Every changed line traces to a task ID.
3. **Verifiable done-conditions.** If you cannot state the check, the task is not defined.
4. No number affecting a result may be hardcoded. Config or nothing.
5. Dependencies are pinned; the lockfile is committed.
6. External data snapshots are committed — the experiment is not otherwise reproducible.
7. Notebooks are for exploration only. **No reported result comes from a notebook.**
8. Every experiment logs its git SHA and config hash.
9. Mandatory tests (leakage, disagreement, policy, schema) are never skipped for time.

---

## 8. Documentation Rules

Every experiment records:

- dataset and subset version
- prediction horizon
- model and agent configuration
- prompt version
- external signal availability
- τ and its calibration run
- deliberation status and rate
- all metrics
- latency and token cost
- seed
- git SHA
- known limitations

---

## 9. Responsible Claims

**Use precisely:**
> "RetailSense combines live/current contextual signals with replayed historical sales and simulated inventory state."

**Never claim:**
> "RetailSense has access to live retailer POS data."

**Do not claim to have invented:** demand forecasting, weather-aware forecasting, multi-agent systems, LLM time-series forecasting, or inventory optimization.

**The contribution is:** calibrated disagreement-triggered selective deliberation, and its empirical evaluation.

**State these limitations explicitly in the paper:**
1. The disagreement score measures spread, not correctness — it cannot detect uniform agent error.
2. Context agents share a naive anchor, so they are not fully independent of sales history.
3. Google Trends is a proxy with a category-level keyword mapping, not item-level.
4. Inventory state is simulated, not observed.
5. Results are on one dataset, one store, one horizon.
6. LLM outputs are not exactly reproducible even at low temperature.

Writing these before finalizing results is deliberate. Limitations discovered after a conclusion is committed to tend to get softened.
