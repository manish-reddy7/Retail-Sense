# RetailSense — Technology Stack

**Version:** 1.0 (new in v2 doc set)
**Purpose:** What to install, why each choice was made, and what to do when a piece fails.
**Related docs:** `architecture.md` (ADRs), `tasks.md` (setup tasks), `rules.md`

---

## 1. Stack at a Glance

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11 | Ecosystem; 3.11 for stable typing + speed, avoiding 3.12 package lag |
| Data | pandas, NumPy | Standard; M5 fits in memory at the chosen subset size |
| Forecasting | LightGBM (primary), XGBoost (alt) | Fast on tabular; strong M5 track record |
| Statistical baseline | statsmodels (ARIMA), plus seasonal-naive | Required baseline arm |
| Orchestration | LangGraph | Conditional edges map onto the τ branch (ADR-005) |
| LLM | Provider-agnostic wrapper | Avoids lock-in; model is a config value |
| Weather | Open-Meteo | Free, no key, historical *forecast* archive available |
| Trends | pytrends | Only practical Google Trends access |
| Calendar | M5 calendar.csv + `holidays` | Already in the dataset |
| Storage | SQLite | Single-user, file-portable, reproducible (ADR-004) |
| Tracking | MLflow | Experiment comparison without hand-rolled logging |
| Dashboard | Streamlit | Fastest path to a demo; Python-native |
| Validation | Pydantic v2 | Enforces the agent contract at the boundary |
| Testing | pytest | Leakage and policy tests are non-optional |
| Version control | Git / GitHub | — |

---

## 2. Environment

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**requirements.txt**

```text
# Core
python-dotenv==1.0.1
pandas==2.2.2
numpy==1.26.4
pydantic==2.7.1
pyyaml==6.0.1

# Modeling
lightgbm==4.3.0
xgboost==2.0.3
scikit-learn==1.4.2
statsmodels==0.14.2
scipy==1.13.0

# Orchestration + LLM
langgraph==0.0.51
langchain-core==0.2.0
openai==1.30.1
tenacity==8.3.0

# External data
requests==2.32.2
pytrends==4.9.2
holidays==0.49

# Storage + tracking
mlflow==2.13.0

# Dashboard
streamlit==1.35.0
plotly==5.22.0

# Testing
pytest==7.4.4
pytest-cov==5.0.0
```

Versions are pinned. On a 16-week timeline, an unpinned dependency upgrade that breaks the pipeline in week 12 is an avoidable catastrophe. Regenerate with `pip freeze` and commit the lockfile.

---

## 3. Repository Layout

```text
retailsense/
├── config/
│   ├── base.yaml              # dataset subset, horizon, seeds
│   ├── agents.yaml            # per-agent params, clips, confidence rules
│   ├── thresholds.yaml        # τ, λ, calibration output
│   └── inventory.yaml         # lead time, safety stock, costs
├── data/
│   ├── raw/                   # M5 csvs (gitignored)
│   ├── external/              # weather + trends snapshots (COMMITTED)
│   └── processed/
├── src/
│   ├── data/                  # loaders, integration, feature engineering
│   │   └── leakage_audit.py   # the gate
│   ├── agents/
│   │   ├── base.py            # contract, Pydantic models
│   │   ├── historical.py
│   │   ├── weather.py
│   │   ├── trend.py
│   │   ├── calendar.py
│   │   └── critic.py
│   ├── orchestration/
│   │   ├── disagreement.py    # pure function
│   │   ├── consensus.py
│   │   ├── deliberation.py
│   │   └── graph.py           # LangGraph wiring — thin
│   ├── inventory/
│   │   ├── policy.py
│   │   └── simulator.py
│   ├── evaluation/
│   │   ├── metrics.py
│   │   ├── calibration.py
│   │   └── store.py           # SQLite; SOLE holder of actuals
│   └── llm/
│       └── client.py          # provider-agnostic wrapper
├── experiments/
│   ├── run_baseline_arima.py
│   ├── run_baseline_xgb.py
│   ├── run_single_agent.py
│   ├── run_consensus.py
│   ├── run_always_deliberate.py
│   └── run_retailsense.py
├── tests/
│   ├── test_leakage.py        # non-negotiable
│   ├── test_disagreement.py
│   ├── test_policy.py
│   └── test_schema.py
├── dashboard/app.py
├── notebooks/                 # exploration only, never the source of results
├── requirements.txt
└── README.md
```

**`data/external/` is committed deliberately.** Weather and Trends snapshots are not reproducible by re-querying — Trends renormalizes and Open-Meteo archives shift. Committing the snapshots is what makes the experiment reproducible at all. This is the single most important line in this document for reproducibility.

---

## 4. External Data Sources

### 4.1 M5 (Kaggle)
`sales_train_evaluation.csv`, `calendar.csv`, `sell_prices.csv`. Full data is ~450MB; the chosen subset (1 store, 20–50 items) is a few MB. Gitignore raw; commit the subset extract.

### 4.2 Open-Meteo
No API key. Two endpoints matter:
- **Forecast API** — for live runs
- **Historical Forecast API** — returns *the forecast that was issued* on a past date

The second is essential. Using the historical *observation* API would inject the actual realized weather, which was not knowable at prediction time — a direct leakage violation (`rules.md` §1.3). Store→lat/lon mapping for M5's CA/TX/WI stores is committed in config.

