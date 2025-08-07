# utils.py - Utility functions and classes
import time
import gc
import os
import network
import math
import random
import machine
import config

# Initialize hardware watchdog if enabled
if config.WATCHDOG_ENABLED:
    try:
        watchdog = machine.WDT(timeout=config.WATCHDOG_TIMEOUT)
    except Exception:
        watchdog = None
else:
    watchdog = None

def feed_watchdog():
    """Feed the watchdog timer if enabled"""
    if watchdog:
        try:
            watchdog.feed()
        except Exception:
            pass

def sync_time_periodic(logger=None):
    """Synchronize time with NTP server - for periodic use"""
    try:
        import ntptime
        wlan = network.WLAN(network.STA_IF)
        
        if not wlan.isconnected():
            if logger:
                logger.log("TIME", "Cannot sync time - no WiFi connection", "WARNING")
            return False
            
        ntptime.host = config.NTP_SERVER
        ntptime.settime()
        
        # Adjust for timezone if configured
        if hasattr(config, 'TIMEZONE_OFFSET'):
            timezone_offset = config.TIMEZONE_OFFSET * 3600
            current_time = time.time() + timezone_offset
            tm = time.localtime(current_time)
            machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0))
        
        if logger:
            logger.log("TIME", f"Time synchronized: {format_datetime(time.localtime())}", "INFO")
        return True
        
    except Exception as e:
        if logger:
            logger.log("TIME", f"Time sync failed: {e}", "WARNING")
        return False

def html_escape(text):
    """Escape HTML characters to prevent XSS"""
    if text is None:
        return ""
    text = str(text)
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#x27;"))

def format_datetime(t):
    """Format datetime in a readable format (YYYY-MM-DD HH:MM:SS)"""
    try:
        formatted = f"{t[0]}-{t[1]:02d}-{t[2]:02d} {t[3]:02d}:{t[4]:02d}:{t[5]:02d}"
        return html_escape(formatted)
    except Exception:
        return html_escape("Time Error")

def format_time(t):
    """Format time only (HH:MM:SS)"""
    try:
        formatted = f"{t[3]:02d}:{t[4]:02d}:{t[5]:02d}"
        return html_escape(formatted)
    except Exception:
        return html_escape("00:00:00")

def format_date(t):
    """Format date only (YYYY-MM-DD)"""
    try:
        return f"{t[0]}-{t[1]:02d}-{t[2]:02d}"
    except Exception:
        return "0000-00-00"

def format_uptime(seconds):
    """Convert seconds to a readable format (days, hours, minutes)"""
    days = seconds // (24 * 3600)
    seconds %= (24 * 3600)
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60

    if days > 0:
        return f"{int(days)}d {int(hours)}h {int(minutes)}m"
    elif hours > 0:
        return f"{int(hours)}h {int(minutes)}m"
    else:
        return f"{int(minutes)}m {int(seconds)}s"

def get_wifi_status_explanation(status):
    """Return a human-readable explanation of a WiFi status code."""
    status_messages = {
        network.STAT_IDLE: "IDLE/No connection attempt yet",
        network.STAT_CONNECTING: "Connecting",
        network.STAT_WRONG_PASSWORD: "Wrong password",
        network.STAT_GOT_IP: "Connected",
        network.STAT_CONNECT_FAIL: "Connection failed",
        network.STAT_NO_AP_FOUND: "No AP found",
        -3: "Connection error"
    }
    return status_messages.get(status, f"Unknown status code: {status}")

def validate_sensor_reading(value, sensor_type):
    """Validate a sensor reading based on config ranges."""
    try:
        value = float(value)
        if sensor_type == 'temperature':
            return config.VALID_TEMP_RANGE[0] <= value <= config.VALID_TEMP_RANGE[1]
        elif sensor_type == 'co2':
            return config.VALID_CO2_RANGE[0] <= value <= config.VALID_CO2_RANGE[1]
        elif sensor_type == 'humidity':
            return config.VALID_HUMIDITY_RANGE[0] <= value <= config.VALID_HUMIDITY_RANGE[1]
        elif sensor_type == 'pressure':
            return config.VALID_PRESSURE_RANGE[0] <= value <= config.VALID_PRESSURE_RANGE[1]
        elif sensor_type == 'light':
            return config.VALID_LIGHT_RANGE[0] <= value <= config.VALID_LIGHT_RANGE[1]
        return False
    except Exception:
        return False

def format_sensor_value(value, decimals=1):
    """Format a sensor value with a fixed number of decimal places."""
    try:
        return f"{float(value):.{decimals}f}"
    except Exception:
        return "Error"

