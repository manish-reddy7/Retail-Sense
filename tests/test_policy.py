from src.inventory import decide
from src.orchestration.consensus import Forecast


def test_policy_is_deterministic():
    forecast = Forecast(100, (75, 125), .1, 4)
    assert decide(forecast, 100, 0) == decide(forecast, 100, 0)


def test_low_inventory_restocks():
    assert decide(Forecast(100, (75,125), .1, 4), 10, 0).action == "RESTOCK"

