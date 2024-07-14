import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522
import time

# Initialize the RFID reader
reader = SimpleMFRC522()

try:
    while True:
        print("Place your RFID card/tag near the reader")
        
        # Read the RFID card/tag
        id, text = reader.read()
        print(f"ID: {id}")
        print(f"Text: {text}")
        
        print("RFID tag detected and details printed")
        print("-----")
        
        # Wait for a while to avoid multiple readings
        time.sleep(2)
finally:
    GPIO.cleanup()
