"""
Backs the frontend's Employee Directory page (currently wired to mock
data in frontend/mock-server/db.json's "employees"/"checklists" keys).
Read-only: assembles the directory list/detail/checklist views from the
same tables the rest of the backend already reads -- Employee (see
routers/employees.py), and ProvisioningRecord/Ticket (see
routers/onboarding.py's provisioning_status()/employee_tickets() and
routers/profile.py's get_profile(), which combine the same two tables
for the Employee Profile screen).

Field notes: several fields the frontend mock exposes (type, progress,
blockers, est, remaining, phone, yearsOfService, jobLevel) have no
backing column or existing backend function anywhere in the project --
see models/employee.py's Employee model. Rather than invent new
business logic to derive them, they're left as None with a TODO below,
same spirit as ProvisioningRecord.external_ref's own TODO in
models/employee.py.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Employee, ProvisioningRecord, Ticket

router = APIRouter(prefix="/employee-directory", tags=["employee-directory"])


def _to_directory_entry(employee: Employee) -> dict:
    return {
        "id": employee.id,
        "name": employee.name,
        "dept": employee.department,
        "type": None,  # TODO: no fresher/experienced classification exists on Employee or elsewhere
        "manager": employee.manager,
        "status": employee.status,
        "progress": None,  # TODO: no onboarding-completion-percentage function exists; raw step data is available via onboarding.py's onboarding_status()/provisioning_status()
        "blockers": None,  # TODO: no "blockers" concept/count exists in current models
        "start": employee.joining_date,
        "est": None,  # TODO: no estimated-completion-date field/function exists
        "remaining": None,  # TODO: no remaining-days field/function exists
        "email": employee.email,
        "phone": None,  # TODO: no phone field exists on the Employee model
        "office": employee.office,
        "empManager": employee.manager,  # TODO: only one manager field exists on Employee; reused since there's no separate "reporting manager" field
        "hireDate": employee.joining_date,
        "yearsOfService": None,  # TODO: no tenure-calculation function exists
        "jobLevel": None,  # TODO: no job-level field exists on the Employee model
        "title": employee.title,
    }


def _to_checklist(db: Session, employee_id: str) -> list:
    """Same two-table read profile.py's get_profile() and onboarding.py's
    provisioning_status()/employee_tickets() already do: ProvisioningRecord
    rows are the real Functional items, Ticket rows are the Mock items
    (Functional items never get a ticket -- see models/employee.py's
    Ticket docstring)."""
    provisioning_records = (
        db.query(ProvisioningRecord)
        .filter(ProvisioningRecord.employee_id == employee_id)
        .all()
    )
    tickets = db.query(Ticket).filter(Ticket.employee_id == employee_id).all()

    checklist = [
        {
            "system": r.provisioning_item,
            "platform": r.software_name,
            "status": r.status,
            "kind": "Functional",
            "detail": r.error_detail,
            "outcome": r.external_ref,  # TODO: only populated once each integrations/*_connector.py returns a real external_ref -- see ProvisioningRecord.external_ref's TODO in models/employee.py
        }
        for r in provisioning_records
    ]
    checklist.extend(
        {
            "system": t.provisioning_item,
            "platform": t.software_name,
            "status": t.status,
            "kind": "Mock",
            "detail": t.notes,
            "outcome": None,  # TODO: Ticket has no field for a connector/system response payload
        }
        for t in tickets
    )
    return checklist


@router.get("")
def list_employee_directory(db: Session = Depends(get_db)):
    employees = db.query(Employee).all()
    return [_to_directory_entry(e) for e in employees]


@router.get("/{employee_id}")
def get_employee_directory_entry(employee_id: str, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return _to_directory_entry(employee)


@router.get("/{employee_id}/checklist")
def get_employee_directory_checklist(employee_id: str, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return _to_checklist(db, employee_id)
