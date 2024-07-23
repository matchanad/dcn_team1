import time
import telepot
from telepot.loop import MessageLoop
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton
import busio
import digitalio
import board
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn
from azure.iot.device import IoTHubDeviceClient, Message, ProvisioningDeviceClient, exceptions
import os

# Telegram bot token
BOT_TOKEN = '7310002513:AAEQeDpJbzX9pXu8NTY0O7YNEYFweNw2xZs'

# Azure IoT Central information
id_scope = "0ne00CDBD95"
device_id = "27yzuc90d6v"
primary_key = "cBkkyw8/SDdwPygExhk8npwAPyHsqO0H7832Xx+XSR0="
provisioning_host = "global.azure-devices-provisioning.net"
template = "{\"Voltage\": %.2f, \"State\": \"%d\"}"

# File to store registered chat IDs
CHAT_ID_FILE = 'registered_chat_ids.txt'

# Initialize the bot
bot = telepot.Bot(BOT_TOKEN)

# Global variables
sensor_active = False
chat_states = {}
current_chat_id = None
calibrated_voltage = None
alert_active = False
prev_Voltage, prev_State = None, None

# States for the state machine
STATE_IDLE = "idle"
STATE_SETUP_INSTALLATION = "setup_installation"
STATE_SETUP_CALIBRATION = "setup_calibration"
STATE_CHECK_BLACK_SURFACE = "check_black_surface"
STATE_ALERT = "alert"
STATE_REGISTER = "register"

# Set up SPI and MCP3008
spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)
cs = digitalio.DigitalInOut(board.D5)
mcp = MCP.MCP3008(spi, cs)
chan = AnalogIn(mcp, MCP.P0)

# Azure IoT Central provisioning
try:
    provisioning_device_client = ProvisioningDeviceClient.create_from_symmetric_key(
        provisioning_host=provisioning_host,
        registration_id=device_id,
        id_scope=id_scope,
        symmetric_key=primary_key
    )

    registration_result = provisioning_device_client.register()

    if registration_result.status == "assigned":
        print("Device successfully provisioned")
        device_client = IoTHubDeviceClient.create_from_symmetric_key(
            symmetric_key=primary_key,
            hostname=registration_result.registration_state.assigned_hub,
            device_id=device_id
        )
        device_client.connect()
    else:
        print(f"Provisioning failed with status: {registration_result.status}")
        raise RuntimeError("Could not provision device. Aborting.")
except exceptions.CredentialError as e:
    print(f"Credential error: {e}")
    exit()
except exceptions.ConnectionFailedError as e:
    print(f"Connection failed error: {e}")
    exit()
except exceptions.ConnectionDroppedError as e:
    print(f"Connection dropped error: {e}")
    exit()
except exceptions.ClientError as e:
    print(f"Client error: {e}")
    exit()
except Exception as e:
    print(f"An unexpected error occurred: {e}")
    exit()

def load_registered_chat_ids():
    if os.path.exists(CHAT_ID_FILE):
        with open(CHAT_ID_FILE, 'r') as f:
            return set(line.strip() for line in f)
    return set()

def save_registered_chat_ids(chat_ids):
    with open(CHAT_ID_FILE, 'w') as f:
        for chat_id in chat_ids:
            f.write(f"{chat_id}\n")

def is_chat_id_registered(chat_id):
    return chat_id in load_registered_chat_ids()

def create_keyboard(options):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=text)] for text in options])
    return keyboard

