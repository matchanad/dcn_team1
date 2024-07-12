import time
from telegram import Bot, Update
from telegram.error import TelegramError

# Telegram bot token
BOT_TOKEN = '6015175658:AAH1ZQkPHCQwcgem4Szo0LNF5Gqred97kps'

# Initialize the bot
bot = Bot(token=BOT_TOKEN)

# Function to handle incoming messages
def handle(update: Update) -> None:
    try:
        message = update.message
        chat_id = message.chat.id
        command = message.text

        print(f'Received command: {command}')

        # Example: Respond to '/startRaspi' command
        if command == '/startRaspi':
            bot.send_message(chat_id=chat_id, text='Hello! I am your Raspberry Pi bot.')
        # Add more commands as needed

    except TelegramError as e:
        print(f"TelegramError: {e}")

def main():
    offset = None

    while True:
        try:
            # Get updates from the bot
            updates = bot.get_updates(offset=offset, timeout=10)

            for update in updates:
                # Update offset to get the next batch of updates
                offset = update.update_id + 1

                handle(update)

        except TelegramError as e:
            print(f"TelegramError: {e}")
            time.sleep(10)  # Wait before retrying
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)  # Wait before retrying

if __name__ == '__main__':
    main()
