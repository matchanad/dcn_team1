from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Telegram bot token
BOT_TOKEN = '6015175658:AAH1ZQkPHCQwcgem4Szo0LNF5Gqred97kps'

# Function to handle the /startRaspi command
def start_raspi(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Hello! I am your Raspberry Pi bot.')

# Function to handle other text messages
def handle_message(update: Update, context: CallbackContext) -> None:
    command = update.message.text
    print('Received command:', command)

    # Example: Respond to '/startRaspi' command (already handled by start_raspi)
    if command == '/startRaspi':
        start_raspi(update, context)
    
    # Add more commands as needed

def main():
    # Initialize the bot and updater
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher

    # Add command handler for /startRaspi
    dispatcher.add_handler(CommandHandler('startRaspi', start_raspi))

    # Add a message handler for other text messages
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    # Start the bot
    updater.start_polling()
    print('Listening...')

    # Run the bot until you press Ctrl-C
    updater.idle()

if __name__ == '__main__':
    main()
