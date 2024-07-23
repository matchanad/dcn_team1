import time
from azure.iot.device import IoTHubDeviceClient, Message, ProvisioningDeviceClient, exceptions
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

# Azure IoT Central information
id_scope = "0ne00CDBD95"
device_id = "27yzuc90d6v"
primary_key = "cBkkyw8/SDdwPygExhk8npwAPyHsqO0H7832Xx+XSR0="
provisioning_host = "global.azure-devices-provisioning.net"
template = "{\"Voltage\": %.2f, \"State\": \"%d\"}"

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

# Azure IoT Device Client
device_client = None

def create_keyboard(options):
    keyboard = [[InlineKeyboardButton(text, callback_data=text)] for text in options]
    return InlineKeyboardMarkup(keyboard)

def handle(update: Update) -> None:
    global current_chat_id, calibrated_voltage

    # ... (rest of the handle function remains the same)

def calibrate_sensor(chat_id):
    global calibrated_voltage

    # ... (rest of the calibrate_sensor function remains the same)

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
    while alert_active.is_set():
        try:
            keyboard = create_keyboard(['Safe'])
            bot.send_message(chat_id=current_chat_id, text='Alert! Break in detected! Tap "Safe" if the situation is under control.', reply_markup=keyboard)
        except TelegramError as e:
            print(f"Error sending alert: {e}")
        time.sleep(2)  # Wait for 2 seconds before sending the next alert

def main():
    global device_client

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

    except exceptions.CredentialError as e:
        print(f"Credential error: {e}")
    except exceptions.ConnectionFailedError as e:
        print(f"Connection failed error: {e}")
    except exceptions.ConnectionDroppedError as e:
        print(f"Connection dropped error: {e}")
    except exceptions.ClientError as e:
        print(f"Client error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if device_client:
            device_client.disconnect()

if __name__ == '__main__':
    main()