def on_chat_message(msg):
    global current_chat_id, calibrated_voltage, sensor_active, alert_active

    content_type, chat_type, chat_id = telepot.glance(msg)
    command = msg['text']

    current_chat_id = chat_id
    print(f'Received command: {command}')

    if not is_chat_id_registered(chat_id):
        bot.sendMessage(chat_id, 'You are not registered. Please use /register to register your chat ID.')
        return

    current_state = chat_states.get(chat_id, STATE_IDLE)

    if command == '/register':
        register_chat_id(chat_id)
        return

    if current_state == STATE_ALERT:
        if command.lower() == 'safe':
            alert_active = False
            sensor_active = False
            chat_states[chat_id] = STATE_IDLE
            bot.sendMessage(chat_id, 'Alert cancelled. Sensor protection stopped.')
        else:
            keyboard = create_keyboard(['Safe'])
            bot.sendMessage(chat_id, 'Break-in alert is still active! Tap "Safe" if the situation is under control.', reply_markup=keyboard)
    elif current_state == STATE_IDLE:
        if command == '/start_protect':
            if calibrated_voltage is None:
                bot.sendMessage(chat_id, 'Please set up the sensor first using /setup_sensor.')
            else:
                sensor_active = True
                bot.sendMessage(chat_id, 'Protection started.')
        elif command == '/end_protect':
            sensor_active = False
            bot.sendMessage(chat_id, 'Protection ended.')
        elif command == '/setup_sensor':
            chat_states[chat_id] = STATE_SETUP_INSTALLATION
            keyboard = create_keyboard(['Yes', 'No'])
            bot.sendMessage(chat_id, 'Have you installed the sensor at the desired location?', reply_markup=keyboard)

    elif current_state == STATE_SETUP_INSTALLATION:
        if command == 'Yes':
            chat_states[chat_id] = STATE_SETUP_CALIBRATION
            keyboard = create_keyboard(['Ready'])
            bot.sendMessage(chat_id, 'Please close the door/window, then tap "Ready" to start calibration.', reply_markup=keyboard)
        else:
            keyboard = create_keyboard(['Yes'])
            bot.sendMessage(chat_id, 'Please install the sensor at the desired location and tap "Yes" when done.', reply_markup=keyboard)

    elif current_state == STATE_SETUP_CALIBRATION:
        if command == 'Ready':
            calibrate_sensor(chat_id)
        else:
            keyboard = create_keyboard(['Ready'])
            bot.sendMessage(chat_id, 'Please close the door/window, then tap "Ready" to start calibration.', reply_markup=keyboard)

    elif current_state == STATE_CHECK_BLACK_SURFACE:
        if command == 'Yes':
            keyboard = create_keyboard(['Done'])
            bot.sendMessage(chat_id, 'Please place a reflective surface or any non-black material opposite to the sensor. This could be a small piece of white tape, aluminum foil, or any light-colored material. Tap "Done" when finished.', reply_markup=keyboard)
            chat_states[chat_id] = STATE_SETUP_CALIBRATION
        else:
            bot.sendMessage(chat_id, 'The sensor is not detecting a closed door/window. Please check the installation and try the setup again using /setup_sensor.')
            chat_states[chat_id] = STATE_IDLE

def on_callback_query(msg):
    query_id, from_id, query_data = telepot.glance(msg, flavor='callback_query')
    command = query_data
    chat_id = msg['message']['chat']['id']

    if not is_chat_id_registered(chat_id):
        bot.sendMessage(chat_id, 'You are not registered. Please use /register to register your chat ID.')
        return

    handle_callback_query(chat_id, command)

def handle_callback_query(chat_id, command):
    global current_chat_id, calibrated_voltage, sensor_active, alert_active

    current_chat_id = chat_id
    print(f'Received command: {command}')

    current_state = chat_states.get(chat_id, STATE_IDLE)

    if current_state == STATE_ALERT:
        if command.lower() == 'safe':
            alert_active = False
            sensor_active = False
            chat_states[chat_id] = STATE_IDLE
            bot.sendMessage(chat_id, 'Alert cancelled. Sensor protection stopped.')
        else:
            keyboard = create_keyboard(['Safe'])
            bot.sendMessage(chat_id, 'Break-in alert is still active! Tap "Safe" if the situation is under control.', reply_markup=keyboard)
    elif current_state == STATE_IDLE:
        if command == '/start_protect':
            if calibrated_voltage is None:
                bot.sendMessage(chat_id, 'Please set up the sensor first using /setup_sensor.')
            else:
                sensor_active = True
                bot.sendMessage(chat_id, 'Protection started.')
        elif command == '/end_protect':
            sensor_active = False
            bot.sendMessage(chat_id, 'Protection ended.')
        elif command == '/setup_sensor':
            chat_states[chat_id] = STATE_SETUP_INSTALLATION
            keyboard = create_keyboard(['Yes', 'No'])
            bot.sendMessage(chat_id, 'Have you installed the sensor at the desired location?', reply_markup=keyboard)

    elif current_state == STATE_SETUP_INSTALLATION:
        if command == 'Yes':
            chat_states[chat_id] = STATE_SETUP_CALIBRATION
            keyboard = create_keyboard(['Ready'])
            bot.sendMessage(chat_id, 'Please close the door/window, then tap "Ready" to start calibration.', reply_markup=keyboard)
        else:
            keyboard = create_keyboard(['Yes'])
            bot.sendMessage(chat_id, 'Please install the sensor at the desired location and tap "Yes" when done.', reply_markup=keyboard)

    elif current_state == STATE_SETUP_CALIBRATION:
        if command == 'Ready':
            calibrate_sensor(chat_id)
        else:
            keyboard = create_keyboard(['Ready'])
            bot.sendMessage(chat_id, 'Please close the door/window, then tap "Ready" to start calibration.', reply_markup=keyboard)

    elif current_state == STATE_CHECK_BLACK_SURFACE:
        if command == 'Yes':
            keyboard = create_keyboard(['Done'])
            bot.sendMessage(chat_id, 'Please place a reflective surface or any non-black material opposite to the sensor. This could be a small piece of white tape, aluminum foil, or any light-colored material. Tap "Done" when finished.', reply_markup=keyboard)
            chat_states[chat_id] = STATE_SETUP_CALIBRATION
        else:
            bot.sendMessage(chat_id, 'The sensor is not detecting a closed door/window. Please check the installation and try the setup again using /setup_sensor.')
            chat_states[chat_id] = STATE_IDLE

