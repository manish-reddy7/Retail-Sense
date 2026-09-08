# RetailSense prototype

An executable prototype of the supplied RetailSense design. It demonstrates the full decision flow with **synthetic demo inputs**; it does not claim M5 results or connect to live weather/Trends services.

## Run

Open `frontend/index.html` in any modern browser. No frontend build step or
Python web server is required.

Or run a terminal scenario:

```powershell
python -m src.demo
pytest -q
```

## Included

- Pydantic forecast contract and explicit abstention handling
- timestamp leakage gate
- independent historical, weather, trend, and calendar demo agents
- scale-free confidence-weighted disagreement and consensus intervals
- selective one-round, bounded deliberation with a conflict taxonomy
- deterministic RESTOCK / HOLD / REDUCE policy; no agent can set quantities
- dependency-free HTML/CSS/JavaScript dashboard

## Next integration step

Replace `src/demo.py` inputs with the M5 subset plus immutable weather and Trends snapshots. Keep actual demand in the evaluation layer only, and use the validation split (not test) to calibrate `thresholds.yaml`.
