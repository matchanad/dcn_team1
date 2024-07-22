import time
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from telegram.error import TelegramError
import RPi.GPIO as GPIO
from threading import Thread, Event
import subprocess
from pyngrok import ngrok

# Telegram bot token
BOT_TOKEN = '7310002513:AAEQeDpJbzX9pXu8NTY0O7YNEYFweNw2xZs'

# Initialize the bot
bot = Bot(token=BOT_TOKEN)

# Define GPIO pin for digital sensor
DIGITAL_PIN = 27

# Global variables
sensor_active = Event()
chat_states = {}
current_chat_id = None
calibrated_digital = None
alert_active = Event()
public_url = None

# States for the state machine
STATE_IDLE = "idle"
STATE_SETUP_INSTALLATION = "setup_installation"
STATE_SETUP_CALIBRATION = "setup_calibration"
STATE_CHECK_BLACK_SURFACE = "check_black_surface"
STATE_ALERT = "alert"

# Set up GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(DIGITAL_PIN, GPIO.IN)

def create_keyboard(options):
    keyboard = [[InlineKeyboardButton(text, callback_data=text)] for text in options]
    return InlineKeyboardMarkup(keyboard)

def handle(update: Update) -> None:
    global current_chat_id, calibrated_digital, public_url

    try:
        if update.callback_query:
            query = update.callback_query
            chat_id = query.message.chat_id
            command = query.data
            query.answer()
        else:
            message = update.message
            chat_id = message.chat_id
            command = message.text

        current_chat_id = chat_id
        print(f'Received command: {command}')

        current_state = chat_states.get(chat_id, STATE_IDLE)

        if current_state == STATE_ALERT:
            if command.lower() == 'safe':
                alert_active.clear()
                sensor_active.clear()
                chat_states[chat_id] = STATE_IDLE
                bot.send_message(chat_id=chat_id, text='Alert cancelled. Sensor protection stopped.')
            else:
                keyboard = create_keyboard(['Safe'])
                bot.send_message(chat_id=chat_id, text='Break-in alert is still active! Tap "Safe" if the situation is under control.', reply_markup=keyboard)
        elif current_state == STATE_IDLE:
            if command == '/start_protect':
                if calibrated_digital is None:
                    bot.send_message(chat_id=chat_id, text='Please set up the sensor first using /setup_sensor.')
                else:
                    sensor_active.set()
                    bot.send_message(chat_id=chat_id, text='Protection started.')
            elif command == '/end_protect':
                sensor_active.clear()
                bot.send_message(chat_id=chat_id, text='Protection ended.')
            elif command == '/setup_sensor':
                chat_states[chat_id] = STATE_SETUP_INSTALLATION
                keyboard = create_keyboard(['Yes', 'No'])
                bot.send_message(chat_id=chat_id, text='Have you installed the sensor at the desired location?', reply_markup=keyboard)
            elif command == '/view':
                if public_url:
                    bot.send_message(chat_id=chat_id, text=f"View the live sensor data here: {public_url}")
                else:
                    bot.send_message(chat_id=chat_id, text="Live view is not available at the moment.")

        elif current_state == STATE_SETUP_INSTALLATION:
            if command == 'Yes':
                chat_states[chat_id] = STATE_SETUP_CALIBRATION
                keyboard = create_keyboard(['Ready'])
                bot.send_message(chat_id=chat_id, text='Please close the door/window, then tap "Ready" to start calibration.', reply_markup=keyboard)
            else:
                keyboard = create_keyboard(['Yes'])
                bot.send_message(chat_id=chat_id, text='Please install the sensor at the desired location and tap "Yes" when done.', reply_markup=keyboard)

        elif current_state == STATE_SETUP_CALIBRATION:
            if command == 'Ready':
                calibrate_sensor(chat_id)
            else:
                keyboard = create_keyboard(['Ready'])
                bot.send_message(chat_id=chat_id, text='Please close the door/window, then tap "Ready" to start calibration.', reply_markup=keyboard)

        elif current_state == STATE_CHECK_BLACK_SURFACE:
            if command == 'Yes':
                keyboard = create_keyboard(['Done'])
                bot.send_message(chat_id=chat_id, text='Please place a reflective surface or any non-black material opposite to the sensor. This could be a small piece of white tape, aluminum foil, or any light-colored material. Tap "Done" when finished.', reply_markup=keyboard)
                chat_states[chat_id] = STATE_SETUP_CALIBRATION
            else:
                bot.send_message(chat_id=chat_id, text='The sensor is not detecting a closed door/window. Please check the installation and try the setup again using /setup_sensor.')
                chat_states[chat_id] = STATE_IDLE

    except TelegramError as e:
        print(f"TelegramError: {e}")

