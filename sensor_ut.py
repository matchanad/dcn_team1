from gpiozero import DistanceSensor
from time import sleep

# Define GPIO pins and Maximum Distance for Break-in
TRIG = 23  # GPIO pin connected to the TRIG pin of HC-SR04
ECHO = 24  # GPIO pin connected to the ECHO pin of HC-SR04
MAX_DISTANCE = 4  # Maximum distance the sensor can measure in meters

def main():
    try:
        # Ask user for the maximum distance threshold
        max_distance = float(input("Enter the maximum distance threshold (in cm): "))

        # Initialize the DistanceSensor
        sensor = DistanceSensor(echo=ECHO, trigger=TRIG, max_distance=MAX_DISTANCE)

        while True:
            try:
                # Get the distance measurement in meters and convert to centimeters
                distance_cm = sensor.distance * 100
                print(f"Measured Distance: {distance_cm:.2f} cm")

                if distance_cm < max_distance:
                    print("Break in!")

            except RuntimeError:
                print("Sensor error: Unable to read distance")

            sleep(1)

    except KeyboardInterrupt:
        print("Measurement stopped by user")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
