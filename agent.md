# RetailSense — Agent Specification

**Version:** 1.0 (new in v2 doc set)
**Purpose:** The complete behavioral contract for every agent. This is the document to open when implementing or debugging an agent.
**Related docs:** `architecture.md`, `design.md`, `rules.md`

---

## 1. Agent Roster

| Agent | Type | Evidence | LLM? | Can revise? |
|---|---|---|---|---|
| Historical Agent | Quantitative | Sales history, price, promo, item/store features | No | Yes (bounded) |
| Weather Agent | Contextual | Open-Meteo forecast + anomalies | Yes | Yes |
| Trend Agent | Contextual | Google Trends interest + delta | Yes | Yes |
| Calendar Agent | Contextual | M5 events, DOW, seasonality | Yes | Yes |
| Critic Agent | Meta | All agent outputs | Yes | N/A — never forecasts |

**Roster is frozen at 5.** Adding agents requires removing one (`rules.md` §6).

---

## 2. Design Principles

**P1 — Evidence separation.** Each agent owns a distinct evidence source. If two agents see the same features, their disagreement is noise rather than signal, and the entire mechanism is measuring nothing. This is the single most important constraint in the document.

**P2 — Comparable outputs.** Every agent emits a forecast on the same scale in the same units, so disagreement is well-defined.

**P3 — Numbers from models, judgment from LLMs.** The LLM interprets, weighs, and explains. It does not invent the demand figure (`rules.md` §2.5).

**P4 — Honest abstention.** An agent lacking evidence abstains. It never guesses to fill the slot, and it is never coerced to zero.

**P5 — Calibrated confidence.** Confidence must mean something. An agent that always reports 0.9 destroys the weighting scheme and flattens D.

---

## 3. Shared Output Contract

```json
{
  "agent_id": "string",
  "run_id": "string",
  "forecast": 0.0,
  "confidence": 0.0,
  "uncertainty": 0.0,
  "prediction_interval": [0.0, 0.0],
  "key_factors": ["string"],
  "reasoning": "string",
  "abstained": false,
  "abstain_reason": null,
  "data_availability": {},
  "latency_ms": 0,
  "tokens": {"in": 0, "out": 0}
}
```

**Field rules**

| Field | Rule |
|---|---|
| `forecast` | Units in the same scale as M5 daily unit sales. Non-negative. Null only if `abstained` |
| `confidence` | [0, 1]. Derivation is agent-specific and documented in §4–§5. Never a constant |
| `uncertainty` | Roughly `1 - confidence`, but each agent may define its own; must be logged |
| `prediction_interval` | 80% interval. Required — this feeds the inventory safety logic |
| `key_factors` | 1–4 short strings. Used by the critic and shown in the dashboard |
| `reasoning` | 1–3 sentences. Never shown to other agents before deliberation (avoids anchoring) |
| `abstained` | True when required evidence is missing or invalid |

Validation happens at the orchestrator boundary. Invalid → one repair retry → abstain.

---

## 4. The Anchoring Problem (read before implementing context agents)

Weather, Trend, and Calendar agents do not observe sales history directly — that is Historical's evidence. But they must emit a forecast in *units*, not a percentage, so D is well-defined.

**Resolution: shared naive anchor.**

Every context agent receives the same simple, transparent anchor:

```text
anchor = median(sales[t-28 : t-1] for same day-of-week)
```

The context agent then produces:

```text
forecast = anchor × (1 + adjustment)
```

where `adjustment` is that agent's own contribution derived from its own evidence.

**Why a naive anchor rather than the Historical Agent's forecast:** if context agents anchored on Historical's XGBoost output, all four forecasts would be correlated by construction, D would collapse toward zero, and the mechanism would have nothing to detect. The naive anchor is deliberately weaker than the Historical Agent — the difference between them is exactly the information the Historical Agent contributes.

**Cost of this choice, to state in the paper.** Context agents are not fully independent of sales history; they share a weak baseline. Disagreement therefore measures divergence in *adjustment*, not in absolute belief. This is a limitation, but the alternative — agents forecasting in incompatible units — makes D undefined.

---

## 5. Forecasting Agents

### 5.1 Historical Agent

**Role.** The quantitative backbone. Most accurate agent in normal conditions; blind to anything not in the sales history.

**Inputs**
- Lags: 1, 7, 14, 28 days
- Rolling mean/std over 7, 28 days
- Day-of-week, week-of-year
- `sell_price`, price change ratio
- SNAP flags, item/dept/store categorical features

**Model.** LightGBM (default) or XGBoost. Trained on the training split, frozen before validation.

**Confidence derivation** — a real signal, not a constant:

```text
confidence = clip(1 - (residual_std_for_similar_context / forecast), 0.3, 0.95)
```

Estimated from out-of-fold residuals, bucketed by recent volatility. Volatile item-store history → lower confidence.

**Uses LLM?** No. Deterministic.

**Revision behavior.** Bounded. On deliberation it may shift at most ±20% from its original forecast, because its evidence base has not changed — only its weighting of others' evidence has. Allowing unbounded revision would let the LLM override the statistical model, defeating ADR-001.

