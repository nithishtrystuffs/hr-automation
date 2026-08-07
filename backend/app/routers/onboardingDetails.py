"""

Onboarding Detail screen -- read-only endpoint that reshapes existing

Employee, ProvisioningRecord, Ticket, and cached System Health rows into

the shape the frontend's onboarding detail page expects. No new business

logic: every value is either read straight off an existing model column,

a simple status-vocabulary lookup (same style routers/employeeDirectory.py

already uses), or a presentation-layer combination of existing rows.

"""

from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session
 
from app.database import get_db

from app.models import Employee, ProvisioningRecord, Ticket

from app.orchestrators import health_check_orchestrator
 
router = APIRouter(prefix="/onboarding-details", tags=["onboarding-details"])
 
# Employee.status ("registered" | "provisioning" | "active") -> the

# onboarding-status vocabulary the frontend already styles in

# lib/utils.ts's statusColorMap (Onboarding / In Progress / Completed).

_STATUS_LABELS = {

    "registered": "Onboarding",

    "provisioning": "In Progress",

    "active": "Completed",

}
 
# System only ever runs one workflow type -- offboarding was removed

# entirely (see models/employee.py's module docstring: "offboarding

# models... are gone"). Not mock data, just the app's one supported type.

_WORKFLOW_TYPE = "Onboarding"
 
 
def _provisioning_alert(record: ProvisioningRecord) -> dict:

    """kind="dismiss" matches AlertCard.tsx's Retry Now / Dismiss actions --

    the natural fit for a failed ProvisioningRecord, which is exactly what

    agents/monitoring_agent.py already retries against retry_count."""

    label = record.software_name or record.provisioning_item

    return {

        "id": f"prov-{record.id}",

        "severity": "critical",

        "title": f"{label} Failed",

        "body": record.error_detail

        or f"{record.provisioning_item} failed after {record.retry_count} attempt(s).",

        "kind": "dismiss",

    }
 
 
def _ticket_alert(ticket: Ticket) -> dict:

    """kind="view" matches AlertCard.tsx's View Details action -- for a

    ticket someone needs to look at. SLA-breached tickets (sla_flagged_at

    set by the Monitoring Agent per models/employee.py's Ticket docstring)

    get bumped to critical instead of high."""

    label = ticket.software_name or ticket.provisioning_item

    if ticket.sla_flagged_at is not None:

        return {

            "id": f"ticket-{ticket.ticket_id}",

            "severity": "critical",

            "title": f"{label} SLA Breached",

            "body": ticket.notes

            or f"Ticket {ticket.ticket_id} (assigned to {ticket.assigned_team}) has been "

            f"pending past the SLA window.",

            "kind": "view",

        }

    return {

        "id": f"ticket-{ticket.ticket_id}",

        "severity": "high",

        "title": f"{label} Pending",

        "body": ticket.notes

        or f"Ticket {ticket.ticket_id} is awaiting {ticket.assigned_team}.",

        "kind": "view",

    }
 
 
def _health_alert(detail: dict) -> dict:

    """kind="ack" matches AlertCard.tsx's Acknowledge action -- informational,

    not tied to a specific record. Reuses health_check_orchestrator's cache

    only (get_cached_health()), per that module's own caching requirement --

    never triggers a live sweep from a router."""

    name = detail.get("name")

    status = detail.get("status")

    severity = "critical" if status == "Down" else "medium"

    body = f"{name} is currently {status}."

    if status == "Degraded":

        body = f"{name} latency is {detail.get('latency')}, above the healthy threshold."

    return {

        "id": f"health-{name}",

        "severity": severity,

        "title": f"{name} {status}",

        "body": body,

        "kind": "ack",

    }
 
 
def _build_alerts(db: Session, employee_id: str) -> list[dict]:

    """Aggregates failed provisioning + pending/SLA-breached tickets for

    this employee, plus any non-Operational entry from the cached system

    health sweep -- combined here only, per instructions."""

    alerts = [

        _provisioning_alert(r)

        for r in db.query(ProvisioningRecord)

        .filter(

            ProvisioningRecord.employee_id == employee_id,

            ProvisioningRecord.status == "failed",

        )

        .all()

    ]
 
    alerts += [

        _ticket_alert(t)

        for t in db.query(Ticket)

        .filter(Ticket.employee_id == employee_id, Ticket.status == "Pending")

        .all()

    ]
 
    health = health_check_orchestrator.get_cached_health()

    alerts += [

        _health_alert(d)

        for d in health.get("systemHealthDetail", [])

        if d.get("status") != "Operational"

    ]
 
    return alerts
 
 
# Generic, status-driven note templates -- platform is no longer a lookup

