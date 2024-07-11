import telepot
import time
from telepot.loop import MessageLoop

# Telegram bot token
BOT_TOKEN = '6015175658:AAH1ZQkPHCQwcgem4Szo0LNF5Gqred97kps'

# Chat ID for your bot
CHAT_ID = 600746930

# Function to handle incoming messages
def handle(msg):
    content_type, chat_type, chat_id = telepot.glance(msg)
    print('Received:', content_type, chat_type, chat_id)

    # Respond to text messages
    if content_type == 'text':
        command = msg['text']
        print('Received command:', command)

        # Example: Respond to '/start' command
        if command == '/startRaspi':
            bot.sendMessage(chat_id, 'Hello! I am your Raspberry Pi bot.')

        # Add more commands as needed

try:
    # Initialize the bot
    bot = telepot.Bot(BOT_TOKEN)

    # Delete webhook if it exists
    bot.deleteWebhook()

    # Start message loop to continuously listen for messages
    MessageLoop(bot, handle).run_as_thread()
    print('Listening...')

    # Keep the program running
    while True:
        time.sleep(10)

except telepot.exception.TelegramError as e:
    print(f"TelegramError: {e}")
