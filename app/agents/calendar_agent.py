import os
from fastapi import APIRouter
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()
USE_GOOGLE_CALENDAR = os.getenv("USE_GOOGLE_CALENDAR", "false").lower() == "true"
TIMEZONE = os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh")

router = APIRouter()

class EventRequest(BaseModel):
    candidate_name: str
    candidate_email: EmailStr
    date: str             # YYYY-MM-DD
    time: str             # HH:MM (24h)
    duration_minutes: int = 30
    platform: str = "Google Meet"  # or "Zoom"/"Teams"

def _simulate_link(platform: str) -> str:
    base = {
        "Google Meet": "https://meet.google.com/",
        "Zoom": "https://zoom.us/j/",
        "Teams": "https://teams.microsoft.com/l/meetup-join/",
    }.get(platform, "https://meet.fake/")
    suffix = "hr-" + datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return base + suffix

@router.post("/create")
async def create(req: EventRequest):
    # Simulated default
    start_iso = f"{req.date}T{req.time}:00"
    try:
        start_dt = datetime.fromisoformat(start_iso)
    except ValueError:
        return {"error": "Invalid date/time format. Use YYYY-MM-DD and HH:MM (24h)."}
    end_dt = start_dt + timedelta(minutes=req.duration_minutes)

    event = {
        "summary": f"Screening Interview – {req.candidate_name}",
        "description": f"Screening interview with {req.candidate_name} for {req.platform}.",
        "start": {"dateTime": start_dt.isoformat(), "timeZone": TIMEZONE},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": TIMEZONE},
        "attendees": [{"email": req.candidate_email}],
        "meeting_link": _simulate_link(req.platform),
        "platform": req.platform,
        "simulated": True,
    }

    if USE_GOOGLE_CALENDAR:
        try:
            from app.utils.google_calendar import create_calendar_event
            real_event = create_calendar_event(event)
            return real_event
        except Exception as e:
            event["warning"] = f"Google Calendar failed, using simulated: {e}"
            return event

    return event
