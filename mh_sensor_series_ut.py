import RPi.GPIO as GPIO
import time

# Set GPIO pins
GPIO.setmode(GPIO.BCM)
charge_pin = 23  # GPIO pin used to charge the capacitor
measure_pin = 24  # GPIO pin used to measure the discharge time

# Set up the GPIO pins
GPIO.setup(charge_pin, GPIO.OUT)
GPIO.setup(measure_pin, GPIO.IN)

def discharge():
    GPIO.setup(measure_pin, GPIO.OUT)
    GPIO.output(measure_pin, False)
    time.sleep(0.01)

def charge_time():
    GPIO.setup(measure_pin, GPIO.IN)
    count = 0
    while not GPIO.input(measure_pin) and count < 10000:
        count += 1
    return count

def analog_read():
    GPIO.output(charge_pin, True)
    time.sleep(0.01)
    GPIO.output(charge_pin, False)
    return charge_time()

try:
    while True:
        analog_value = analog_read()
        print(f"Analog Value: {analog_value}")
        time.sleep(1)

except KeyboardInterrupt:
    print("Measurement stopped by User")
    GPIO.cleanup()
