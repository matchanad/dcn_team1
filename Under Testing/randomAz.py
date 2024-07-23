import time
import random
from azure.iot.device import IoTHubDeviceClient, Message, ProvisioningDeviceClient, exceptions

# Replace these values with your Azure IoT Central information
id_scope = "0ne00CDBD95"
device_id = "tcrt5000"
primary_key = "tmzgh6TO1zrU7ixSpAlGvk7LI2Bbbrbk4QeFzcECRyw="

provisioning_host = "global.azure-devices-provisioning.net"
template = "{\"Voltage\": %.2f, \"State\": \"%s\"}"

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

    # Function to simulate reading voltage and state
    def read_sensor_data():
        Voltage = random.uniform(0, 3.3)
        State = "Open" if Voltage > 1 else "Closed"  # '0' for Open and '1' for Closed
        return Voltage, State

    try:
        while True:
            Voltage, State = read_sensor_data()
            msg_txt = template % (Voltage, State)
            message = Message(msg_txt)
            print(f"Sending message: {message}")
            device_client.send_message(message)
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