def calculate_statistics(values):
    """Calculate min, max, average, and count for a list of numerical values."""
    try:
        values = [float(v) for v in values if v is not None]
        if not values:
            return None
        return {
            'min': min(values),
            'max': max(values),
            'avg': sum(values) / len(values),
            'count': len(values)
        }
    except Exception:
        return None

def ensure_directory(directory):
    """Ensure that a directory exists (create it if necessary)."""
    try:
        try:
            os.stat(directory)
        except OSError:
            os.mkdir(directory)
        return True
    except Exception as e:
        print(f"Error creating directory {directory}: {e}")
        return False

class ExponentialBackoff:
    """Implements exponential backoff for retry strategies."""
    def __init__(self, base_delay, max_delay=60, jitter=0.1):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.attempt = 0

    def get_delay(self):
        delay = min(self.base_delay * (2 ** self.attempt), self.max_delay)
        if self.jitter > 0:
            jitter_amount = delay * self.jitter
            delay = delay + (jitter_amount * (2 * random.random() - 1))
        self.attempt += 1
        return delay

    def reset(self):
        self.attempt = 0

class CircularBuffer:
    """Fixed-size circular buffer that overwrites the oldest items when full."""
    def __init__(self, maxlen):
        self.data = [None] * maxlen
        self.maxlen = maxlen
        self.size = 0
        self.index = 0

    def append(self, item):
        self.data[self.index] = item
        self.index = (self.index + 1) % self.maxlen
        if self.size < self.maxlen:
            self.size += 1

    def get_all(self):
        if self.size == 0:
            return []
        if self.size < self.maxlen:
            return self.data[:self.size]
        else:
            return self.data[self.index:] + self.data[:self.index]

    def __iter__(self):
        if self.size < self.maxlen:
            for i in range(self.size):
                yield self.data[i]
        else:
            for i in range(self.index, self.maxlen):
                yield self.data[i]
            for i in range(self.index):
                yield self.data[i]

    def __len__(self):
        return self.size

class Logger:
    """Base logger class with file rotation."""
    def __init__(self, log_dir=config.LOG_DIRECTORY, max_size=config.MAX_LOG_SIZE):
        self.log_dir = log_dir
        self.max_size = max_size
        self._ensure_log_directory()

    def _ensure_log_directory(self):
        ensure_directory(self.log_dir)

    def _check_rotation(self, filename):
        try:
            size = os.stat(filename)[6]
            return size >= self.max_size
        except Exception:
            return False

    def _rotate_log(self, log_path, max_backups=config.MAX_LOG_FILES):
        try:
            t = time.localtime()
            timestamp = f"{t[0]}{t[1]:02d}{t[2]:02d}-{t[3]:02d}{t[4]:02d}"
            base_name = log_path.split('/')[-1]
            backup_name = f"{base_name}.{timestamp}"
            backup_path = f"{self.log_dir}/{backup_name}"
            os.rename(log_path, backup_path)
            self._cleanup_old_logs(base_name, max_backups)
            return True
        except Exception as e:
            print(f"Log rotation error: {e}")
            return False

    def _cleanup_old_logs(self, base_name, max_backups):
        try:
            backup_files = []
            for filename in os.listdir(self.log_dir):
                if filename.startswith(base_name + '.'):
                    backup_files.append(filename)
            backup_files.sort()
            while len(backup_files) > max_backups:
                oldest = backup_files.pop(0)
                try:
                    os.remove(f"{self.log_dir}/{oldest}")
                except Exception:
                    pass
        except Exception as e:
            print(f"Cleanup error: {e}")

class NetworkLogger(Logger):
    """Logger for network events."""
    def __init__(self, log_path=f"{config.LOG_DIRECTORY}/{config.NETWORK_LOG_FILE}"):
        super().__init__()
        self.log_path = log_path
        self._ensure_log_file()

    def _ensure_log_file(self):
        try:
            try:
                os.stat(self.log_path)
            except OSError:
                with open(self.log_path, 'w') as f:
                    f.write(f"Network Log Started: {format_datetime(time.localtime())}\n")
        except Exception as e:
            print(f"Error creating network log: {e}")

    def log(self, event_type, message, severity="INFO", error=None):
        try:
            if self._check_rotation(self.log_path):
                self._rotate_log(self.log_path)
                self._ensure_log_file()
            timestamp = format_datetime(time.localtime())
            log_entry = f"{timestamp} [{severity}] [{event_type}] {message}"
            if error:
                log_entry += f" | Error: {error}"
            with open(self.log_path, 'a') as f:
                f.write(log_entry + '\n')
            if severity in ["ERROR", "CRITICAL"]:
                print(log_entry)
        except Exception as e:
            print(f"Logging error: {e}")

