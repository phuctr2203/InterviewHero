"""
Agent Management System - Orchestrates communication between specialized agents
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from enum import Enum
from dataclasses import dataclass, asdict
from app.services.openai_client import client, AZURE_OPENAI_DEPLOYMENT

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AgentType(Enum):
    RECRUITER = "recruiter"
    SCHEDULER = "scheduler"
    INTERVIEWER = "interviewer"
    EMAIL_MONITOR = "email_monitor"
    CV_ANALYZER = "cv_analyzer"
    INTERVIEW_ANALYZER = "interview_analyzer"

class MessageType(Enum):
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    TASK_ASSIGNMENT = "task_assignment"
    STATUS_UPDATE = "status_update"

@dataclass
class AgentMessage:
    id: str
    from_agent: AgentType
    to_agent: AgentType
    message_type: MessageType
    content: Dict[str, Any]
    timestamp: datetime
    priority: int = 1  # 1=low, 2=medium, 3=high
    requires_response: bool = False

@dataclass
class AgentTask:
    id: str
    agent_type: AgentType
    task_type: str
    data: Dict[str, Any]
    status: str = "pending"  # pending, in_progress, completed, failed
    created_at: datetime = None
    completed_at: datetime = None
    result: Optional[Dict[str, Any]] = None

class BaseAgent:
    """Base class for all specialized agents"""
    
    def __init__(self, agent_type: AgentType, agent_manager: 'AgentManager'):
        self.agent_type = agent_type
        self.agent_manager = agent_manager
        self.message_queue = asyncio.Queue()
        self.is_active = False
        
    async def start(self):
        """Start the agent's message processing loop"""
        self.is_active = True
        logger.info(f"🤖 {self.agent_type.value} agent started")
        
        while self.is_active:
            try:
                # Process messages from queue
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                await self.process_message(message)
                self.message_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"❌ Error in {self.agent_type.value} agent: {e}")
    
    async def stop(self):
        """Stop the agent"""
        self.is_active = False
        logger.info(f"⏹️ {self.agent_type.value} agent stopped")
    
    async def process_message(self, message: AgentMessage):
        """Process incoming message - to be implemented by subclasses"""
        logger.info(f"📨 {self.agent_type.value} received: {message.message_type.value} from {message.from_agent.value}")
        
    async def send_message(self, to_agent: AgentType, message_type: MessageType, 
                          content: Dict[str, Any], priority: int = 1, requires_response: bool = False):
        """Send message to another agent"""
        message = AgentMessage(
            id=f"msg_{datetime.now().timestamp()}",
            from_agent=self.agent_type,
            to_agent=to_agent,
            message_type=message_type,
            content=content,
            timestamp=datetime.now(),
            priority=priority,
            requires_response=requires_response
        )
        
        await self.agent_manager.route_message(message)

