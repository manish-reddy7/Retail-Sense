from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, model_validator


class AgentOutput(BaseModel):
    agent_id: str
    forecast: float | None = Field(default=None, ge=0)
    confidence: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0)
    prediction_interval: tuple[float, float] | None = None
    key_factors: list[str] = Field(min_length=1, max_length=4)
    reasoning: str
    abstained: bool = False
    abstain_reason: str | None = None
    data_availability: dict[str, str] = Field(default_factory=dict)
    position_held: bool = False
    changed_because: str | None = None

    @model_validator(mode="after")
    def validate_abstention(self) -> "AgentOutput":
        if self.abstained:
            if self.forecast is not None or not self.abstain_reason:
                raise ValueError("abstentions require a reason and no forecast")
        elif self.forecast is None or self.prediction_interval is None:
            raise ValueError("active forecasts require forecast and prediction_interval")
        return self


class Context(BaseModel):
    anchor: float = Field(gt=0)
    historical_mean: float = Field(gt=0)
    recent_volatility: float = Field(ge=0)
    weather_anomaly: float | None = None
    weather_available: bool = True
    trend_zscore: float | None = None
    trend_available: bool = True
    event: str | None = None
    event_multiplier: float = Field(default=1.0, gt=0)
    weekday_multiplier: float = Field(default=1.0, gt=0)


class CriticReport(BaseModel):
    conflict_type: Literal["T1", "T2", "T3", "T4", "T5"]
    conflict_summary: str
    resolvable: bool
    recommendation: Literal["revise", "widen_interval"]
    challenges: dict[str, str]

