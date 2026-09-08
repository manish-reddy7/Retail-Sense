from __future__ import annotations
from dataclasses import dataclass
from src.agents import Context, calendar_agent, historical_agent, trend_agent, weather_agent
from src.agents.base import AgentOutput, CriticReport
from src.inventory import InventoryDecision, decide
from .consensus import Forecast, consensus
from .deliberation import critique, revise


@dataclass(frozen=True)
class RunResult:
    initial: list[AgentOutput]
    final_outputs: list[AgentOutput]
    forecast: Forecast
    triggered: bool
    critic: CriticReport | None
    decision: InventoryDecision


def run_pipeline(context: Context, tau: float, on_hand: int, on_order: int) -> RunResult:
    initial = [historical_agent(context), weather_agent(context), trend_agent(context), calendar_agent(context)]
    first = consensus(initial)
    triggered = first.disagreement >= tau
    critic: CriticReport | None = None
    final_outputs = initial
    if triggered:
        critic = critique(initial)
        if critic.resolvable:
            final_outputs = revise(initial)
            final = consensus(final_outputs)
        else:
            low, high = first.interval
            margin = (high-low) * .75
            final = Forecast(first.point, (max(0, round(first.point-margin,1)), round(first.point+margin,1)), first.disagreement, first.contributors)
    else:
        final = first
    return RunResult(initial, final_outputs, final, triggered, critic, decide(final, on_hand, on_order))

