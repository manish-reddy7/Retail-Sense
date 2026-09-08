from src.agents.base import AgentOutput
from src.orchestration.consensus import disagreement


def out(value: float) -> AgentOutput:
    return AgentOutput(agent_id=str(value), forecast=value, confidence=.7, uncertainty=.3, prediction_interval=(value-1,value+1), key_factors=["x"], reasoning="x")


def test_scale_invariance():
    assert round(disagreement([out(10), out(20)]), 8) == round(disagreement([out(100), out(200)]), 8)


def test_identical_is_zero():
    assert disagreement([out(10), out(10)]) == 0