class RecruiterAgent(BaseAgent):
    """Handles candidate communication and initial screening"""
    
    def __init__(self, agent_manager: 'AgentManager'):
        super().__init__(AgentType.RECRUITER, agent_manager)
    
    async def process_message(self, message: AgentMessage):
        await super().process_message(message)
        
        if message.message_type == MessageType.TASK_ASSIGNMENT:
            task_type = message.content.get("task_type")
            
            if task_type == "send_availability_request":
                await self.send_availability_request(message.content)
            elif task_type == "send_meeting_confirmation":
                await self.send_meeting_confirmation(message.content)
            elif task_type == "send_rejection_acknowledgment":
                await self.send_rejection_acknowledgment(message.content)
            elif task_type == "request_clarification":
                await self.send_clarification_request(message.content)
            elif task_type == "request_availability_clarification":
                await self.send_availability_clarification_request(message.content)
    
    async def send_availability_request(self, data: Dict[str, Any]):
        """Send availability request to candidate"""
        candidate_email = data.get('candidate_email')
        candidate_name = data.get('candidate_name')
        position_title = data.get('position_title', 'Software Engineer')
        
        logger.info(f"📧 Sending availability request to {candidate_email}")
        
        # Import Gmail client
        from app.services.gmail_client import send_email
        
        # Compose email
        subject = f"Interview Invitation - {position_title} Position"
        
        message_text = f"""Dear {candidate_name},

Thank you for your interest in the {position_title} position with our company.

We would like to schedule an interview with you to discuss your qualifications and learn more about your experience.

Please reply to this email with your availability for the next week. We are flexible with timing and can accommodate your schedule.

Some suggested time slots:
- Monday-Friday: 9:00 AM - 5:00 PM (UTC)
- Duration: 45-60 minutes
- Format: Video call (Google Meet link will be provided upon confirmation)

Please let us know:
1. Your preferred dates and times
2. Your timezone
3. Any scheduling constraints we should be aware of

We look forward to speaking with you!

Best regards,
HR Team

---
This email was sent automatically by our recruitment system. Please reply to schedule your interview.
"""
        
        try:
            # Send real email
            message_id, thread_id = send_email(
                to=candidate_email,
                subject=subject,
                message_text=message_text
            )
            
            if message_id:
                logger.info(f"✅ Availability request sent to {candidate_email} (Message ID: {message_id})")
                
                # Store thread ID for monitoring replies
                await self.agent_manager.store_email_thread(candidate_email, thread_id, message_id)
                
                # Notify scheduler and email monitor that request was sent
                await self.send_message(
                    to_agent=AgentType.SCHEDULER,
                    message_type=MessageType.NOTIFICATION,
                    content={
                        "event": "availability_request_sent",
                        "candidate_email": candidate_email,
                        "candidate_name": candidate_name,
                        "thread_id": thread_id,
                        "message_id": message_id
                    }
                )
                
                # Tell email monitor to watch for replies
                await self.send_message(
                    to_agent=AgentType.EMAIL_MONITOR,
                    message_type=MessageType.TASK_ASSIGNMENT,
                    content={
                        "task_type": "monitor_candidate_reply",
                        "candidate_email": candidate_email,
                        "thread_id": thread_id,
                        "message_id": message_id
                    }
                )
            else:
                logger.error(f"❌ Failed to send availability request to {candidate_email}")
                
        except Exception as e:
            logger.error(f"❌ Error sending email to {candidate_email}: {e}")
    
    async def send_meeting_confirmation(self, data: Dict[str, Any]):
        """Send meeting confirmation to candidate with Google Meet link"""
        candidate_email = data.get('candidate_email')
        availability = data.get('availability', {})
        
        logger.info(f"📅 Sending meeting confirmation to {candidate_email}")
        
        # Import required modules
        from app.services.gmail_client import send_email
        from app.utils.google_meet import generate_google_meet_url, format_interview_datetime, create_calendar_event_details, create_google_calendar_link
        
        try:
            # Generate Google Meet URL
            meet_url = generate_google_meet_url()
            
            # Extract candidate name from email
            candidate_name = candidate_email.split('@')[0].replace('.', ' ').title()
            
            # Parse interview datetime
            preferred_dates = availability.get('preferred_dates', [])
            preferred_times = availability.get('preferred_times', [])
            timezone = availability.get('timezone', 'UTC')
            
            if preferred_dates and preferred_times:
                interview_datetime = format_interview_datetime(preferred_dates[0], preferred_times[0], timezone)
            else:
                # Fallback datetime
                from datetime import datetime, timedelta
                interview_datetime = datetime.now() + timedelta(days=1)
            
            # Create calendar event details
            event_details = create_calendar_event_details(
                candidate_name=candidate_name,
                interview_datetime=interview_datetime,
                duration_minutes=45,
                position=data.get('position_title', 'Software Engineer')
            )
            
            # Create Google Calendar link
            calendar_link = create_google_calendar_link(event_details)
            
            # Format the datetime for email
            interview_date = interview_datetime.strftime('%A, %B %d, %Y')
            interview_time = interview_datetime.strftime('%I:%M %p')
            
            # Compose confirmation email
            subject = f"Interview Confirmed - {interview_date} at {interview_time}"
            
            message_text = f"""Dear {candidate_name},

Great news! Your interview has been confirmed for the {data.get('position_title', 'Software Engineer')} position.

📅 Interview Details:
• Date: {interview_date}
• Time: {interview_time} {timezone}
• Duration: 45 minutes
• Format: Video call via Google Meet

🔗 Join the Meeting:
{meet_url}

📎 Add to Calendar:
{calendar_link}

📝 Interview Agenda:
1. Introduction and background (10 minutes)
2. Technical discussion and experience review (25 minutes)
3. Questions from you about the role and company (10 minutes)

💡 Before the Interview:
• Please join the meeting 2-3 minutes early to test your connection
• Ensure you have a stable internet connection and quiet environment
• Have your resume and any questions ready
• Technical questions will be based on your experience and the role requirements

If you need to reschedule or have any questions, please reply to this email as soon as possible.

We look forward to speaking with you!

Best regards,
HR Team

---
Interview Meeting Link: {meet_url}
Add to Google Calendar: {calendar_link}
"""
            
            # Send email
            message_id, thread_id = send_email(
                to=candidate_email,
                subject=subject,
                message_text=message_text
            )
            
            if message_id:
                logger.info(f"✅ Meeting confirmation sent to {candidate_email} (Message ID: {message_id})")
            else:
                logger.error(f"❌ Failed to send meeting confirmation to {candidate_email}")
                
        except Exception as e:
            logger.error(f"❌ Error sending meeting confirmation to {candidate_email}: {e}")
    
    async def send_rejection_acknowledgment(self, data: Dict[str, Any]):
        """Send polite response when candidate rejects interview"""
        candidate_email = data.get('candidate_email')
        candidate_reason = data.get('candidate_reason', '')
        
        logger.info(f"📧 Sending rejection acknowledgment to {candidate_email}")
        
        from app.services.gmail_client import send_email
        
        try:
            candidate_name = candidate_email.split('@')[0].replace('.', ' ').title()
            
            subject = "Thank you for your response"
            
            message_text = f"""Dear {candidate_name},

Thank you for getting back to us regarding the interview opportunity.

We completely understand your decision and appreciate you taking the time to let us know. We respect your choice and wish you all the best in your job search and career journey.

If your circumstances change in the future, please don't hesitate to reach out. We would be happy to consider your application for other suitable positions that may arise.

Thank you again for your interest in our company, and we wish you continued success.

Best regards,
HR Team

---
This is an automated response from our recruitment system.
"""
            
            # Send email
            message_id, thread_id = send_email(
                to=candidate_email,
                subject=subject,
                message_text=message_text
            )
            
            if message_id:
                logger.info(f"✅ Rejection acknowledgment sent to {candidate_email}")
            else:
                logger.error(f"❌ Failed to send rejection acknowledgment to {candidate_email}")
                
        except Exception as e:
            logger.error(f"❌ Error sending rejection acknowledgment: {e}")
    
    async def send_clarification_request(self, data: Dict[str, Any]):
        """Send request for clarification when response is unclear"""
        candidate_email = data.get('candidate_email')
        original_message = data.get('original_message', '')
        
        logger.info(f"📧 Sending clarification request to {candidate_email}")
        
        from app.services.gmail_client import send_email
        
        try:
            candidate_name = candidate_email.split('@')[0].replace('.', ' ').title()
            
            subject = "Interview Scheduling - Could you please clarify?"
            
            message_text = f"""Dear {candidate_name},

Thank you for your response to our interview invitation.

We want to make sure we schedule the interview at a time that works best for you, but we need a bit more clarity on your availability.

Could you please let us know:
• Your preferred date(s) for the interview
• Your preferred time(s) 
• Your timezone

For example: "I'm available on Monday, August 26th at 2:00 PM EST" or "I'm free Tuesday or Wednesday afternoon after 1:00 PM PST"

We're flexible and want to accommodate your schedule. The interview will take approximately 45 minutes and will be conducted via Google Meet.

Please reply with your specific availability, and we'll send you a meeting confirmation with all the details.

Thank you for your patience!

Best regards,
HR Team
"""
            
            # Send email
            message_id, thread_id = send_email(
                to=candidate_email,
                subject=subject,
                message_text=message_text
            )
            
            if message_id:
                logger.info(f"✅ Clarification request sent to {candidate_email}")
            else:
                logger.error(f"❌ Failed to send clarification request to {candidate_email}")
                
        except Exception as e:
            logger.error(f"❌ Error sending clarification request: {e}")
    
    async def send_availability_clarification_request(self, data: Dict[str, Any]):
        """Send request for specific availability when time is unclear"""
        candidate_email = data.get('candidate_email')
        reason = data.get('reason', 'Could not determine specific meeting time')
        
        logger.info(f"📧 Sending availability clarification to {candidate_email}")
        
        from app.services.gmail_client import send_email
        
        try:
            candidate_name = candidate_email.split('@')[0].replace('.', ' ').title()
            
            subject = "Interview Scheduling - Please specify your preferred time"
            
            message_text = f"""Dear {candidate_name},

Thank you for accepting our interview invitation!

To schedule the meeting, we need you to specify your exact preferred date and time. Could you please reply with:

• Specific date (e.g., "Monday, August 26th, 2025")
• Specific time (e.g., "2:00 PM" or "14:00")
• Your timezone (e.g., "UTC", "EST", "PST")

For example: "I'm available on Monday, August 26th at 2:00 PM EST"

Once we receive your specific availability, we'll immediately send you:
• Google Meet link for the interview
• Calendar invitation
• Interview agenda and preparation tips

The interview will take approximately 45 minutes.

We look forward to hearing from you!

Best regards,
HR Team
"""
            
            # Send email
            message_id, thread_id = send_email(
                to=candidate_email,
                subject=subject,
                message_text=message_text
            )
            
            if message_id:
                logger.info(f"✅ Availability clarification sent to {candidate_email}")
            else:
                logger.error(f"❌ Failed to send availability clarification to {candidate_email}")
                
        except Exception as e:
            logger.error(f"❌ Error sending availability clarification: {e}")

class SchedulerAgent(BaseAgent):
    """Handles scheduling logic and calendar management"""
    
    def __init__(self, agent_manager: 'AgentManager'):
        super().__init__(AgentType.SCHEDULER, agent_manager)
        self.pending_schedules = {}
    
    async def process_message(self, message: AgentMessage):
        await super().process_message(message)
        
        if message.message_type == MessageType.NOTIFICATION:
            event = message.content.get("event")
            
            if event == "candidate_response_received":
                await self.process_candidate_response(message.content)
    
    async def process_candidate_response(self, data: Dict[str, Any]):
        """Process candidate availability response"""
        candidate_email = data.get("candidate_email")
        availability = data.get("availability")
        
        logger.info(f"📅 Processing response for {candidate_email}")
        
        # Check if candidate accepted or rejected
        response_type = availability.get("response_type", "unclear")
        
        if response_type == "accept":
            logger.info(f"✅ {candidate_email} ACCEPTED the interview")
            await self.handle_interview_acceptance(candidate_email, availability)
            
        elif response_type == "reject":
            logger.info(f"❌ {candidate_email} REJECTED the interview")
            await self.handle_interview_rejection(candidate_email, availability)
            
        else:
            logger.warning(f"❓ {candidate_email} response unclear - manual review needed")
            await self.handle_unclear_response(candidate_email, availability)
    
    async def handle_interview_acceptance(self, candidate_email: str, availability: Dict[str, Any]):
        """Handle when candidate accepts the interview"""
        # Parse and validate availability
        if self.validate_availability(availability):
            # Ask recruiter to send meeting confirmation with Google Meet link
            await self.send_message(
                to_agent=AgentType.RECRUITER,
                message_type=MessageType.TASK_ASSIGNMENT,
                content={
                    "task_type": "send_meeting_confirmation",
                    "candidate_email": candidate_email,
                    "availability": availability,
                    "response_type": "accept"
                }
            )
            
            # Notify interviewer to prepare
            await self.send_message(
                to_agent=AgentType.INTERVIEWER,
                message_type=MessageType.NOTIFICATION,
                content={
                    "event": "interview_scheduled",
                    "candidate_email": candidate_email,
                    "schedule": availability
                }
            )
        else:
            # Availability not valid, ask for clarification
            await self.send_message(
                to_agent=AgentType.RECRUITER,
                message_type=MessageType.TASK_ASSIGNMENT,
                content={
                    "task_type": "request_availability_clarification",
                    "candidate_email": candidate_email,
                    "reason": "Could not determine specific meeting time"
                }
            )
    
    async def handle_interview_rejection(self, candidate_email: str, availability: Dict[str, Any]):
        """Handle when candidate rejects the interview"""
        reason = availability.get("reason", "Candidate declined interview")
        
        # Ask recruiter to send polite rejection response
        await self.send_message(
            to_agent=AgentType.RECRUITER,
            message_type=MessageType.TASK_ASSIGNMENT,
            content={
                "task_type": "send_rejection_acknowledgment",
                "candidate_email": candidate_email,
                "candidate_reason": reason,
                "response_type": "reject"
            }
        )
    
    async def handle_unclear_response(self, candidate_email: str, availability: Dict[str, Any]):
        """Handle when candidate response is unclear"""
        # Ask recruiter to request clarification
        await self.send_message(
            to_agent=AgentType.RECRUITER,
            message_type=MessageType.TASK_ASSIGNMENT,
            content={
                "task_type": "request_clarification",
                "candidate_email": candidate_email,
                "original_message": availability.get("candidate_message", ""),
                "response_type": "unclear"
            }
        )
    
    def validate_availability(self, availability: Dict[str, Any]) -> bool:
        """Validate if the proposed time is acceptable"""
        # Add business logic here
        return True

