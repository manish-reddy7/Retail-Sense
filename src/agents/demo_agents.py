from __future__ import annotations
from .base import AgentOutput, Context


def _output(agent_id: str, forecast: float, confidence: float, factor: str, reasoning: str) -> AgentOutput:
    width = max(3.0, forecast * (1 - confidence) * 1.35)
    return AgentOutput(agent_id=agent_id, forecast=round(max(0, forecast), 1), confidence=round(confidence, 2),
        uncertainty=round(1 - confidence, 2), prediction_interval=(round(max(0, forecast-width), 1), round(forecast+width, 1)),
        key_factors=[factor], reasoning=reasoning)


def historical_agent(c: Context) -> AgentOutput:
    confidence = min(.95, max(.3, 1 - c.recent_volatility / c.historical_mean))
    return _output("historical", c.historical_mean, confidence, "Recent demand pattern",
                   "Uses sales-history pattern and residual volatility; it does not inspect external context.")


def weather_agent(c: Context) -> AgentOutput:
    if not c.weather_available or c.weather_anomaly is None:
        return AgentOutput(agent_id="weather", confidence=0, uncertainty=1, key_factors=["Weather unavailable"],
            reasoning="Required weather snapshot is missing.", abstained=True, abstain_reason="missing weather snapshot",
            data_availability={"weather": "missing"})
    adjustment = max(-.4, min(.6, .07 * c.weather_anomaly))
    confidence = max(.3, .75 - (.25 if abs(c.weather_anomaly) < .5 else 0))
    return _output("weather", c.anchor * (1 + adjustment), confidence, f"Weather anomaly {c.weather_anomaly:+.1f}",
                   "Applies a bounded weather adjustment to the shared naive anchor.")


def trend_agent(c: Context) -> AgentOutput:
    if not c.trend_available or c.trend_zscore is None:
        return AgentOutput(agent_id="trend", confidence=0, uncertainty=1, key_factors=["Trend unavailable"],
            reasoning="Required immutable Trends snapshot is missing.", abstained=True, abstain_reason="missing trend snapshot",
            data_availability={"trends": "missing"})
    adjustment = max(-.3, min(.5, .09 * c.trend_zscore))
    confidence = max(.2, .60 - (.25 if abs(c.trend_zscore) < 1 else 0))
    return _output("trend", c.anchor * (1 + adjustment), confidence, f"Trend z-score {c.trend_zscore:+.1f}",
                   "Uses the category-level interest proxy with deliberately conservative confidence.")


def calendar_agent(c: Context) -> AgentOutput:
    multiplier = c.event_multiplier * c.weekday_multiplier
    confidence = .80 - (.15 if c.event else 0)
    factor = c.event or "Known weekday seasonality"
    return _output("calendar", c.anchor * multiplier, confidence, factor,
                   "Uses only known-in-advance calendar and weekday effects.")

