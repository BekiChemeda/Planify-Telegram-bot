from pymongo import MongoClient
from app.config import Config

class Database:
    def __init__(self):
        self.client = MongoClient(Config.MONGO_URI)
        self.db = self.client[Config.DB_NAME]
        self.users = self.db.users

    def get_user(self, chat_id):
        return self.users.find_one({"chat_id": chat_id})

    def create_user(self, chat_id, user_data):
        if not self.get_user(chat_id):
            user_data["chat_id"] = chat_id
            self.users.insert_one(user_data)
            return True
        return False

    def update_user(self, chat_id, update_data):
        self.users.update_one({"chat_id": chat_id}, {"$set": update_data})

    def get_user_credentials(self, chat_id):
        user = self.get_user(chat_id)
        if user and "credentials" in user:
            return user["credentials"]
        return None

    def save_user_credentials(self, chat_id, creds_json):
        self.update_user(chat_id, {"credentials": creds_json})

    def get_user_settings(self, chat_id):
        user = self.get_user(chat_id)
        if user and "settings" in user:
            return user["settings"]
        return {"colors": {}, "notifications": True}

    def update_user_settings(self, chat_id, settings):
        self.update_user(chat_id, {"settings": settings})

db = Database()