class InterviewerAgent(BaseAgent):
    """Handles interview preparation and question generation"""
    
    def __init__(self, agent_manager: 'AgentManager'):
        super().__init__(AgentType.INTERVIEWER, agent_manager)
    
    async def process_message(self, message: AgentMessage):
        await super().process_message(message)
        
        if message.message_type == MessageType.NOTIFICATION:
            event = message.content.get("event")
            
            if event == "interview_scheduled":
                await self.prepare_interview_questions(message.content)
    
    async def prepare_interview_questions(self, data: Dict[str, Any]):
        """Prepare interview questions for the candidate"""
        candidate_email = data.get("candidate_email")
        logger.info(f"📋 Preparing interview questions for {candidate_email}")
        
        # Request CV analysis from CV analyzer
        await self.send_message(
            to_agent=AgentType.CV_ANALYZER,
            message_type=MessageType.REQUEST,
            content={
                "action": "analyze_cv",
                "candidate_email": candidate_email
            },
            requires_response=True
        )

class EmailMonitorAgent(BaseAgent):
    """Monitors emails and detects candidate responses"""
    
    def __init__(self, agent_manager: 'AgentManager'):
        super().__init__(AgentType.EMAIL_MONITOR, agent_manager)
        self.monitoring = False
        self.monitored_threads = {}  # {thread_id: candidate_email}
    
    async def process_message(self, message: AgentMessage):
        await super().process_message(message)
        
        if message.message_type == MessageType.TASK_ASSIGNMENT:
            task_type = message.content.get("task_type")
            
            if task_type == "monitor_candidate_reply":
                await self.add_thread_monitoring(message.content)
    
    async def add_thread_monitoring(self, data: Dict[str, Any]):
        """Add a thread to monitor for replies"""
        thread_id = data.get("thread_id")
        candidate_email = data.get("candidate_email")
        message_id = data.get("message_id")
        
        if thread_id and candidate_email:
            self.monitored_threads[thread_id] = candidate_email
            logger.info(f"📧 ✅ Now monitoring thread {thread_id} (message {message_id}) for replies from {candidate_email}")
            logger.info(f"📧 📊 Total monitored threads: {len(self.monitored_threads)}")
        else:
            logger.error(f"❌ Failed to add thread monitoring - missing thread_id: {thread_id} or candidate_email: {candidate_email}")
    
    async def start_monitoring(self):
        """Start email monitoring"""
        self.monitoring = True
        logger.info("📧 Email monitoring started")
        
        # Real email monitoring loop
        while self.monitoring and self.is_active:
            try:
                # Check monitored threads for replies
                await self.check_for_replies()
                await asyncio.sleep(60)  # Check every 60 seconds
            except Exception as e:
                logger.error(f"❌ Error in email monitoring: {e}")
                await asyncio.sleep(60)  # Continue monitoring even after errors
    
    async def check_for_replies(self):
        """Check monitored threads for new replies"""
        if not self.monitored_threads:
            logger.info("📧 No threads being monitored")
            return
            
        logger.info(f"📧 Checking {len(self.monitored_threads)} monitored threads for replies")
        
        try:
            from app.services.gmail_client import get_latest_reply_in_thread
        except ImportError as e:
            logger.error(f"❌ Error importing Gmail client: {e}")
            return
        
        for thread_id, candidate_email in list(self.monitored_threads.items()):
            try:
                logger.info(f"📧 Checking thread {thread_id} for replies from {candidate_email}")
                
                # Check for latest reply from this candidate
                reply_body = get_latest_reply_in_thread(thread_id, candidate_email)
                
                if reply_body:
                    logger.info(f"📧 Found reply from {candidate_email} in thread {thread_id}: {reply_body[:100]}...")
                    
                    # Parse availability from reply
                    availability = await self.parse_availability_from_email(reply_body)
                    
                    # Process the candidate email
                    await self.process_candidate_email({
                        "from": candidate_email,
                        "body": reply_body,
                        "thread_id": thread_id,
                        "parsed_availability": availability
                    })
                    
                    # Remove from monitoring (found reply)
                    del self.monitored_threads[thread_id]
                    logger.info(f"✅ Removed thread {thread_id} from monitoring after processing reply")
                else:
                    logger.info(f"📧 No new reply found in thread {thread_id} from {candidate_email}")
                    
            except Exception as e:
                logger.error(f"❌ Error checking thread {thread_id}: {e}")
                import traceback
                logger.error(traceback.format_exc())
    
    async def parse_availability_from_email(self, email_body: str) -> Dict[str, Any]:
        """Parse availability information and candidate response from email body using AI"""
        try:
            from app.services.openai_client import client, AZURE_OPENAI_DEPLOYMENT
            
            prompt = f"""
            Analyze this candidate's email response to an interview invitation.
            Determine if they ACCEPT or REJECT the interview and extract scheduling information.
            
            Email content:
            {email_body}
            
            Return a JSON object with:
            - response_type: "accept" or "reject" or "unclear"
            - preferred_dates: array of date strings (YYYY-MM-DD) - only if accepting
            - preferred_times: array of time strings (HH:MM format) - only if accepting  
            - timezone: string (e.g., "UTC", "EST", "PST") - only if accepting
            - constraints: array of any mentioned scheduling constraints
            - confidence: number 0-1 indicating parsing confidence
            - reason: string explaining their response (for rejections or unclear cases)
            - candidate_message: brief summary of what the candidate said
            
            Examples:
            - "I'm available Monday at 2 PM" = accept with availability
            - "Sorry, I can't make it" = reject
            - "I'm not interested" = reject
            - "Unfortunately I have to decline" = reject
            - "Thanks but I found another position" = reject
            """
            
            response = client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": "You are an AI assistant that parses scheduling information from emails. Return valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            # Get and clean the response content
            response_content = response.choices[0].message.content
            logger.info(f"📧 OpenAI availability response: {response_content[:200]}...")
            
            # Clean markdown formatting
            cleaned_content = response_content.strip()
            if cleaned_content.startswith('```json'):
                cleaned_content = cleaned_content[7:]
                if cleaned_content.endswith('```'):
                    cleaned_content = cleaned_content[:-3]
            elif cleaned_content.startswith('```'):
                cleaned_content = cleaned_content[3:]
                if cleaned_content.endswith('```'):
                    cleaned_content = cleaned_content[:-3]
            
            cleaned_content = cleaned_content.strip()
            
            # Parse the JSON response
            import json
            availability = json.loads(cleaned_content)
            logger.info(f"✅ Successfully parsed availability: {availability}")
            return availability
            
        except Exception as e:
            logger.error(f"❌ Error parsing availability: {e}")
            return {
                "response_type": "unclear",
                "preferred_dates": [],
                "preferred_times": [],
                "timezone": "UTC",
                "constraints": [],
                "confidence": 0,
                "reason": f"Error parsing email: {str(e)}",
                "candidate_message": "Unable to parse candidate response"
            }
    
    async def process_candidate_email(self, email_data: Dict[str, Any]):
        """Process detected candidate email"""
        logger.info(f"📧 Processing candidate email from {email_data.get('from')}")
        
        # Notify scheduler about the response
        await self.send_message(
            to_agent=AgentType.SCHEDULER,
            message_type=MessageType.NOTIFICATION,
            content={
                "event": "candidate_response_received",
                "candidate_email": email_data.get("from"),
                "email_content": email_data.get("body"),
                "availability": email_data.get("parsed_availability")
            }
        )

