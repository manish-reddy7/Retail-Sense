from __future__ import annotations
from dataclasses import dataclass
from src.orchestration.consensus import Forecast


@dataclass(frozen=True)
class InventoryDecision:
    action: str
    quantity: int
    reorder_point: float
    safety_stock: float
    rationale: str


def decide(forecast: Forecast, on_hand: int, on_order: int, lead_time_days: int = 3, service_z: float = 1.28, review_days: int = 7) -> InventoryDecision:
    sigma = max(0, (forecast.interval[1] - forecast.interval[0]) / (2 * 1.28))
    safety = service_z * sigma * (lead_time_days ** .5)
    reorder = forecast.point * lead_time_days + safety
    inventory_position = on_hand + on_order
    target = forecast.point * (lead_time_days + review_days) + safety
    if inventory_position < reorder:
        return InventoryDecision("RESTOCK", max(0, round(target - inventory_position)), round(reorder,1), round(safety,1), "Inventory position is below the deterministic reorder point.")
    if inventory_position > target * 1.2:
        return InventoryDecision("REDUCE", 0, round(reorder,1), round(safety,1), "Inventory is materially above the review-period target.")
    return InventoryDecision("HOLD", 0, round(reorder,1), round(safety,1), "Inventory is within the policy band.")