**Abstains when.** Fewer than 28 days of history for the item-store pair.

---

### 5.2 Weather Agent

**Role.** Estimate how forecast weather deviates demand from the anchor.

**Inputs**
- `temp_max`, `temp_min`, `precipitation_mm`, `windspeed` — Open-Meteo forecast issued at t-1 for t
- Anomalies vs. the item-store's own 30-day seasonal norm
- Item category (weather sensitivity differs by department)

**Two-stage design**

*Stage 1 — rule/statistical:* a category-level weather sensitivity coefficient learned on the training split by regressing residuals-from-anchor on weather anomalies. Produces a candidate adjustment.

*Stage 2 — LLM interpretation:* the LLM receives the anomaly summary, the learned coefficient, and its confidence interval; it may modulate the adjustment within a bounded range and must explain why.

```text
adjustment = clip(learned_coefficient × anomaly, -0.4, +0.6)
forecast   = anchor × (1 + adjustment)
```

The clip is load-bearing. Without it the agent can produce implausible forecasts on extreme-anomaly days, which would spike D for reasons unrelated to genuine uncertainty.

**Confidence derivation**
```text
base 0.75
 − 0.20  if the weather forecast horizon exceeds 3 days
 − 0.25  if the item category has weak learned sensitivity (|coef| below threshold)
 − 0.30  if weather data is cached/stale
```

**Abstains when.** No weather data for the store location on t.

---

### 5.3 Trend Agent

**Role.** Detect consumer-interest shifts not yet visible in sales.

**Inputs**
- Google Trends interest series for the mapped keyword
- Trend delta: current vs. 4-week and 12-week baselines
- Trend anomaly z-score

**Critical constraint.** M5 item IDs are anonymized. Keywords must be mapped at **department/category** level (e.g. `FOODS_3` → a defensible category term). The mapping table is committed to the repo and treated as a documented approximation, not ground truth. If no defensible mapping exists for a category, the Trend Agent abstains for those items rather than guessing.

**Leakage hazard — the sharpest in the project.** Google Trends normalizes its series against the queried window, so pulling a series *today* that includes future dates yields values informed by future data. **Mandatory handling:** for each prediction date `t`, query only the window ending at `t-1`, snapshot the result with its retrieval timestamp, and never re-query the same window later. See `rules.md` §1.8.

```text
adjustment = clip(trend_sensitivity × trend_zscore, -0.3, +0.5)
forecast   = anchor × (1 + adjustment)
```

**Confidence derivation**
```text
base 0.60   (structurally lower — Trends is a proxy, not sales)
 − 0.20  if keyword mapping is category-level rather than specific
 − 0.25  if the trend signal is within noise (|z| < 1)
 − 0.30  if the snapshot is stale
```

Trend Agent should be the **least confident agent by design**. If it routinely reports high confidence, the confidence derivation is wrong.

**Abstains when.** No keyword mapping, or the Trends series has excessive missing values.

---

### 5.4 Calendar Agent

**Role.** Capture predictable, known-in-advance timing effects.

**Inputs**
- M5 `event_name_1/2`, `event_type_1/2`
- SNAP flags by state
- Day-of-week, month, proximity to holidays (days-until/days-since)

**Design.** Learned multipliers from the training split — for each event type and day-of-week, the historical ratio of actual demand to the anchor. The LLM handles composite situations the multipliers cannot (e.g. a holiday falling on an atypical weekday, two overlapping events) and explains the reasoning.

```text
adjustment = (event_multiplier × dow_multiplier) - 1
forecast   = anchor × (1 + adjustment)
```

**Confidence derivation**
```text
base 0.80   (calendar effects are the most predictable)
 − 0.15  if the event has fewer than 3 historical occurrences in training
 − 0.20  if multiple overlapping events (interaction unmodeled)
 + 0.05  if it is a plain non-event weekday (highly predictable)
```

**Abstains when.** Never — calendar data is always available. This makes it the reliable floor of the ensemble.

---

## 6. Critic Agent — Full Specification

The Critic was the most underspecified component in the v1 docs, and it is the second most novel element of the project after the trigger itself. It is specified in full here.

### 6.1 Activation
Only when `D ≥ τ`. Never runs on the fast path — that is the entire point of the mechanism.

### 6.2 What the Critic Does Not Do
- Does not produce a forecast
- Does not decide who is right
- Does not compute the consensus
- Does not touch the inventory decision

Its job is to make disagreement **interpretable and actionable**, so that revision is informed rather than a blind second guess.

### 6.3 Inputs
- All agent outputs (forecast, confidence, key_factors, reasoning)
- The disagreement score D and τ
- The anchor value
- Data availability flags

### 6.4 Conflict Taxonomy

The Critic must classify the conflict into exactly one primary type. This taxonomy is what turns a scalar into a diagnosis, and it is what makes the deliberation round targeted:

