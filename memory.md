# RetailSense — Project Memory

**Version:** 2.0
**Purpose:** The compact source of truth. Read this first in any new working session, then open the specific doc you need.

---

## 1. Identity

**Name:** RetailSense
**Title:** *RetailSense: A Disagreement-Triggered Multi-Agent Framework for Real-Time Inventory Demand Forecasting and Restocking Decisions*

**One sentence:**
> RetailSense uses specialized agents to forecast demand from historical sales and external signals, detects when their predictions strongly disagree, triggers targeted deliberation only in those cases, and converts the resulting forecast into an inventory restocking decision.

**For the paper:**
> We investigate whether calibrated inter-agent disagreement can serve as an actionable uncertainty signal for selectively triggering deliberation and improving inventory decisions.

---

## 2. The Core Idea

The project is about **when to deliberate**, not merely whether to use multiple agents.

```text
Multiple specialized forecasts
          ↓
   Disagreement score D  (normalized, confidence-weighted)
          ↓
   D < τ  →  fast consensus       (0 extra LLM calls)
   D ≥ τ  →  critic + 1 round     (~3 extra LLM calls)
          ↓
     Final forecast + interval
          ↓
   RESTOCK / HOLD / REDUCE
```

---

## 3. Research Questions

| ID | Question | Status |
|---|---|---|
| RQ1 | Does disagreement-triggered deliberation beat statistical, single-agent, consensus, and always-on deliberation? | Primary |
| RQ2 | Does disagreement correlate with actual forecast error? | **Load-bearing — tested at week 5** |
| RQ3 | Does selective deliberation match always-on at materially lower cost? | Efficiency claim |

**RQ2 is the assumption everything rests on.** If it fails, the project reframes to characterizing *when* disagreement is informative. That pivot is planned, not improvised — see `phases.md` Phase 1.5.

---

## 4. Document Map

| Doc | Open it when you need |
|---|---|
| `prd.md` | Requirements, acceptance criteria, success metrics, open questions |
| `architecture.md` | System structure, the disagreement math, ADRs, failure modes |
| `agent.md` | Any agent's exact behavior, the critic taxonomy, deliberation protocol |
| `design.md` | Interaction flows, inventory policy math, DB schema, dashboard spec |
| `stack.md` | What to install, repo layout, testing, cost budget, what to do when things break |
| `phases.md` | Timeline, gates, contingency, risk register |
| `tasks.md` | The executable backlog with dependencies and done-conditions |
| `rules.md` | Any question of the form "am I allowed to..." |
| `memory.md` | This file — orientation |

---

## 5. Agents (frozen roster of 5)

| Agent | Evidence | Implementation | Confidence baseline |
|---|---|---|---|
| Historical | Sales history, price, promo | LightGBM (no LLM) | 0.3–0.95, from residuals |
| Weather | Open-Meteo forecast + anomalies | Learned coefficient + LLM | ~0.75 base |
| Trend | Google Trends + delta | Learned coefficient + LLM | ~0.60 base (lowest by design) |
| Calendar | M5 events, DOW, seasonality | Learned multipliers + LLM | ~0.80 base, never abstains |
| Critic | All agent outputs | LLM only | N/A — never forecasts |

Context agents anchor on a shared naive baseline (28-day same-DOW median), **not** on the Historical Agent — anchoring on Historical would correlate everything and collapse D.

---

## 6. Key Formulas

**Disagreement** (normalized — scale-free, this is the v2 change):
$$\bar{y}_c = \frac{\sum c_i y_i}{\sum c_i} \qquad V = \frac{\sum c_i(y_i-\bar{y}_c)^2}{\sum c_i} \qquad D = \frac{\sqrt{V}}{\bar{y}_c + \epsilon}$$

**τ calibration:** minimize `WAPE(τ) + λ · trigger_rate(τ)` over validation D-quantiles. Report the full sweep.

**Inventory:**
$$ReorderPoint = (forecast \times L) + z\sigma\sqrt{L}$$

---

## 7. Data Strategy

| Source | Role | Status |
|---|---|---|
| M5 Walmart | Primary ground truth, chronological replay | Real historical |
| Open-Meteo | Weather context — **forecast archive, not observations** | Live external |
| Google Trends | Consumer-interest proxy, category-level keywords | Near-real-time external |
| M5 calendar | Events, seasonality | Known in advance |
| Inventory state | Stock, lead time, orders | **Simulated** |
| Corporación Favorita | Second benchmark | **Deferred** |

