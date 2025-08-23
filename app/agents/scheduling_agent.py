from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
import json
from datetime import datetime, timedelta
from app.services.openai_client import client, generate_email_prompt, parse_availability_prompt, AZURE_OPENAI_DEPLOYMENT
from app.services.gmail_client import send_email, get_emails, read_email

router = APIRouter()

def generate_google_meet_link() -> str:
    """Generate a Google Meet link"""
    import random
    import string
    
    def random_segment(length):
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
    
    meeting_id = f"{random_segment(3)}-{random_segment(4)}-{random_segment(3)}"
    return f"https://meet.google.com/{meeting_id}"

class CandidateRequest(BaseModel):
    name: str
    email: EmailStr
    position: str = "Software Engineer"
    job_title: str = "Software Engineer"

class MeetingInviteRequest(BaseModel):
    candidate_email: EmailStr
    candidate_name: str
    date: str  # YYYY-MM-DD
    time: str  # HH:MM
    timezone: str = "UTC"
    position: str = "Software Engineer"

@router.post("/request-availability")
async def request_availability(req: CandidateRequest):
    """Step 1: Send email to candidate asking for availability"""
    subject = f"Screening Interview Availability – {req.job_title}"
    prompt = generate_email_prompt(req.name, req.email, req.position, req.job_title)
    
    try:
        resp = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        email_text = resp.choices[0].message.content
        message_id, thread_id = send_email(req.email, subject, email_text)
        
        return {
            "status": "availability_request_sent",
            "email_text": email_text, 
            "message_id": message_id, 
            "thread_id": thread_id, 
            "to": req.email, 
            "subject": subject
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send availability request: {str(e)}")

@router.post("/schedule-meeting")
async def schedule_meeting(req: MeetingInviteRequest):
    """Step 2: Send Google Meet invitation"""
    try:
        # Generate Google Meet link
        meet_link = generate_google_meet_link()
        
        # Parse datetime for better formatting
        try:
            meeting_datetime = datetime.fromisoformat(f"{req.date}T{req.time}:00")
            formatted_date = meeting_datetime.strftime("%A, %B %d, %Y")
            formatted_time = meeting_datetime.strftime("%I:%M %p")
        except:
            formatted_date = req.date
            formatted_time = req.time
        
        # Send confirmation email
        meeting_subject = f"Interview Confirmed - {req.position} Position"
        meeting_body = f"""
Dear {req.candidate_name},

Thank you for your interest in the {req.position} position. Your screening interview has been confirmed for:

📅 Date: {formatted_date}
🕒 Time: {formatted_time} ({req.timezone})
📹 Meeting Link: {meet_link}
⏰ Duration: 30 minutes

MEETING DETAILS:
• Please join the Google Meet at the scheduled time
• Have your resume/CV ready for reference
• Ensure you have a stable internet connection
• The interview will take approximately 30 minutes

If you need to reschedule, please let us know as soon as possible.

Best regards,
HR Team

---
Meeting Link: {meet_link}
        """.strip()
        
        message_id, thread_id = send_email(req.candidate_email, meeting_subject, meeting_body)
        
        return {
            "status": "meeting_confirmed",
            "message_id": message_id,
            "thread_id": thread_id,
            "meeting_link": meet_link,
            "meeting_time": f"{formatted_date} at {formatted_time} ({req.timezone})",
            "candidate_name": req.candidate_name,
            "position": req.position
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send meeting confirmation: {str(e)}")

@router.get("/check-responses")
async def check_email_responses(candidate_email: str = None):
    """Step 3: Check for email responses and parse availability"""
    try:
        # Search for recent emails
        query = f"from:{candidate_email}" if candidate_email else "is:unread"
        messages = get_emails(query=query, max_results=10)
        
        responses = []
        for message in messages:
            email_data = read_email(message['id'])
            if email_data and 'available' in email_data.get('body', '').lower():
                # Parse availability using AI
                prompt = parse_availability_prompt(email_data['body'])
                resp = client.chat.completions.create(
                    model=AZURE_OPENAI_DEPLOYMENT,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                )
                
                try:
                    availability_data = json.loads(resp.choices[0].message.content)
                    responses.append({
                        "message_id": email_data['id'],
                        "from": email_data.get('from'),
                        "subject": email_data.get('subject'),
                        "availability": availability_data,
                        "body": email_data['body'][:200] + "..." if len(email_data['body']) > 200 else email_data['body']
                    })
                except json.JSONDecodeError:
                    responses.append({
                        "message_id": email_data['id'],
                        "from": email_data.get('from'),
                        "subject": email_data.get('subject'),
                        "raw_text": email_data['body'],
                        "parse_error": "Could not parse availability"
                    })
        
        return {"status": "responses_checked", "responses": responses}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check responses: {str(e)}")

@router.post("/auto-schedule-from-response")
async def auto_schedule_from_response(
    message_id: str,
    candidate_name: str,
    position: str = "Software Engineer"
):
    """Step 4: Automatically schedule meeting based on email response"""
    try:
        # Read the specific email
        email_data = read_email(message_id)
        if not email_data:
            raise HTTPException(status_code=404, detail="Email not found")
        
        # Parse availability
        prompt = parse_availability_prompt(email_data['body'])
        resp = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        
        availability_data = json.loads(resp.choices[0].message.content)
        
        # Get the first available option
        if 'options' in availability_data and availability_data['options']:
            first_option = availability_data['options'][0]
        else:
            first_option = availability_data
        
        # Schedule the meeting
        meeting_req = MeetingInviteRequest(
            candidate_email=email_data['from'].split('<')[-1].strip('>') if '<' in email_data['from'] else email_data['from'],
            candidate_name=candidate_name,
            date=first_option['date'],
            time=first_option['time'],
            timezone=first_option.get('timezone', 'UTC'),
            position=position
        )
        
        result = await schedule_meeting(meeting_req)
        result['parsed_availability'] = availability_data
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to auto-schedule: {str(e)}")

# Legacy endpoint for backward compatibility
@router.post("/send")
async def send(req: CandidateRequest):
    """Legacy endpoint - use /request-availability instead"""
    return await request_availability(req)
