# Pico W Environmental Monitor & Web Server

This project transforms a Raspberry Pi Pico W into a sophisticated environmental monitoring station. It measures CO2, temperature, and humidity using an SCD4x sensor and presents the data through a self-hosted web interface.

The web dashboard provides real-time readings, historical data charts, and system health statistics. It is designed to be reliable for long-term use, with features like a hardware watchdog, power-saving modes, and robust error handling.

<img width="551" height="872" alt="Screenshot 2025-07-11 at 5 14 35 PM" src="https://github.com/user-attachments/assets/879ed906-4209-4bb4-9a88-7ac9889b1fe7" />


## Features

-   **Real-Time Monitoring:** View live CO2, temperature, and humidity readings from any device on your network.
-   **Web Dashboard:** Modern, mobile-friendly web interface that updates data asynchronously without page reloads.
-   **Historical Data Charting:** An interactive chart displays trends for the last 3 hours of sensor data.
-   **C/F Temperature Toggle:** Switch between Celsius and Fahrenheit with the click of a button.
-   **System Health Monitoring:** The dashboard shows Pico W's memory usage, storage, uptime, and more.
-   **Data Logging:** Automatically logs sensor data to a CSV file on the Pico every 15 minutes.
-   **Downloadable Data:** Download the complete history as a CSV or JSON file directly from the webpage.
-   **Robust & Reliable:**
    -   Hardware watchdog automatically reboots the device if the software freezes.
    -   Power-saving mode (`lightsleep`) reduces energy consumption during idle periods.
    -   Automatic WiFi reconnection logic.
-   **Remote Diagnostics:**
    -   A simple `/test.html` page to verify web server functionality.
    -   WebREPL is enabled for remote debugging and code updates.

## Required Hardware

1.  **Raspberry Pi Pico W:** The core of the project.
2.  **Sensirion SCD40 or SCD41 Sensor:** A high-quality CO2, temperature, and humidity sensor. This project is configured for the I2C interface.
3.  **Breadboard and Jumper Wires:** For connecting the sensor to the Pico.
4.  **Micro USB Cable:** For power and programming.

## Wiring Diagram

Connect the SCD4x sensor to the Raspberry Pi Pico W using the default I2C bus (`I2C 1`).

| SCD4x Pin | Pico W Pin                                       | Description           |
| :-------- | :----------------------------------------------- | :-------------------- |
| **VDD**   | **3V3 (OUT)** (Physical Pin 36)                  | Power for the sensor  |
| **GND**   | **GND** (Any Ground Pin, e.g., Physical Pin 38)  | Ground                |
| **SCL**   | **GP27** (Physical Pin 36) - `I2C1 SCL`          | I2C Clock             |
| **SDA**   | **GP26** (Physical Pin 35) - `I2C1 SDA`          | I2C Data              |

*Note: Ensure your `config.py` file reflects these pin numbers (`I2C_SCL_PIN = 27`, `I2C_SDA_PIN = 26`).*

## Setup and Installation

### 1. Install MicroPython on your Pico W

If you haven't already, flash your Pico W with the latest version of MicroPython.
-   Download the "Pico W" UF2 file from the [official MicroPython website](https://micropython.org/download/RPI_PICO_W/).
-   Hold the `BOOTSEL` button on your Pico, plug it into your computer, and drag the UF2 file to the `RPI-RP2` drive that appears.

### 2. Install Thonny IDE

[Thonny](https://thonny.org/) is the recommended IDE for beginners. It has a built-in package manager and makes it easy to interact with the Pico's file system and REPL.

### 3. Copy Project Files

Copy all the following project files to the root directory of your Raspberry Pi Pico W using Thonny's file manager:

-   `main.py`
-   `boot.py`
-   `config.py`
-   `web_server.py`
-   `web_template.py`
-   `sensor_manager.py`
-   `system_monitor.py`
-   `data_logger.py`
-   `memory_handler.py`
-   `scd4x.py`
-   `utils.py`
-   `webrepl_cfg.py`

### 4. Configure Your Settings

Open the `config.py` file in Thonny and edit the following essential settings:

```python
# --- MUST-HAVE CONFIGURATION ---
WIFI_SSID = 'Your_WiFi_Name_Here'
WIFI_PASSWORD = 'Your_WiFi_Password_Here'

# --- RECOMMENDED CONFIGURATION ---
# Set your local time zone offset from UTC (e.g., US Eastern is -5)
TIMEZONE_OFFSET = -5 

# Set a secure password for remote access
WEBREPL_PASSWORD = "a_strong_password" 
```

### 5. Run the Project

You are now ready to start the monitor!

1.  **Disconnect and Reconnect:** Unplug the Pico from your computer and plug it back in. This will trigger the proper `boot.py` -> `main.py` startup sequence.
2.  **Find the IP Address:** Connect to the Pico with Thonny. The IP address will be printed in the REPL console shortly after startup, for example:
    ```
    Server running at http://192.168.1.123:80
    ```
3.  **Open the Dashboard:** Open a web browser on any device on the same WiFi network and navigate to the IP address shown.

## How to Use the Dashboard

-   **Live Data:** The cards at the top show the most recent sensor readings. They update automatically every 10 seconds.
-   **Temperature Toggle:** Click the "Show °F" / "Show °C" button to switch temperature units.
-   **History Chart:** The chart displays data logged every 15 minutes. It will start populating after the first 15 minutes of runtime and will be fully populated after 3 hours.
-   **System Status:** Shows real-time statistics about the Pico W's performance.
-   **Data Download:** Use the links at the bottom of the page to download all historical data in either CSV or JSON format.
-   **Test Page:** If the main dashboard doesn't load, you can navigate to `http://<your-pico-ip>/test.html` to check if the underlying web server is still running.

## Troubleshooting

-   **No Data on Webpage:**
    1.  Press F12 in your browser to open Developer Tools and check the "Console" for JavaScript errors.
    2.  Check the Thonny REPL output for Python errors, especially from the `/api/data` handler.
    3.  Ensure the sensor is wired correctly and that the I2C pins in `config.py` are correct.
-   **Can't Connect to Webpage:**
    1.  Verify the IP address in the Thonny REPL.
    2.  Ensure your computer/phone is on the same WiFi network as the Pico.
    3.  Try to `ping` the Pico's IP address from your computer's terminal.
    4.  Check the `/test.html` page to see if the server is running at all.
-   **"ImportError" on Startup:**
    -   This usually means a file is missing or contains a syntax error. Double-check that all `.py` files have been copied to the Pico and are not corrupted.
