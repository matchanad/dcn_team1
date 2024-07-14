import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522
import time

# Initialize the RFID reader
reader = SimpleMFRC522()

# Set up the GPIO pin for the LED
LED_PIN = 18
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)

try:
    while True:
        print("Place your RFID card/tag near the reader")
        
        # Read the RFID card/tag
        id, text = reader.read()
        print(f"ID: {id}")
        print(f"Text: {text}")
        
        # Action: Toggle LED
        GPIO.output(LED_PIN, not GPIO.input(LED_PIN))
        
        print("LED state toggled")
        print("-----")
        
        # Wait for a while to avoid multiple readings
        time.sleep(2)
finally:
    GPIO.cleanup()
