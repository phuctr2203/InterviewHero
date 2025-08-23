from fastapi import FastAPI
from app.agents.cv_agent import router as cv_router
from app.agents.scheduling_agent import router as scheduling_router
from app.agents.email_listener import router as email_router
from app.agents.calendar_agent import router as calendar_router
from app.agents.monitor_agent import router as monitor_router
from app.agents.interview_prep_agent import router as interview_prep_router
from app.agents.interview_analyzer_agent import router as interview_analyzer_router
from app.agents.agent_system import router as agent_system_router

app = FastAPI(title="HR Multi-Agent System with Intelligent Coordination")

# Legacy individual agent endpoints (for backward compatibility)
app.include_router(cv_router, prefix="/cv", tags=["CV Agent"])
app.include_router(scheduling_router, prefix="/schedule", tags=["Scheduling Agent"])
app.include_router(email_router, prefix="/email", tags=["Email Listener"])
app.include_router(calendar_router, prefix="/calendar", tags=["Calendar Agent"])
app.include_router(monitor_router, prefix="/monitor", tags=["Email Monitor"])
app.include_router(interview_prep_router, prefix="/interview-prep", tags=["Interview Preparation"])
app.include_router(interview_analyzer_router, prefix="/interview-analyzer", tags=["Interview Analysis"])

# New multi-agent system
app.include_router(agent_system_router, prefix="/agents", tags=["Agent System"])

@app.get("/health")
def health():
    return {"status": "ok"}
