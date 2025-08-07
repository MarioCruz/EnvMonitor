# config.py - Configuration settings for the Environmental Monitor

# --- Generate and Display a Unique Device ID ---
import machine
import binascii

# This creates a unique name like "Pico-E66181029AC37C4C"
unique_id_bytes = machine.unique_id()
unique_id_hex = binascii.hexlify(unique_id_bytes).decode('utf-8').upper()
DEVICE_ID = f"{unique_id_hex}"

# Bluetooth device name (if Bluetooth functionality is needed)
BT_DEVICE_NAME = f"EnvMonitor-{unique_id_hex[-8:]}"  # Use last 8 chars of device ID

# Print the generated ID to the console when the program starts
print(f"[Config] System initialized with unique DEVICE_ID: {DEVICE_ID}")
print(f"[Config] Bluetooth device name: {BT_DEVICE_NAME}")
# -------------------------------------------------------------


# This module contains all configurable parameters for the system.

WIFI_SSID = 'SSID'
WIFI_PASSWORD = 'PWD'

# Network connection settings
WIFI_MAX_ATTEMPTS = 10            # Maximum number of connection attempts
WIFI_CONNECT_TIMEOUT = 30         # Seconds to wait for connection
WIFI_RETRY_DELAY = 5              # Seconds between connection attempts
WIFI_INIT_DELAY = 2               # Seconds after interface activation
NTP_MAX_ATTEMPTS = 7              # Max Time Sync attempts
NETWORK_CHECK_INTERVAL = 60       # Seconds between network status checks
WEAK_SIGNAL_THRESHOLD = -70       # dBm, threshold for weak signal warning
RECONNECT_DELAY_BASE = 5          # Base delay for exponential backoff

# Static IP configuration
USE_STATIC_IP = False             # Set to False to use DHCP
STATIC_IP = "192.168.1.97"        # Static IP address
SUBNET_MASK = "255.255.255.0"     # Subnet mask
GATEWAY = "192.168.1.1"           # Default gateway
DNS_SERVER = "8.8.8.8"            # Primary DNS server
BACKUP_DNS_SERVER = "8.8.4.4"     # Secondary DNS server

# Data Upload Settings
UPLOAD_URL = "https://growingbeyond.earth/log_json.php"
UPLOAD_DEBUG_MODE = True  # Set to True for verbose console output, False for quiet operation
UPLOAD_RESPONSE_TIMEOUT = 10 # Seconds to wait for a server response

# Software version
VERSION = "2.5"                   # Software version number (updated)
SOFTWARE_DATE = "2026-07-25"

# I2C Configuration
I2C_SCL_PIN = 27                  # I2C clock pin
I2C_SDA_PIN = 26                  # I2C data pin
I2C_FREQUENCY = 100000            # 100kHz

# CO2 Sensor Settings
SCD4X_I2C_ADDR = 0x62             # I2C address of SCD4X sensor
SENSOR_ALTITUDE = 0               # Location altitude in meters
SENSOR_PRESSURE = 1013            # Default pressure in hPa
TEMP_OFFSET = 0                   # Temperature calibration offset in °C

# VEML7700 Ambient Light Sensor Settings
VEML7700_I2C_ADDR = 0x10          # I2C address of VEML7700 sensor
VEML7700_CONFIG_DELAY_MS = 100    # Delay after configuration in milliseconds
VEML7700_MAX_ERRORS = 5           # Maximum consecutive errors before reset attempt
VEML7700_RESET_DELAY = 2          # Seconds to wait after sensor reset
VEML7700_RETRY_ATTEMPTS = 3       # Number of read retry attempts

# Light sensor calibration settings
LIGHT_CALIBRATION_ENABLED = True  # Enable light sensor calibration
LIGHT_CALIBRATION_OFFSET = 0.0    # Offset to add to light readings (lux)
LIGHT_CALIBRATION_MULTIPLIER = 1.0 # Multiplier for light readings (for scaling)
LIGHT_CALIBRATION_MIN_LUX = 0.0   # Minimum calibrated light value
LIGHT_CALIBRATION_MAX_LUX = 65535.0 # Maximum calibrated light value

