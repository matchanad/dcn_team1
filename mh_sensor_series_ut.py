import RPi.GPIO as GPIO
import time

# Set the GPIO mode
GPIO.setmode(GPIO.BCM)

# Define the GPIO pins for the sensor
TRIG = 23
ECHO = 24

# Set up the GPIO pins
GPIO.setup(TRIG, GPIO.OUT)
GPIO.setup(ECHO, GPIO.IN)

def measure_distance():
    # Ensure the trigger pin is low
    GPIO.output(TRIG, False)
    time.sleep(2)
    
    # Send a 10us pulse to trigger the sensor
    GPIO.output(TRIG, True)
    time.sleep(0.00001)
    GPIO.output(TRIG, False)
    
    # Wait for the echo start
    while GPIO.input(ECHO) == 0:
        pulse_start = time.time()
    
    # Wait for the echo end
    while GPIO.input(ECHO) == 1:
        pulse_end = time.time()
    
    # Calculate the duration of the pulse
    pulse_duration = pulse_end - pulse_start
    
    # Distance is pulse duration multiplied by the speed of sound (34300 cm/s)
    # and divided by 2 (round trip)
    distance = pulse_duration * 34300 / 2
    
    return distance

def detect_break_in(threshold_distance):
    distance = measure_distance()
    if distance < threshold_distance:
        print(f"Break-in detected! Distance: {distance:.2f} cm")
        # Add your alert/notification code here

def get_threshold_distance():
    while True:
        try:
            threshold = float(input("Enter the threshold distance (in cm) for break-in detection: "))
            if threshold > 0:
                return threshold
            else:
                print("Please enter a positive number.")
        except ValueError:
            print("Invalid input. Please enter a valid number.")

try:
    # Get the threshold distance from user input
    threshold_distance = get_threshold_distance()
    print(f"Using threshold distance: {threshold_distance} cm")

    while True:
        detect_break_in(threshold_distance)
        time.sleep(1)

except KeyboardInterrupt:
    # Clean up the GPIO pins before exiting
    GPIO.cleanup()
