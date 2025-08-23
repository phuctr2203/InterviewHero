from __future__ import print_function
import os
import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# Gmail API scope: read/write emails
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

def get_gmail_service():
    """Authenticate and return Gmail API service."""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "app/credentials.json", SCOPES
            )
            # Use run_local_server instead of run_console for better UX
            creds = flow.run_local_server(port=8080)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)

def send_email(to, subject, message_text, sender=None, attachments=None, html=False):
    """
    Send email using Gmail API.
    
    Args:
        to (str): Recipient email address
        subject (str): Email subject
        message_text (str): Email body
        sender (str, optional): Sender email (defaults to authenticated user)
        attachments (list, optional): List of file paths to attach
        html (bool): Whether message_text is HTML
    """
    try:
        service = get_gmail_service()
        
        # Create multipart message for attachments support
        if attachments:
            message = MIMEMultipart()
            message.attach(MIMEText(message_text, 'html' if html else 'plain'))
            
            # Add attachments
            for file_path in attachments:
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as attachment:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment.read())
                    
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {os.path.basename(file_path)}'
                    )
                    message.attach(part)
                else:
                    print(f"⚠️ Warning: Attachment file not found: {file_path}")
        else:
            # Simple text message
            message = MIMEText(message_text, 'html' if html else 'plain')
        
        message["to"] = to
        if sender:
            message["from"] = sender
        message["subject"] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        message_body = {"raw": raw}

        sent_message = service.users().messages().send(
            userId="me", body=message_body
        ).execute()
        print(f"✅ Email sent! Message ID: {sent_message['id']}")
        return sent_message['id'], sent_message.get('threadId')
        
    except HttpError as error:
        print(f"❌ An error occurred while sending email: {error}")
        return None

def get_emails(query="", max_results=10, label_ids=None):
    """
    Retrieve emails from Gmail.
    
    Args:
        query (str): Gmail search query (e.g., 'is:unread', 'from:example@gmail.com')
        max_results (int): Maximum number of emails to retrieve
        label_ids (list): List of label IDs to filter by
    
    Returns:
        list: List of email messages
    """
    try:
        service = get_gmail_service()
        
        # Get message IDs
        results = service.users().messages().list(
            userId="me", 
            q=query, 
            maxResults=max_results,
            labelIds=label_ids
        ).execute()
        
        messages = results.get("messages", [])
        
        if not messages:
            print("📭 No messages found.")
            return []
        
        print(f"📧 Found {len(messages)} message(s)")
        return messages
        
    except HttpError as error:
        print(f"❌ An error occurred while retrieving emails: {error}")
        return []

def read_email(message_id):
    """
    Read a specific email by message ID.
    
    Args:
        message_id (str): Gmail message ID
        
    Returns:
        dict: Email details including sender, subject, body, etc.
    """
    try:
        service = get_gmail_service()
        message = service.users().messages().get(
            userId="me", id=message_id
        ).execute()
        
        # Extract email details
        email_data = {
            'id': message['id'],
            'thread_id': message['threadId'],
            'labels': message.get('labelIds', []),
            'snippet': message.get('snippet', ''),
        }
        
        # Extract headers (sender, subject, date)
        headers = message['payload'].get('headers', [])
        for header in headers:
            if header['name'].lower() == 'from':
                email_data['from'] = header['value']
            elif header['name'].lower() == 'subject':
                email_data['subject'] = header['value']
            elif header['name'].lower() == 'date':
                email_data['date'] = header['value']
            elif header['name'].lower() == 'to':
                email_data['to'] = header['value']
        
        # Extract body
        email_data['body'] = extract_email_body(message['payload'])
        
        return email_data
        
    except HttpError as error:
        print(f"❌ An error occurred while reading email: {error}")
        return None

def extract_email_body(payload):
    """Extract email body from payload."""
    body = ""
    
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                if 'data' in part['body']:
                    data = part['body']['data']
                    body = base64.urlsafe_b64decode(data).decode('utf-8')
                    break
            elif part['mimeType'] == 'text/html':
                if 'data' in part['body']:
                    data = part['body']['data']
                    body = base64.urlsafe_b64decode(data).decode('utf-8')
    else:
        if payload['mimeType'] in ['text/plain', 'text/html']:
            if 'data' in payload['body']:
                data = payload['body']['data']
                body = base64.urlsafe_b64decode(data).decode('utf-8')
    
    return body

def mark_as_read(message_id):
    """Mark a message as read."""
    try:
        service = get_gmail_service()
        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
        print(f"✅ Message {message_id} marked as read")
    except HttpError as error:
        print(f"❌ Error marking message as read: {error}")

def mark_as_unread(message_id):
    """Mark a message as unread."""
    try:
        service = get_gmail_service()
        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={'addLabelIds': ['UNREAD']}
        ).execute()
        print(f"✅ Message {message_id} marked as unread")
    except HttpError as error:
        print(f"❌ Error marking message as unread: {error}")

def delete_email(message_id):
    """Delete an email."""
    try:
        service = get_gmail_service()
        service.users().messages().delete(
            userId="me", id=message_id
        ).execute()
        print(f"✅ Message {message_id} deleted")
    except HttpError as error:
        print(f"❌ Error deleting message: {error}")

def get_labels():
    """Get all available Gmail labels."""
    try:
        service = get_gmail_service()
        results = service.users().labels().list(userId="me").execute()
        labels = results.get('labels', [])
        
        print("📋 Available labels:")
        for label in labels:
            print(f"  - {label['name']} (ID: {label['id']})")
        
        return labels
    except HttpError as error:
        print(f"❌ Error getting labels: {error}")
        return []

def get_latest_reply_in_thread(thread_id, from_email=None):
    """
    Get the latest reply in a thread, optionally filtered by sender.
    
    Args:
        thread_id (str): Gmail thread ID
        from_email (str, optional): Filter replies from this email address
        
    Returns:
        str: Body text of the latest reply, or None if no reply found
    """
    try:
        service = get_gmail_service()
        
        # Get all messages in the thread
        thread = service.users().threads().get(
            userId="me", 
            id=thread_id
        ).execute()
        
        messages = thread.get('messages', [])
        if len(messages) <= 1:
            return None  # No replies (only original message)
        
        # Sort messages by internal date (newest first)
        messages.sort(key=lambda x: int(x.get('internalDate', 0)), reverse=True)
        
        # Look through all messages to find the latest reply
        for message in messages:  # Check all messages, newest first
            email_data = read_email(message['id'])
            if email_data:
                sender = email_data.get('from', '')
                
                # If from_email is specified, filter by sender
                if from_email:
                    if from_email.lower() not in sender.lower():
                        continue
                    # Found a message from the specified sender - this is a reply
                    return email_data.get('body', '')
                else:
                    # If no from_email specified, skip the first message (original) and return the first reply
                    if message != messages[0]:  # Not the original message
                        return email_data.get('body', '')
        
        return None
        
    except HttpError as error:
        print(f"❌ Error getting thread replies: {error}")
        return None
