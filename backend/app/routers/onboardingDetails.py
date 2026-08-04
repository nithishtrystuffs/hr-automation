"""
Backs the frontend's Onboarding Details panel (frontend/mock-server/db.json's
"onboardingDetails" key). Read-only: aggregates from the same tables/orchestrator
the rest of the backend already reads -- Employee (see routers/employees.py),
ProvisioningRecord/Ticket (see routers/onboarding.py's provisioning_status()/
employee_tickets(), routers/profile.py's get_profile(), and
routers/employeeDirectory.py's _to_checklist(), which all combine the same two
tables), and the Health Check Orchestrator's cached sweep (see
routers/healthcheck.py's get_system_health(), which reads the same
get_cached_health() used below).

Field notes: the frontend mock's plannedCompletion/daysRemaining rely on an
estimated-completion-date concept that has no backing column or existing
backend function anywhere in the project -- same gap already flagged in
routers/employeeDirectory.py's module docstring for its "est"/"remaining"
fields. Left as None with a TODO below rather than inventing a business rule
for it.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Employee, ProvisioningRecord, Ticket
from app.orchestrators import health_check_orchestrator

router = APIRouter(prefix="/onboarding-details", tags=["onboarding-details"])

# Employee.status -> frontend's onboardingDetails.status. Employee.status only
# ever holds these three values (see models/employee.py's own comment on the
# column); anything unexpected falls back to the raw value rather than 500ing.
_STATUS_MAP = {
    "registered": "Not Started",
    "provisioning": "In Progress",
    "active": "Completed",
}


def _failed_provisioning_alerts(records: list[ProvisioningRecord]) -> list[dict]:
    """One alert per failed Functional item -- same rows
    routers/monitoring.py's monitoring_console() surfaces as
    "failing_provisioning_records"."""
    return [
        {
            "id": f"provisioning-{r.id}",
            "severity": "critical",
            "title": f"{r.software_name or r.provisioning_item} Failed",
            "body": r.error_detail or f"{r.provisioning_item} could not be provisioned.",
            "kind": "dismiss",
        }
        for r in records
        if r.status == "failed"
    ]


def _pending_ticket_alerts(tickets: list[Ticket]) -> list[dict]:
    """One alert per Mock item stuck in the side-branch "Pending" status --
    same rows routers/monitoring.py's monitoring_console() surfaces as
    "pending_tickets"."""
    return [
        {
            "id": f"ticket-{t.id}",
            "severity": "high",
            "title": f"{t.provisioning_item} Pending",
            "body": t.notes or f"Awaiting {t.assigned_team} action (ticket {t.ticket_id}).",
            "kind": "view",
        }
        for t in tickets
        if t.status == "Pending"
    ]


def _system_health_alerts(records: list[ProvisioningRecord]) -> list[dict]:
    """One alert per downstream system this employee's own provisioning
    actually depends on (matched by software_name) that the Health Check
    Orchestrator's cached sweep currently reports as not fully Operational --
    see orchestrators/health_check_orchestrator.py's get_cached_health().
    Never triggers a live sweep, same read-only rule routers/healthcheck.py's
    get_system_health() follows."""
    software_names = {r.software_name for r in records if r.software_name}
    if not software_names:
        return []

    try:
        detail = health_check_orchestrator.get_cached_health().get("systemHealthDetail", [])
    except Exception:
        return []  # cached health isn't on this endpoint's critical path -- degrade quietly, same as an empty cache

    alerts = []
    for entry in detail:
        if entry.get("status") == "Operational":
            continue
        if not any(entry["name"] in software for software in software_names):
            continue
        alerts.append({
            "id": f"health-{entry['name']}",
            "severity": "high" if entry.get("status") == "Down" else "medium",
            "title": f"{entry['name']} {entry.get('status')}",
            "body": f"Latency/status: {entry.get('latency')}.",
            "kind": "ack",
        })
    return alerts


@router.get("/{employee_id}")
def get_onboarding_details(employee_id: str, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    records = (
        db.query(ProvisioningRecord)
        .filter(ProvisioningRecord.employee_id == employee_id)
        .all()
    )
    tickets = db.query(Ticket).filter(Ticket.employee_id == employee_id).all()

    alerts = (
        _failed_provisioning_alerts(records)
        + _pending_ticket_alerts(tickets)
        + _system_health_alerts(records)
    )

    return {
        "status": _STATUS_MAP.get(employee.status, employee.status),
        # TODO: only an onboarding workflow exists in this backend (offboarding
        # models were removed entirely -- see models/employee.py's module
        # docstring); hardcoded rather than derived until a second workflow
        # type is reintroduced.
        "type": "Onboarding",
        "startDate": employee.joining_date,
        # TODO: no estimated-completion-date field/function exists anywhere in
        # the project -- see routers/employeeDirectory.py's matching "est" TODO.
        "plannedCompletion": None,
        # TODO: no remaining-days field/function exists, so this can't be
        # calculated from plannedCompletion above -- see
        # routers/employeeDirectory.py's matching "remaining" TODO.
        "daysRemaining": None,
        "alerts": alerts,
    }