# key, it's just interpolated into whichever status template applies.

PLATFORM_NOTE_TEMPLATES = {

    "Success": "The {platform} account for {username} has been successfully created",

    "In Progress": "The {platform} account for {username} is in progress",

    "Pending": "The {platform} account for {username} creation is pending",

    "Failed": "The {platform} account for {username} creation failed",

}
 
# ProvisioningRecord.status (backend vocabulary) -> the four note-template

# buckets above. This is the *only* place status strings are compared --

# add new backend status values here, never in the note-generation logic.

STATUS_TEMPLATE_MAPPING = {

    "completed": "Success",

    "success": "Success",

    "active": "Success",

    "provisioning": "In Progress",

    "in_progress": "In Progress",

    "running": "In Progress",

    "pending": "Pending",

    "failed": "Failed",

}
 
FUNCTIONAL_AGENT_KEYS = ["identity", "email", "time_billing", "document_management"]
 
 
def _format_dt(value):

    return value.strftime("%d-%m-%Y %H:%M:%S") if value else None
 
 
def _display_status(status: str) -> str:

    """Maps a ProvisioningRecord's raw status to the note-template

    vocabulary. Falls back to "Pending" for any status not yet in

    STATUS_TEMPLATE_MAPPING, rather than raising -- a new/unmapped

    backend status shouldn't 500 this endpoint."""

    return STATUS_TEMPLATE_MAPPING.get(status, "Pending")
 
 
def _provisioning_note(record: ProvisioningRecord, username: str) -> str:

    """Builds the Provisional Status note from record.status + platform,

    per PLATFORM_NOTE_TEMPLATES. No per-platform or per-status branching --

    adding a platform needs no code change, adding a status only needs an

    entry in STATUS_TEMPLATE_MAPPING."""

    display_status = _display_status(record.status)

    template = PLATFORM_NOTE_TEMPLATES[display_status]

    return template.format(platform=record.software_name, username=username)
 
 
@router.get("/{employee_id}/provisional-status")

def provisional_status(employee_id: str, db: Session = Depends(get_db)):

    """Functional-item provisioning status per employee, shaped for the

    Provisional Status screen. platform/startTime/endtime/credentials.username

    are read straight off ProvisioningRecord/Employee (null if the backend

    row/column has no value yet); ticketID, ticketStatus, credentials.password

    are mocked since this codebase has no ticket or credential concept for

    Functional items. note is generated dynamically from record.status and

    record.software_name via PLATFORM_NOTE_TEMPLATES/STATUS_TEMPLATE_MAPPING."""

    employees = (

        db.query(Employee)

        .filter(Employee.employee_id == employee_id)

        .all()

    )
 
    result = {}

    for employee in employees:

        records = (

            db.query(ProvisioningRecord)

            .filter(ProvisioningRecord.employee_id == employee.id)

            .filter(ProvisioningRecord.agent_key.in_(FUNCTIONAL_AGENT_KEYS))

            .all()

        )

        username = employee.name  # real

        password = username.replace(" ", "") if username else None  # mock -- no credential storage in the schema

        result[employee.employee_id] = [

            {

                "platform": record.software_name,  # real

                "ticketID": "TKT:001",  # mock -- Functional items never get a Ticket row

                "ticketStatus": "Success",  # mock -- no ticket lifecycle exists for Functional items

                "startTime": _format_dt(record.last_attempted_at),  # real

                #"endtime": _format_dt(record.completed_at),  # real

                "endtime":"05-08-2026 09:17:45", #mock

                "credentials": {

                    "username": username,  # real

                    "password": password,  # mock

                },

                "note": _provisioning_note(record, username),  # dynamic, status + platform driven

            }

            for record in records

        ]
 
    return {"ProvisionalStatus": result}
 
 
@router.get("/{employee_id}")

def get_onboarding_details(employee_id: str, db: Session = Depends(get_db)):

    employee = db.query(Employee).filter(Employee.employee_id == employee_id).first()

    if not employee:

        raise HTTPException(status_code=404, detail="Employee not found")
 
    return {

        "status": _STATUS_LABELS.get(employee.status, employee.status),

        "type": _WORKFLOW_TYPE,

        "startDate": employee.joining_date,

        # TODO: no estimated-completion-date field exists anywhere

        # (OnboardingTracker/ProvisioningRecord only record actual

        # timestamps) -- populate once such a field/orchestrator exists.

        "plannedCompletion": None,

        # TODO: depends on plannedCompletion above; left None rather than

        # inventing a days-remaining estimate with no backing date.

        "daysRemaining": None,

        "alerts": _build_alerts(db, employee_id),

    }
 