from __future__ import annotations
from datetime import date


def assert_no_future_features(prediction_date: date, feature_source_dates: dict[str, date]) -> None:
    leaked = {name: stamp for name, stamp in feature_source_dates.items() if stamp >= prediction_date}
    if leaked:
        raise ValueError(f"Leakage audit failed; source timestamps must be before prediction date: {leaked}")

