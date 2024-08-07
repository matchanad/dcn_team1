import time
from azure.iot.device import IoTHubDeviceClient, Message, ProvisioningDeviceClient, exceptions
import busio
import digitalio
import board
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn

# Replace these values with your Azure IoT Central information
id_scope = "0ne00CDBD95"
device_id = "27yzuc90d6v"
primary_key = "cBkkyw8/SDdwPygExhk8npwAPyHsqO0H7832Xx+XSR0="

provisioning_host = "global.azure-devices-provisioning.net"
template = "{\"Voltage\": %.2f, \"State\": \"%d\"}"

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

    # Create the SPI bus
    spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)

    # Create the CS (chip select)
    cs = digitalio.DigitalInOut(board.D5)

    # Create the MCP object
    mcp = MCP.MCP3008(spi, cs)

    # Create an analog input channel on pin 0
    chan = AnalogIn(mcp, MCP.P0)

    # Function to read sensor data
    def read_sensor_data():
        Voltage = chan.voltage
        State = 0 if Voltage < 1.0 else 1  # Adjust the threshold as needed
        return Voltage, State

    # Initialize previous values
    prev_Voltage, prev_State = read_sensor_data()

    try:
        while True:
            Voltage, State = read_sensor_data()
            if Voltage != prev_Voltage or State != prev_State:
                msg_txt = template % (Voltage, State)
                message = Message(msg_txt)
                print(f"Sending message: {message}")
                device_client.send_message(message)
                prev_Voltage, prev_State = Voltage, State
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        device_client.disconnect()

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
