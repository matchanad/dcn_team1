import time
from telegram import Bot, Update
from telegram.error import TelegramError
import RPi.GPIO as GPIO
from threading import Thread, Event

# Telegram bot token
BOT_TOKEN = '7310002513:AAEQeDpJbzX9pXu8NTY0O7YNEYFweNw2xZs'

# Initialize the bot
bot = Bot(token=BOT_TOKEN)

# Define GPIO pins for MH series sensor
ANALOG_PIN = 17
DIGITAL_PIN = 27

# Global variables
sensor_active = Event()
chat_states = {}
current_chat_id = None
calibrated_analog = None
calibrated_digital = None

# States for the state machine
STATE_IDLE = "idle"
STATE_SETUP_INSTALLATION = "setup_installation"
STATE_SETUP_CALIBRATION = "setup_calibration"

# Set up GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(DIGITAL_PIN, GPIO.IN)
GPIO.setup(ANALOG_PIN, GPIO.IN)

def read_analog():
    # Discharge capacitor
    GPIO.setup(ANALOG_PIN, GPIO.OUT)
    GPIO.output(ANALOG_PIN, GPIO.LOW)
    time.sleep(0.1)

    # Count the time it takes to charge the capacitor
    start_time = time.time()
    GPIO.setup(ANALOG_PIN, GPIO.IN)
    end_time = time.time()

    return int((end_time - start_time) * 1000000)  # Return microseconds

def handle(update: Update) -> None:
    global current_chat_id

    try:
        message = update.message
        chat_id = message.chat.id
        current_chat_id = chat_id
        command = message.text

        print(f'Received command: {command}')

        current_state = chat_states.get(chat_id, STATE_IDLE)

        if current_state == STATE_IDLE:
            if command == '/startProtect':
                if calibrated_analog is None or calibrated_digital is None:
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

    except TelegramError as e:
        print(f"TelegramError: {e}")

def is_black_surface():
    # Take a few readings to determine if it's a black surface
    readings = [read_analog() for _ in range(5)]
    average_reading = sum(readings) / len(readings)
    # Adjust this threshold based on your sensor's behavior with black surfaces
    return average_reading > 900  # High analog value typically indicates a black surface

def calibrate_sensor(chat_id):
    global calibrated_analog, calibrated_digital

    bot.send_message(chat_id=chat_id, text='Starting calibration. Please ensure the door/window is closed.')
    
    if is_black_surface():
        bot.send_message(chat_id=chat_id, text='Black surface detected. Calibrating analog values only.')
        analog_values = []
        for _ in range(30):
            analog_value = read_analog()
            analog_values.append(analog_value)
            print(f"Analog value: {analog_value}")
            time.sleep(1)
        
        if max(analog_values) - min(analog_values) < 100:
            calibrated_analog = sum(analog_values) / len(analog_values)
            calibrated_digital = None  # We won't use digital for black surfaces
            bot.send_message(chat_id=chat_id, text=f'Calibration complete. Analog: {calibrated_analog:.2f}')
            chat_states[chat_id] = STATE_IDLE
        else:
            bot.send_message(chat_id=chat_id, text='Calibration failed. Analog values not stable. Please try again.')
            chat_states[chat_id] = STATE_SETUP_CALIBRATION
    else:
        # Check if the door is closed using digital value
        for _ in range(5):  # Try 5 times
            digital_value = GPIO.input(DIGITAL_PIN)
            if digital_value == 0:  # Assuming 0 means closed
                break
            bot.send_message(chat_id=chat_id, text='The door/window appears to be open. Please close it and wait.')
            time.sleep(5)
        else:  # This executes if the for loop completes without breaking
            bot.send_message(chat_id=chat_id, text='Could not detect a closed door/window. Please try setup again.')
            chat_states[chat_id] = STATE_IDLE
            return

        bot.send_message(chat_id=chat_id, text='Door/window detected as closed. Beginning calibration...')
        
        analog_values = []
        digital_values = []

        # Take 30 readings over 30 seconds
        for _ in range(30):
            digital_value = GPIO.input(DIGITAL_PIN)
            analog_value = read_analog()
            digital_values.append(digital_value)
            analog_values.append(analog_value)
            print(f"Digital value: {digital_value}, Analog value: {analog_value}")
            time.sleep(1)

        # Check if the values are stable
        digital_stable = all(value == 0 for value in digital_values)
        analog_stable = max(analog_values) - min(analog_values) < 100

        if digital_stable and analog_stable:
            calibrated_digital = 0
            calibrated_analog = sum(analog_values) / len(analog_values)
            bot.send_message(chat_id=chat_id, text=f'Calibration complete. Digital: LOW, Analog: {calibrated_analog:.2f}')
            chat_states[chat_id] = STATE_IDLE
        else:
            if not digital_stable:
                bot.send_message(chat_id=chat_id, text='Calibration failed. Door/window not consistently closed. Please try again.')
            elif not analog_stable:
                bot.send_message(chat_id=chat_id, text='Calibration failed. Analog values not stable. Please try again.')
            chat_states[chat_id] = STATE_SETUP_CALIBRATION
            
def monitor_sensor():
    global current_chat_id, calibrated_analog, calibrated_digital

    while True:
        if sensor_active.is_set() and calibrated_analog is not None:
            current_analog = read_analog()
            current_digital = GPIO.input(DIGITAL_PIN) if calibrated_digital is not None else None

            if calibrated_digital is None:
                # For black surfaces, only check analog
                if abs(current_analog - calibrated_analog) > 100:
                    print("Break-in detected!")
                    if current_chat_id is not None:
                        bot.send_message(chat_id=current_chat_id, text='Alert! Break in!')
                        sensor_active.clear()
                else:
                    print("Secure")
            else:
                # For non-black surfaces, check both analog and digital
                if abs(current_analog - calibrated_analog) > 100 or current_digital != calibrated_digital:
                    print("Break-in detected!")
                    if current_chat_id is not None:
                        bot.send_message(chat_id=current_chat_id, text='Alert! Break in!')
                        sensor_active.clear()
                else:
                    print("Secure")
        time.sleep(1)

def main():
    sensor_thread = Thread(target=monitor_sensor)
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
            time.sleep(10)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

if __name__ == '__main__':
    try:
        main()
    finally:
        GPIO.cleanup()