import logging
import os
from pymongo import MongoClient
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client['telegram_bot']
users_collection = db['users']
conversations_collection = db['conversations']

# States for conversation handler
PROFILE_PICTURE, SEX, BIRTHDAY, LOCATION = range(4)

def start(update: Update, context: CallbackContext) -> None:
    main_menu(update)

def main_menu(update: Update) -> None:
    buttons = [
        [KeyboardButton("Register")],
        [KeyboardButton("Search for Match")],
        [KeyboardButton("Disconnect")]
    ]
    reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
    update.message.reply_text('Choose an option:', reply_markup=reply_markup)

def register(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Hi! Send me your profile picture.', reply_markup=ReplyKeyboardRemove())
    return PROFILE_PICTURE

def profile_picture(update: Update, context: CallbackContext) -> int:
    user = update.message.from_user
    photo_file = update.message.photo[-1].get_file()
    photo_file.download(f'{user.id}_profile.jpg')

    user_data = {
        'user_id': user.id,
        'username': user.username,
        'profile_picture': f'{user.id}_profile.jpg'
    }
    context.user_data['user_data'] = user_data

    # Ask for sex with buttons
    buttons = [[KeyboardButton("Male"), KeyboardButton("Female")]]
    reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
    update.message.reply_text('Got it! Now tell me your sex:', reply_markup=reply_markup)
    return SEX

def sex(update: Update, context: CallbackContext) -> int:
    sex = update.message.text.lower()
    if sex not in ['male', 'female']:
        update.message.reply_text('Please select "Male" or "Female" using the buttons.')
        return SEX

    context.user_data['user_data']['sex'] = sex
    update.message.reply_text('Great! Now send me your birthday (YYYY-MM-DD).', reply_markup=ReplyKeyboardRemove())
    return BIRTHDAY

def birthday(update: Update, context: CallbackContext) -> int:
    context.user_data['user_data']['birthday'] = update.message.text

    # Ask for location
    location_button = KeyboardButton(text="Share location", request_location=True)
    location_keyboard = ReplyKeyboardMarkup([[location_button]], one_time_keyboard=True)
    update.message.reply_text('Please share your location.', reply_markup=location_keyboard)

    return LOCATION

def location(update: Update, context: CallbackContext) -> int:
    user_location = update.message.location
    context.user_data['user_data']['location'] = {
        'latitude': user_location.latitude,
        'longitude': user_location.longitude
    }

    # Save user data to MongoDB
    users_collection.insert_one(context.user_data['user_data'])
    update.message.reply_text('Thank you! Your information has been saved.', reply_markup=ReplyKeyboardRemove())
    main_menu(update)
    return ConversationHandler.END

def search(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user = users_collection.find_one({'user_id': user_id})

    if not user:
        update.message.reply_text('You need to register first. Use the main menu to start.')
        return

    buttons = [[KeyboardButton("Male"), KeyboardButton("Female")]]
    reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
    update.message.reply_text('Enter the sex of the person you are looking for:', reply_markup=reply_markup)

def search_match(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    sex = update.message.text.lower()  
    if sex not in ['male', 'female']:
        buttons = [[KeyboardButton("Male"), KeyboardButton("Female")]]
        reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
        update.message.reply_text('Search  for "Male" or "Female"', reply_markup=reply_markup)
        return

    matched_user = users_collection.find_one({'sex': sex})

    if matched_user:
        conversation_data = {
            'user1': user_id,
            'user2': matched_user['user_id'],
            'active': True
        }
        conversations_collection.insert_one(conversation_data)

        update.message.reply_text(f'Matched with {matched_user["username"]}. You can start chatting now.')
        context.bot.send_message(matched_user['user_id'], f'Matched with {user["username"]}. You can start chatting now.')

        context.user_data['current_chat'] = matched_user['user_id']
    else:
        update.message.reply_text('No match found.')
    main_menu(update)

def message_handler(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    conversation = conversations_collection.find_one({'user1': user_id, 'active': True}) or \
                   conversations_collection.find_one({'user2': user_id, 'active': True})

    if conversation:
        recipient_id = conversation['user2'] if conversation['user1'] == user_id else conversation['user1']
        context.bot.send_message(recipient_id, update.message.text)
    else:
        update.message.reply_text('No active chat. Use the main menu to find a match.')
        main_menu(update)


def disconnect(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    conversation = conversations_collection.find_one_and_update(
        {'$or': [{'user1': user_id, 'active': True}, {'user2': user_id, 'active': True}]},
        {'$set': {'active': False}}
    )

    if conversation:
        recipient_id = conversation['user2'] if conversation['user1'] == user_id else conversation['user1']
        context.bot.send_message(recipient_id, 'The other user has disconnected. Use the main menu to find a new match.')
        update.message.reply_text('You have disconnected. Use the main menu to find a new match.')
    else:
        update.message.reply_text('No active chat to disconnect from.')
    main_menu(update)

def help_command(update: Update, context: CallbackContext) -> None:
    help_text = (
        "Welcome to the Chat Bot! Here are the available commands:\n"
        "/start - Show the main menu\n"
        "/help - Show this help message\n\n"
        "Main Menu Options:\n"
        "1. Register - Register your profile\n"
        "2. Search for Match - Find a chat match\n"
        "3. Disconnect - Disconnect from the current chat\n\n"
        "To start, use the main menu to select an option."
    )
    update.message.reply_text(help_text)

def button_handler(update: Update, context: CallbackContext) -> None:
    text = update.message.text

    if text == "Register":
        return register(update, context)
    elif text == "Search for Match":
        return search(update, context)
    elif text == "Disconnect":
        return disconnect(update, context)
    else:
        update.message.reply_text("Please choose a valid option from the menu.")
        main_menu(update)

def cancel(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Operation cancelled.', reply_markup=ReplyKeyboardRemove())
    main_menu(update)
    return ConversationHandler.END

def main() -> None:
    # Set up the updater and dispatcher
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dispatcher = updater.dispatcher

    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex('^(Register)$'), register)],
        states={
            PROFILE_PICTURE: [MessageHandler(Filters.photo, profile_picture)],
            SEX: [MessageHandler(Filters.text & ~Filters.command, sex)],
            BIRTHDAY: [MessageHandler(Filters.text & ~Filters.command, birthday)],
            LOCATION: [MessageHandler(Filters.location, location)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CommandHandler('help', help_command))
    dispatcher.add_handler(MessageHandler(Filters.regex('^(Search for Match)$'), search_match))
    dispatcher.add_handler(MessageHandler(Filters.regex('^(Disconnect)$'), disconnect))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, message_handler))
    dispatcher.add_handler(MessageHandler(Filters.regex('^(Register|Search for Match|Disconnect)$'), button_handler))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