**Real-time definition:** hybrid — live contextual signals + replayed historical sales + simulated inventory. Never claims live POS access.

---

## 8. Evaluation Arms

1. ARIMA / seasonal-naive
2. XGBoost
3. Single agent
4. Multi-agent weighted consensus (no deliberation)
5. Always-on deliberation (control)
6. **RetailSense** — selective deliberation

All arms: identical splits, identical inventory simulator, ≥3 seeds.

---

## 9. Metrics

**Forecasting:** MAE, RMSE, sMAPE, WAPE
**Inventory:** stockout rate, overstock units, holding cost, stockout cost, total cost
**Mechanism:** disagreement-error Spearman ρ, trigger rate, error before/after on the deliberated subset, latency, LLM calls, tokens

---

## 10. Timeline

```text
Week  0     Setup and scope freeze
Weeks 1–3   Forecasting agents        → gate: pairwise correlation < 0.95
Weeks 4–5   External context          → gate: zero leakage violations
Week  5     ⚠ RQ2 SMOKE TEST          → gate: go / pivot decision
Weeks 6–10  Disagreement + deliberation → gate: τ calibrated, prompts frozen
Weeks 11–13 Inventory layer           → gate: policy determinism tests
Weeks 14–16 Evaluation, paper, demo
```

---

## 11. Non-Negotiable Rules (short form)

- Never leak future data — audit gate is automatic
- Weather from the forecast archive, never observations
- Trends snapshots immutable — never re-query a past window
- Never describe M5 as Indian retail data
- Google Trends is a proxy, not sales
- Numerical models are the quantitative backbone
- LLM never sets the order quantity
- A failed agent never becomes a zero forecast
- τ calibrated on validation, never on test, never by eye
- Prompts frozen at Phase 3 start
- One deliberation round
- Log initial and revised separately
- Holding position is valid and tracked
- No improvement claimed without multi-seed evidence
- Report negative results honestly

---

## 12. Current Status

### Confirmed
- Title, scope, research questions, non-goals
- Hybrid real-time definition
- M5 primary; Open-Meteo + Trends + M5 calendar external
- 4 forecasting agents + 1 critic, roster frozen
- Normalized disagreement score (supersedes raw variance)
- τ calibration procedure specified
- Critic conflict taxonomy T1–T5 specified
- One-round deliberation with per-agent bounds
- Transparent rule-based inventory policy
- RQ2 smoke test at week 5 with a written pivot plan
- 16-week single-student feasibility

### Open decisions
| # | Question | Blocking? |
|---|---|---|
| OQ1 | Exact M5 store/item subset | **Yes — Phase 0** |
| OQ2 | Trends keyword mapping for anonymized M5 items | **Yes — Phase 0** |
| OQ3 | Final LLM provider/model | No — config value |
| OQ4 | Safety stock: fixed multiple vs. service-level | No — by Phase 4 |
| OQ5 | Lead time: fixed vs. stochastic | No — start fixed |

### Deferred (parking lot)
- Second dataset validation (Corporación Favorita)
- Synthetic disruption stress tests
- Multi-round adaptive deliberation
- Learned inventory policy / RL
- Multi-horizon forecasting

---

## 13. Known Weaknesses (state these before someone else does)

1. **D measures spread, not correctness.** Uniformly wrong agents produce D ≈ 0. Report the low-D/high-error quadrant explicitly.
2. **Context agents share a naive anchor**, so they are not fully independent of sales history. Disagreement measures divergence in adjustment, not in absolute belief.
3. **Trends keywords are category-level**, because M5 item IDs are anonymized.
4. **Inventory is simulated**, not observed.
5. **One dataset, one store, one horizon.**
6. **LLM outputs are not exactly reproducible** even at low temperature — report variance, not point claims.

---

## 14. The 30-Second Pitch

> Retail demand shifts with weather, consumer interest, and events in ways historical patterns don't capture. RetailSense runs four specialized agents that each look at different evidence, measures how much they disagree, and spends extra reasoning only when they conflict — then turns the result into a restocking decision. The research question is whether that disagreement is a real uncertainty signal, and whether reasoning selectively beats reasoning always.