def calibrate_sensor(chat_id):
    global calibrated_digital

    bot.send_message(chat_id=chat_id, text='Starting calibration. Please ensure the door/window is closed.')
    
    # Check if the door is closed using digital value
    for _ in range(5):  # Try 5 times
        digital_value = GPIO.input(DIGITAL_PIN)
        if digital_value == 0:  # Assuming 0 means closed
            calibrated_digital = 0
            bot.send_message(chat_id=chat_id, text='Calibration complete. The sensor is working correctly.')
            chat_states[chat_id] = STATE_IDLE
            return
        time.sleep(1)
    
    # If we get here, the sensor is not detecting a closed door
    keyboard = create_keyboard(['Yes', 'No'])
    bot.send_message(chat_id=chat_id, text='The sensor is not detecting a closed door/window. Is the door/window surface black or very dark?', reply_markup=keyboard)
    chat_states[chat_id] = STATE_CHECK_BLACK_SURFACE

def monitor_sensor():
    global current_chat_id, calibrated_digital

    while True:
        if sensor_active.is_set() and calibrated_digital is not None:
            current_digital = GPIO.input(DIGITAL_PIN)

            if current_digital != calibrated_digital and not alert_active.is_set():
                print("Break-in detected!")
                if current_chat_id is not None:
                    alert_active.set()
                    chat_states[current_chat_id] = STATE_ALERT
                    send_alert()
            elif current_digital == calibrated_digital:
                print("Secure")
        time.sleep(0.01)

def send_alert():
    while alert_active.is_set():
        try:
            keyboard = create_keyboard(['Safe'])
            bot.send_message(chat_id=current_chat_id, text='Alert! Break in detected! Tap "Safe" if the situation is under control.', reply_markup=keyboard)
        except TelegramError as e:
            print(f"Error sending alert: {e}")
        time.sleep(2)  # Wait for 2 seconds before sending the next alert

def run_streamlit():
    subprocess.Popen(["streamlit", "run", "streamlit_app.py"])

def setup_ngrok():
    public_url = ngrok.connect(8501)
    print(f' * ngrok tunnel "{public_url}" -> "http://127.0.0.1:8501"')
    return public_url

def main():
    global public_url

    # Start Streamlit
    streamlit_thread = Thread(target=run_streamlit)
    streamlit_thread.daemon = True
    streamlit_thread.start()

    # Set up ngrok
    public_url = setup_ngrok()

    # Start sensor monitoring thread
    sensor_thread = Thread(target=monitor_sensor)
    sensor_thread.daemon = True
    sensor_thread.start()

    # Start alert thread
    alert_thread = Thread(target=send_alert)
    alert_thread.daemon = True
    alert_thread.start()

    # Set up Telegram bot
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Add handlers
    dp.add_handler(CommandHandler("start_protect", lambda update, context: handle(update)))
    dp.add_handler(CommandHandler("end_protect", lambda update, context: handle(update)))
    dp.add_handler(CommandHandler("setup_sensor", lambda update, context: handle(update)))
    dp.add_handler(CommandHandler("view", lambda update, context: handle(update)))
    dp.add_handler(CallbackQueryHandler(handle))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle))

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C
    updater.idle()

if __name__ == '__main__':
    try:
        main()
    finally:
        GPIO.cleanup()
        ngrok.kill()  # Kill ngrok process when exiting