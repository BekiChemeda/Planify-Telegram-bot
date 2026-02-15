import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    DB_NAME = "planify_bot"
    
    # Paths
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CREDENTIALS_FILE = os.path.join(BASE_DIR, "app", "spike", "credentials.json")
    TOKEN_FILE = os.path.join(BASE_DIR, "app", "spike", "token.json")
    
    # Calendar Settings
    SCOPES = ['https://www.googleapis.com/auth/calendar']