# Environmental alert thresholds (used by JavaScript on the webpage)
CO2_WARNING = 1000                # CO2 PPM warning level
CO2_DANGER = 2000                 # CO2 PPM danger level
TEMP_HIGH = 30                    # Maximum comfortable temperature in °C
TEMP_LOW = 15                     # Minimum comfortable temperature in °C
HUMIDITY_HIGH = 70                # Maximum comfortable humidity %
HUMIDITY_LOW = 30                 # Minimum comfortable humidity %
PRESSURE_HIGH = 1030              # High pressure threshold in hPa
PRESSURE_LOW = 980                # Low pressure threshold in hPa

# Light level thresholds (for status indication)
LIGHT_DARK = 10                   # Below this is considered dark (lux)
LIGHT_DIM = 100                   # Below this is considered dim (lux)
LIGHT_BRIGHT = 1000               # Above this is considered bright (lux)

# Sensor validation ranges (for detecting implausible readings)
VALID_CO2_RANGE = (400, 5000)     # Valid range for CO2 in PPM
VALID_TEMP_RANGE = (-10, 50)      # Valid range for temperature in °C
VALID_HUMIDITY_RANGE = (0, 100)   # Valid range for humidity in %
VALID_PRESSURE_RANGE = (870, 1085)# Valid range for pressure in hPa
VALID_LIGHT_RANGE = (0, 100000)   # Valid range for light in lux (0 to ~100k lux)

# Error handling parameters
MAX_CONSECUTIVE_ERRORS = 3        # Threshold for sensor reset
SENSOR_RETRY_DELAY = 1            # Seconds between sensor retries
SENSOR_RESET_DELAY = 2            # Seconds to wait after sensor reset
SENSOR_INIT_DELAY = 5             # Seconds to wait after initialization
MAX_RECOVERY_ATTEMPTS = 3         # Maximum recovery attempts before giving up

# Memory management thresholds (simplified)
MEMORY_WARNING_THRESHOLD = 75     # % memory usage that triggers warning
MEMORY_CRITICAL_THRESHOLD = 85    # % memory usage for critical actions
GC_COLLECT_INTERVAL = 60          # Seconds between forced garbage collections

# Storage thresholds
STORAGE_WARNING_THRESHOLD = 80    # % storage usage warning level
STORAGE_CRITICAL_THRESHOLD = 90   # % storage usage critical level

# Logging settings
LOG_INTERVAL = 15 * 60            # Seconds between data log entries (15 min) # <-- CHANGED
LOG_DIRECTORY = '/logs'           # Directory for log storage
SENSOR_LOG_FILE = 'sensor_log.txt'# Filename for sensor data log
NETWORK_LOG_FILE = 'network.log'  # Filename for network event log
ERROR_LOG_FILE = 'error.log'      # Filename for error log
MAX_LOG_SIZE = 1024 * 50          # Maximum log file size (50KB) to save space
MAX_LOG_FILES = 3                 # Maximum number of rotated log files

# Number of recent data points to display on the history charts.
# Reduced for better memory usage on Pico W
CHART_HISTORY_POINTS = 50

# Time Settings
NTP_SERVER = 'time.google.com'    # Primary NTP server
TIMEZONE_OFFSET = -5              # Hours from UTC (e.g., -5 for EST, 0 for GMT/UTC)
NTP_SYNC_INTERVAL = 6 * 3600      # Sync time every 6 hours (in seconds)

# Web server settings
WEB_SERVER_PORT = 80              # Port for web server
ALLOWED_ENDPOINTS = [             # Valid web server endpoints
    '/', '/csv', '/json',
    '/logs/network.log', '/api/data', '/api/history', '/test.html', '/sensors'
]

# Security settings
MAX_REQUESTS_PER_MINUTE = 60      # Rate limit per IP address
BLOCKED_IPS_TIMEOUT = 300         # Seconds to block excessive requesters
WEBREPL_ENABLED = True            # Enable/disable WebREPL
WEBREPL_PASSWORD = "webrepl"      # Change this for security

# Power management (disabled for stability)
LOW_POWER_MODE_ENABLED = False     # Keep disabled for web server reliability
SLEEP_WHEN_IDLE = False            # Keep disabled
SLEEP_DURATION = 1000             # Not used when disabled

# Hardware watchdog settings (disabled for development)
WATCHDOG_ENABLED = False           # Keep disabled during development
WATCHDOG_TIMEOUT = 8000           # Not used when disabled