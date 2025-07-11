# main.py - Corrected and Final Version
import time
import json
import network
import gc
import socket
import select
from machine import I2C, Pin, reset, lightsleep
from web_server import WebServer
from system_monitor import SystemMonitor
from sensor_manager import SensorManager
from data_logger import DataLogger
import config
from web_template import create_html, send_chunked_html
from utils import NetworkLogger, ExceptionHandler, SecurityManager, feed_watchdog
from memory_handler import MemoryHandler

def initialize_system():
    """Initializes all system components and returns them in a dictionary."""
    try:
        print("[System] Initializing system components...")
        gc.collect()
        
        logger = NetworkLogger()
        exception_handler = ExceptionHandler(logger)

        i2c = I2C(1, scl=Pin(config.I2C_SCL_PIN), sda=Pin(config.I2C_SDA_PIN), freq=config.I2C_FREQUENCY)
        print("[System] I2C initialized.")

        monitor = SystemMonitor(logger)
        sensor_manager = SensorManager(i2c, monitor, logger)
        data_logger = DataLogger(monitor, logger)
        print("[System] Core monitors and loggers initialized.")
        
        memory_handler = MemoryHandler(logger)
        memory_handler.register_component('data_logger', data_logger)

        # 1. Create the WebServer instance FIRST.
        web_server = WebServer(monitor, sensor_manager, data_logger)

        # 2. Use the WebServer's own method to connect to WiFi.
        if not web_server.connect_wifi(config.WIFI_SSID, config.WIFI_PASSWORD):
            raise Exception("Fatal: Could not connect to WiFi network.")
        
        # 3. NOW, initialize the server socket.
        if not web_server.initialize_server(config.WEB_SERVER_PORT):
            raise Exception("Fatal: Could not initialize web server socket.")

        print("[System] System initialization completed successfully.")
        gc.collect()
        
        return {
            'led': Pin("LED", Pin.OUT),
            'monitor': monitor,
            'web_server': web_server,
            'sensor_manager': sensor_manager,
            'data_logger': data_logger,
            'logger': logger,
            'exception_handler': exception_handler,
            'security_manager': SecurityManager(logger),
            'memory_handler': memory_handler
        }
    except Exception as e:
        print(f"[System] FATAL: System initialization error: {e}")
        time.sleep(10)
        reset()

def main():
    try:
        components = initialize_system()
        web_server = components['web_server']
        
        # Pre-generate the static HTML shell by passing the entire config module
        html_shell = create_html(config)
        gc.collect()

        print(f"Server running at http://{web_server.ip_address}:{config.WEB_SERVER_PORT}")
        print("Main loop started. Use Ctrl+C to stop.")

        last_log_time = time.time()
        last_blink_time = time.time()

        while True:
            # Feed the watchdog at the start of every loop for maximum safety
            if config.WATCHDOG_ENABLED:
                feed_watchdog()

            try:
                # Use select() to wait for a connection without blocking the CPU
                r, _, _ = select.select([web_server.socket], [], [], 0.1)
                
                if r:
                    # An incoming connection is waiting
                    client, addr = web_server.socket.accept()
                    
                    if components['security_manager'].validate_request(addr[0]):
                        method, path = web_server.handle_request(client)
                        
                        # If the path is for the main page, serve the pre-generated shell.
                        # API calls and downloads are handled inside web_server.py now.
                        if method and path and path == '/':
                            send_chunked_html(client, html_shell)
                    else:
                        client.close() # Rate limit exceeded
                
                # --- POWER SAVING LOGIC ---
                elif config.LOW_POWER_MODE_ENABLED and config.SLEEP_WHEN_IDLE:
                    # If there was no socket activity, go into a light sleep.
                    lightsleep(config.SLEEP_DURATION)

            except Exception as e:
                components['exception_handler'].handle('Main Loop', str(e))
                if "memory" in str(e).lower():
                    print("Memory error detected, performing emergency recovery")
                    components['memory_handler'].check_memory(force=True)
                time.sleep(2) # Brief pause after any loop error

            # -- Periodic Tasks --
            current_time = time.time()

            # Blink LED as a heartbeat to show the main loop is running
            if current_time - last_blink_time > 1:
                components['led'].toggle()
                last_blink_time = current_time

            # Log data periodically (the function itself checks the interval)
            if current_time - last_log_time >= config.LOG_INTERVAL:
                try:
                    readings = components['sensor_manager'].get_readings()
                    if readings:
                        co2, temp_c, temp_f, humidity, pressure = readings
                        components['data_logger'].log_data(temp_c, temp_f, co2, humidity, pressure)
                        last_log_time = current_time
                except Exception as e:
                    components['exception_handler'].handle('Data Logging', str(e))

    except KeyboardInterrupt:
        print("\nShutdown requested by user.")
    except Exception as e:
        print(f"A fatal error occurred in main: {e}")
        time.sleep(10)
        reset()
    finally:
        if 'components' in locals() and 'web_server' in components:
            components['web_server'].shutdown()
            components['led'].off()
        print("Server stopped. Pico halted.")

if __name__ == "__main__":
    main()