def register_chat_id(chat_id):
    registered_chat_ids = load_registered_chat_ids()

    if chat_id in registered_chat_ids:
        bot.sendMessage(chat_id, 'Your chat ID is already registered.')
        return

    admin_chat_id = registered_chat_ids.pop() if registered_chat_ids else None

    if admin_chat_id:
        keyboard = create_keyboard(['Yes', 'No'])
        bot.sendMessage(admin_chat_id, f'Chat ID {chat_id} is requesting registration. Approve?', reply_markup=keyboard)
        chat_states[admin_chat_id] = STATE_REGISTER
    else:
        registered_chat_ids.add(chat_id)
        save_registered_chat_ids(registered_chat_ids)
        bot.sendMessage(chat_id, 'You have been registered as the first chat ID. No need for approval.')
        chat_states[chat_id] = STATE_IDLE

def approve_registration(admin_chat_id, new_chat_id):
    registered_chat_ids = load_registered_chat_ids()
    registered_chat_ids.add(new_chat_id)
    save_registered_chat_ids(registered_chat_ids)
    bot.sendMessage(admin_chat_id, f'Chat ID {new_chat_id} has been registered.')
    bot.sendMessage(new_chat_id, 'You have been registered as a chat ID.')

def calibrate_sensor(chat_id):
    global calibrated_voltage

    bot.sendMessage(chat_id, 'Starting calibration. Please ensure the door/window is closed.')

    for _ in range(5):  # Try 5 times
        voltage = chan.voltage
        if voltage < 1.0:  # Voltage less than 1.0V means closed
            calibrated_voltage = voltage
            bot.sendMessage(chat_id, f'Calibration complete. The sensor is working correctly. Calibrated voltage: {calibrated_voltage:.2f}V')
            chat_states[chat_id] = STATE_IDLE
            return
        time.sleep(1)

    keyboard = create_keyboard(['Yes', 'No'])
    bot.sendMessage(chat_id, 'The sensor is not detecting a closed door/window. Is the door/window surface black or very dark?', reply_markup=keyboard)
    chat_states[chat_id] = STATE_CHECK_BLACK_SURFACE

def monitor_sensor():
    global current_chat_id, calibrated_voltage, sensor_active, alert_active, prev_Voltage, prev_State

    if sensor_active and calibrated_voltage is not None:
        current_voltage = chan.voltage
        State = 0 if current_voltage < 1.0 else 1  # Adjust the threshold as needed

        if current_voltage >= 1.0 and not alert_active:  # Break-in detected if voltage is 1.0V or more
            print(f"Break-in detected! Current voltage: {current_voltage:.2f}V")
            if current_chat_id is not None:
                alert_active = True
                chat_states[current_chat_id] = STATE_ALERT
                send_alert()
        else:
            print(f"Secure. Current voltage: {current_voltage:.2f}V")

        msg_txt = template % (current_voltage, State)
        message = Message(msg_txt)
        print(f"Sending message to Azure IoT Central: {message}")
        device_client.send_message(message)

def send_alert():
    global alert_active

    while alert_active:
        try:
            keyboard = create_keyboard(['Safe'])
            bot.sendMessage(current_chat_id, 'Alert! Break in detected! Tap "Safe" if the situation is under control.', reply_markup=keyboard)
        except telepot.exception.TelegramError as e:
            print(f"Error sending alert: {e}")
        time.sleep(2)  # Wait for 2 seconds before sending the next alert

def main():
    MessageLoop(bot, {'chat': on_chat_message, 'callback_query': on_callback_query}).run_as_thread()

    while True:
        try:
            monitor_sensor()
            time.sleep(0.1)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

if __name__ == '__main__':
    main()
