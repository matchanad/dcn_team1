import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522

def read_rfid():
    reader = SimpleMFRC522()
    try:
        print("Hold a tag near the reader")
        id, text = reader.read()
        print(f"ID: {id}")
        print(f"Text: {text}")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    read_rfid()
