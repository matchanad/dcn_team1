import time
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from threading import Thread, Event
import busio
import digitalio
import board
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn

# Telegram bot token
BOT_TOKEN = '7310002513:AAEQeDpJbzX9pXu8NTY0O7YNEYFweNw2xZs'

# Initialize the bot
bot = Bot(token=BOT_TOKEN)

# Global variables
sensor_active = Event()
chat_states = {}
current_chat_id = None
calibrated_voltage = None
alert_active = Event()

# States for the state machine
STATE_IDLE = "idle"
STATE_SETUP_INSTALLATION = "setup_installation"
STATE_SETUP_CALIBRATION = "setup_calibration"
STATE_CHECK_BLACK_SURFACE = "check_black_surface"
STATE_ALERT = "alert"

# Set up SPI and MCP3008
spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)
cs = digitalio.DigitalInOut(board.D5)
mcp = MCP.MCP3008(spi, cs)
chan = AnalogIn(mcp, MCP.P0)

def create_keyboard(options):
    keyboard = [[InlineKeyboardButton(text, callback_data=text)] for text in options]
    return InlineKeyboardMarkup(keyboard)

def handle(update: Update) -> None:
    global current_chat_id, calibrated_voltage

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

        if command == 'view_dashboard':
            bot.send_message(chat_id=chat_id, text='You can view the live sensor data at: http://tcrt5000.azureiotcentral.com')
            return

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
                if calibrated_voltage is None:
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
    global calibrated_voltage

    bot.send_message(chat_id=chat_id, text='Starting calibration. Please ensure the door/window is closed.')
    
    for _ in range(5):  # Try 5 times
        voltage = chan.voltage
        if voltage < 1.0:  # Voltage less than 1.0V means closed
            calibrated_voltage = voltage
            bot.send_message(chat_id=chat_id, text=f'Calibration complete. The sensor is working correctly. Calibrated voltage: {calibrated_voltage:.2f}V')
            chat_states[chat_id] = STATE_IDLE
            return
        time.sleep(1)
    
    keyboard = create_keyboard(['Yes', 'No'])
    bot.send_message(chat_id=chat_id, text='The sensor is not detecting a closed door/window. Is the door/window surface black or very dark?', reply_markup=keyboard)
    chat_states[chat_id] = STATE_CHECK_BLACK_SURFACE

def monitor_sensor():
    global current_chat_id, calibrated_voltage

    while True:
        if sensor_active.is_set() and calibrated_voltage is not None:
            current_voltage = chan.voltage

            if current_voltage >= 1.0 and not alert_active.is_set():  # Break-in detected if voltage is 1.0V or more
                print(f"Break-in detected! Current voltage: {current_voltage:.2f}V")
                if current_chat_id is not None:
                    alert_active.set()
                    chat_states[current_chat_id] = STATE_ALERT
                    send_alert()
            else:
                print(f"Secure. Current voltage: {current_voltage:.2f}V")
        time.sleep(0.01)

def send_alert():
    while alert_active.is_set():
        try:
            keyboard = create_keyboard(['Safe'])
            bot.send_message(chat_id=current_chat_id, text='Alert! Break in detected! Tap "Safe" if the situation is under control.', reply_markup=keyboard)
        except TelegramError as e:
            print(f"Error sending alert: {e}")
        time.sleep(2)  # Wait for 2 seconds before sending the next alert

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
        # Clean up (if needed)
        pass