class ErrorLogger(Logger):
    """Logger for system errors."""
    def __init__(self, log_path=f"{config.LOG_DIRECTORY}/{config.ERROR_LOG_FILE}"):
        super().__init__()
        self.log_path = log_path
        self._ensure_log_file()

    def _ensure_log_file(self):
        try:
            try:
                os.stat(self.log_path)
            except OSError:
                with open(self.log_path, 'w') as f:
                    f.write(f"Error Log Started: {format_datetime(time.localtime())}\n")
        except Exception as e:
            print(f"Error creating error log: {e}")

    def log(self, component, message, critical=False):
        try:
            if self._check_rotation(self.log_path):
                self._rotate_log(self.log_path)
                self._ensure_log_file()
            timestamp = format_datetime(time.localtime())
            severity = "CRITICAL" if critical else "ERROR"
            log_entry = f"{timestamp} [{severity}] [{component}] {message}"
            with open(self.log_path, 'a') as f:
                f.write(log_entry + '\n')
            print(log_entry)
        except Exception as e:
            print(f"Error logging error: {e}")

# Removed redundant NetworkManager class - functionality integrated into WebServer

# Removed redundant MemoryMonitor class - functionality moved to MemoryHandler

# Removed redundant StorageMonitor class - functionality integrated into SystemMonitor

class SecurityManager:
    """Manages request rate limiting and security."""
    def __init__(self, logger):
        self.logger = logger
        self.request_counts = {}
        self.blocked_ips = {}
        self.last_cleanup = time.time()
        self.cleanup_interval = 60  # 1 minute
        self.max_requests = config.MAX_REQUESTS_PER_MINUTE
        self.block_duration = config.BLOCKED_IPS_TIMEOUT

    def validate_request(self, client_ip):
        current_time = time.time()
        if current_time - self.last_cleanup > self.cleanup_interval:
            self._cleanup()
            self.last_cleanup = current_time
        if client_ip in self.blocked_ips:
            block_time = self.blocked_ips[client_ip]
            if current_time < block_time:
                return False
            else:
                del self.blocked_ips[client_ip]
        return self._check_rate(client_ip, current_time)

    def _check_rate(self, client_ip, current_time):
        if client_ip not in self.request_counts:
            self.request_counts[client_ip] = {'count': 1, 'window_start': current_time}
            return True
        data = self.request_counts[client_ip]
        window_duration = current_time - data['window_start']
        if window_duration > 60:
            data['count'] = 1
            data['window_start'] = current_time
            return True
        data['count'] += 1
        if data['count'] > self.max_requests:
            self.blocked_ips[client_ip] = current_time + self.block_duration
            self.logger.log("SECURITY", f"IP {client_ip} blocked for excessive requests", "WARNING")
            return False
        return True

    def _cleanup(self):
        current_time = time.time()
        self.request_counts = {ip: data for ip, data in self.request_counts.items()
                               if current_time - data['window_start'] < 120}
        self.blocked_ips = {ip: expire_time for ip, expire_time in self.blocked_ips.items()
                            if current_time < expire_time}

class RetryWithBackoff:
    """Decorator for functions that need retry with exponential backoff."""
    def __init__(self, max_retries=3, base_delay=1, max_delay=10, jitter=0.1):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            backoff = ExponentialBackoff(self.base_delay, self.max_delay, self.jitter)
            last_exception = None
            for attempt in range(self.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < self.max_retries:
                        delay = backoff.get_delay()
                        time.sleep(delay)
            raise last_exception
        return wrapper

class ExceptionHandler:
    """
    ExceptionHandler logs errors with context and tracks error frequency.

    Attributes:
        logger: A logger instance to record exception messages.
        critical_threshold (int): Number of errors after which a critical message is logged.
        error_count (int): Tracks the number of exceptions handled.
    """
    def __init__(self, logger, critical_threshold=5):
        self.logger = logger
        self.critical_threshold = critical_threshold
        self.error_count = 0

    def handle(self, context, error_message):
        """
        Logs an exception with the specified context and error message.

        Args:
            context (str): Description of where the exception occurred.
            error_message (str): The exception message.
        """
        try:
            self.error_count += 1
            message = f"{context}: {error_message}"
            self.logger.log("EXCEPTION", message)
            print(f"[ExceptionHandler] {message}")
            if self.error_count >= self.critical_threshold:
                critical_msg = ("Critical error threshold reached. "
                                "Consider initiating a system reset or switching to a safe mode.")
                self.logger.log("EXCEPTION", critical_msg, "CRITICAL")
                print(f"[ExceptionHandler] {critical_msg}")
        except Exception as e:
            print(f"[ExceptionHandler] Error while handling exception: {str(e)}")
