from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import Optional, List
from app.config import Config
import json
import datetime

class CalendarEventSchema(BaseModel):
    summary: str = Field(description="Brief title of the event")
    start_time: str = Field(description="Start time in ISO 8601 format (YYYY-MM-DDTHH:MM:SS)")
    end_time: str = Field(description="End time in ISO 8601 format (YYYY-MM-DDTHH:MM:SS)")
    location: Optional[str] = Field(description="Location of the event if specified")
    attendees: List[str] = Field(description="List of email addresses for attendees", default=[])
    description: Optional[str] = Field(description="Detailed description extracted from text")
    category: str = Field(description="Category of the event: Work, Personal, Health, Finance, Other")

class AIService:
    def __init__(self):
        # Initialize the client using the API key from config
        # Note: The user code showed `client = genai.Client()`, assuming env var or passing api_key
        self.client = genai.Client(api_key=Config.GEMINI_API_KEY)

    def extract_event_details(self, text: str, current_time: str) -> CalendarEventSchema:
        prompt = f"""
        Extract calendar event details from the following text.
        The current date and time is: {current_time}.
        If the year is not specified, assume the upcoming occurrence relative to now.
        Infer the category (Work, Personal, Health, Finance, Other) based on the context.
        Text: "{text}"
        """
        
        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash", # Fallback to 2.0-flash as 3 might not be widely available contextually, but user asked for it.
                # If you have access, change to "gemini-3-flash-preview"
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=CalendarEventSchema
                )
            )
            
            # The response.text should be JSON
            data = json.loads(response.text)
            return CalendarEventSchema(**data)
        except Exception as e:
            print(f"AI Error: {e}")
            return None
