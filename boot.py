# boot.py - Optimized boot sequence for Pico W 2
import machine
import gc
import time
import network
import config

# Format datetime for logs
def format_datetime(t):
    try:
        return f"{t[0]}-{t[1]:02d}-{t[2]:02d} {t[3]:02d}:{t[4]:02d}:{t[5]:02d}"
    except:
        return "Time Error"

# Initialize logger for boot process
try:
    from utils import NetworkLogger, feed_watchdog
    boot_logger = NetworkLogger()
except:
    # Simple fallback logger
    class SimpleLogger:
        def log(self, component, message, severity="INFO", error=None):
            print(f"{component}: {message}")
    boot_logger = SimpleLogger()
    
    def feed_watchdog():
        try:
            import machine
            if hasattr(machine, 'WDT'):
                wdt = machine.WDT(0)
                wdt.feed()
        except:
            pass

def configure_watchdog():
    """Configure hardware watchdog if enabled"""
    if not hasattr(config, 'WATCHDOG_ENABLED') or not config.WATCHDOG_ENABLED:
        return None
        
    try:
        # Initialize with specified timeout
        timeout = getattr(config, 'WATCHDOG_TIMEOUT', 8000)
        watchdog = machine.WDT(timeout=timeout)
        boot_logger.log("BOOT", f"Watchdog initialized with {timeout}ms timeout", "INFO")
        return watchdog
    except Exception as e:
        boot_logger.log("BOOT", "Failed to initialize watchdog", "WARNING")
        return None

def setup_wifi():
    """Set up WiFi interface without connecting"""
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        delay = getattr(config, 'WIFI_INIT_DELAY', 2)
        time.sleep(delay)  # Allow interface to initialize
        
        # Configure static IP if enabled
        if hasattr(config, 'USE_STATIC_IP') and config.USE_STATIC_IP:
            try:
                boot_logger.log("BOOT", f"Configuring static IP: {config.STATIC_IP}", "INFO")
                wlan.ifconfig((
                    config.STATIC_IP,
                    config.SUBNET_MASK,
                    config.GATEWAY,
                    config.DNS_SERVER
                ))
            except Exception as e:
                boot_logger.log("BOOT", "Static IP configuration failed", "WARNING")
        
        return wlan
    except Exception as e:
        boot_logger.log("BOOT", "WiFi setup failed", "ERROR")
        return None

def sync_time(wlan):
    """Synchronize time with NTP server if connected"""
    if not wlan or not wlan.isconnected():
        boot_logger.log("TIME", "Cannot sync time - no WiFi connection", "WARNING")
        return False
        
    try:
        import ntptime
        
        # Try to set time
        ntptime.host = getattr(config, 'NTP_SERVER', 'time.google.com')
        boot_logger.log("TIME", f"Attempting to sync time with {ntptime.host}", "INFO")
        
        # Try multiple times
        for attempt in range(3):
            try:
                ntptime.settime()
                
                # Adjust for timezone if configured
                if hasattr(config, 'TIMEZONE_OFFSET'):
                    # Adjust time for timezone
                    timezone_offset = config.TIMEZONE_OFFSET * 3600  # Convert hours to seconds
                    current_time = time.time() + timezone_offset
                    tm = time.localtime(current_time)
                    machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0))
                
                boot_logger.log("TIME", f"Time synchronized: {format_datetime(time.localtime())}", "INFO")
                return True
            except:
                time.sleep(1)
                continue
        
        boot_logger.log("TIME", "Failed to sync time after multiple attempts", "WARNING")
        return False
    except Exception as e:
        boot_logger.log("TIME", "Error during time sync", "ERROR")
        return False

def print_system_info():
    """Print system information to console"""
    try:
        unique_id = machine.unique_id()
        id_hex = ':'.join(['%02x' % b for b in unique_id])
        
        print("\nSystem Information:")
        print(f"Device ID: {id_hex}")
        print(f"CPU Frequency: {machine.freq() / 1000000}MHz")
        
        try:
            import sys
            print(f"MicroPython Version: {sys.version}")
            print(f"Platform: {sys.platform}")
        except:
            pass
        
        # Memory information
        gc.collect()
        free_mem = gc.mem_free()
        alloc_mem = gc.mem_alloc()
        total_mem = free_mem + alloc_mem
        
        print("\nMemory Information:")
        print(f"Free: {free_mem} bytes ({free_mem/1024:.1f} KB)")
        print(f"Used: {alloc_mem} bytes ({alloc_mem/1024:.1f} KB)")
        print(f"Total: {total_mem} bytes ({total_mem/1024:.1f} KB)")
        print(f"Usage: {(alloc_mem / total_mem) * 100:.1f}%")
        
        if hasattr(config, 'VERSION'):
            print(f"\nSoftware Version: {config.VERSION}")
            
    except Exception as e:
        print(f"Error printing system info: {e}")