### 4.3 Google Trends (pytrends)
The most fragile dependency in the stack. Known problems: aggressive rate limiting, unofficial API subject to breakage, and window-relative normalization.

**Handling:**
- Query once per `(keyword, window ending t-1)`, cache to `data/external/trends/`, never re-query
- Exponential backoff via `tenacity`; on persistent failure the Trend Agent abstains
- Snapshot files record keyword, window, retrieval timestamp
- **First component cut under time pressure** (`phases.md`, Contingency)

### 4.4 LLM Provider
Wrapped behind `src/llm/client.py` exposing a single `complete(prompt, schema) -> dict`. Model name lives in config. Any OpenAI-compatible endpoint works, which keeps ADR-001 provider-neutral and protects against a provider becoming unavailable or repriced mid-project.

---

## 5. Configuration

Every experiment is a config file. No number that affects a result may be hardcoded.

```yaml
# config/base.yaml
experiment_name: retailsense_v1
seed: 42
dataset:
  store_id: CA_1
  item_subset: config/items_50.txt
  train_end:  "2015-04-24"
  val_end:    "2016-01-01"
  test_end:   "2016-04-24"
horizon_days: 1

# config/thresholds.yaml
disagreement:
  tau: 0.18          # produced by calibration; never hand-tuned
  lambda_cost: 0.05
  calibration_run: calib_20250310_a

# config/inventory.yaml
lead_time_days: 3
safety_stock:
  method: service_level
  z: 1.65            # ~95%
costs:
  holding_per_unit_day: 0.10
  stockout_per_unit: 1.00
```

`tau` carries a pointer to the calibration run that produced it. A τ without provenance is indistinguishable from a τ tuned to make the demo look good.

---

## 6. Testing Strategy

```text
        ╱  End-to-end  ╲     1–2: full replay on a tiny slice
       ╱  Integration   ╲    ~10: agent→orchestrator→policy paths
      ╱   Unit tests     ╲   ~40: disagreement math, policy, schema, features
```

**Mandatory tests — the project is not defensible without them:**

| Test | Asserts |
|---|---|
| `test_leakage.py::test_no_future_features` | No feature's source timestamp ≥ prediction timestamp |
| `test_leakage.py::test_actuals_isolated` | Agent code paths cannot read the actuals table |
| `test_leakage.py::test_weather_is_forecast` | Weather comes from the forecast archive, not observations |
| `test_disagreement.py::test_scale_invariance` | D is unchanged when all forecasts are scaled by a constant |
| `test_disagreement.py::test_identical_forecasts` | Identical forecasts → D = 0 |
| `test_policy.py::test_determinism` | Same inputs → same action and quantity, always |
| `test_policy.py::test_llm_cannot_set_quantity` | Quantity is a pure function of policy inputs |
| `test_schema.py::test_invalid_agent_output` | Invalid output → abstain, never a zero forecast |

Skip testing: plotting code, notebook exploration, Streamlit layout.

---

## 7. Cost and Runtime Budget

Rough estimate for planning; measure and update once Phase 3 is running.

| Item | Estimate |
|---|---|
| LLM calls per fast-path run | 3 (context agents) |
| LLM calls per deliberated run | 3 + 1 critic + ~2 revisions ≈ 6 |
| Test-set runs (50 items × 100 days) | ~5,000 |
| Expected deliberation rate | ~20% |
| Total calls, RetailSense arm | ≈ 5,000 × (0.8×3 + 0.2×6) ≈ 18,000 |
| Total calls, always-on arm | ≈ 30,000 |

The gap between those last two rows **is RQ3**. It must be measured and reported, not estimated.

**Cost controls:** cache LLM responses by prompt hash during development; run the small dev slice until the pipeline is stable; set a hard project token budget in config and abort on breach.

---

## 8. Reproducibility Checklist

- [ ] Seed set for NumPy, LightGBM, and any sampling
- [ ] LLM temperature ≤ 0.3 and logged
- [ ] Prompts versioned in the repo, frozen at Phase 3 start
- [ ] External data snapshots committed
- [ ] Config committed per experiment; τ carries its calibration run ID
- [ ] MLflow run ID recorded in every results table
- [ ] `pip freeze` lockfile committed

**Caveat to state in the paper:** LLM outputs are not perfectly reproducible even at low temperature. Report multi-seed variance rather than claiming exact reproducibility, and treat any improvement smaller than the observed run-to-run variance as unsupported.

---

## 9. What to Do When Something Breaks

| Symptom | Action |
|---|---|
| pytrends returns 429 repeatedly | Use cached snapshots; if unavailable, Trend Agent abstains. Do not block the pipeline |
| Open-Meteo historical-forecast gap for a date | Mark degraded, lower Weather confidence, log it. Never substitute observed weather |
| LangGraph breaking change | Agent logic is plain Python — bypass the graph with a direct sequential runner (ADR-005 mitigation) |
| LLM provider outage | Swap `model` in config; the wrapper is provider-agnostic |
| SQLite lock during parallel runs | One DB file per run; merge afterward |
| Deliberation rate near 0% or 100% | τ is miscalibrated — rerun calibration; do not hand-adjust |
