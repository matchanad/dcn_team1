import asyncio
import time
from azure.iot.device import IoTHubDeviceClient, Message, ProvisioningDeviceClient, exceptions
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
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

# Global variables
sensor_active = asyncio.Event()
chat_states = {}
current_chat_id = None
calibrated_voltage = None
alert_active = asyncio.Event()

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Welcome! Use /setup_sensor to begin setup.')

async def view_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('You can view the live sensor data at: http://tcrt5000.azureiotcentral.com')

async def setup_sensor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    chat_states[chat_id] = STATE_SETUP_INSTALLATION
    keyboard = create_keyboard(['Yes', 'No'])
    await update.message.reply_text('Have you installed the sensor at the desired location?', reply_markup=keyboard)

async def start_protect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global calibrated_voltage
    if calibrated_voltage is None:
        await update.message.reply_text('Please set up the sensor first using /setup_sensor.')
    else:
        sensor_active.set()
        await update.message.reply_text('Protection started.')

async def end_protect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sensor_active.clear()
    await update.message.reply_text('Protection ended.')

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    command = query.data
    
    current_state = chat_states.get(chat_id, STATE_IDLE)

    if current_state == STATE_ALERT:
        if command.lower() == 'safe':
            alert_active.clear()
            sensor_active.clear()
            chat_states[chat_id] = STATE_IDLE
            await query.edit_message_text('Alert cancelled. Sensor protection stopped.')
        else:
            keyboard = create_keyboard(['Safe'])
            await query.edit_message_text('Break-in alert is still active! Tap "Safe" if the situation is under control.', reply_markup=keyboard)
    elif current_state == STATE_SETUP_INSTALLATION:
        if command == 'Yes':
            chat_states[chat_id] = STATE_SETUP_CALIBRATION
            keyboard = create_keyboard(['Ready'])
            await query.edit_message_text('Please close the door/window, then tap "Ready" to start calibration.', reply_markup=keyboard)
        else:
            keyboard = create_keyboard(['Yes'])
            await query.edit_message_text('Please install the sensor at the desired location and tap "Yes" when done.', reply_markup=keyboard)
    elif current_state == STATE_SETUP_CALIBRATION:
        if command == 'Ready':
            await calibrate_sensor(chat_id, query)
        else:
            keyboard = create_keyboard(['Ready'])
            await query.edit_message_text('Please close the door/window, then tap "Ready" to start calibration.', reply_markup=keyboard)
    elif current_state == STATE_CHECK_BLACK_SURFACE:
        if command == 'Yes':
            keyboard = create_keyboard(['Done'])
            await query.edit_message_text('Please place a reflective surface or any non-black material opposite to the sensor. This could be a small piece of white tape, aluminum foil, or any light-colored material. Tap "Done" when finished.', reply_markup=keyboard)
            chat_states[chat_id] = STATE_SETUP_CALIBRATION
        else:
            await query.edit_message_text('The sensor is not detecting a closed door/window. Please check the installation and try the setup again using /setup_sensor.')
            chat_states[chat_id] = STATE_IDLE

async def calibrate_sensor(chat_id, query):
    global calibrated_voltage

    await query.edit_message_text('Starting calibration. Please ensure the door/window is closed.')
    
    for _ in range(5):  # Try 5 times
        voltage = chan.voltage
        if voltage < 1.0:  # Voltage less than 1.0V means closed
            calibrated_voltage = voltage
            await query.edit_message_text(f'Calibration complete. The sensor is working correctly. Calibrated voltage: {calibrated_voltage:.2f}V')
            chat_states[chat_id] = STATE_IDLE
            return
        await asyncio.sleep(1)
    
    keyboard = create_keyboard(['Yes', 'No'])
    await query.edit_message_text('The sensor is not detecting a closed door/window. Is the door/window surface black or very dark?', reply_markup=keyboard)
    chat_states[chat_id] = STATE_CHECK_BLACK_SURFACE

async def monitor_sensor():
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
                await asyncio.to_thread(device_client.send_message, message)
                prev_voltage, prev_state = current_voltage, current_state

            if current_voltage >= 1.0 and not alert_active.is_set():  # Break-in detected if voltage is 1.0V or more
                print(f"Break-in detected! Current voltage: {current_voltage:.2f}V")
                if current_chat_id is not None:
                    alert_active.set()
                    chat_states[current_chat_id] = STATE_ALERT
                    asyncio.create_task(send_alert())
            else:
                print(f"Secure. Current voltage: {current_voltage:.2f}V")
        await asyncio.sleep(0.01)

async def send_alert():
    while alert_active.is_set():
        try:
            keyboard = create_keyboard(['Safe'])
            await bot.send_message(chat_id=current_chat_id, text='Alert! Break in detected! Tap "Safe" if the situation is under control.', reply_markup=keyboard)
        except Exception as e:
            print(f"Error sending alert: {e}")
        await asyncio.sleep(2)  # Wait for 2 seconds before sending the next alert

async def main():
    global device_client, bot

    # Provisioning
    provisioning_device_client = ProvisioningDeviceClient.create_from_symmetric_key(
        provisioning_host=provisioning_host,
        registration_id=device_id,
        id_scope=id_scope,
        symmetric_key=primary_key
    )

    registration_result = await asyncio.to_thread(provisioning_device_client.register)

    if registration_result.status == "assigned":
        print("Device successfully provisioned")
        device_client = IoTHubDeviceClient.create_from_symmetric_key(
            symmetric_key=primary_key,
            hostname=registration_result.registration_state.assigned_hub,
            device_id=device_id
        )
        await asyncio.to_thread(device_client.connect)
    else:
        print(f"Provisioning failed with status: {registration_result.status}")
        raise RuntimeError("Could not provision device. Aborting.")

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("view_dashboard", view_dashboard))
    application.add_handler(CommandHandler("setup_sensor", setup_sensor))
    application.add_handler(CommandHandler("start_protect", start_protect))
    application.add_handler(CommandHandler("end_protect", end_protect))
    application.add_handler(CallbackQueryHandler(button))

    bot = application.bot

    # Start the sensor monitoring task
    asyncio.create_task(monitor_sensor())

    # Start the bot
    await application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if device_client:
            asyncio.run(asyncio.to_thread(device_client.disconnect))