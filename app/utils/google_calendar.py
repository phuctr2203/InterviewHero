import os
import pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
CRED_PATH = os.path.join(DATA_DIR, "credentials.json")
TOKEN_CAL_PATH = os.path.join(DATA_DIR, "token.calendar.pickle")

SCOPES = ['https://www.googleapis.com/auth/calendar']

def _auth_calendar():
    creds = None
    if os.path.exists(TOKEN_CAL_PATH):
        with open(TOKEN_CAL_PATH, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CRED_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_CAL_PATH, 'wb') as token:
            pickle.dump(creds, token)
    return creds

def create_calendar_event(event_dict: dict):
    creds = _auth_calendar()
    service = build('calendar', 'v3', credentials=creds)
    body = {
        'summary': event_dict.get('summary'),
        'description': event_dict.get('description'),
        'start': event_dict.get('start'),
        'end': event_dict.get('end'),
        'attendees': event_dict.get('attendees', []),
        # Note: Generating Meet links via API may require Workspace;
        # here we rely on Google to attach one if policy allows.
        'conferenceData': {
            'createRequest': {'requestId': event_dict['summary'].replace(' ', '-')}
        }
    }
    created = service.events().insert(calendarId='primary', body=body,
                                      conferenceDataVersion=1).execute()
    return {
        "id": created.get('id'),
        "htmlLink": created.get('htmlLink'),
        "hangoutLink": created.get('hangoutLink'),
        "start": created.get('start'),
        "end": created.get('end'),
        "attendees": created.get('attendees'),
        "simulated": False,
    }
