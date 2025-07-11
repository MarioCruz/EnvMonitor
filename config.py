# config.py - Configuration settings for the Environmental Monitor
# This module contains all configurable parameters for the system.

# WiFi Settings
WIFI_SSID = 'YourSSID
WIFI_PASSWORD = 'YourPassword'

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

# Software version
VERSION = "2.2"                   # Software version number (updated)

# I2C Configuration
I2C_SCL_PIN = 27                  # I2C clock pin
I2C_SDA_PIN = 26                  # I2C data pin
I2C_FREQUENCY = 100000            # 100kHz

# CO2 Sensor Settings
SCD4X_I2C_ADDR = 0x62             # I2C address of SCD4X sensor
SENSOR_ALTITUDE = 0               # Location altitude in meters
SENSOR_PRESSURE = 1013            # Default pressure in hPa
TEMP_OFFSET = 0                   # Temperature calibration offset in °C

# Environmental alert thresholds (used by JavaScript on the webpage)
CO2_WARNING = 1000                # CO2 PPM warning level
CO2_DANGER = 2000                 # CO2 PPM danger level
TEMP_HIGH = 30                    # Maximum comfortable temperature in °C
TEMP_LOW = 15                     # Minimum comfortable temperature in °C
HUMIDITY_HIGH = 70                # Maximum comfortable humidity %
HUMIDITY_LOW = 30                 # Minimum comfortable humidity %
PRESSURE_HIGH = 1030              # High pressure threshold in hPa
PRESSURE_LOW = 980                # Low pressure threshold in hPa

# Sensor validation ranges (for detecting implausible readings)
VALID_CO2_RANGE = (400, 5000)     # Valid range for CO2 in PPM
VALID_TEMP_RANGE = (-10, 50)      # Valid range for temperature in °C
VALID_HUMIDITY_RANGE = (0, 100)   # Valid range for humidity in %
VALID_PRESSURE_RANGE = (870, 1085)# Valid range for pressure in hPa

# Error handling parameters
MAX_CONSECUTIVE_ERRORS = 3        # Threshold for sensor reset
SENSOR_RETRY_DELAY = 1            # Seconds between sensor retries
SENSOR_RESET_DELAY = 2            # Seconds to wait after sensor reset
SENSOR_INIT_DELAY = 5             # Seconds to wait after initialization
MAX_RECOVERY_ATTEMPTS = 3         # Maximum recovery attempts before giving up

# Memory management thresholds
MEMORY_WARNING_THRESHOLD = 80     # % memory usage that triggers warning
MEMORY_CRITICAL_THRESHOLD = 90    # % memory usage for critical actions
GC_COLLECT_INTERVAL = 300         # Seconds between forced garbage collections

# Storage thresholds
STORAGE_WARNING_THRESHOLD = 80    # % storage usage warning level
STORAGE_CRITICAL_THRESHOLD = 90   # % storage usage critical level

# Logging settings
LOG_INTERVAL = 15 * 60            # Seconds between data log entries (15 min)
LOG_DIRECTORY = '/logs'           # Directory for log storage
SENSOR_LOG_FILE = 'sensor_log.txt'# Filename for sensor data log
NETWORK_LOG_FILE = 'network.log'  # Filename for network event log
ERROR_LOG_FILE = 'error.log'      # Filename for error log
MAX_LOG_SIZE = 1024 * 50          # Maximum log file size (50KB) to save space
MAX_LOG_FILES = 3                 # Maximum number of rotated log files

# Time Settings
NTP_SERVER = 'time.google.com'    # Primary NTP server
TIMEZONE_OFFSET = -5              # Hours from UTC (e.g., -5 for EST, 0 for GMT/UTC)

# Web server settings
WEB_SERVER_PORT = 80              # Port for web server
ALLOWED_ENDPOINTS = [             # Valid web server endpoints
    '/', '/csv', '/json', 
    '/logs/network.log', '/api/data', '/api/history', '/test.html'
]

# Security settings
MAX_REQUESTS_PER_MINUTE = 60      # Rate limit per IP address
BLOCKED_IPS_TIMEOUT = 300         # Seconds to block excessive requesters
WEBREPL_ENABLED = True            # Enable/disable WebREPL
WEBREPL_PASSWORD = "MakeThisHard"      # Change this for security

# Power management
LOW_POWER_MODE_ENABLED = False     # Enable/disable low power mode
SLEEP_WHEN_IDLE = False            # Sleep when not actively serving requests
SLEEP_DURATION = 1000             # Sleep time in milliseconds (1000ms = 1s)

# Hardware watchdog settings
WATCHDOG_ENABLED = False           # Enable hardware watchdog for reliability
WATCHDOG_TIMEOUT = 8000           # Watchdog timeout in milliseconds (8 seconds)