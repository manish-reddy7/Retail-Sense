# RetailSense — Design Specification

**Version:** 2.0
**Covers:** system design principles, interaction flows, inventory policy design, data schema, and dashboard handoff spec.
**Related docs:** `architecture.md`, `agent.md`, `stack.md`

---

## 1. Design Principles

### 1.1 Hybrid by design
Numerical models produce numbers; LLMs produce judgment. Neither is asked to do the other's job (ADR-001).

### 1.2 Evidence separation
Each agent owns a distinct evidence source, so disagreement carries information rather than noise (`agent.md` §2, P1).

### 1.3 Deliberate only when needed
Agreement is cheap. Conflict earns an extra reasoning round. This is the product thesis and the research contribution in a single sentence.

### 1.4 Traceability by default
Every number on screen traces back to a logged row. Nothing is displayed that cannot be reconstructed from the evaluation store.

### 1.5 Honest surfaces
The interface must be able to say "the agents disagree and deliberation did not resolve it." A UI that can only display confident answers will misrepresent the system's actual behavior, and — more importantly — will hide the T3 case that the research needs to report.

---

## 2. Interaction Flows

### 2.1 Low-disagreement flow (the common case, ~70–90% of runs)

```text
4 agent forecasts
      ↓
D computed  →  D < τ
      ↓
confidence-weighted consensus
      ↓
prediction interval from weighted spread
      ↓
inventory policy
      ↓
action + quantity
```
Zero additional LLM calls. Target latency: under 5s.

### 2.2 High-disagreement flow

```text
4 agent forecasts
      ↓
D computed  →  D ≥ τ
      ↓
Critic: classify conflict (T1–T5), emit per-agent challenges
      ↓
      ├─ resolvable: false  →  keep consensus, WIDEN interval, flag
      │
      └─ resolvable: true
             ↓
        1 revision round (agents may hold position)
             ↓
        re-consensus over revised outputs
      ↓
inventory policy
      ↓
action + quantity + conflict explanation
```

The `resolvable: false` branch is a first-class path, not an error case. It corresponds to genuine irreducible uncertainty, and forcing it down the revision path would manufacture movement where none is warranted.

---

## 3. Consensus Design

Both paths use the identical function so that any measured difference is attributable to deliberation itself:

```python
final = sum(c_i * y_i) / sum(c_i)
```

**Prediction interval:**
```python
spread = sqrt(weighted_variance(forecasts, confidences))
width  = max(spread, mean_agent_uncertainty * final)
interval = [final - 1.28*width, final + 1.28*width]   # 80%
```

When the critic returns `resolvable: false`, width is multiplied by 1.5. The system's response to unresolved conflict is a wider stated uncertainty, which flows directly into higher safety stock — meaning disagreement affects the business decision even when it does not change the point forecast. That pathway is worth highlighting in the paper.

---

## 4. Forecast Output Design

```json
{
  "run_id": "run_20160115_CA1_FOODS3_090",
  "prediction_timestamp": "2016-01-14T18:00:00",
  "target_date": "2016-01-15",
  "store_id": "CA_1",
  "item_id": "FOODS_3_090",
  "horizon": "next_day",
  "anchor": 850.0,
  "final_forecast": 1080.0,
  "confidence": 0.84,
  "prediction_interval": [950, 1240],
  "disagreement_score": 0.21,
  "tau": 0.18,
  "deliberation_triggered": true,
  "conflict_type": "T1",
  "reason": "Historical weekly pattern conflicts with a +7C heat anomaly and rising search interest.",
  "resolvable": true,
  "agents_abstained": [],
  "latency_ms": 6420,
  "llm_calls": 6
}
```

---

## 5. Inventory Decision Design

### 5.1 Policy

```text
LeadTimeDemand = final_forecast × lead_time_days
SafetyStock    = z × σ_forecast × √lead_time_days
ReorderPoint   = LeadTimeDemand + SafetyStock
```

where `σ_forecast` is derived from the prediction interval width — so a deliberation that widens the interval automatically raises safety stock.

### 5.2 Decision logic

```python
if current_stock < reorder_point:
    action = "RESTOCK"
    order_quantity = reorder_point + review_period_demand - current_stock - on_order
elif current_stock > reorder_point + overstock_margin:
    action = "REDUCE"          # place no order; flag for markdown/transfer
    order_quantity = 0
else:
    action = "HOLD"
    order_quantity = 0
```

`overstock_margin` is configured, not inferred.

**Hard constraint.** `order_quantity` is a pure function of policy inputs. The LLM has no path to it (`rules.md` §4.3). This is tested (`test_policy.py::test_llm_cannot_set_quantity`), because a reviewer's first question about any LLM-in-the-loop inventory system is whether the model can invent an order — and the answer must be a test, not a paragraph.

### 5.3 Worked example

```text
final_forecast   = 1,100/day      σ = 120
lead_time        = 3 days         z = 1.65
current_stock    = 700            on_order = 0

LeadTimeDemand = 1,100 × 3            = 3,300
SafetyStock    = 1.65 × 120 × √3      ≈   343
ReorderPoint                          ≈ 3,643

700 < 3,643  →  RESTOCK
order_quantity = 3,643 + 1,100 - 700 - 0 = 4,043
```

---

## 6. Data Storage Design

SQLite. The evaluation store is the sole holder of ground truth (ADR-006).

