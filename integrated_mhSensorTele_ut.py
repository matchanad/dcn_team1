import time
from telegram import Bot, Update
from telegram.error import TelegramError
import RPi.GPIO as GPIO
from threading import Thread, Event

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

# States for the state machine
STATE_IDLE = "idle"
STATE_SETUP_INSTALLATION = "setup_installation"
STATE_SETUP_CALIBRATION = "setup_calibration"
STATE_CHECK_BLACK_SURFACE = "check_black_surface"
STATE_ALERT = "alert"

# Set up GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(DIGITAL_PIN, GPIO.IN)

def handle(update: Update) -> None:
    global current_chat_id, calibrated_digital

    try:
        message = update.message
        chat_id = message.chat.id
        current_chat_id = chat_id
        command = message.text

        print(f'Received command: {command}')

        current_state = chat_states.get(chat_id, STATE_IDLE)

        if current_state == STATE_ALERT:
            if command.lower() == 'safe':
                alert_active.clear()
                sensor_active.clear()
                chat_states[chat_id] = STATE_IDLE
                bot.send_message(chat_id=chat_id, text='Alert cancelled. Sensor protection stopped.')
            else:
                bot.send_message(chat_id=chat_id, text='Break-in alert is still active! Type "safe" if the situation is under control.')
        elif current_state == STATE_IDLE:
            if command == '/startProtect':
                if calibrated_digital is None:
                    bot.send_message(chat_id=chat_id, text='Please set up the sensor first using /setupSensor.')
                else:
                    sensor_active.set()
                    bot.send_message(chat_id=chat_id, text='Protection started.')
            elif command == '/endProtect':
                sensor_active.clear()
                bot.send_message(chat_id=chat_id, text='Protection ended.')
            elif command == '/setupSensor':
                chat_states[chat_id] = STATE_SETUP_INSTALLATION
                bot.send_message(chat_id=chat_id, text='Have you installed the sensor at the desired location? If yes, reply with "yes".')

        elif current_state == STATE_SETUP_INSTALLATION:
            if command.lower() == 'yes':
                chat_states[chat_id] = STATE_SETUP_CALIBRATION
                bot.send_message(chat_id=chat_id, text='Please close the door/window, then reply with "ready" to start calibration.')
            else:
                bot.send_message(chat_id=chat_id, text='Please install the sensor at the desired location and reply with "yes".')

        elif current_state == STATE_SETUP_CALIBRATION:
            if command.lower() == 'ready':
                calibrate_sensor(chat_id)
            else:
                bot.send_message(chat_id=chat_id, text='Please close the door/window, then reply with "ready" to start calibration.')

        elif current_state == STATE_CHECK_BLACK_SURFACE:
            if command.lower() == 'yes':
                bot.send_message(chat_id=chat_id, text='Please place a reflective surface or any non-black material opposite to the sensor. This could be a small piece of white tape, aluminum foil, or any light-colored material. Once done, reply with "done".')
                chat_states[chat_id] = STATE_SETUP_CALIBRATION
            else:
                bot.send_message(chat_id=chat_id, text='The sensor is not detecting a closed door/window. Please check the installation and try the setup again using /setupSensor.')
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
    bot.send_message(chat_id=chat_id, text='The sensor is not detecting a closed door/window. Is the door/window surface black or very dark? Reply with "yes" or "no".')
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
        time.sleep(1)

def send_alert():
    while alert_active.is_set():
        try:
            bot.send_message(chat_id=current_chat_id, text='Alert! Break in detected! Type "safe" if the situation is under control.')
        except TelegramError as e:
            print(f"Error sending alert: {e}")
        time.sleep(10)  # Wait for 10 seconds before sending the next alert

def main():
    sensor_thread = Thread(target=monitor_sensor)
    sensor_thread.daemon = True
    sensor_thread.start()

    alert_thread = Thread(target=send_alert)
    alert_thread.daemon = True
    alert_thread.start()

    offset = None

    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=10)

            for update in updates:
                offset = update.update_id + 1
                handle(update)

        except TelegramError as e:
            print(f"TelegramError: {e}")
            time.sleep(10)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

if __name__ == '__main__':
    try:
        main()
    finally:
        GPIO.cleanup()