def connect_wifi_if_needed():
    """Connect to WiFi if needed for boot process"""
    wlan = setup_wifi()
    if not wlan:
        return None
        
    # Check if already connected
    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        boot_logger.log("BOOT", f"Already connected to WiFi with IP: {ip}", "INFO")
        return wlan
    
    # Try to connect
    if not hasattr(config, 'WIFI_SSID') or not hasattr(config, 'WIFI_PASSWORD'):
        boot_logger.log("BOOT", "WiFi credentials not configured", "WARNING")
        return None
        
    boot_logger.log("BOOT", f"Connecting to {config.WIFI_SSID}", "INFO")
    
    try:
        wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
        
        # Wait for connection
        max_wait = getattr(config, 'WIFI_CONNECT_TIMEOUT', 30)
        while max_wait > 0:
            feed_watchdog()
            if wlan.isconnected():
                ip = wlan.ifconfig()[0]
                boot_logger.log("BOOT", f"Connected to WiFi with IP: {ip}", "INFO")
                return wlan
            
            max_wait -= 1
            time.sleep(1)
            
        boot_logger.log("BOOT", "Failed to connect to WiFi during boot", "WARNING")
        return None
        
    except Exception as e:
        boot_logger.log("BOOT", "Error connecting to WiFi", "ERROR")
        return None

def initialize_webrepl():
    """Initialize WebREPL if enabled"""
    if not hasattr(config, 'WEBREPL_ENABLED') or not config.WEBREPL_ENABLED:
        return False
        
    try:
        # Check if WebREPL is already configured
        try:
            import webrepl_cfg
            # Just import to check if it exists
        except ImportError:
            # Create config file with password
            if hasattr(config, 'WEBREPL_PASSWORD'):
                with open('webrepl_cfg.py', 'w') as f:
                    f.write(f"PASS = '{config.WEBREPL_PASSWORD}'")
            else:
                with open('webrepl_cfg.py', 'w') as f:
                    f.write("PASS = 'pico2023'")
        
        # Start WebREPL
        import webrepl
        webrepl.start()
        boot_logger.log("BOOT", "WebREPL started", "INFO")
        return True
        
    except Exception as e:
        boot_logger.log("BOOT", "Failed to initialize WebREPL", "ERROR")
        return False

def main():
    """Main boot sequence"""
    print("\nStarting boot sequence...")
    boot_logger.log("BOOT", "Starting boot sequence", "INFO")
    
    # Initialize LED for status indication
    led = machine.Pin("LED", machine.Pin.OUT)
    led.on()  # Turn on during boot
    
    try:
        # Configure watchdog
        watchdog = configure_watchdog()
        feed_watchdog()
        
        # Force garbage collection before starting
        gc.collect()
        
        # Print system information
        print_system_info()
        
        # Connect to WiFi if needed for time sync
        wlan = connect_wifi_if_needed()
        feed_watchdog()
        
        # Sync time if connected
        if wlan and wlan.isconnected():
            sync_time(wlan)
            
        # Initialize WebREPL if enabled
        initialize_webrepl()
        
        feed_watchdog()
        
        # Print current time
        current_time = time.localtime()
        print(f"\nCurrent time: {format_datetime(current_time)}")
        
        # Turn off LED when boot complete
        for _ in range(3):  # Blink LED to indicate successful boot
            led.toggle()
            time.sleep(0.1)
            led.toggle()
            time.sleep(0.1)
        led.off()
        
        boot_logger.log("BOOT", "Boot sequence completed successfully", "INFO")
        print("\nBoot sequence complete!")
        print("-" * 40)
        
        return True
        
    except Exception as e:
        boot_error = f"Boot error: {e}"
        print(boot_error)
        boot_logger.log("BOOT", boot_error, "ERROR")
        
        # Keep LED on to indicate error
        led.on()
        return False

# Run boot sequence
if __name__ == "__main__":
    main()