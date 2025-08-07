# main.py - Final version with a simplified main loop
import time
import json
import network
import gc
import socket
import select
from machine import I2C, Pin, reset, lightsleep

# --- Core Application Modules ---
from web_server import WebServer
from system_monitor import SystemMonitor
from sensor_manager import SensorManager
from data_logger import DataLogger
import config
from web_template import create_html 
# Note: send_chunked_html is now used inside web_server.py
from utils import NetworkLogger, ExceptionHandler, SecurityManager, feed_watchdog, sync_time_periodic
from memory_handler import MemoryHandler
from uploader import upload_data_to_server


def initialize_system():
    """Bulletproof initialization for middle school students"""
    for attempt in range(3):  # Try 3 times before giving up
        try:
            print(f"[System] Starting initialization (attempt {attempt + 1}/3)...")
            gc.collect()
            
            # Step 1: Basic components (these should never fail)
            print("[System] Creating logger...")
            logger = NetworkLogger()
            
            print("[System] Setting up I2C...")
            i2c = I2C(1, scl=Pin(config.I2C_SCL_PIN), sda=Pin(config.I2C_SDA_PIN), freq=config.I2C_FREQUENCY)
            
            print("[System] Creating system monitor...")
            monitor = SystemMonitor(logger)
            
            # Step 2: Sensor (can fail, but we'll continue)
            print("[System] Initializing sensor...")
            sensor_manager = SensorManager(i2c, monitor, logger)
            
            print("[System] Setting up data logging...")
            data_logger = DataLogger(monitor, logger)
            
            print("[System] Configuring memory management...")
            memory_handler = MemoryHandler(logger)
            memory_handler.register_component('data_logger', data_logger)

            # Step 3: Network (most likely to fail)
            print("[System] Creating web server...")
            web_server = WebServer(monitor, sensor_manager, data_logger, logger)

            print(f"[System] Connecting to WiFi: {config.WIFI_SSID}")
            if not web_server.connect_wifi(config.WIFI_SSID, config.WIFI_PASSWORD):
                raise Exception(f"Cannot connect to WiFi '{config.WIFI_SSID}' - Check password and network")
            
            print(f"[System] Starting web server on port {config.WEB_SERVER_PORT}...")
            if not web_server.initialize_server(config.WEB_SERVER_PORT):
                raise Exception("Cannot start web server - Port may be in use")

            print("[System] ✓ All systems ready!")
            print(f"[System] ✓ WiFi connected: {web_server.ip_address}")
            print(f"[System] ✓ Web server running on port {config.WEB_SERVER_PORT}")
            gc.collect()
            
            return {
                'led': Pin("LED", Pin.OUT),
                'web_server': web_server,
                'sensor_manager': sensor_manager,
                'data_logger': data_logger,
                'logger': logger,
                'security_manager': SecurityManager(logger),
                'memory_handler': memory_handler
            }
            
        except Exception as e:
            print(f"[System] ✗ Initialization failed: {e}")
            if attempt < 2:  # Not the last attempt
                print(f"[System] Waiting 5 seconds before retry...")
                time.sleep(5)
            else:
                print("[System] ✗ FATAL: All initialization attempts failed!")
                print("[System] Check your WiFi settings in config.py")
                print("[System] Make sure sensor is connected properly")
                print("[System] Restarting in 10 seconds...")
                time.sleep(10)
                reset()

def main():
    try:
        components = initialize_system()
        web_server = components['web_server']
        
        # Pre-generate the static HTML shell
        html_shell = create_html(config)
        
        # --- NEW STEP: Give the web server the HTML to serve ---
        web_server.set_html_shell(html_shell)
        
        # Free up the memory used by the local copy
        html_shell = None
        gc.collect()

        print(f"Server running at http://{web_server.ip_address}:{config.WEB_SERVER_PORT}")
        print("Main loop started. Use Ctrl+C to stop.")

        last_log_time = time.time()
        last_blink_time = time.time()
        last_ntp_sync = time.time()  # Track last NTP sync time

        # Main loop with bulletproof error handling
        consecutive_errors = 0
        while True:
            try:
                if config.WATCHDOG_ENABLED:
                    feed_watchdog()

                # Handle web requests
                try:
                    r, _, _ = select.select([web_server.socket], [], [], 0.1)
                    
                    if r:
                        client, addr = web_server.socket.accept()
                        
                        if components['security_manager'].validate_request(addr[0]):
                            web_server.handle_request(client)
                        else:
                            client.close() 
                    
                    consecutive_errors = 0  # Reset error counter on success
                    
                except OSError as e:
                    # Socket errors - try to recover
                    consecutive_errors += 1
                    if "ECONNABORTED" in str(e) or "EBADF" in str(e):
                        print(f"[Main] Socket error, attempting recovery...")
                        if web_server.recover_socket():
                            print(f"[Main] ✓ Socket recovery successful")
                            consecutive_errors = 0
                        else:
                            print(f"[Main] ✗ Socket recovery failed")
                            time.sleep(5)
                    else:
                        print(f"[Main] Network error: {e}")
                        time.sleep(2)
                        
                except Exception as e:
                    consecutive_errors += 1
                    print(f"[Main] Request handling error: {e}")
                    time.sleep(1)
                
                # If too many consecutive errors, try full restart
                if consecutive_errors > 10:
                    print("[Main] Too many errors, restarting system...")
                    time.sleep(3)
                    reset()

            except Exception as e:
                # This should never happen, but just in case...
                print(f"[Main] CRITICAL ERROR: {e}")
                print("[Main] Restarting in 5 seconds...")
                time.sleep(5)
                reset()

            # -- Periodic Tasks --
            current_time = time.time()

            if current_time - last_blink_time > 1:
                components['led'].toggle()
                last_blink_time = current_time
                
                # Check network connection periodically
                if not web_server.check_network_connection():
                    components['logger'].log("NETWORK", "Network connection issues detected", "WARNING")
            
            # Periodic NTP sync every 6 hours
            if current_time - last_ntp_sync >= config.NTP_SYNC_INTERVAL:
                if sync_time_periodic(components['logger']):
                    last_ntp_sync = current_time
                else:
                    # Retry in 30 minutes if sync failed
                    last_ntp_sync = current_time - config.NTP_SYNC_INTERVAL + 1800

            if current_time - last_log_time >= config.LOG_INTERVAL:
                try:
                    readings = components['sensor_manager'].get_readings()
                    if readings:
                        co2, temp_c, temp_f, humidity, pressure, lux = readings
                        components['data_logger'].log_data(temp_c, temp_f, co2, humidity, pressure, lux)
                        last_log_time = current_time

                        upload_data = {
                            "co2_ppm": co2, "temperature_c": temp_c,
                            "humidity_percent": humidity, "pressure_hpa": pressure,
                            "light_lux": lux
                        }
                        upload_data_to_server(upload_data)
                        
                except Exception as e:
                    components['logger'].log('DATA', str(e), 'ERROR')

    except KeyboardInterrupt:
        print("\nShutdown requested by user.")
    except Exception as e:
        print(f"A fatal error occurred in main: {e}")
        time.sleep(10)
        reset()
    finally:
        if 'components' in locals() and 'web_server' in components:
            components['web_server'].shutdown()
            if 'led' in components:
                components['led'].off()
        print("Server stopped. Pico halted.")

if __name__ == "__main__":
    main()