from __future__ import annotations
from src.agents.base import AgentOutput, CriticReport

BOUNDS = {"historical": .20, "weather": .35, "trend": .40, "calendar": .25}


def critique(outputs: list[AgentOutput]) -> CriticReport:
    active = [o for o in outputs if not o.abstained]
    forecasts = [o.forecast for o in active]
    spread = max(forecasts) - min(forecasts)
    mean = sum(forecasts) / len(forecasts)
    low_conf = all(o.confidence < .55 for o in active)
    degraded = [o.agent_id for o in active if any(v != "available" for v in o.data_availability.values())]
    if degraded:
        kind, resolvable = "T5", True
    elif low_conf:
        kind, resolvable = "T3", False
    else:
        outlier = max(active, key=lambda o: abs(o.forecast - mean))
        kind, resolvable = ("T1", True) if outlier.agent_id == "historical" else ("T4", True)
    return CriticReport(conflict_type=kind, resolvable=resolvable, recommendation="revise" if resolvable else "widen_interval",
        conflict_summary=f"{kind}: forecasts span {spread:.1f} units around a mean of {mean:.1f}.",
        challenges={o.agent_id: "Reassess only your evidence; holding position is valid." for o in active})


def revise(outputs: list[AgentOutput]) -> list[AgentOutput]:
    active = [o for o in outputs if not o.abstained]
    target = sum(o.forecast * o.confidence for o in active) / sum(o.confidence for o in active)
    revised: list[AgentOutput] = []
    for o in outputs:
        if o.abstained:
            revised.append(o); continue
        max_shift = BOUNDS[o.agent_id] * o.forecast
        shift = max(-max_shift, min(max_shift, .35 * (target - o.forecast)))
        new_value = o.forecast + shift
        if abs(shift) < .01:
            revised.append(o.model_copy(update={"position_held": True, "changed_because": "Evidence supports original position."}))
        else:
            width = max(3, new_value * (1-o.confidence)*1.35)
            revised.append(o.model_copy(update={"forecast": round(new_value,1), "prediction_interval": (round(max(0,new_value-width),1),round(new_value+width,1)), "changed_because": "Moved within the agent-specific revision bound."}))
    return revised

