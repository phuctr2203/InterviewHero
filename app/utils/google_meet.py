"""
Google Meet URL generation utilities
"""
import uuid
from datetime import datetime, timedelta
import random
import string
from typing import Dict, Any

def generate_google_meet_url() -> str:
    """
    Generate a Google Meet URL for the interview
    Note: This creates a mock URL for demo purposes.
    In production, you would integrate with Google Calendar API to create actual meetings.
    """
    # Generate a realistic-looking meeting ID
    meeting_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    meet_id_formatted = f"{meeting_id[:3]}-{meeting_id[3:7]}-{meeting_id[7:]}"
    
    return f"https://meet.google.com/{meet_id_formatted}"

def create_calendar_event_details(candidate_name: str, interview_datetime: datetime, 
                                duration_minutes: int = 60, position: str = "Software Engineer") -> Dict[str, Any]:
    """
    Create calendar event details for the interview
    """
    meet_url = generate_google_meet_url()
    
    # Calculate end time
    end_time = interview_datetime + timedelta(minutes=duration_minutes)
    
    return {
        "title": f"Interview with {candidate_name} - {position}",
        "start_time": interview_datetime,
        "end_time": end_time,
        "meet_url": meet_url,
        "description": f"""
Interview Details:
- Candidate: {candidate_name}
- Position: {position}
- Duration: {duration_minutes} minutes
- Meeting Link: {meet_url}

Interview Agenda:
1. Introduction and background (10 mins)
2. Technical discussion (30 mins)
3. Questions from candidate (15 mins)
4. Next steps (5 mins)

Please join the meeting a few minutes early to test your connection.
        """.strip(),
        "attendees": []
    }

def format_interview_datetime(date_str: str, time_str: str, timezone: str = "UTC") -> datetime:
    """
    Format interview date and time into datetime object
    """
    try:
        # Parse date and time
        from datetime import datetime
        
        # Handle different date formats
        if 'T' in date_str:
            # ISO format
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            # Standard date format
            date_part = datetime.strptime(date_str, "%Y-%m-%d").date()
            time_part = datetime.strptime(time_str, "%H:%M").time()
            dt = datetime.combine(date_part, time_part)
        
        return dt
    except Exception as e:
        # Fallback to current time + 1 day
        return datetime.now() + timedelta(days=1)

def create_google_calendar_link(event_details: Dict[str, Any]) -> str:
    """
    Create a Google Calendar add event link
    """
    import urllib.parse
    
    start_time = event_details['start_time']
    end_time = event_details['end_time']
    
    # Format times for Google Calendar (YYYYMMDDTHHMMSSZ)
    start_formatted = start_time.strftime('%Y%m%dT%H%M%SZ')
    end_formatted = end_time.strftime('%Y%m%dT%H%M%SZ')
    
    params = {
        'action': 'TEMPLATE',
        'text': event_details['title'],
        'dates': f"{start_formatted}/{end_formatted}",
        'details': event_details['description'],
        'location': event_details['meet_url']
    }
    
    query_string = urllib.parse.urlencode(params)
    return f"https://calendar.google.com/calendar/render?{query_string}"