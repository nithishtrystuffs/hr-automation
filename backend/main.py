"""
Entry point. Wires up all routers, creates DB tables on startup (fine
for POC -- use Alembic migrations if this grows past the POC), pre-warms
Ollama.

Trimmed for PDD v3: offboarding/access/assets/reports/insights/decisions/
compliance/licenses/audit routers are gone along with the models/services
they served. routers/approvals.py exists as a stub but is deliberately
NOT included below -- see its module docstring (pending PDD Suggestion #1).
"""
from dotenv import load_dotenv

load_dotenv()

import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app import models  # noqa: F401 -- ensures models are registered before create_all
from app.ai_client import prewarm
from app.routers import (
    auth, employees, hrms_sync, onboarding, dashboard, profile,
    hr_assistant, tickets, monitoring,agent_ticketing,healthcheck,employeeDirectory,onboardingDetails
)
from app.tests.test import router as dashboard_router  # noqa: F401 -- ensures test router is registered before create_all  
# TODO: from app.agents.monitoring_agent import monitoring_loop  -- uncomment
# once at least one integrations/*_connector.py is implemented, see below.

app = FastAPI(title="AI Orchestration POC API -- Employee Onboarding (v3)")
app.include_router(dashboard_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(employees.router)
app.include_router(hrms_sync.router)
app.include_router(onboarding.router)
app.include_router(dashboard.router)
app.include_router(profile.router)
app.include_router(tickets.router)
app.include_router(monitoring.router)
app.include_router(hr_assistant.router)
app.include_router(agent_ticketing.router)
app.include_router(healthcheck.router)
app.include_router(employeeDirectory.router)
app.include_router(onboardingDetails.router)

# TODO: app.include_router(approvals.router) -- see routers/approvals.py's
# module docstring, this is intentionally not wired in yet.


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    prewarm()
    # TODO: asyncio.create_task(monitoring_loop())  -- the Monitoring Agent's
    # background poll loop (agents/monitoring_agent.py). Commented out
    # rather than started, since right now every STATUS_CHECKERS entry
    # there is None -- it would just spin doing nothing. Uncomment the
    # import above and this line together, once at least one connector
    # (integrations/*_connector.py) is implemented and wired into
    # STATUS_CHECKERS.


@app.get("/")
def health():
    return {
        "status": "backend running",
        "service": "AI Orchestration POC -- Employee Onboarding (v3)",
    }
