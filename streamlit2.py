# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

from time import sleep, time
import streamlit as st
import pandas as pd
import altair as alt
import spidev
import RPi.GPIO as GPIO

# Set up SPI bus
spi = spidev.SpiDev()
spi.open(0, 0)  # Open SPI bus 0, device (CS) 0
spi.max_speed_hz = 1350000  # Set max speed

# Set up GPIO for digital input
GPIO.setmode(GPIO.BCM)
digital_pin = 6
GPIO.setup(digital_pin, GPIO.IN)

def read_adc(channel):
    """Read ADC from the specified channel (0-7)"""
    if channel < 0 or channel > 7:
        return -1
    r = spi.xfer2([1, (8 + channel) << 4, 0])
    adc_out = ((r[1] & 3) << 8) + r[2]
    return adc_out

def convert_to_voltage(adc_value):
    """Convert the raw ADC value to a voltage (0-3.3V)"""
    return adc_value * (3.3 / 1023.0)

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
    adc_value = read_adc(0)
    voltage = convert_to_voltage(adc_value)

    # Get the current state of the digital pin
    digital_value = GPIO.input(digital_pin)

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
    return data, voltage, digital_value

# Read data and update plot in a loop
try:
    while True:
        # Read data
        data, current_voltage, digital_value = read_data()
        
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
        if digital_value == 1:
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
finally:
    # Clean up GPIO
    GPIO.cleanup()
    spi.close()
