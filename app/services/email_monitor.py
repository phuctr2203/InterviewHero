import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from app.services.gmail_client import get_emails, read_email, mark_as_read, send_email
from app.services.openai_client import client, parse_availability_prompt, is_candidate_response_prompt, AZURE_OPENAI_DEPLOYMENT

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EmailMonitorService:
    def __init__(self):
        self.is_running = False
        self.processed_messages = set()  # Track processed message IDs to avoid duplicates
        self.check_interval = 30  # Check every 30 seconds
        self.last_check_time = None
        self.total_checks = 0
        self.successful_schedules = 0
        self.failed_schedules = 0
        
    async def start(self):
        """Start the email monitoring service"""
        self.is_running = True
        logger.info("🚀 Email Monitor Service started - watching for candidate responses...")
        
        while self.is_running:
            try:
                await self.check_and_process_emails()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"❌ Error in email monitor: {e}")
                await asyncio.sleep(self.check_interval)
    
    def stop(self):
        """Stop the email monitoring service"""
        self.is_running = False
        logger.info("⏹️ Email Monitor Service stopped")
    
    async def check_and_process_emails(self):
        """Check for new emails and process candidate responses"""
        self.total_checks += 1
        self.last_check_time = datetime.now()
        
        try:
            logger.info(f"🔍 Checking emails (check #{self.total_checks})...")
            
            # Search for unread emails that might be responses
            messages = get_emails(query="is:unread", max_results=20)
            
            logger.info(f"📧 Found {len(messages)} unread emails")
            
            new_responses = 0
            for message in messages:
                message_id = message['id']
                
                # Skip if already processed
                if message_id in self.processed_messages:
                    logger.debug(f"⏭️ Skipping already processed message: {message_id}")
                    continue
                
                # Read email content
                email_data = read_email(message_id)
                if not email_data:
                    logger.debug(f"⚠️ Could not read email data for message: {message_id}")
                    continue
                
                # Debug: Log email details
                logger.info(f"🔍 Checking email from: {email_data.get('from', 'Unknown')}")
                logger.info(f"📧 Subject: {email_data.get('subject', 'No subject')}")
                logger.debug(f"📝 Body preview: {email_data.get('body', '')[:200]}...")
                
                # Check if this looks like a candidate availability response
                is_candidate = await self.is_candidate_response(email_data)
                logger.info(f"🤔 Is candidate response: {is_candidate}")
                
                if is_candidate:
                    logger.info(f"📧 Found candidate response from: {email_data.get('from')}")
                    
                    # Process the response
                    success = await self.process_candidate_response(email_data)
                    
                    if success:
                        # Mark as processed and read
                        self.processed_messages.add(message_id)
                        mark_as_read(message_id)
                        new_responses += 1
                        self.successful_schedules += 1
                        logger.info(f"✅ Successfully processed response from {email_data.get('from')}")
                    else:
                        self.failed_schedules += 1
                        logger.warning(f"⚠️ Failed to process response from {email_data.get('from')}")
            
            if new_responses > 0:
                logger.info(f"📊 Processed {new_responses} new candidate responses")
                
        except Exception as e:
            logger.error(f"❌ Error checking emails: {e}")
    
    async def is_candidate_response(self, email_data: Dict[str, Any]) -> bool:
        """Use AI to check if an email looks like a candidate availability response"""
        subject = email_data.get('subject', '')
        body = email_data.get('body', '')
        
        logger.info(f"🤖 Using AI to analyze email for candidate response patterns:")
        logger.debug(f"   Subject: '{subject}'")
        logger.debug(f"   Body preview: '{body[:150]}...'")
        
        try:
            # Use GPT-4o to intelligently detect candidate responses
            prompt = is_candidate_response_prompt(subject, body)
            resp = client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            
            # Parse AI response
            import json
            ai_response = resp.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if ai_response.startswith('```json'):
                ai_response = ai_response.replace('```json', '').replace('```', '').strip()
            elif ai_response.startswith('```'):
                ai_response = ai_response.replace('```', '').strip()
            
            ai_analysis = json.loads(ai_response)
            
            is_candidate = ai_analysis.get('is_candidate_response', False)
            confidence = ai_analysis.get('confidence', 0.0)
            reason = ai_analysis.get('reason', 'No reason provided')
            contains_availability = ai_analysis.get('contains_availability', False)
            
            logger.info(f"🤖 AI Analysis:")
            logger.info(f"   Is candidate response: {is_candidate}")
            logger.info(f"   Confidence: {confidence:.2f}")
            logger.info(f"   Contains availability: {contains_availability}")
            logger.info(f"   Reason: {reason}")
            
            # Use AI decision with high confidence threshold
            result = is_candidate and confidence >= 0.7
            
            logger.info(f"🎯 Final decision: {'✅ IS candidate response' if result else '❌ NOT candidate response'}")
            logger.info(f"   (Confidence threshold: 0.7, Got: {confidence:.2f})")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error in AI analysis: {e}")
            # Fallback to simple keyword detection
            logger.info("🔄 Falling back to keyword detection...")
            
            body_lower = body.lower()
            subject_lower = subject.lower()
            
            # Simple fallback logic
            has_reply_indicator = any(keyword in subject_lower for keyword in ['re:', 'interview', 'screening'])
            has_availability = any(keyword in body_lower for keyword in ['available', 'schedule', 'time', 'date', 'thanks for your email'])
            
            result = has_reply_indicator or (has_availability and len(body) > 20)
            logger.info(f"🔄 Fallback result: {'✅ IS candidate response' if result else '❌ NOT candidate response'}")
            
            return result
    
    async def process_candidate_response(self, email_data: Dict[str, Any]) -> bool:
        """Process a candidate's availability response and schedule meeting"""
        try:
            # Extract candidate info from email
            candidate_email = self.extract_email_address(email_data.get('from', ''))
            candidate_name = self.extract_candidate_name(email_data.get('from', ''))
            
            # Parse availability using AI
            availability_data = await self.parse_availability(email_data['body'])
            if not availability_data:
                logger.warning(f"Could not parse availability from {candidate_email}")
                return False
            
            # Get the best available time slot
            time_slot = self.get_best_time_slot(availability_data)
            if not time_slot:
                logger.warning(f"No suitable time slot found for {candidate_email}")
                return False
            
            # Send meeting confirmation with Google Meet link
            confirmation_result = await self.send_meeting_confirmation(
                candidate_email=candidate_email,
                candidate_name=candidate_name,
                date=time_slot['date'],
                time=time_slot['time'],
                timezone=time_slot.get('timezone', 'UTC')
            )
            
            if confirmation_result:
                logger.info(f"🎉 Meeting confirmed for {candidate_name} on {time_slot['date']} at {time_slot['time']}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error processing candidate response: {e}")
            return False
    
    async def parse_availability(self, email_body: str) -> Optional[Dict[str, Any]]:
        """Parse availability from email using AI"""
        try:
            prompt = parse_availability_prompt(email_body)
            resp = client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            
            availability_data = json.loads(resp.choices[0].message.content)
            return availability_data
            
        except Exception as e:
            logger.error(f"❌ Error parsing availability: {e}")
            return None
    
    def get_best_time_slot(self, availability_data: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Select the best time slot from parsed availability"""
        try:
            # Handle multiple options
            if 'options' in availability_data and availability_data['options']:
                # Take the first available option
                return availability_data['options'][0]
            else:
                # Single option format
                if 'date' in availability_data and 'time' in availability_data:
                    return availability_data
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error selecting time slot: {e}")
            return None
    
    async def send_meeting_confirmation(self, candidate_email: str, candidate_name: str, 
                                      date: str, time: str, timezone: str = "UTC") -> bool:
        """Send meeting confirmation with Google Meet link"""
        try:
            # Generate Google Meet link
            meet_link = self.generate_google_meet_link()
            
            # Parse datetime for better formatting
            try:
                meeting_datetime = datetime.fromisoformat(f"{date}T{time}:00")
                formatted_date = meeting_datetime.strftime("%A, %B %d, %Y")
                formatted_time = meeting_datetime.strftime("%I:%M %p")
            except:
                # Fallback to original format if parsing fails
                formatted_date = date
                formatted_time = time
            
            # Send confirmation email
            meeting_subject = f"Interview Confirmed - {formatted_date} at {formatted_time}"
            meeting_body = f"""
Dear {candidate_name},

Perfect! Your screening interview has been confirmed for:

📅 Date: {formatted_date}
🕒 Time: {formatted_time} ({timezone})
📹 Meeting Link: {meet_link}
⏰ Duration: 30 minutes

MEETING DETAILS:
• Please join the Google Meet at the scheduled time
• Have your resume/CV ready for reference
• Ensure you have a stable internet connection
• The interview will take approximately 30 minutes

If you need to reschedule, please reply to this email as soon as possible.

Looking forward to speaking with you!

Best regards,
HR Team

---
Meeting Link: {meet_link}
            """.strip()
            
            send_email(candidate_email, meeting_subject, meeting_body)
            
            logger.info(f"📅 Meeting confirmation sent to {candidate_email}")
            logger.info(f"🔗 Google Meet link: {meet_link}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error sending meeting confirmation: {e}")
            return False
    
    def extract_email_address(self, from_field: str) -> str:
        """Extract clean email address from 'from' field"""
        if '<' in from_field and '>' in from_field:
            return from_field.split('<')[-1].strip('>')
        return from_field.strip()
    
    def extract_candidate_name(self, from_field: str) -> str:
        """Extract candidate name from 'from' field"""
        if '<' in from_field:
            return from_field.split('<')[0].strip().strip('"')
        # Fallback: use email username
        email = self.extract_email_address(from_field)
        return email.split('@')[0].replace('.', ' ').title()
    
    def generate_google_meet_link(self) -> str:
        """Generate a Google Meet link (simplified approach)"""
        import random
        import string
        
        # Generate a random meeting ID (Google Meet format: xxx-yyyy-zzz)
        def random_segment(length):
            return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
        
        meeting_id = f"{random_segment(3)}-{random_segment(4)}-{random_segment(3)}"
        return f"https://meet.google.com/{meeting_id}"

# Global instance
email_monitor = EmailMonitorService()

async def start_email_monitor():
    """Start the email monitoring service"""
    await email_monitor.start()

def stop_email_monitor():
    """Stop the email monitoring service"""
    email_monitor.stop()