class CVAnalyzerAgent(BaseAgent):
    """Analyzes candidate CVs and extracts insights"""
    
    def __init__(self, agent_manager: 'AgentManager'):
        super().__init__(AgentType.CV_ANALYZER, agent_manager)
    
    def extract_candidate_name(self, cv_text: str, candidate_email: str) -> str:
        """Extract candidate name from CV or email"""
        try:
            # Try to extract from email first
            if candidate_email:
                name_part = candidate_email.split('@')[0]
                # Convert email format to name (e.g., john.doe -> John Doe)
                name = name_part.replace('.', ' ').replace('_', ' ').title()
                
                # If CV contains actual name, try to extract it
                if cv_text:
                    lines = cv_text.split('\n')[:5]  # Check first 5 lines
                    for line in lines:
                        line = line.strip()
                        # Look for name patterns
                        if len(line.split()) <= 3 and len(line) > 2 and not '@' in line and not any(char.isdigit() for char in line):
                            if any(word.istitle() for word in line.split()):
                                return line
                
                return name
            else:
                return "the candidate"
        except:
            return "the candidate"
    
    def create_fallback_analysis(self, candidate_name: str, candidate_email: str, cv_text: str) -> Dict[str, Any]:
        """Create a fallback analysis when OpenAI fails"""
        logger.info(f"🔄 Creating fallback analysis for {candidate_name}")
        
        # Basic skill extraction from CV text
        skills = []
        if cv_text:
            common_skills = ["Python", "JavaScript", "React", "Node.js", "Java", "SQL", "Docker", "AWS", "Git", "HTML", "CSS"]
            cv_upper = cv_text.upper()
            skills = [skill for skill in common_skills if skill.upper() in cv_upper]
        
        # Estimate experience from years mentioned in CV
        experience_years = 0
        if cv_text:
            import re
            year_matches = re.findall(r'20\d{2}', cv_text)
            if len(year_matches) >= 2:
                years = [int(y) for y in year_matches]
                experience_years = max(years) - min(years)
        
        # Generate basic personalized questions
        basic_questions = [
            {
                "question": f"Hi {candidate_name}, can you tell me about yourself and your background?",
                "purpose": "Opening question to get candidate comfortable and understand their background",
                "follow_up_hints": "Listen for key experiences, skills, and career progression"
            },
            {
                "question": "What attracted you to apply for this position?",
                "purpose": "Understand candidate motivation and interest",
                "follow_up_hints": "Look for genuine interest vs generic answers"
            },
            {
                "question": "Can you walk me through your most recent work experience?",
                "purpose": "Understand current/recent role and responsibilities",
                "follow_up_hints": "Ask about specific projects, challenges, achievements"
            },
            {
                "question": f"I see you have experience with {', '.join(skills[:3]) if skills else 'various technologies'}. Can you tell me more about that?",
                "purpose": "Assess technical capabilities based on CV",
                "follow_up_hints": "Ask for specific examples of how they've used these skills"
            },
            {
                "question": "Describe a challenging project you've worked on recently.",
                "purpose": "Evaluate problem-solving abilities and technical depth",
                "follow_up_hints": "Focus on their role, approach, and outcome"
            },
            {
                "question": "How do you approach learning new technologies?",
                "purpose": "Assess learning mindset and adaptability",
                "follow_up_hints": "Look for concrete examples of continuous learning"
            },
            {
                "question": "Tell me about a time you had to collaborate with team members to solve a problem.",
                "purpose": "Evaluate teamwork and communication skills",
                "follow_up_hints": "Focus on their communication and conflict resolution"
            },
            {
                "question": "What are your career goals for the next few years?",
                "purpose": "Understand career aspirations and alignment with role",
                "follow_up_hints": "See if goals align with company growth opportunities"
            },
            {
                "question": "Why are you looking for a new opportunity?",
                "purpose": "Understand motivation for job change",
                "follow_up_hints": "Listen for red flags vs legitimate career advancement"
            },
            {
                "question": "What questions do you have about our company or this role?",
                "purpose": "Assess level of research and genuine interest",
                "follow_up_hints": "Quality questions indicate preparation and interest"
            }
        ]
        
        return {
            "candidate_name": candidate_name,
            "key_skills": skills,
            "experience_years": experience_years,
            "education": "Not specified",
            "highlights": ["Experience with modern technologies", "Professional background"],
            "match_score": 75,  # Neutral score
            "summary": f"Fallback analysis generated - {candidate_name} appears to have {experience_years} years of experience with skills in {', '.join(skills[:3]) if skills else 'various technologies'}.",
            "interview_questions": basic_questions,
            "estimated_duration": "30 minutes",
            "interview_focus_areas": ["Background", "Experience", "Technical skills", "Teamwork", "Motivation"]
        }
    
    async def send_interview_questions_to_hr(self, analysis_result: Dict[str, Any], task_data: Dict[str, Any]):
        """Send interview questions to HR email"""
        try:
            from app.services.gmail_client import send_email
            
            candidate_name = analysis_result.get("candidate_name", "Candidate")
            candidate_email = analysis_result.get("candidate_email", "")
            position_title = task_data.get("position_title", "Software Engineer")
            match_score = analysis_result.get("match_score", 0)
            
            # Format interview questions
            questions_html = ""
            for i, q in enumerate(analysis_result.get("interview_questions", []), 1):
                questions_html += f"""
                <div style="margin-bottom: 20px;">
                    <h4>{i}. {q.get('question', '')}</h4>
                    <p><strong>Purpose:</strong> {q.get('purpose', '')}</p>
                    <p><strong>Follow-up hints:</strong> {q.get('follow_up_hints', '')}</p>
                </div>
                """
            
            # Create comprehensive candidate review section
            candidate_review_html = f"""
            <div style="background-color: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 8px; border: 1px solid #dee2e6;">
                <h2 style="color: #495057; margin-top: 0; border-bottom: 2px solid #6c757d; padding-bottom: 10px;">
                    📋 Candidate Review & Assessment
                </h2>
                
                <div style="display: grid; gap: 15px;">
                    <div style="background-color: white; padding: 15px; border-radius: 5px; border-left: 4px solid #007bff;">
                        <h4 style="color: #007bff; margin: 0 0 10px 0;">👤 Personal Information</h4>
                        <p><strong>Full Name:</strong> {candidate_name}</p>
                        <p><strong>Email:</strong> {candidate_email}</p>
                        <p><strong>Position Applied:</strong> {position_title}</p>
                    </div>
                    
                    <div style="background-color: white; padding: 15px; border-radius: 5px; border-left: 4px solid #28a745;">
                        <h4 style="color: #28a745; margin: 0 0 10px 0;">💼 Professional Profile</h4>
                        <p><strong>Years of Experience:</strong> {analysis_result.get('experience_years', 0)} years</p>
                        <p><strong>Education:</strong> {analysis_result.get('education', 'Not provided')}</p>
                        <p><strong>Technical Skills:</strong> {', '.join(analysis_result.get('key_skills', [])) if analysis_result.get('key_skills') else 'Various technologies'}</p>
                    </div>
                    
                    <div style="background-color: white; padding: 15px; border-radius: 5px; border-left: 4px solid #ffc107;">
                        <h4 style="color: #f57c00; margin: 0 0 10px 0;">⭐ Key Highlights</h4>
                        {'<ul style="margin: 0; padding-left: 20px;">' + ''.join([f'<li style="margin-bottom: 5px;">{h}</li>' for h in analysis_result.get('highlights', [])]) + '</ul>' if analysis_result.get('highlights') else '<p style="font-style: italic; color: #6c757d;">No specific highlights identified</p>'}
                    </div>
                    
                    <div style="background-color: white; padding: 15px; border-radius: 5px; border-left: 4px solid #dc3545;">
                        <h4 style="color: #dc3545; margin: 0 0 10px 0;">🎯 Match Assessment</h4>
                        <div style="display: flex; align-items: center; margin-bottom: 10px;">
                            <span style="font-size: 18px; font-weight: bold; margin-right: 15px;">Match Score:</span>
                            <div style="background-color: #e9ecef; border-radius: 10px; padding: 5px; width: 200px; position: relative;">
                                <div style="background-color: {
                                    '#28a745' if match_score >= 80 else 
                                    '#ffc107' if match_score >= 60 else 
                                    '#fd7e14' if match_score >= 40 else '#dc3545'
                                }; height: 20px; border-radius: 5px; width: {match_score}%; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;">
                                    {match_score}%
                                </div>
                            </div>
                        </div>
                        <p style="margin: 0;"><strong>Assessment Summary:</strong></p>
                        <p style="margin: 5px 0; padding: 10px; background-color: #f8f9fa; border-radius: 3px; font-style: italic;">
                            {analysis_result.get('summary', 'No summary provided')}
                        </p>
                    </div>
                    
                    <div style="background-color: white; padding: 15px; border-radius: 5px; border-left: 4px solid #6f42c1;">
                        <h4 style="color: #6f42c1; margin: 0 0 10px 0;">🎤 Interview Focus Areas</h4>
                        <div style="display: flex; flex-wrap: wrap; gap: 8px;">
                            {''.join([f'<span style="background-color: #e7e3ff; color: #6f42c1; padding: 5px 10px; border-radius: 15px; font-size: 12px; font-weight: 500;">{area}</span>' for area in analysis_result.get('interview_focus_areas', [])])}
                        </div>
                    </div>
                </div>
            </div>
            """
            
            # Create HTML email content
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 800px; margin: 0 auto; padding: 20px;">
                    <h1 style="color: #2c3e50; text-align: center; border-bottom: 3px solid #3498db; padding-bottom: 15px;">
                        📄 Candidate Analysis & Interview Guide
                    </h1>
                    
                    {candidate_review_html}
                    
                    <div style="background-color: white; padding: 20px; margin: 20px 0; border-radius: 8px; border: 1px solid #dee2e6;">
                        <h2 style="color: #27ae60; margin-top: 0; border-bottom: 2px solid #27ae60; padding-bottom: 10px;">
                            🎤 Interview Questions ({len(analysis_result.get('interview_questions', []))} questions - {analysis_result.get('estimated_duration', '30 minutes')})
                        </h2>
                        <div style="margin: 20px 0;">
                            {questions_html}
                        </div>
                    </div>
                    
                    <div style="background-color: #fff3cd; padding: 20px; margin: 20px 0; border: 1px solid #ffeaa7; border-radius: 8px;">
                        <h4 style="color: #856404; margin-top: 0; display: flex; align-items: center;">
                            💡 Interview Tips & Best Practices
                        </h4>
                        <ul style="color: #856404; margin: 0; padding-left: 20px;">
                            <li style="margin-bottom: 8px;">Start with the opening question to make the candidate comfortable</li>
                            <li style="margin-bottom: 8px;">Allow 5-7 minutes for the candidate to ask questions at the end</li>
                            <li style="margin-bottom: 8px;">Take notes on key responses for follow-up discussions</li>
                            <li style="margin-bottom: 8px;">Use follow-up hints to dive deeper into interesting topics</li>
                            <li style="margin-bottom: 8px;">Focus on cultural fit and motivation alongside technical skills</li>
                            <li>Pay attention to communication skills and problem-solving approach</li>
                        </ul>
                    </div>
                    
                    <hr style="margin: 30px 0; border: none; border-top: 1px solid #dee2e6;">
                    <div style="text-align: center; color: #7f8c8d; font-size: 12px; padding: 15px;">
                        <p style="margin: 0;">🤖 This comprehensive interview guide was automatically generated by the HR Multi-Agent System</p>
                        <p style="margin: 5px 0 0 0;">Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Send email to HR
            subject = f"Interview Questions Ready: {candidate_name} - {position_title}"
            
            message_id, thread_id = send_email(
                to="interview.hero.hr@gmail.com",
                subject=subject,
                message_text=html_content,
                html=True
            )
            
            if message_id:
                logger.info(f"✅ Interview questions sent to HR for {candidate_name} (Message ID: {message_id})")
            else:
                logger.error(f"❌ Failed to send interview questions to HR for {candidate_name}")
                
        except Exception as e:
            logger.error(f"❌ Error sending interview questions to HR: {e}")
    
    async def process_message(self, message: AgentMessage):
        await super().process_message(message)
        
        if message.message_type == MessageType.REQUEST:
            action = message.content.get("action")
            
            if action == "analyze_cv":
                await self.analyze_cv(message)
        elif message.message_type == MessageType.TASK_ASSIGNMENT:
            task_type = message.content.get("task_type")
            
            if task_type == "analyze_cv":
                await self.analyze_cv_from_task(message.content)
    
    async def analyze_cv(self, message: AgentMessage):
        """Analyze candidate's CV"""
        candidate_email = message.content.get("candidate_email")
        logger.info(f"📄 Analyzing CV for {candidate_email}")
        
        # Simulate CV analysis
        analysis_result = {
            "candidate_email": candidate_email,
            "key_skills": ["Python", "React", "Node.js"],
            "experience_years": 3,
            "education": "Computer Science",
            "highlights": ["Led migration project", "Mentored junior developers"]
        }
        
        # Send analysis back to interviewer
        await self.send_message(
            to_agent=message.from_agent,
            message_type=MessageType.RESPONSE,
            content={
                "analysis": analysis_result,
                "original_request_id": message.id
            }
        )
    
    async def send_candidate_availability_request(self, analysis_result: Dict[str, Any], task_data: Dict[str, Any]):
        """Send availability request email to candidate after CV analysis"""
        try:
            from app.services.gmail_client import send_email
            
            candidate_name = analysis_result.get("candidate_name", "Candidate")
            candidate_email = analysis_result.get("candidate_email", "")
            position_title = task_data.get("position_title", "Software Engineer")
            
            if not candidate_email:
                logger.warning("⚠️ No candidate email provided, cannot send availability request")
                return
            
            logger.info(f"📧 Sending availability request to {candidate_name} ({candidate_email})")
            
            subject = f"Interview Invitation - {position_title} Position"
            
            message_text = f"""Dear {candidate_name},

Thank you for your interest in the {position_title} position with our company.

We have reviewed your CV and would like to schedule an interview with you to discuss your qualifications and learn more about your experience.

Please reply to this email with 2-3 time slots when you would be available for a 30-minute screening interview in the next 5 business days. We are flexible with timing and can accommodate your schedule.

We look forward to hearing from you soon.

Best regards,
HR Team
"""
            
            # Send the email
            message_id, thread_id = send_email(
                to=candidate_email,
                subject=subject,
                message_text=message_text
            )
            
            if message_id:
                logger.info(f"✅ Availability request sent to {candidate_name} (Message ID: {message_id})")
                
                # Add thread to monitoring for replies
                if thread_id:
                    await self.agent_manager.agents[AgentType.EMAIL_MONITOR].add_thread_monitoring({
                        "thread_id": thread_id,
                        "candidate_email": candidate_email,
                        "message_id": message_id
                    })
                    logger.info(f"📧 Added thread {thread_id} to monitoring for {candidate_name}")
                else:
                    logger.warning(f"⚠️ No thread_id returned for {candidate_name}, cannot monitor for replies")
            else:
                logger.error(f"❌ Failed to send availability request to {candidate_name}")
                
        except Exception as e:
            logger.error(f"❌ Error sending availability request to {candidate_name}: {e}")
    
    async def analyze_cv_from_task(self, data: Dict[str, Any]):
        """Analyze CV from task assignment"""
        candidate_email = data.get("candidate_email")
        cv_text = data.get("cv_text")
        job_description = data.get("job_description")
        
        logger.info(f"📄 Analyzing CV for {candidate_email}")
        
        if cv_text:
            try:
                # Use AI to analyze the CV
                from app.services.openai_client import client, AZURE_OPENAI_DEPLOYMENT
                
                # First, extract candidate name from CV or email
                candidate_name = self.extract_candidate_name(cv_text, candidate_email)
                
                prompt = f"""
                Analyze this candidate's CV and create a personalized 30-minute HR screening interview guide.
                
                Candidate: {candidate_name}
                
                CV Content:
                {cv_text}
                
                Job Description:
                {job_description or "Software Engineer position"}
                
                Please provide:
                1. Key technical skills and experience analysis
                2. Years of experience (estimate)
                3. Education background
                4. Notable achievements or highlights
                5. Match score with job requirements (0-100)
                6. Personalized interview questions (10-12 questions for 30 minutes)
                
                For the interview questions, create personalized questions that:
                - Address the candidate by name when appropriate
                - Reference specific companies, projects, or experiences mentioned in their CV
                - Flow naturally in conversation
                - Cover: background, experience, technical skills, behavioral, motivation
                - Are suitable for HR screening (not deep technical)
                
                Example personalized questions:
                - "Hi {candidate_name}, can you tell me about yourself?"
                - "I see you worked at [Company from CV] - can you tell me about your role there?"
                - "You mentioned [specific project/achievement] - what was your contribution?"
                
                Format as JSON with these fields:
                - candidate_name: string
                - key_skills: array of strings
                - experience_years: number
                - education: string
                - highlights: array of strings
                - match_score: number
                - summary: string
                - interview_questions: array of objects with "question", "purpose", "follow_up_hints"
                - estimated_duration: "30 minutes"
                - interview_focus_areas: array of strings
                """
                
                response = client.chat.completions.create(
                    model=AZURE_OPENAI_DEPLOYMENT,
                    messages=[
                        {"role": "system", "content": "You are an AI assistant that analyzes CVs for recruitment. Return valid JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1
                )
                
                import json
                
                # Get the response content
                response_content = response.choices[0].message.content
                logger.info(f"📄 OpenAI response for {candidate_email}: {response_content[:200]}...")
                
                if not response_content or response_content.strip() == "":
                    raise Exception("Empty response from OpenAI")
                
                # Clean the response content - remove markdown code blocks if present
                cleaned_content = response_content.strip()
                if cleaned_content.startswith('```json'):
                    # Remove ```json at the start and ``` at the end
                    cleaned_content = cleaned_content[7:]  # Remove ```json
                    if cleaned_content.endswith('```'):
                        cleaned_content = cleaned_content[:-3]  # Remove trailing ```
                elif cleaned_content.startswith('```'):
                    # Remove generic ``` blocks
                    cleaned_content = cleaned_content[3:]
                    if cleaned_content.endswith('```'):
                        cleaned_content = cleaned_content[:-3]
                
                cleaned_content = cleaned_content.strip()
                
                # Try to parse JSON
                try:
                    analysis_result = json.loads(cleaned_content)
                    logger.info(f"✅ Successfully parsed JSON response for {candidate_email}")
                except json.JSONDecodeError as e:
                    logger.error(f"❌ JSON decode error: {e}")
                    logger.error(f"❌ Original content: {response_content[:500]}...")
                    logger.error(f"❌ Cleaned content: {cleaned_content[:500]}...")
                    # Fallback to basic analysis
                    analysis_result = self.create_fallback_analysis(candidate_name, candidate_email, cv_text)
                
                analysis_result["candidate_email"] = candidate_email
                
                logger.info(f"✅ CV analysis completed for {candidate_email} - Match score: {analysis_result.get('match_score', 'N/A')}")
                
                # Send interview questions to HR email
                await self.send_interview_questions_to_hr(analysis_result, data)
                
                # Send availability request email to candidate
                await self.send_candidate_availability_request(analysis_result, data)
                
                # Mark task as completed
                task_id = data.get("task_id")
                if task_id and task_id in self.agent_manager.tasks:
                    self.agent_manager.tasks[task_id].status = "completed"
                    self.agent_manager.tasks[task_id].result = analysis_result
                    self.agent_manager.tasks[task_id].completed_at = datetime.now()
                
            except Exception as e:
                logger.error(f"❌ Error analyzing CV for {candidate_email}: {e}")
                
                # Mark task as failed
                task_id = data.get("task_id")
                if task_id and task_id in self.agent_manager.tasks:
                    self.agent_manager.tasks[task_id].status = "failed"
                    self.agent_manager.tasks[task_id].result = {"error": str(e)}
        else:
            logger.warning(f"⚠️ No CV text provided for {candidate_email}")
            
            # Generate basic interview questions even without CV
            candidate_name = self.extract_candidate_name("", candidate_email)
            
            basic_questions = [
                {
                    "question": f"Hi {candidate_name}, can you tell me about yourself and your background?",
                    "purpose": "Opening question to get candidate comfortable and understand their background",
                    "follow_up_hints": "Listen for key experiences, skills, and career progression"
                },
                {
                    "question": "What attracted you to apply for this position?",
                    "purpose": "Understand candidate motivation and interest",
                    "follow_up_hints": "Look for genuine interest vs generic answers"
                },
                {
                    "question": "Can you walk me through your most recent work experience?",
                    "purpose": "Understand current/recent role and responsibilities",
                    "follow_up_hints": "Ask about specific projects, challenges, achievements"
                },
                {
                    "question": "What are your strongest technical skills?",
                    "purpose": "Assess technical capabilities",
                    "follow_up_hints": "Ask for specific examples of how they've used these skills"
                },
                {
                    "question": "Describe a challenging project you've worked on recently.",
                    "purpose": "Evaluate problem-solving abilities and technical depth",
                    "follow_up_hints": "Focus on their role, approach, and outcome"
                },
                {
                    "question": "How do you stay updated with new technologies and industry trends?",
                    "purpose": "Assess learning mindset and professional development",
                    "follow_up_hints": "Look for concrete examples of continuous learning"
                },
                {
                    "question": "Tell me about a time you had to work in a team to solve a problem.",
                    "purpose": "Evaluate teamwork and collaboration skills",
                    "follow_up_hints": "Focus on their communication and conflict resolution"
                },
                {
                    "question": "What are your career goals for the next 2-3 years?",
                    "purpose": "Understand career aspirations and alignment with role",
                    "follow_up_hints": "See if goals align with company growth opportunities"
                },
                {
                    "question": "Why are you looking to leave your current position?",
                    "purpose": "Understand motivation for job change",
                    "follow_up_hints": "Listen for red flags vs legitimate career advancement"
                },
                {
                    "question": "What questions do you have about our company or this role?",
                    "purpose": "Assess level of research and genuine interest",
                    "follow_up_hints": "Quality questions indicate preparation and interest"
                }
            ]
            
            # Create result with basic analysis
            basic_result = {
                "candidate_name": candidate_name,
                "candidate_email": candidate_email,
                "key_skills": [],
                "experience_years": 0,
                "education": "Not provided",
                "highlights": [],
                "match_score": 50,
                "summary": "CV not provided - general interview questions generated",
                "interview_questions": basic_questions,
                "estimated_duration": "30 minutes",
                "interview_focus_areas": ["Background", "Experience", "Technical skills", "Motivation", "Cultural fit"]
            }
            
            # Send basic interview questions to HR email
            await self.send_interview_questions_to_hr(basic_result, data)
            
            # Send availability request email to candidate (even without CV)
            await self.send_candidate_availability_request(basic_result, data)
            
            # Mark task as completed with basic analysis
            task_id = data.get("task_id")
            if task_id and task_id in self.agent_manager.tasks:
                self.agent_manager.tasks[task_id].status = "completed"
                self.agent_manager.tasks[task_id].result = basic_result

class InterviewAnalyzerAgent(BaseAgent):
    """Agent that analyzes interview conversations and evaluates candidate performance"""
    
    def __init__(self, agent_manager):
        super().__init__(AgentType.INTERVIEW_ANALYZER, agent_manager)
        
        # Import OpenAI client for this agent
        try:
            from app.services.openai_client import client, AZURE_OPENAI_DEPLOYMENT
            self.client = client
            self.deployment = AZURE_OPENAI_DEPLOYMENT
            import json
            self.json = json
        except ImportError as e:
            logger.error(f"❌ Failed to import OpenAI client: {e}")
            self.client = None
            self.deployment = None
            self.json = None
    
    async def process_message(self, message: AgentMessage):
        await super().process_message(message)
        
        if message.message_type == MessageType.REQUEST:
            action = message.content.get("action")
            
            if action == "analyze_interview":
                await self.analyze_interview(message.content)
        elif message.message_type == MessageType.TASK_ASSIGNMENT:
            task_type = message.content.get("task_type")
            
            if task_type == "analyze_interview":
                await self.analyze_interview_from_task(message.content)
    
    async def analyze_interview(self, data: Dict[str, Any]):
        """Analyze interview conversation"""
        conversation_text = data.get("conversation_text", "")
        candidate_name = data.get("candidate_name", "Unknown Candidate")
        position = data.get("position", "Software Engineer")
        
        logger.info(f"🎭 Analyzing interview conversation for {candidate_name}")
        
        try:
            # Parse conversation into Q&A format
            qa_pairs = await self.extract_questions_answers(conversation_text)
            
            # Generate summaries for each answer
            summarized_qa = await self.summarize_answers(qa_pairs)
            
            # Evaluate candidate performance
            evaluation = await self.evaluate_candidate(summarized_qa, candidate_name, position)
            
            result = {
                "candidate_name": candidate_name,
                "position": position,
                "questions_answers": summarized_qa,
                "evaluation": evaluation,
                "processed_at": datetime.now().isoformat()
            }
            
            logger.info(f"✅ Interview analysis completed for {candidate_name}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error analyzing interview for {candidate_name}: {e}")
            return {
                "error": str(e),
                "candidate_name": candidate_name,
                "position": position
            }
    
    async def analyze_interview_from_task(self, data: Dict[str, Any]):
        """Analyze interview from a task assignment"""
        try:
            result = await self.analyze_interview(data)
            
            # Mark task as completed
            task_id = data.get("task_id")
            if task_id and task_id in self.agent_manager.tasks:
                self.agent_manager.tasks[task_id].status = "completed"
                self.agent_manager.tasks[task_id].result = result
                self.agent_manager.tasks[task_id].completed_at = datetime.now()
                
        except Exception as e:
            logger.error(f"❌ Error in interview analysis task: {e}")
            
            # Mark task as failed
            task_id = data.get("task_id")
            if task_id and task_id in self.agent_manager.tasks:
                self.agent_manager.tasks[task_id].status = "failed"
                self.agent_manager.tasks[task_id].result = {"error": str(e)}
    
    async def extract_questions_answers(self, conversation_text: str) -> List[Dict[str, Any]]:
        """Extract questions and answers from conversation"""
        prompt = f"""
        Analyze this interview conversation and extract all questions asked by the interviewer and the corresponding answers from the candidate.
        
        Conversation:
        {conversation_text}
        
        Please identify and extract:
        1. Each question asked by the interviewer
        2. The corresponding answer from the candidate
        3. Categorize each question (e.g., "Background", "Technical", "Behavioral", "Experience", "Motivation")
        
        Format as JSON array with objects containing:
        - question: the exact question asked
        - answer: the candidate's full response
        - category: question category
        - question_number: sequential number starting from 1
        
        Example format:
        [
            {{
                "question_number": 1,
                "question": "Can you tell me about yourself?",
                "answer": "I am a software engineer with 5 years of experience...",
                "category": "Background"
            }}
        ]
        
        Return only valid JSON.
        """
        
        try:
            if not self.client:
                logger.error("❌ OpenAI client not available")
                return []
                
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": "You are an AI assistant that analyzes interview conversations. Return valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            response_content = response.choices[0].message.content.strip()
            
            # Clean JSON response
            if response_content.startswith('```json'):
                response_content = response_content[7:]
                if response_content.endswith('```'):
                    response_content = response_content[:-3]
            elif response_content.startswith('```'):
                response_content = response_content[3:]
                if response_content.endswith('```'):
                    response_content = response_content[:-3]
                    
            response_content = response_content.strip()
            
            if not self.json:
                logger.error("❌ JSON module not available")
                return []
                
            qa_pairs = self.json.loads(response_content)
            logger.info(f"✅ Extracted {len(qa_pairs)} Q&A pairs from conversation")
            return qa_pairs
            
        except Exception as e:
            logger.error(f"❌ Error extracting Q&A pairs: {e}")
            return []
    
    async def summarize_answers(self, qa_pairs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate summaries for each answer"""
        summarized_qa = []
        
        for qa in qa_pairs:
            try:
                prompt = f"""
                Summarize this interview answer while preserving key information and insights:
                
                Question: {qa.get('question', '')}
                Full Answer: {qa.get('answer', '')}
                
                Provide:
                1. A concise summary (2-3 sentences) that captures the main points
                2. Key highlights or notable mentions
                3. Assessment of answer quality (Poor/Fair/Good/Excellent)
                
                Format as JSON:
                {{
                    "summary": "Brief summary of the answer...",
                    "key_points": ["Point 1", "Point 2"],
                    "quality": "Good",
                    "completeness": "Complete/Partial/Incomplete"
                }}
                """
                
                if not self.client:
                    logger.error("❌ OpenAI client not available")
                    break
                    
                response = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=[
                        {"role": "system", "content": "You are an AI assistant that summarizes interview answers. Return valid JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1
                )
                
                response_content = response.choices[0].message.content.strip()
                
                # Clean JSON response
                if response_content.startswith('```json'):
                    response_content = response_content[7:]
                    if response_content.endswith('```'):
                        response_content = response_content[:-3]
                elif response_content.startswith('```'):
                    response_content = response_content[3:]
                    if response_content.endswith('```'):
                        response_content = response_content[:-3]
                        
                response_content = response_content.strip()
                
                if not self.json:
                    logger.error("❌ JSON module not available")
                    break
                    
                summary_data = self.json.loads(response_content)
                
                # Combine original Q&A with summary
                qa_with_summary = {
                    **qa,
                    "answer_summary": summary_data.get("summary", "Summary not available"),
                    "key_points": summary_data.get("key_points", []),
                    "answer_quality": summary_data.get("quality", "Fair"),
                    "completeness": summary_data.get("completeness", "Partial")
                }
                
                summarized_qa.append(qa_with_summary)
                
            except Exception as e:
                logger.error(f"❌ Error summarizing answer for question {qa.get('question_number', 'Unknown')}: {e}")
                # Add original Q&A without summary
                qa_with_summary = {
                    **qa,
                    "answer_summary": "Summary not available",
                    "key_points": [],
                    "answer_quality": "Fair",
                    "completeness": "Partial"
                }
                summarized_qa.append(qa_with_summary)
        
        logger.info(f"✅ Generated summaries for {len(summarized_qa)} answers")
        return summarized_qa
    
    async def evaluate_candidate(self, qa_pairs: List[Dict[str, Any]], candidate_name: str, position: str) -> Dict[str, Any]:
        """Evaluate candidate based on their interview performance"""
        
        # Create comprehensive evaluation prompt
        qa_text = ""
        for qa in qa_pairs:
            qa_text += f"Q{qa.get('question_number', '?')}: {qa.get('question', '')}\n"
            qa_text += f"A{qa.get('question_number', '?')}: {qa.get('answer', '')}\n"
            qa_text += f"Quality: {qa.get('answer_quality', 'Fair')}\n\n"
        
        prompt = f"""
        Evaluate this candidate's interview performance for the {position} position.
        
        Candidate: {candidate_name}
        Position: {position}
        
        Questions and Answers:
        {qa_text}
        
        Please provide a comprehensive evaluation including:
        
        1. Overall Performance Score (0-100)
        2. Strengths (3-5 key strengths)
        3. Areas for Improvement (2-4 areas)
        4. Technical Competence Assessment
        5. Communication Skills Assessment
        6. Cultural Fit Assessment
        7. Recommendation (Hire/No Hire/Further Interview)
        8. Detailed Comments for HR team
        9. Question-by-question analysis scores
        
        Format as JSON:
        {{
            "overall_score": 85,
            "recommendation": "Hire",
            "strengths": ["Strong technical background", "Clear communication"],
            "improvement_areas": ["Could provide more specific examples"],
            "technical_competence": {{
                "score": 85,
                "comments": "Demonstrates solid understanding..."
            }},
            "communication_skills": {{
                "score": 90,
                "comments": "Articulates thoughts clearly..."
            }},
            "cultural_fit": {{
                "score": 80,
                "comments": "Shows alignment with company values..."
            }},
            "detailed_comments": "This candidate shows strong potential...",
            "question_scores": [
                {{"question_number": 1, "score": 85, "feedback": "Good response covering key points"}},
                {{"question_number": 2, "score": 90, "feedback": "Excellent examples provided"}}
            ]
        }}
        
        Return only valid JSON.
        """
        
        try:
            if not self.client:
                logger.error("❌ OpenAI client not available")
                return self._get_fallback_evaluation(candidate_name, "OpenAI client not available")
                
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": "You are an expert HR interviewer evaluating candidate performance. Return valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            response_content = response.choices[0].message.content.strip()
            
            # Clean JSON response
            if response_content.startswith('```json'):
                response_content = response_content[7:]
                if response_content.endswith('```'):
                    response_content = response_content[:-3]
            elif response_content.startswith('```'):
                response_content = response_content[3:]
                if response_content.endswith('```'):
                    response_content = response_content[:-3]
                    
            response_content = response_content.strip()
            
            if not self.json:
                logger.error("❌ JSON module not available")
                return self._get_fallback_evaluation(candidate_name, "JSON module not available")
            
            evaluation = self.json.loads(response_content)
            logger.info(f"✅ Generated evaluation for {candidate_name} - Score: {evaluation.get('overall_score', 'N/A')}")
            return evaluation
            
        except Exception as e:
            logger.error(f"❌ Error evaluating candidate {candidate_name}: {e}")
            return self._get_fallback_evaluation(candidate_name, str(e))
    
    def _get_fallback_evaluation(self, candidate_name: str, error_message: str):
        """Generate a fallback evaluation when the main evaluation fails"""
        return {
            "overall_score": 70,
            "recommendation": "Further Interview",
            "strengths": ["Interview completed"],
            "improvement_areas": ["Evaluation system error"],
            "technical_competence": {"score": 70, "comments": "Unable to evaluate due to system error"},
            "communication_skills": {"score": 70, "comments": "Unable to evaluate due to system error"},
            "cultural_fit": {"score": 70, "comments": "Unable to evaluate due to system error"},
            "detailed_comments": f"System error occurred during evaluation: {error_message}",
            "question_scores": []
        }

class AgentManager:
    """Central manager for all agents"""
    
    def __init__(self):
        self.agents: Dict[AgentType, BaseAgent] = {}
        self.message_history: List[AgentMessage] = []
        self.tasks: Dict[str, AgentTask] = {}
        self.email_threads: Dict[str, Dict[str, str]] = {}  # {candidate_email: {thread_id, message_id}}
        self.is_running = False
    
    async def initialize(self):
        """Initialize all agents"""
        self.agents[AgentType.RECRUITER] = RecruiterAgent(self)
        self.agents[AgentType.SCHEDULER] = SchedulerAgent(self)
        self.agents[AgentType.INTERVIEWER] = InterviewerAgent(self)
        self.agents[AgentType.EMAIL_MONITOR] = EmailMonitorAgent(self)
        self.agents[AgentType.CV_ANALYZER] = CVAnalyzerAgent(self)
        self.agents[AgentType.INTERVIEW_ANALYZER] = InterviewAnalyzerAgent(self)
        
        logger.info("🏗️ Agent Manager initialized with 6 agents")
    
    async def start_all_agents(self):
        """Start all agents"""
        self.is_running = True
        tasks = []
        
        for agent in self.agents.values():
            tasks.append(asyncio.create_task(agent.start()))
        
        # Start email monitoring
        if AgentType.EMAIL_MONITOR in self.agents:
            email_agent = self.agents[AgentType.EMAIL_MONITOR]
            tasks.append(asyncio.create_task(email_agent.start_monitoring()))
        
        logger.info("🚀 All agents started")
        
        # Keep running until stopped
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"❌ Error in agent system: {e}")
    
    async def stop_all_agents(self):
        """Stop all agents"""
        self.is_running = False
        
        for agent in self.agents.values():
            await agent.stop()
        
        logger.info("⏹️ All agents stopped")
    
    async def route_message(self, message: AgentMessage):
        """Route message to the appropriate agent"""
        self.message_history.append(message)
        
        target_agent = self.agents.get(message.to_agent)
        if target_agent:
            await target_agent.message_queue.put(message)
            logger.info(f"📨 Routed message from {message.from_agent.value} to {message.to_agent.value}")
        else:
            logger.error(f"❌ Target agent {message.to_agent.value} not found")
    
    async def assign_task(self, agent_type: AgentType, task_type: str, data: Dict[str, Any]) -> str:
        """Assign a task to a specific agent"""
        task_id = f"task_{datetime.now().timestamp()}"
        
        task = AgentTask(
            id=task_id,
            agent_type=agent_type,
            task_type=task_type,
            data=data,
            created_at=datetime.now()
        )
        
        self.tasks[task_id] = task
        
        # Send task assignment message
        message = AgentMessage(
            id=f"msg_{datetime.now().timestamp()}",
            from_agent=AgentType.RECRUITER,  # Manager acts as recruiter for task assignment
            to_agent=agent_type,
            message_type=MessageType.TASK_ASSIGNMENT,
            content={
                "task_id": task_id,
                "task_type": task_type,
                **data
            },
            timestamp=datetime.now()
        )
        
        await self.route_message(message)
        logger.info(f"📋 Assigned task {task_id} to {agent_type.value}")
        
        return task_id
    
    async def store_email_thread(self, candidate_email: str, thread_id: str, message_id: str):
        """Store email thread information for monitoring"""
        self.email_threads[candidate_email] = {
            "thread_id": thread_id,
            "message_id": message_id,
            "timestamp": datetime.now().isoformat()
        }
        logger.info(f"📧 Stored thread {thread_id} for candidate {candidate_email}")
    
    def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all agents"""
        return {
            "is_running": self.is_running,
            "agents": {
                agent_type.value: {
                    "active": agent.is_active,
                    "queue_size": agent.message_queue.qsize()
                }
                for agent_type, agent in self.agents.items()
            },
            "total_messages": len(self.message_history),
            "active_tasks": len([t for t in self.tasks.values() if t.status in ["pending", "in_progress"]])
        }
    
    def get_message_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent message history"""
        recent_messages = self.message_history[-limit:]
        return [
            {
                "id": msg.id,
                "from": msg.from_agent.value,
                "to": msg.to_agent.value,
                "type": msg.message_type.value,
                "timestamp": msg.timestamp.isoformat(),
                "content": msg.content
            }
            for msg in recent_messages
        ]

# Global agent manager instance
agent_manager = AgentManager()