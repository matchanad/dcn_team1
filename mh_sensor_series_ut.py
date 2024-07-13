import RPi.GPIO as GPIO
import time

# Set the GPIO mode to BCM
GPIO.setmode(GPIO.BCM)

# Define the GPIO pin connected to the sensor
SENSOR_PIN = 17

# Setup the GPIO pin as an input
GPIO.setup(SENSOR_PIN, GPIO.IN)

def detect_break_in():
    print("Monitoring for break-ins. Press CTRL+C to exit.")
    try:
        while True:
            if GPIO.input(SENSOR_PIN):
                print("Break-in detected!")
                # Add your alarm or notification code here
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Monitoring stopped.")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    detect_break_in()