| Type | Signature | Typical resolution |
|---|---|---|
| **T1 — History vs. Context** | Historical is the outlier; context agents cluster elsewhere | Ask whether the context anomaly is large enough to override an established pattern |
| **T2 — Context split** | Context agents disagree with each other | Ask which contextual signal is better evidenced for this item category |
| **T3 — Low-confidence noise** | Wide spread but all confidences low | Likely genuine uncertainty, not resolvable — recommend widening the interval rather than moving the point |
| **T4 — Single outlier** | One agent far from a tight cluster of three | Ask the outlier to justify or abstain |
| **T5 — Data degradation** | Spread traceable to stale or missing inputs | Down-weight the degraded agent; flag the run |

### 6.5 Output Contract

```json
{
  "conflict_type": "T1",
  "conflict_summary": "Historical pattern predicts 800 based on a stable weekly cycle; weather and trend agents predict 1100-1200 citing a +7C heat anomaly and a 50% rise in search interest.",
  "camps": {
    "low": ["historical_agent"],
    "high": ["weather_agent", "trend_agent", "calendar_agent"]
  },
  "weakest_assumption": "The weather agent's category sensitivity coefficient was learned from only 12 comparable heat-anomaly days.",
  "challenges": {
    "historical_agent": "Your forecast assumes the recent weekly pattern holds. Three agents cite an external anomaly outside your feature space. Does your residual volatility support holding at 800?",
    "weather_agent": "Your coefficient rests on a thin sample. Should your confidence be lower given the limited comparable history?"
  },
  "resolvable": true,
  "recommendation": "revise"
}
```

`resolvable: false` with `recommendation: "widen_interval"` is a legitimate and important output — it corresponds to T3, where the honest answer is that the disagreement reflects irreducible uncertainty and the right response is a wider prediction interval, not a moved point forecast. **This must be implemented, not skipped.** Without it, every deliberation is forced to produce movement, which manufactures the appearance of a working mechanism.

### 6.6 Critic Failure Handling
If the Critic fails or returns invalid output: skip deliberation, keep the pre-deliberation consensus, log `deliberation_failed: true`. Never fabricate a conflict report.

---

## 7. Deliberation Protocol

### 7.1 Sequence
```text
1. Critic classifies conflict, emits per-agent challenges
2. Each challenged agent receives:
     - its own original output
     - the critic's conflict summary + its specific challenge
     - peer forecasts + key_factors  (NOT peer full reasoning — avoids anchoring cascade)
3. Each returns a revised output + `changed_because`
4. Re-consensus over revised outputs
5. Log initial and revised separately  (rules.md §3.5)
```

### 7.2 Revision Output Additions

```json
{
  "revised_forecast": 900.0,
  "revised_confidence": 0.78,
  "changed_because": "The heat anomaly exceeds anything in my recent feature window; I concede partial upward movement while noting my pattern evidence remains strong.",
  "position_held": false
}
```

### 7.3 Holding Position Is Valid
`position_held: true` with an unchanged forecast is a legitimate outcome and must be recorded. An agent that always moves is not deliberating, it is capitulating — and a system where every agent capitulates converges by social pressure rather than evidence. **Track the hold rate per agent as a diagnostic:** a hold rate near 0% indicates the deliberation prompt is coercive and needs rewriting.

### 7.4 Bounds
| Agent | Max revision |
|---|---|
| Historical | ±20% (evidence base unchanged; see §5.1) |
| Weather | ±35% |
| Trend | ±40% |
| Calendar | ±25% |

### 7.5 Post-Deliberation Consensus
Same weighted consensus as the fast path, using revised forecasts and revised confidences. Using an identical consensus function on both paths is deliberate: it ensures any measured difference between paths is attributable to deliberation itself, not to a different aggregation rule.

---

## 8. Prompt Design Rules

1. **Structured output enforced.** JSON schema in the request; validate before use.
2. **No peer reasoning pre-deliberation.** Prevents anchoring cascades that artificially deflate D.
3. **Temperature ≤ 0.3** for all agent calls. Reproducibility beats creativity here.
4. **Seed and log every prompt.** Prompts are experimental configuration and must be versioned with results.
5. **Never ask the LLM for a bare number.** Always: evidence → interpretation → bounded adjustment.
6. **Prompts are frozen at the start of Phase 3.** Changing a prompt mid-evaluation invalidates cross-arm comparison.

---

## 9. Agent Evaluation

Each agent is evaluated **independently** before the ensemble is assembled (`phases.md` Phase 1 exit criteria).

| Metric | Purpose |
|---|---|
| MAE / WAPE per agent | Is this agent contributing signal at all? |
| Confidence calibration curve | Does stated confidence track realized accuracy? |
| Abstention rate | Is the agent silently absent from most runs? |
| Pairwise forecast correlation | **Are agents actually independent?** |
| Revision rate / hold rate | Is deliberation meaningful or performative? |

**Pairwise correlation is the diagnostic that validates P1.** If two agents correlate above ~0.95, they share an evidence space, their disagreement is noise, and one should be cut or redesigned. Run this check at the end of Phase 1 — before building anything on top of the ensemble.
