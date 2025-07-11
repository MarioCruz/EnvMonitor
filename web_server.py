# web_server.py - Corrected with implemented file downloads
import network
import socket
import time
from machine import Pin, unique_id
import config
import gc
import os
import json

def format_uptime(seconds):
    """Formats uptime in a human-readable string."""
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

    def handle_api_data(self, client_socket):
        """Handles the /api/data endpoint to provide live data."""
        try:
            readings = self.sensor_manager.get_readings()
            system_stats = self.monitor.check_system_health()
            if readings:
                co2, temp_c, temp_f, humidity, pressure = readings
                data = {
                    "temp_c": temp_c, "temp_f": temp_f, "co2": co2, "humidity": humidity, "pressure": pressure,
                    "uptime_str": format_uptime(system_stats.get('uptime', 0)),
                    "memory_percent": system_stats.get('memory_percent', 0),
                    "memory_used_kb": system_stats.get('memory_used', 0) / 1024,
                    "storage_percent": system_stats.get('storage_percent', 0),
                    "device_model": system_stats.get('device_model', 'Unknown')
                }
                self.send_response(client_socket, json.dumps(data), content_type='application/json')
            else:
                self.send_response(client_socket, '{"error":"Failed to get sensor readings"}', status_code=500)
        except Exception as e:
            print(f"ERROR in handle_api_data: {e}")
            self.send_response(client_socket, '{"error":"API error"}', status_code=500)

    def handle_test_page(self, client_socket):
        """Handles the /test.html page for basic server function testing."""
        try:
            current_time = time.localtime()
            formatted_time = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(*current_time)
            device_id_bytes = unique_id()
            device_id_str = ':'.join(['%02x' % byte for byte in device_id_bytes])
            test_html_content = f"""
            <!DOCTYPE html><html><head><title>Pico W Test Page</title><style>body{{font-family:sans-serif;}}</style></head>
            <body><h1>Web Server is Running!</h1><p>If you see this, the core server is functional.</p>
            <ul><li><strong>Device ID:</strong> {device_id_str}</li><li><strong>Time:</strong> {formatted_time}</li></ul>
            <p><a href="/">Back to Dashboard</a></p></body></html>
            """
            self.send_response(client_socket, test_html_content)
        except Exception:
            self.send_response(client_socket, "<h1>Error</h1>", status_code=500)

    def handle_request(self, client_socket):
        """Parses an incoming request and routes it to the correct handler."""
        try:
            client_socket.settimeout(2.0)
            request_bytes = client_socket.recv(1024)
            if not request_bytes: client_socket.close(); return None, None
            
            request = request_bytes.decode('utf-8')
            first_line = request.split('\r\n')[0]
            parts = first_line.split(' ')
            if len(parts) < 2:
                client_socket.close()
                return None, None
            method, path = parts[0], parts[1]
            
            # Route to the appropriate handler based on the path
            if path == '/test.html': self.handle_test_page(client_socket); return None, None
            if path == '/api/data': self.handle_api_data(client_socket); return None, None
            if path == '/api/history': self.handle_api_history(client_socket); return None, None
            if path in ['/csv', '/json', '/logs/network.log', '/logs/sensor_log.txt']: 
                self.handle_file_download(client_socket, path)
                return None, None
            
            # If no API/file path matched, return method and path to the main loop for HTML serving
            return method, path
        except Exception as e:
            self.log_network_event("REQUEST", f"Error handling request: {str(e)}", "ERROR")
            client_socket.close() # Ensure socket is closed on error
            return None, None

    def initialize_log_files(self):
        """Ensures the log directory and network log file exist."""
        try:
            os.mkdir('/logs')
        except OSError as e:
            if e.args[0] != 17: print(f"Error creating logs directory: {e}")
        try:
            os.stat('/logs/network.log')
        except OSError:
            with open('/logs/network.log', 'w') as f: f.write("Network Log Started\n")

    def log_network_event(self, event_type, message, severity="INFO"):
        """Logs network-related events to a file."""
        try:
            timestamp = time.localtime()
            log_entry = f"{timestamp[0]}-{timestamp[1]:02d}-{timestamp[2]:02d} {timestamp[3]:02d}:{timestamp[4]:02d}:{timestamp[5]:02d} [{severity}] [{event_type}] {message}\n"
            with open('/logs/network.log', 'a') as f: f.write(log_entry)
        except Exception as e:
            print(f"Error writing to network log: {e}")

    def connect_wifi(self, ssid, password, max_wait=30):
        """Establishes a connection to the WiFi network."""
        self.log_network_event("WIFI", f"Connecting to WiFi network: {ssid}")
        try:
            self.wlan = network.WLAN(network.STA_IF)
            self.wlan.active(True)
            if getattr(config, 'USE_STATIC_IP', False): self.wlan.ifconfig((config.STATIC_IP, config.SUBNET_MASK, config.GATEWAY, config.DNS_SERVER))
            if self.wlan.isconnected(): 
                self.ip_address = self.wlan.ifconfig()[0]
                return True
            self.wlan.connect(ssid, password)
            start_time = time.time()
            while time.time() - start_time < max_wait:
                if self.wlan.isconnected(): 
                    self.ip_address = self.wlan.ifconfig()[0]
                    self.log_network_event("WIFI", f"Connected. IP: {self.ip_address}")
                    return True
                time.sleep(1)
            raise Exception("WiFi connection timeout")
        except Exception as e:
            self.log_network_event("WIFI", f"Connection failed: {str(e)}", "CRITICAL")
            return False

    def initialize_server(self, port=80):
        """Initializes the web server socket."""
        self.port = port
        if not self.wlan or not self.wlan.isconnected(): return False
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
        """Handles the /api/history endpoint for chart data."""
        try:
            history_data = self.data_logger.get_history()
            chart_json = { 
                'timestamps': [entry['timestamp'].split(' ')[1] for entry in history_data], 
                'temperatures': [entry['temp_c'] for entry in history_data], 
                'co2_levels': [entry['co2'] for entry in history_data], 
                'humidities': [entry['humidity'] for entry in history_data] 
            }
            self.send_response(client_socket, json.dumps(chart_json), content_type='application/json')
        except Exception as e:
            self.send_response(client_socket, f'{{"error":"History API error: {e}"}}', status_code=500)

    def send_response(self, client_socket, content, status_code=200, content_type="text/html", headers=None):
        """Sends a complete HTTP response to the client."""
        try:
            status_text = {200: "OK", 404: "Not Found", 500: "Internal Server Error"}.get(status_code, "OK")
            response_headers = [f"HTTP/1.1 {status_code} {status_text}", f"Content-Type: {content_type}", "Connection: close"]
            if headers: 
                response_headers.extend([f"{k}: {v}" for k, v in headers.items()])
            
            header_string = "\r\n".join(response_headers) + "\r\n\r\n"
            
            # Check if content is bytes, if not, encode it
            if not isinstance(content, bytes):
                content = content.encode('utf-8')

            client_socket.sendall(header_string.encode('utf-8') + content)
        except Exception as e:
            self.log_network_event("RESPONSE", f"Failed to send response: {str(e)}", "ERROR")
        finally:
            client_socket.close()

    def handle_file_download(self, client_socket, path):
        """Handles file download requests for CSV, JSON, and log files."""
        gc.collect()
        
        try:
            if path == '/csv':
                history = self.data_logger.get_history()
                # Create CSV content in memory
                csv_content = "DateTime,Temperature_C,Temperature_F,CO2_PPM,Humidity,Pressure\n"
                for entry in history:
                    csv_content += f"{entry['timestamp']},{entry['temp_c']},{entry['temp_f']},{entry['co2']},{entry['humidity']},{entry['pressure']}\n"
                
                headers = {'Content-Disposition': 'attachment; filename="sensor_data.csv"'}
                self.send_response(client_socket, csv_content, content_type="text/csv", headers=headers)
                
            elif path == '/json':
                history = self.data_logger.get_history()
                json_content = json.dumps(history)
                headers = {'Content-Disposition': 'attachment; filename="sensor_data.json"'}
                self.send_response(client_socket, json_content, content_type="application/json", headers=headers)

            elif path.startswith('/logs/'):
                filename = path.lstrip('/')
                try:
                    # Check file size to prevent memory errors
                    file_size = os.stat(filename)[6]
                    if file_size > (gc.mem_free() * 0.8): # Safety check: only load if it fits comfortably in RAM
                        error_msg = "Log file is too large to send."
                        self.send_response(client_socket, error_msg, status_code=500)
                        self.log_network_event("DOWNLOAD", f"Failed to send {filename}: {error_msg}", "ERROR")
                        return

                    with open(filename, 'rb') as f:
                        content = f.read()
                    
                    headers = {'Content-Disposition': f'attachment; filename="{os.path.basename(filename)}"'}
                    self.send_response(client_socket, content, content_type="text/plain", headers=headers)
                
                except OSError:
                    self.send_response(client_socket, "File Not Found", status_code=404)
            else:
                self.send_response(client_socket, "Invalid Path", status_code=404)

        except Exception as e:
            self.log_network_event("DOWNLOAD", f"Error generating file for {path}: {str(e)}", "ERROR")
            self.send_response(client_socket, "Server error while generating file.", status_code=500)
        finally:
            gc.collect()

    def shutdown(self):
        """Shuts down the web server socket."""
        if self.socket:
            self.socket.close()
            self.log_network_event("SERVER", "Web server shut down.")