### `forecast_runs`
| Column | Type | Notes |
|---|---|---|
| run_id | TEXT PK | |
| experiment_id | TEXT | FK → experiments |
| prediction_timestamp | TEXT | |
| target_date | TEXT | |
| store_id, item_id | TEXT | |
| horizon_days | INT | |
| anchor | REAL | |
| final_forecast | REAL | |
| confidence | REAL | |
| pi_lower, pi_upper | REAL | |
| disagreement_score | REAL | logged on **every** run, not just deliberated ones |
| tau_used | REAL | |
| deliberation_triggered | INT | |
| conflict_type | TEXT | nullable |
| resolvable | INT | nullable |
| actual_demand | REAL | **written only after the forecast row is committed** |
| abs_error | REAL | computed at reveal |
| latency_ms | INT | |
| llm_calls, tokens_in, tokens_out | INT | |

### `agent_predictions`
| Column | Notes |
|---|---|
| run_id, agent_id | composite PK |
| initial_forecast, initial_confidence | |
| revised_forecast, revised_confidence | null on fast path |
| position_held | INT, null on fast path |
| changed_because | TEXT |
| key_factors | JSON |
| abstained, abstain_reason | |
| data_availability | JSON |
| latency_ms, tokens_in, tokens_out | |

Keeping initial and revised in the same row makes the before/after deliberation analysis a single query — which is the core table of the paper.

### `critic_reports`
`run_id` PK, `conflict_type`, `conflict_summary`, `camps` (JSON), `weakest_assumption`, `challenges` (JSON), `resolvable`, `recommendation`.

### `inventory_state`
`run_id` PK, `current_stock`, `on_order`, `safety_stock`, `lead_time_days`, `reorder_point`, `action`, `order_quantity`, `realized_stockout_units`, `realized_overstock_units`, `holding_cost`, `stockout_cost`.

### `experiments`
`experiment_id` PK, `arm` (arima | xgboost | single_agent | consensus | always_deliberate | retailsense), `config_hash`, `seed`, `git_sha`, `mlflow_run_id`, `started_at`, `notes`.

`git_sha` + `config_hash` together make any reported number traceable to the exact code and configuration that produced it.

### `evaluation_results`
`experiment_id`, `model_name`, `mae`, `rmse`, `smape`, `wape`, `stockout_rate`, `overstock_units`, `holding_cost`, `stockout_cost`, `total_cost`, `deliberation_rate`, `mean_latency_ms`, `total_llm_calls`, `disagreement_error_spearman`.

---

## 7. Dashboard Handoff Spec

Streamlit, three views. Desktop-first; the demo runs on a laptop.

### 7.1 Main view

```text
┌────────────────────────────────────────────────────────┐
│  RetailSense          [Store ▾] [Item ▾] [Date ▾]      │
├────────────────────────────────────────────────────────┤
│  Historical Agent     820      ████████░░  conf 0.84   │
│  Weather Agent      1,150      ████████░░  conf 0.82   │
│  Trend Agent        1,200      ██████░░░░  conf 0.61   │
│  Calendar Agent     1,100      ████████░░  conf 0.80   │
├────────────────────────────────────────────────────────┤
│  Disagreement  0.21   τ = 0.18        ⚠ HIGH           │
│  ⚡ Deliberation triggered — conflict type T1          │
│  History vs. context: weekly pattern vs. heat anomaly  │
├────────────────────────────────────────────────────────┤
│  FINAL FORECAST    1,080 units                         │
│  Confidence 84%    Range 950 – 1,240                   │
├────────────────────────────────────────────────────────┤
│  Current stock 700    Reorder point 3,643              │
│  Stockout risk HIGH                                    │
│                                                        │
│         ▶  RESTOCK  —  order 4,043 units               │
└────────────────────────────────────────────────────────┘
```

| Element | State | Behavior |
|---|---|---|
| Disagreement badge | D < τ | Neutral gray, "LOW" |
| Disagreement badge | D ≥ τ | Amber, "HIGH", deliberation banner appears |
| Deliberation banner | resolvable: false | Reads "unresolved — interval widened", interval shown in amber |
| Agent row | abstained | Greyed, "abstained — {reason}", no bar |
| Action chip | RESTOCK / HOLD / REDUCE | Amber / neutral / blue |
| Any panel | loading | Skeleton rows, never a spinner over stale numbers |
| Any panel | agent failure | Inline notice; the run still renders with remaining agents |

**Empty state:** before a selection, show the pipeline diagram and a one-line explanation of the mechanism. The evaluator's first ten seconds should teach them what the system does.

### 7.2 Explainability view
- Per-agent: forecast, confidence, key factors, full reasoning
- Critic report: conflict type, camps, weakest assumption, challenges
- Before/after deliberation table with `position_held` marked (a held position is shown as "held — {reason}", never as a failure)
- Plain-language derivation of the action from the policy inputs

### 7.3 Evaluation view
- Metrics table across all six arms, identical splits
- **Disagreement vs. absolute error scatter with the fitted trend and Spearman ρ** — this is the RQ2 figure and the single most important chart in the project
- Deliberation rate, error before/after on the deliberated subset only
- Latency and LLM-call comparison vs. always-on (the RQ3 figure)
- τ calibration sweep curve, showing why the chosen τ was selected

**Do not hide a null result.** If ρ is weak, the scatter shows it. The evaluation view is a measurement instrument, not a marketing surface — and a project that reports an honest negative on RQ2 is more defensible than one that appears to have tuned its way to a positive.

### 7.4 Accessibility notes
- Never encode state in color alone — the disagreement badge carries the text "LOW"/"HIGH" alongside its color
- All charts have data tables behind an expander
- Logical tab order: selectors → agents → decision
