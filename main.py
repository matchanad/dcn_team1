import time
from azure.iot.device import IoTHubDeviceClient, Message, ProvisioningDeviceClient, exceptions
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler
import busio
import digitalio
import board
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn
from threading import Thread, Event

# Telegram bot token
BOT_TOKEN = '7310002513:AAEQeDpJbzX9pXu8NTY0O7YNEYFweNw2xZs'

# Azure IoT Central information
id_scope = "0ne00CDBD95"
device_id = "27yzuc90d6v"
primary_key = "cBkkyw8/SDdwPygExhk8npwAPyHsqO0H7832Xx+XSR0="
provisioning_host = "global.azure-devices-provisioning.net"
template = "{\"Voltage\": %.2f, \"State\": \"%d\"}"

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

# Azure IoT Device Client
device_client = None

def create_keyboard(options):
    keyboard = [[InlineKeyboardButton(text, callback_data=text)] for text in options]
    return InlineKeyboardMarkup(keyboard)

def start(update, context):
    update.message.reply_text('Welcome! Use /setup_sensor to begin setup.')

def view_dashboard(update, context):
    update.message.reply_text('You can view the live sensor data at: http://tcrt5000.azureiotcentral.com')

def setup_sensor(update, context):
    chat_id = update.effective_chat.id
    chat_states[chat_id] = STATE_SETUP_INSTALLATION
    keyboard = create_keyboard(['Yes', 'No'])
    update.message.reply_text('Have you installed the sensor at the desired location?', reply_markup=keyboard)

def start_protect(update, context):
    global calibrated_voltage
    if calibrated_voltage is None:
        update.message.reply_text('Please set up the sensor first using /setup_sensor.')
    else:
        sensor_active.set()
        update.message.reply_text('Protection started.')

def end_protect(update, context):
    sensor_active.clear()
    update.message.reply_text('Protection ended.')

def button(update, context):
    query = update.callback_query
    query.answer()
    chat_id = query.message.chat_id
    command = query.data
    
    current_state = chat_states.get(chat_id, STATE_IDLE)

    if current_state == STATE_ALERT:
        if command.lower() == 'safe':
            alert_active.clear()
            sensor_active.clear()
            chat_states[chat_id] = STATE_IDLE
            query.edit_message_text('Alert cancelled. Sensor protection stopped.')
        else:
            keyboard = create_keyboard(['Safe'])
            query.edit_message_text('Break-in alert is still active! Tap "Safe" if the situation is under control.', reply_markup=keyboard)
    elif current_state == STATE_SETUP_INSTALLATION:
        if command == 'Yes':
            chat_states[chat_id] = STATE_SETUP_CALIBRATION
            keyboard = create_keyboard(['Ready'])
            query.edit_message_text('Please close the door/window, then tap "Ready" to start calibration.', reply_markup=keyboard)
        else:
            keyboard = create_keyboard(['Yes'])
            query.edit_message_text('Please install the sensor at the desired location and tap "Yes" when done.', reply_markup=keyboard)
    elif current_state == STATE_SETUP_CALIBRATION:
        if command == 'Ready':
            calibrate_sensor(chat_id, query)
        else:
            keyboard = create_keyboard(['Ready'])
            query.edit_message_text('Please close the door/window, then tap "Ready" to start calibration.', reply_markup=keyboard)
    elif current_state == STATE_CHECK_BLACK_SURFACE:
        if command == 'Yes':
            keyboard = create_keyboard(['Done'])
            query.edit_message_text('Please place a reflective surface or any non-black material opposite to the sensor. This could be a small piece of white tape, aluminum foil, or any light-colored material. Tap "Done" when finished.', reply_markup=keyboard)
            chat_states[chat_id] = STATE_SETUP_CALIBRATION
        else:
            query.edit_message_text('The sensor is not detecting a closed door/window. Please check the installation and try the setup again using /setup_sensor.')
            chat_states[chat_id] = STATE_IDLE

def calibrate_sensor(chat_id, query):
    global calibrated_voltage

    query.edit_message_text('Starting calibration. Please ensure the door/window is closed.')
    
    for _ in range(5):  # Try 5 times
        voltage = chan.voltage
        if voltage < 1.0:  # Voltage less than 1.0V means closed
            calibrated_voltage = voltage
            query.edit_message_text(f'Calibration complete. The sensor is working correctly. Calibrated voltage: {calibrated_voltage:.2f}V')
            chat_states[chat_id] = STATE_IDLE
            return
        time.sleep(1)
    
    keyboard = create_keyboard(['Yes', 'No'])
    query.edit_message_text('The sensor is not detecting a closed door/window. Is the door/window surface black or very dark?', reply_markup=keyboard)
    chat_states[chat_id] = STATE_CHECK_BLACK_SURFACE

def monitor_sensor():
    global current_chat_id, calibrated_voltage, device_client

    prev_voltage = None
    prev_state = None

    while True:
        if sensor_active.is_set() and calibrated_voltage is not None:
            current_voltage = chan.voltage
            current_state = 1 if current_voltage >= 1.0 else 0

            if current_voltage != prev_voltage or current_state != prev_state:
                # Send data to Azure IoT Central
                msg_txt = template % (current_voltage, current_state)
                message = Message(msg_txt)
                print(f"Sending message to Azure IoT Central: {message}")
                device_client.send_message(message)
                prev_voltage, prev_state = current_voltage, current_state

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
    global bot
    while alert_active.is_set():
        try:
            keyboard = create_keyboard(['Safe'])
            bot.send_message(chat_id=current_chat_id, text='Alert! Break in detected! Tap "Safe" if the situation is under control.', reply_markup=keyboard)
        except Exception as e:
            print(f"Error sending alert: {e}")
        time.sleep(2)  # Wait for 2 seconds before sending the next alert

def main():
    global device_client, bot

    try:
        # Provisioning
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

        updater = Updater(BOT_TOKEN, use_context=True)
        dp = updater.dispatcher

        dp.add_handler(CommandHandler("start", start))
        dp.add_handler(CommandHandler("view_dashboard", view_dashboard))
        dp.add_handler(CommandHandler("setup_sensor", setup_sensor))
        dp.add_handler(CommandHandler("start_protect", start_protect))
        dp.add_handler(CommandHandler("end_protect", end_protect))
        dp.add_handler(CallbackQueryHandler(button))

        bot = updater.bot

        # Start the sensor monitoring thread
        sensor_thread = Thread(target=monitor_sensor)
        sensor_thread.daemon = True
        sensor_thread.start()

        # Start the bot
        updater.start_polling()
        updater.idle()

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if device_client:
            device_client.disconnect()

if __name__ == '__main__':
    main()