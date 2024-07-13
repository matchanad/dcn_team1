import time
from telegram import Bot, Update
from telegram.error import TelegramError
from gpiozero import DistanceSensor
from time import sleep
from threading import Thread, Event

# Telegram bot token
BOT_TOKEN = '7310002513:AAEQeDpJbzX9pXu8NTY0O7YNEYFweNw2xZs'

# Initialize the bot
bot = Bot(token=BOT_TOKEN)

# Define GPIO pins and Maximum Distance for Break-in
TRIG = 23  # GPIO pin connected to the TRIG pin of HC-SR04
ECHO = 24  # GPIO pin connected to the ECHO pin of HC-SR04
MAX_DISTANCE = 4  # Maximum distance the sensor can measure in meters

# Global variables
sensor_active = Event()
max_distance = None
sensor_thread = None
chat_states = {}

# States for the state machine
STATE_IDLE = "idle"
STATE_SETUP_INSTALLATION = "setup_installation"
STATE_SETUP_DOOR_CLOSED = "setup_door_closed"
STATE_SETUP_CALIBRATION = "setup_calibration"

def handle(update: Update) -> None:
    try:
        message = update.message
        chat_id = message.chat.id
        command = message.text

        print(f'Received command: {command}')

        # Check the current state of the chat
        current_state = chat_states.get(chat_id, STATE_IDLE)

        if current_state == STATE_IDLE:
            if command == '/startProtect':
                if max_distance is None:
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
                chat_states[chat_id] = STATE_SETUP_DOOR_CLOSED
                bot.send_message(chat_id=chat_id, text='Close the door/window, have you closed it? If yes, reply with "yes".')
            else:
                bot.send_message(chat_id=chat_id, text='Please install the sensor at the desired location and reply with "yes".')

        elif current_state == STATE_SETUP_DOOR_CLOSED:
            if command.lower() == 'yes':
                chat_states[chat_id] = STATE_SETUP_CALIBRATION
                bot.send_message(chat_id=chat_id, text='Starting distance calibration for 15 seconds...')
                calibrate_sensor(chat_id)
            else:
                bot.send_message(chat_id=chat_id, text='Please close the door/window and reply with "yes".')

    except TelegramError as e:
        print(f"TelegramError: {e}")

def calibrate_sensor(chat_id):
    global max_distance

    sensor = DistanceSensor(echo=ECHO, trigger=TRIG, max_distance=MAX_DISTANCE)
    distances = []

    start_time = time.time()
    while time.time() - start_time < 15:
        distance_cm = sensor.distance * 100
        distances.append(distance_cm)
        sleep(1)

    if len(set(distances)) == 1:  # Check if all measurements are the same
        max_distance = distances[0]
        bot.send_message(chat_id=chat_id, text=f'Setup complete. Maximum distance threshold is {max_distance:.2f} cm. Ready to protect the house!')
    else:
        bot.send_message(chat_id=chat_id, text='Distance not constant. Please try again.')
    
    chat_states[chat_id] = STATE_IDLE  # Reset state to idle after calibration

def monitor_distance():
    global max_distance

    sensor = DistanceSensor(echo=ECHO, trigger=TRIG, max_distance=MAX_DISTANCE)

    while True:
        if sensor_active.is_set():
            distance_cm = sensor.distance * 100
            print(f"Measured Distance: {distance_cm:.2f} cm")

            if distance_cm > max_distance:
                bot.send_message(chat_id=chat_id, text="Break in!")
                sensor_active.clear()

        sleep(1)

def main():
    global sensor_thread

    sensor_thread = Thread(target=monitor_distance)
    sensor_thread.daemon = True
    sensor_thread.start()

    offset = None

    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=10)

            for update in updates:
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
