from src.agents import Context
from src.orchestration.pipeline import run_pipeline


def demo_context() -> Context:
    return Context(anchor=82, historical_mean=76, recent_volatility=17, weather_anomaly=4.2, trend_zscore=1.8,
                   event="Sporting event", event_multiplier=1.12, weekday_multiplier=1.04)


if __name__ == "__main__":
    result = run_pipeline(demo_context(), tau=.16, on_hand=120, on_order=0)
    print(f"Forecast: {result.forecast.point} {result.forecast.interval}; D={result.forecast.disagreement}")
    print(f"Deliberation: {result.triggered}; action: {result.decision.action} {result.decision.quantity} units")

