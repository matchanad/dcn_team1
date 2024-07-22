# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

import busio
import digitalio
import board
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn
from time import sleep, time
import json
from azure.iot.device import IoTHubDeviceClient, Message, ProvisioningDeviceClient

# Azure IoT Hub Device Provisioning Service (DPS) parameters
ID_SCOPE = "0ne00CDBD95"
DEVICE_ID = "tcrt5000"
PRIMARY_KEY = "tmzgh6TO1zrU7ixSpAlGvk7LI2Bbbrbk4QeFzcECRyw="

# Function to provision the device and get the connection string
def provision_device(id_scope, device_id, primary_key):
    provisioning_host = f"{id_scope}.global.azure-devices-provisioning.net"
    provisioning_device_client = ProvisioningDeviceClient.create_from_symmetric_key(
        provisioning_host=provisioning_host,
        registration_id=device_id,
        id_scope=id_scope,
        symmetric_key=primary_key
    )
    registration_result = provisioning_device_client.register()
    if registration_result.status == "assigned":
        connection_string = f"HostName={registration_result.registration_state.assigned_hub};DeviceId={device_id};SharedAccessKey={primary_key}"
        return connection_string
    else:
        raise Exception("Failed to provision device")

# Get the connection string from the provisioning service
CONNECTION_STRING = provision_device(ID_SCOPE, DEVICE_ID, PRIMARY_KEY)

# Create the SPI bus
spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)

# Create the CS (chip select)
cs = digitalio.DigitalInOut(board.D5)

# Create the MCP object
mcp = MCP.MCP3008(spi, cs)

# Create an analog input channel on pin 0
chan = AnalogIn(mcp, MCP.P0)

# Initialize the digital input pin (e.g., D6)
digital_pin = digitalio.DigitalInOut(board.D6)
digital_pin.direction = digitalio.Direction.INPUT

# Initialize the IoT Hub device client
client = IoTHubDeviceClient.create_from_connection_string(CONNECTION_STRING)

def send_telemetry(voltage, state):
    telemetry_data = {
        "Voltage": Voltage,
        "State": State
    }
    message = Message(json.dumps(telemetry_data))
    client.send_message(message)
    print(f"Telemetry sent: {telemetry_data}")

# Start time
start_time = time()

# Main loop to read data and send telemetry
try:
    while True:
        # Get the current voltage
        Voltage = chan.voltage

        # Get the current state of the digital pin
        State = 0 if digital_pin.value else 1

        # Send telemetry data to Azure IoT Hub
        send_telemetry(Voltage, State)

        # Sleep for 1 second
        sleep(1)
except KeyboardInterrupt:
    # Exit the loop when Ctrl+C is pressed
    print("Exiting...")
finally:
    client.shutdown()
