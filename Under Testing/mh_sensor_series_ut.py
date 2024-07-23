import spidev
import time

# Create SPI object
spi = spidev.SpiDev()
# Open SPI bus 0, device (CS) 0
spi.open(0, 0)

# Function to read SPI data from MCP3008
def read_channel(channel):
    adc = spi.xfer2([1, (8 + channel) << 4, 0])
    data = ((adc[1] & 3) << 8) + adc[2]
    return data

# Function to convert data to voltage level
def convert_volts(data, places):
    volts = (data * 3.3) / float(1023)
    volts = round(volts, places)
    return volts

# Main program loop
try:
    while True:
        # Read the analog input from channel 0
        analog_input = read_channel(0)
        voltage = convert_volts(analog_input, 2)
        
        print(f"Analog Input: {analog_input}, Voltage: {voltage}V")
        
        # Delay for a second
        time.sleep(1)

except KeyboardInterrupt:
    spi.close()
    print("Program terminated.")
