# web_server.py - Corrected with self-contained helper function
import network
import socket
import time
from machine import Pin, unique_id
import config
import gc
import os
import json

# --- HELPER FUNCTION ADDED HERE ---
# This function is now self-contained within this file to prevent NameErrors.
def format_uptime(seconds):
    try:
        if seconds < 0: return "0m 0s"
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        if days > 0:
            return f"{int(days)}d {int(hours)}h"
        elif hours > 0:
            return f"{int(hours)}h {int(minutes)}m"
        else:
            return f"{int(minutes)}m {int(seconds)}s"
    except:
        return "Error"
# --- END OF HELPER FUNCTION ---

class WebServer:
    def __init__(self, monitor, sensor_manager, data_logger):
        self.monitor = monitor
        self.sensor_manager = sensor_manager
        self.data_logger = data_logger
        self.led = Pin("LED", Pin.OUT)
        self.socket = None
        self.wlan = None
        self.ip_address = None
        self.initialize_log_files()

    # --- THIS IS THE CORRECTED FUNCTION ---
    def handle_api_data(self, client_socket):
        try:
            readings = self.sensor_manager.get_readings()
            system_stats = self.monitor.check_system_health()
            
            if readings:
                co2, temp_c, temp_f, humidity, pressure = readings
                
                # Now this call to format_uptime() will work correctly.
                uptime_string = format_uptime(system_stats.get('uptime', 0))
                
                data = {
                    "temp_c": temp_c,
                    "temp_f": temp_f,
                    "co2": co2,
                    "humidity": humidity,
                    "pressure": pressure,
                    "uptime_str": uptime_string,
                    "memory_percent": system_stats.get('memory_percent', 0),
                    "memory_used_kb": system_stats.get('memory_used', 0) / 1024,
                    "storage_percent": system_stats.get('storage_percent', 0),
                }
                # Add a print statement for debugging
                print(f"Serving API data: {data}")
                self.send_response(client_socket, json.dumps(data), content_type='application/json')
            else:
                self.send_response(client_socket, '{"error":"Failed to get sensor readings"}', status_code=500, content_type='application/json')
        except Exception as e:
            print(f"ERROR in handle_api_data: {e}")
            self.send_response(client_socket, f'{{"error":"API error"}}', status_code=500, content_type='application/json')

    def handle_test_page(self, client_socket):
        # (This function is already correct)
        try:
            current_time = time.localtime()
            formatted_time = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(*current_time)
            device_id_bytes = unique_id()
            device_id_str = ':'.join(['%02x' % byte for byte in device_id_bytes])
            test_html_content = """
            <!DOCTYPE html><html><head><title>Pico W Test Page</title><style>body{{font-family:sans-serif;}}</style></head>
            <body><h1>Web Server is Running!</h1><p>If you see this, the core server is functional.</p>
            <ul><li><strong>Device ID:</strong> {}</li><li><strong>Time:</strong> {}</li></ul>
            <p><a href="/">Back to Dashboard</a></p></body></html>
            """.format(device_id_str, formatted_time)
            self.send_response(client_socket, test_html_content)
        except Exception as e:
            self.send_response(client_socket, "<h1>Error</h1>", status_code=500)

    def handle_request(self, client_socket):
        # (This function is already correct)
        try:
            client_socket.settimeout(2.0)
            request_bytes = client_socket.recv(1024)
            if not request_bytes: client_socket.close(); return None, None
            request = request_bytes.decode('utf-8')
            request_lines = request.split('\r\n')
            if not request_lines: raise Exception("Empty request")
            method, path, _ = request_lines[0].split(' ')
            if path == '/test.html':
                self.handle_test_page(client_socket); return None, None
            if path == '/api/data':
                self.handle_api_data(client_socket); return None, None
            if path == '/api/history':
                self.handle_api_history(client_socket); return None, None
            if path in ['/csv', '/json', '/logs/network.log']:
                self.handle_file_download(client_socket, path); return None, None
            return method, path
        except Exception as e:
            self.log_network_event("REQUEST", f"Error handling request: {str(e)}", "ERROR")
            return None, None

    def initialize_log_files(self):
        # (This function is unchanged)
        try:
            os.mkdir('/logs')
        except OSError as e:
            if e.args[0] != 17: print(f"Error creating logs directory: {e}")
        try:
            os.stat('/logs/network.log')
        except OSError:
            with open('/logs/network.log', 'w') as f: f.write("Network Log Started\n")
    
    def log_network_event(self, event_type, message, severity="INFO"):
        # (This function is unchanged)
        try:
            timestamp = time.localtime()
            log_entry = f"{timestamp[0]}-{timestamp[1]:02d}-{timestamp[2]:02d} {timestamp[3]:02d}:{timestamp[4]:02d}:{timestamp[5]:02d} [{severity}] [{event_type}] {message}\n"
            with open('/logs/network.log', 'a') as f: f.write(log_entry)
        except Exception as e:
            print(f"Error writing to network log: {e}")

    def connect_wifi(self, ssid, password, max_wait=30):
        # (This function is unchanged)
        ip_mode = '[DHCP]'
        if getattr(config, 'USE_STATIC_IP', False): ip_mode = '[FIXED IP]'
        self.log_network_event("WIFI", f"Connecting to WiFi network: {ssid} {ip_mode}")
        try:
            self.wlan = network.WLAN(network.STA_IF)
            self.wlan.active(True)
            if getattr(config, 'USE_STATIC_IP', False): self.wlan.ifconfig((config.STATIC_IP, config.SUBNET_MASK, config.GATEWAY, config.DNS_SERVER))
            if self.wlan.isconnected(): self.ip_address = self.wlan.ifconfig()[0]; return True
            self.wlan.connect(ssid, password)
            start_time = time.time()
            while time.time() - start_time < max_wait:
                if self.wlan.isconnected(): self.ip_address = self.wlan.ifconfig()[0]; self.log_network_event("WIFI", f"Connected successfully. IP: {self.ip_address}"); return True
                time.sleep(1)
            raise Exception("WiFi connection timeout")
        except Exception as e:
            self.log_network_event("WIFI", f"Connection failed: {str(e)}", "CRITICAL")
            return False

    def initialize_server(self, port=80):
        # (This function is unchanged)
        self.port = port
        if not self.wlan or not self.wlan.isconnected(): self.log_network_event("SERVER", "WiFi not connected during initialization", "CRITICAL"); return False
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(('0.0.0.0', port))
            self.socket.listen(1)
            self.socket.setblocking(False)
            self.log_network_event("SERVER", f"Web server started on port {port}")
            return True
        except Exception as e:
            self.log_network_event("SERVER", f"Failed to initialize: {str(e)}", "CRITICAL")
            return False

    def handle_api_history(self, client_socket):
        # (This function is unchanged)
        try:
            history_data = self.data_logger.get_history()
            chart_json = { 'timestamps': [entry['timestamp'].split(' ')[1] for entry in history_data], 'temperatures': [entry['temp_c'] for entry in history_data], 'co2_levels': [entry['co2'] for entry in history_data] }
            self.send_response(client_socket, json.dumps(chart_json), content_type='application/json')
        except Exception as e:
            self.send_response(client_socket, f'{{"error":"History API error: {e}"}}', status_code=500, content_type='application/json')

    def send_response(self, client_socket, content, status_code=200, content_type="text/html", headers=None):
        # (This function is unchanged)
        try:
            status_text = {200: "OK", 500: "Internal Server Error"}.get(status_code, "OK")
            response_headers = [f"HTTP/1.1 {status_code} {status_text}", f"Content-Type: {content_type}", "Connection: close"]
            if headers: response_headers.extend([f"{k}: {v}" for k, v in headers.items()])
            header_string = "\r\n".join(response_headers) + "\r\n\r\n"
            client_socket.sendall(header_string.encode() + content.encode())
        except Exception as e:
            self.log_network_event("RESPONSE", f"Failed to send response: {str(e)}", "ERROR")
        finally:
            client_socket.close()