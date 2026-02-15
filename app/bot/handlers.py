import datetime
from telebot import types
from app.bot.bot_instance import bot
from app.db.mongo import db
from app.services.google_service import GoogleCalendarService
from app.services.ai_service import AIService, CalendarEventSchema

# In-memory storage for temporary states
temp_events = {}
user_auth_flows = {}
ai_service = AIService()

# --- Keyboards ---
def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Create Task"), types.KeyboardButton("My Tasks"))
    markup.add(types.KeyboardButton("Settings"), types.KeyboardButton("Auth"))
    return markup

def get_confirmation_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Confirm", callback_data="confirm_event"),
               types.InlineKeyboardButton("Edit", callback_data="edit_event"),
               types.InlineKeyboardButton("Cancel", callback_data="cancel_event"))
    return markup

def get_tasks_keyboard(events):
    markup = types.InlineKeyboardMarkup()
    for event in events:
        summary = event.get('summary', 'No Title')
        start = event.get('start', {}).get('dateTime', '') or event.get('start', {}).get('date', '')
        # Format start time slightly
        try:
            dt = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
            start_str = dt.strftime("%b %d %H:%M")
        except:
            start_str = start
            
        markup.add(types.InlineKeyboardButton(f"{summary} ({start_str})", callback_data=f"view_{event['id']}"))
    markup.add(types.InlineKeyboardButton("Refresh", callback_data="refresh_tasks"))
    return markup

def get_event_action_keyboard(event_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Delete", callback_data=f"delete_{event_id}"),
               types.InlineKeyboardButton("Back", callback_data="refresh_tasks"))
    return markup

# --- Handlers ---

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    chat_id = message.chat.id
    db.create_user(chat_id, {"username": message.from_user.username})
    bot.reply_to(message, "Welcome to Planify! \nUse /auth to connect Google Calendar.\nSend me any text to schedule an event.", reply_markup=get_main_menu())

@bot.message_handler(commands=['auth'])
@bot.message_handler(func=lambda m: m.text == "Auth")
def authenticate(message):
    chat_id = message.chat.id
    service = GoogleCalendarService(chat_id)
    auth_url, flow = service.get_auth_url()
    
    if auth_url:
        user_auth_flows[chat_id] = flow
        msg = bot.send_message(chat_id, f"Please authenticate here:\n{auth_url}\n\nThen refer to the redirect page (localhost) or just paste the code here if provided.")
        bot.register_next_step_handler(msg, process_auth_code)
    else:
        bot.send_message(chat_id, "Could not generate auth URL.")

def process_auth_code(message):
    chat_id = message.chat.id
    code = message.text.strip()
    flow = user_auth_flows.get(chat_id)
    
    if flow:
        service = GoogleCalendarService(chat_id)
        success, msg = service.finish_auth(flow, code)
        bot.send_message(chat_id, msg)
        del user_auth_flows[chat_id]
        # Clean up code message
        try:
            bot.delete_message(chat_id, message.message_id)
        except:
            pass
    else:
        bot.send_message(chat_id, "Auth session expired. Please run /auth again.")

@bot.message_handler(func=lambda m: m.text == "Create Task")
def manual_create_start(message):
    bot.send_message(message.chat.id, "Please describe the task/event in natural language (e.g., 'Meeting with John tomorrow at 3pm').")

@bot.message_handler(func=lambda m: m.text == "My Tasks")
def list_tasks(message):
    list_upcoming_events(message.chat.id)

