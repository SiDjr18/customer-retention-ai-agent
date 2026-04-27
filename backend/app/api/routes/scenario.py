"""
Scenario Simulation route.

POST /scenario/simulate  — what-if retention campaign modeller.
"""
from fastapi import APIRouter, HTTPException

from app.decision_engine.scenario_service import (
    ScenarioService, SimulationRequest, SimulationResponse,
)

router = APIRouter()


@router.post(
    "/simulate",
    response_model=SimulationResponse,
    summary="Simulate a retention campaign scenario",
)
async def simulate_scenario(body: SimulationRequest) -> SimulationResponse:
    """
    What-if retention campaign simulator.

    Supply a budget, discount offer, target segment, and success-rate assumption.
    The engine will calculate how many customers can be reached, how many will
    be retained, and the expected ROI — all from the live dataset.

    **Auto-threshold**: if the supplied risk_threshold yields 0 matching
    customers (common when scores are sigmoid-compressed), the engine
    automatically falls back to the 75th-percentile threshold.
    """
    try:
        svc = ScenarioService()
        return svc.simulate(body)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"Dataset unavailable: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
