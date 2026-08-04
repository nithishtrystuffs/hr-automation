"""
Backs the frontend's System Health panel. Read-only by design: GET
/system-health only ever returns whatever the Health Check Orchestrator's
background loop last cached (see
orchestrators/health_check_orchestrator.py's module docstring -- the API
layer must never trigger a live sweep on a page load). POST
/system-health/refresh is the one deliberate escape hatch for an
on-demand manual refresh (e.g. an admin "Refresh now" button), calling
the same orchestrator function the background loop itself calls.
"""
import logging

from fastapi import APIRouter, HTTPException

from app.orchestrators import health_check_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system-health", tags=["system-health"])


@router.get("")
def get_system_health():
    """Returns the latest cached health sweep. Never runs a new one --
    see health_check_orchestrator.get_cached_health()'s docstring."""
    try:
        return health_check_orchestrator.get_cached_health()
    except Exception as exc:
        logger.error("Failed to read cached system health: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to read cached system health") from exc


@router.post("/refresh")
def refresh_system_health():
    """Manually triggers an immediate health sweep (bypassing the 30-minute
    schedule) and returns the freshly updated cached result. Same
    orchestrator function (refresh_health_cache()) the background loop
    calls on its own schedule -- this just calls it on demand."""
    try:
        return health_check_orchestrator.refresh_health_cache()
    except Exception as exc:
        logger.error("Failed to refresh system health: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to refresh system health") from exc
