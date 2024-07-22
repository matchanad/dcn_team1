# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

from time import sleep, time
import streamlit as st
import pandas as pd
import altair as alt

# Import or mock hardware components
try:
    import busio
    import digitalio
    import board
    import adafruit_mcp3xxx.mcp3008 as MCP
    from adafruit_mcp3xxx.analog_in import AnalogIn
    hardware_available = True
except ImportError:
    hardware_available = False

class MockSPI:
    def __init__(self, *args, **kwargs):
        pass

class MockDigitalInOut:
    def __init__(self, *args, **kwargs):
        self.direction = None
        self.value = 0

class MockAnalogIn:
    def __init__(self, *args, **kwargs):
        self.voltage = 0.0

if hardware_available:
    # Create the SPI bus
    spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)

    # Create the CS (chip select)
    cs = digitalio.DigitalInOut(board.D5)

    # Create the MCP object
    mcp = MCP.MCP3008(spi, cs)

    # Create an analog input channel on pin 0
    chan = AnalogIn(mcp, MCP.P0)

    # Initialize the digital input pin (e.g., D6)
    digital_pin = digitalio.DigitalInOut(board.D6)
    digital_pin.direction = digitalio.Direction.INPUT
else:
    # Mock the hardware components
    spi = MockSPI()
    cs = MockDigitalInOut()
    mcp = None
    chan = MockAnalogIn()
    digital_pin = MockDigitalInOut()

# Initialize lists to store time and voltage data
time_data = []
voltage_data = []

# Start time
start_time = time()

# Set up the Streamlit app
st.title('Real-time Voltage from MCP3008')
chart_placeholder = st.empty()
status_placeholder = st.empty()

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
    return data, voltage

# Read data and update plot in a loop
try:
    while True:
        # Read data
        data, current_voltage = read_data()
        
        # Create an Altair chart
        chart = alt.Chart(data).mark_line().encode(
            x=alt.X('Time:Q', title='Time (s)'),
            y=alt.Y('Voltage:Q', title='Voltage (V)')
        ).properties(
            width=700,
            height=400
        )
        
        # Update the Streamlit chart
        chart_placeholder.altair_chart(chart)
        
        # Determine door/window status and color
        if current_voltage > 1:
            status = "Open"
            status_color = "#FF0000"  # Red
        else:
            status = "Closed"
            status_color = "#00FF00"  # Green
        
        # Create a DataFrame to display the status in a table
        status_html = f"""
        <div style="display: flex; align-items: center;">
            <div style="width: 20px; height: 20px; background-color: {status_color}; border-radius: 50%; margin-right: 10px;"></div>
            <div>
                <h3 style="margin: 0;">{status}</h3>
                <p style="margin: 0;">Current Voltage: {current_voltage:.2f} V</p>
            </div>
        </div>
        """
        
        status_placeholder.markdown(status_html, unsafe_allow_html=True)
        
        # Sleep for 1 second
        sleep(1)
except KeyboardInterrupt:
    # Exit the loop when Ctrl+C is pressed
    print("Exiting...")
