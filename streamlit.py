# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

import busio
import digitalio
import board
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn
from time import sleep, time
import streamlit as st
import pandas as pd

# Create the SPI bus
spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)

# Create the CS (chip select)
cs = digitalio.DigitalInOut(board.D5)

# Create the MCP object
mcp = MCP.MCP3008(spi, cs)

# Create an analog input channel on pin 0
chan = AnalogIn(mcp, MCP.P0)

# Initialize lists to store time and voltage data
time_data = []
voltage_data = []

# Start time
start_time = time()

# Set up the Streamlit app
st.title('Real-time Voltage from MCP3008')
chart = st.line_chart(pd.DataFrame({'Time': [], 'Voltage': []}))

# Function to read data and update plot
def read_data():
    # Get the current voltage
    voltage = chan.voltage

    # Calculate elapsed time
    current_time = time() - start_time

    # Append the time and voltage data to the lists
    time_data.append(current_time)
    voltage_data.append(voltage)

    # Keep the last 100 data points
    if len(time_data) > 100:
        time_data.pop(0)
        voltage_data.pop(0)

    # Create a DataFrame with the time and voltage data
    data = pd.DataFrame({'Time': time_data, 'Voltage': voltage_data})
    return data

# Read data and update plot in a loop
try:
    while True:
        # Read data
        data = read_data()
        
        # Update the Streamlit line chart
        chart.add_rows(data)
        
        # Sleep for 1 second
        sleep(1)
except KeyboardInterrupt:
    # Exit the loop when Ctrl+C is pressed
    print("Exiting...")

