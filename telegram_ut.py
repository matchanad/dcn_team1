import telebot

# Initialize the bot with your token
bot = telebot.TeleBot("6015175658:AAH1ZQkPHCQwcgem4Szo0LNF5Gqred97kps")

# Set up GPIO
# Add any GPIO setup you need here

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Welcome! I'm your Raspberry Pi Telegram bot.")

@bot.message_handler(commands=['startRaspi'])
def start_raspi(message):
    bot.reply_to(message, "Raspberry Pi is starting up!")
    # Add your Raspberry Pi startup code here
    # For example:
    # os.system("sudo systemctl start your_service.service")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, "You said: " + message.text)

# Start the bot
bot.polling()