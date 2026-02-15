import telebot
from app.config import Config
from app.bot import bot_instance
# Import handlers to register them
from app.bot import handlers 

if __name__ == "__main__":
    print("🤖 Planify Bot Started...")
    try:
        bot_instance.bot.infinity_polling()
    except Exception as e:
        print(f"Bot error: {e}")