def list_upcoming_events(chat_id):
    service = GoogleCalendarService(chat_id)
    events = service.list_upcoming_events()
    
    if events is None:
        bot.send_message(chat_id, "Please authenticate first using /auth.")
        return

    if not events:
        bot.send_message(chat_id, "No upcoming events found.")
        return

    bot.send_message(chat_id, "Here are your upcoming events:", reply_markup=get_tasks_keyboard(events))

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    
    if call.data == "confirm_event":
        event = temp_events.get(chat_id)
        if event:
            service = GoogleCalendarService(chat_id)
            # Use settings for colors if available
            settings = db.get_user_settings(chat_id)
            color_id = settings.get('colors', {}).get(event.category)
            
            try:
                service.create_event(
                    summary=event.summary,
                    start_time=event.start_time,
                    end_time=event.end_time,
                    description=event.description,
                    location=event.location,
                    attendees=event.attendees,
                    color_id=color_id
                )
                bot.answer_callback_query(call.id, "Event created!")
                bot.edit_message_text("Event added to your calendar successfully! ✅", chat_id, call.message.message_id)
                del temp_events[chat_id]
            except Exception as e:
                bot.send_message(chat_id, f"Error creating event: {e}")
        else:
            bot.answer_callback_query(call.id, "Session expired.")
            
    elif call.data == "cancel_event":
        if chat_id in temp_events:
            del temp_events[chat_id]
        bot.answer_callback_query(call.id, "Cancelled.")
        bot.delete_message(chat_id, call.message.message_id)

    elif call.data == "edit_event":
        msg = bot.send_message(chat_id, "Please enter the correction (e.g., 'Change time to 5pm'):")
        bot.register_next_step_handler(msg, process_edit_request)

    elif call.data == "refresh_tasks":
        bot.delete_message(chat_id, call.message.message_id)
        list_tasks(call.message) # Hacky call passing message object

    elif call.data.startswith("view_"):
        event_id = call.data.split("_")[1]
        # Fetch details? We have them in list mostly, but let's show actions
        bot.edit_message_text(f"Event ID: {event_id}\nSelect action:", chat_id, call.message.message_id, reply_markup=get_event_action_keyboard(event_id))

    elif call.data.startswith("delete_"):
        event_id = call.data.split("_")[1]
        service = GoogleCalendarService(chat_id)
        if service.delete_event(event_id):
            bot.answer_callback_query(call.id, "Event deleted.")
            bot.delete_message(chat_id, call.message.message_id)
            list_tasks(call.message)
        else:
            bot.answer_callback_query(call.id, "Failed to delete.")

def process_edit_request(message):
    chat_id = message.chat.id
    correction = message.text
    original_event = temp_events.get(chat_id)
    
    if original_event:
        # Re-parse context
        # Ideally we'd keep original text, but let's just make a composite text
        composite_text = f"Summary: {original_event.summary}, Time: {original_event.start_time}. Correction: {correction}"
        
        # Or simpler: Just re-run AI with correction as prompt?
        # Let's clean up user message
        try:
             bot.delete_message(chat_id, message.message_id)
        except:
             pass

        process_natural_language(message, text_override=composite_text)
    else:
        bot.send_message(chat_id, "No event to edit.")

@bot.message_handler(func=lambda m: True)
def process_natural_language(message, text_override=None):
    if message.text.startswith('/'): return
    
    chat_id = message.chat.id
    text = text_override or message.text
    
    msg = bot.send_message(chat_id, "Thinking... 🧠")
    
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    event_schema = ai_service.extract_event_details(text, current_time)
    
    bot.delete_message(chat_id, msg.message_id)
    if not text_override:
        # Delete user message to keep chat clean as requested
        try:
           bot.delete_message(chat_id, message.message_id)
        except:
           pass

    if event_schema:
        temp_events[chat_id] = event_schema
        
        # Get color based on category
        settings = db.get_user_settings(chat_id)
        category_color = "Default"
        if event_schema.category in settings.get('colors', {}):
             category_color = settings['colors'][event_schema.category] # Maps to color ID

        response_text = (
            f"📅 **New Event Proposal**\n\n"
            f"📌 **Summary:** {event_schema.summary}\n"
            f"🕒 **Start:** {event_schema.start_time}\n"
            f"🕓 **End:** {event_schema.end_time}\n"
            f"📍 **Location:** {event_schema.location or 'N/A'}\n"
            f"📝 **Description:** {event_schema.description or 'N/A'}\n"
            f"🎨 **Category:** {event_schema.category} (Color: {category_color})\n\n"
            f"Does this look correct?"
        )
        
        bot.send_message(chat_id, response_text, parse_mode="Markdown", reply_markup=get_confirmation_keyboard())
    else:
        bot.send_message(chat_id, "Sorry, I couldn't understand that. Try being more specific.")
