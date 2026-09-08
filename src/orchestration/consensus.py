from __future__ import annotations
from dataclasses import dataclass
from src.agents.base import AgentOutput


@dataclass(frozen=True)
class Forecast:
    point: float
    interval: tuple[float, float]
    disagreement: float
    contributors: int


def _active(outputs: list[AgentOutput]) -> list[AgentOutput]:
    active = [o for o in outputs if not o.abstained and o.forecast is not None]
    if len(active) < 2:
        raise ValueError("at least two non-abstaining agents are required")
    return active


def disagreement(outputs: list[AgentOutput], epsilon: float = 1e-6) -> float:
    active = _active(outputs)
    weight = sum(o.confidence for o in active)
    mean = sum(o.confidence * o.forecast for o in active) / weight
    variance = sum(o.confidence * (o.forecast - mean) ** 2 for o in active) / weight
    # Do not add epsilon to a positive denominator: that would subtly break
    # the scale-invariance required for comparing low- and high-volume items.
    return (variance ** .5) / (mean if mean > epsilon else epsilon)


def consensus(outputs: list[AgentOutput]) -> Forecast:
    active = _active(outputs)
    weight = sum(o.confidence for o in active)
    point = sum(o.confidence * o.forecast for o in active) / weight
    spread = disagreement(active) * point
    uncertainty = sum(o.uncertainty * o.confidence for o in active) / weight * point
    margin = max(2.0, 1.28 * (spread + uncertainty))
    return Forecast(round(point, 1), (round(max(0, point-margin), 1), round(point+margin, 1)), round(disagreement(active), 3), len(active))
