from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import datetime
import json
from app.config import Config
from app.db.mongo import db

class GoogleCalendarService:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.creds = self._load_credentials()
        self.service = None
        if self.creds:
            try:
                self.service = build('calendar', 'v3', credentials=self.creds)
            except Exception as e:
                print(f"Error building service: {e}")
                self.creds = None # Force re-auth if invalid

    def _load_credentials(self):
        creds_json = db.get_user_credentials(self.chat_id)
        if creds_json:
            creds = Credentials.from_authorized_user_info(json.loads(creds_json), Config.SCOPES)
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    # Save refreshed creds
                    db.save_user_credentials(self.chat_id, creds.to_json())
                except Exception:
                    return None
            return creds
        return None

    def get_auth_url(self):
        # Using InstalledAppFlow for simplicity, but for a real bot we'd need a web server for redirect_uri
        # Or we use the OOB flow if allowed (deprecated).
        # Since we can't spin up a server on the user's machine, we have to trick it or use a specific flow.
        # For this implementation, we will use a flow that prints a URL.
        # However, InstalledAppFlow.from_client_secrets_file usually tries to launch browser or local server.
        # We can use `run_console` if OOB is enabled, but it's deprecated.
        
        # Strategy: Logic to be handled in the bot. 
        # Here we just initialize the flow.
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                Config.CREDENTIALS_FILE, Config.SCOPES)
            
            # This is tricky for a bot. 
            # If we run flow.run_local_server(), it blocks and expects a browser on the server.
            # If we run flow.run_console(), it prints to stdout.
            
            # We will use the copy-paste URL method which is often the fallback.
            flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
            auth_url, _ = flow.authorization_url(prompt='consent')
            return auth_url, flow
        except Exception as e:
            print(f"Error creating flow: {e}")
            return None, None

    def finish_auth(self, flow, code):
        try:
            flow.fetch_token(code=code)
            self.creds = flow.credentials
            db.save_user_credentials(self.chat_id, self.creds.to_json())
            self.service = build('calendar', 'v3', credentials=self.creds)
            return True, "Authenticated successfully!"
        except Exception as e:
            return False, str(e)

    def list_upcoming_events(self, max_results=10):
        if not self.service:
            return None
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        events_result = self.service.events().list(
            calendarId='primary', timeMin=now,
            maxResults=max_results, singleEvents=True,
            orderBy='startTime').execute()
        return events_result.get('items', [])

    def create_event(self, event_data):
        if not self.service:
            return None
        event = self.service.events().insert(calendarId='primary', body=event_data).execute()
        return event

    def delete_event(self, event_id):
        if not self.service:
            return False
        try:
            self.service.events().delete(calendarId='primary', eventId=event_id).execute()
            return True
        except Exception:
            return False

    def get_colors(self):
         if not self.service:
            return None
         colors = self.service.colors().get().execute()
         return colors.get('event', {})

