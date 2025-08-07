# web_server.py - FINAL version with graceful timeout handling
import network
import socket
import time
from machine import Pin, unique_id
import config
import gc
import os
import json
from web_template import send_chunked_html 

def format_uptime(seconds):
    """Formats uptime in a human-readable string."""
    try:
        if seconds < 0: return "0m 0s"
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        if days > 0: return f"{int(days)}d {int(hours)}h"
        elif hours > 0: return f"{int(hours)}h {int(minutes)}m"
        else: return f"{int(minutes)}m {int(seconds)}s"
    except: return "Error"

class WebServer:
    def __init__(self, monitor, sensor_manager, data_logger, logger):
        self.monitor = monitor
        self.sensor_manager = sensor_manager
        self.data_logger = data_logger
        self.logger = logger
        self.socket = None
        self.wlan = None
        self.ip_address = None
        self.html_shell = None
        self.last_network_check = 0
        self.reconnect_attempts = 0
        self.last_reconnect_time = 0

    def set_html_shell(self, html):
        self.html_shell = html
        self.logger.log("SERVER", "Main HTML page has been cached.", "INFO")

    def handle_api_data(self, client_socket):
        # This function is fast and remains unchanged
        try:
            readings = self.sensor_manager.get_readings()
            system_stats = self.monitor.check_system_health()
            sensor_status = self.sensor_manager.get_status()
            model_name = os.uname().machine.split(' with')[0]

            if readings:
                co2, temp_c, temp_f, humidity, pressure, lux = readings
                data = {
                    "temp_c": temp_c, "temp_f": temp_f, "co2": co2, "humidity": humidity, "pressure": pressure, "lux": lux,
                    "uptime_str": format_uptime(system_stats.get('uptime', 0)),
                    "memory_percent": system_stats.get('memory_percent', 0),
                    "memory_used_kb": system_stats.get('memory_used', 0) / 1024,
                    "storage_percent": system_stats.get('storage_percent', 0),
                    "light_sensor_available": sensor_status.get('light_sensor_available', False),
                    "light_sensor_errors": sensor_status.get('light_sensor_errors', 0),
                    "device_id": config.DEVICE_ID,
                    "device_model": model_name
                }
                self.send_response(client_socket, json.dumps(data), content_type='application/json')
            else:
                self.send_response(client_socket, '{"error":"Failed to get sensor readings"}', status_code=500)
        except Exception as e:
            self.logger.log("API", f"Error in handle_api_data: {e}", "ERROR")
            self.send_response(client_socket, '{"error":"API error"}', status_code=500)

    def handle_request(self, client_socket):
        """Parses and handles requests with graceful timeout handling on recv."""
        path = 'unknown'
        try:
            client_socket.settimeout(5.0) 
            request_bytes = client_socket.recv(1024)
            
            if not request_bytes: 
                client_socket.close()
                return
            
            request = request_bytes.decode('utf-8')
            first_line = request.split('\r\n')[0]
            parts = first_line.split(' ')
            if len(parts) < 2:
                client_socket.close()
                return
            
            method, path = parts[0], parts[1]
            
            # Master routing logic
            if path == '/':
                send_chunked_html(client_socket, self.html_shell)
            elif path == '/api/history': 
                self.stream_api_history(client_socket)
            elif path == '/api/data': 
                self.handle_api_data(client_socket)
            elif path in ['/csv', '/json'] or path.startswith('/logs/'):
                self.handle_file_download(client_socket, path)
            elif path == '/test.html':
                 self.handle_test_page(client_socket)
            elif path == '/sensors':
                self.handle_sensors_page(client_socket)
            else:
                self.send_response(client_socket, "<h1>404 Not Found</h1>", status_code=404)
        
        except Exception as e:
            self.logger.log("REQUEST", f"Request error for '{path}': {e}", "WARNING")
        finally:
            try:
                client_socket.close()
            except:
                pass

    def stream_api_history(self, client_socket):
        gc.collect()
        try:
            history_data = self.data_logger.get_history()
            headers = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n"
            client_socket.sendall(headers.encode('utf-8'))
            
            # Build JSON response more efficiently
            response = {
                "timestamps": [entry['timestamp'].split(' ')[1] for entry in history_data],
                "temperatures": [round(entry['temp_c'], 1) for entry in history_data],
                "co2_levels": [entry['co2'] for entry in history_data],
                "humidities": [round(entry['humidity'], 1) for entry in history_data],
                "light_levels": [round(entry.get('lux', 0.0), 1) for entry in history_data]
            }
            
            import json
            client_socket.sendall(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            self.logger.log("API", f"History stream error: {e}", "ERROR")
        finally:
            try:
                client_socket.close()
            except:
                pass
            gc.collect()

    def connect_wifi(self, ssid, password, max_wait=30):
        """Bulletproof WiFi connection for students"""
        print(f"[WiFi] Connecting to '{ssid}'...")
        try:
            self.wlan = network.WLAN(network.STA_IF)
            self.wlan.active(True)
            time.sleep(1)  # Give it time to activate
            
            # Check if already connected
            if self.wlan.isconnected(): 
                self.ip_address = self.wlan.ifconfig()[0]
                print(f"[WiFi] ✓ Already connected! IP: {self.ip_address}")
                return True
            
            # Start connection
            print(f"[WiFi] Attempting to connect...")
            self.wlan.connect(ssid, password)
            
            # Wait with clear feedback
            start_time = time.time()
            dots = 0
            while time.time() - start_time < max_wait:
                if self.wlan.isconnected(): 
                    self.ip_address = self.wlan.ifconfig()[0]
                    print(f"\n[WiFi] ✓ Connected successfully!")
                    print(f"[WiFi] ✓ Your IP address: {self.ip_address}")
                    self.logger.log("WIFI", f"Connected. IP: {self.ip_address}", "INFO")
                    return True
                
                # Show progress dots
                if dots % 3 == 0:
                    print(f"\r[WiFi] Connecting{'.' * (dots // 3 + 1)}", end="")
                dots += 1
                time.sleep(1)
            
            # Connection failed
            status = self.wlan.status()
            if status == network.STAT_WRONG_PASSWORD:
                raise Exception(f"Wrong password for '{ssid}' - Check config.py")
            elif status == network.STAT_NO_AP_FOUND:
                raise Exception(f"Network '{ssid}' not found - Check network name")
            else:
                raise Exception(f"Connection timeout after {max_wait} seconds")
                
        except Exception as e:
            print(f"\n[WiFi] ✗ Connection failed: {e}")
            self.logger.log("WIFI", f"Connection failed: {e}", "ERROR")
            return False

    def initialize_server(self, port=80):
        # ... (method unchanged)
        self.port = port
        if not self.wlan or not self.wlan.isconnected(): return False
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(('0.0.0.0', port))
            self.socket.listen(1)
            self.socket.setblocking(False)
            self.logger.log("SERVER", f"Web server started on port {port}", "INFO")
            return True
        except Exception as e:
            self.logger.log("SERVER", f"Failed to initialize: {e}", "CRITICAL")
            return False

    def send_response(self, client_socket, content, status_code=200, content_type="text/html", headers=None):
        # ... (method unchanged)
        try:
            status_text = {200: "OK", 404: "Not Found", 500: "Internal Server Error", 503: "Service Unavailable"}.get(status_code, "OK")
            response_headers = [f"HTTP/1.1 {status_code} {status_text}", f"Content-Type: {content_type}", "Connection: close"]
            if headers: 
                response_headers.extend([f"{k}: {v}" for k, v in headers.items()])
            header_string = "\r\n".join(response_headers) + "\r\n\r\n"
            if not isinstance(content, bytes):
                content = content.encode('utf-8')
            client_socket.sendall(header_string.encode('utf-8') + content)
        except Exception as e:
            self.logger.log("RESPONSE", f"Failed to send response: {e}", "ERROR")
        finally:
            if client_socket:
                client_socket.close()
    
    def handle_file_download(self, client_socket, path):
        # Corrected this method to no longer use the streaming function for /json
        gc.collect()
        try:
            if path == '/csv':
                # ... (streaming for CSV is correct and unchanged)
                history = self.data_logger.get_history()
                headers = "HTTP/1.1 200 OK\r\nContent-Type: text/csv\r\nContent-Disposition: attachment; filename=\"sensor_data.csv\"\r\nConnection: close\r\n\r\n"
                client_socket.sendall(headers.encode('utf-8'))
                client_socket.sendall("DateTime,Temperature_C,Temperature_F,CO2_PPM,Humidity,Pressure,Light_Lux\n".encode('utf-8'))
                for entry in history:
                    lux_value = entry.get('lux', 0.0)  # Support old format without lux
                    line = f"{entry['timestamp']},{entry['temp_c']},{entry['temp_f']},{entry['co2']},{entry['humidity']},{entry['pressure']},{lux_value}\n"
                    client_socket.sendall(line.encode('utf-8'))
            elif path == '/json':
                # Reverted /json to use json.dumps, which is fine for a file download
                history = self.data_logger.get_history()
                json_content = json.dumps(history)
                headers = {'Content-Disposition': 'attachment; filename="sensor_data.json"'}
                self.send_response(client_socket, json_content, content_type="application/json", headers=headers)
                return 
            elif path.startswith('/logs/'):
                # ... (streaming for logs is correct and unchanged)
                filename = path.lstrip('/')
                try:
                    file_size = os.stat(filename)[6]
                    if file_size > (gc.mem_free() * 0.8):
                        self.send_response(client_socket, "Log file is too large to display.", status_code=500)
                        return
                    headers = f"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Disposition: attachment; filename=\"{os.path.basename(filename)}\"\r\nConnection: close\r\n\r\n"
                    client_socket.sendall(headers.encode('utf-8'))
                    with open(filename, 'rb') as f:
                        while True:
                            chunk = f.read(512)
                            if not chunk: break
                            client_socket.sendall(chunk)
                except OSError:
                    self.send_response(client_socket, "File Not Found", status_code=404)
                    return
            else:
                self.send_response(client_socket, "Invalid Path", status_code=404)
                return
        except Exception as e:
            self.logger.log("DOWNLOAD", f"Error streaming file for {path}: {e}", "ERROR")
        finally:
            if client_socket: client_socket.close()
            gc.collect()

    def check_network_connection(self):
        """Check and recover network connection if needed"""
        current_time = time.time()
        if current_time - self.last_network_check < 30:  # Check every 30 seconds
            return self.wlan and self.wlan.isconnected()
        
        self.last_network_check = current_time
        
        if not self.wlan or not self.wlan.isconnected():
            self.logger.log("WIFI", "Connection lost, attempting reconnect", "WARNING")
            if self.reconnect_wifi():
                self.reconnect_attempts = 0
                return True
            else:
                self.reconnect_attempts += 1
                return False
        
        # Check signal strength for early warning
        try:
            rssi = self.wlan.status('rssi')
            if rssi < -75:  # Weak signal threshold
                self.logger.log("WIFI", f"Weak signal detected: {rssi} dBm", "WARNING")
        except:
            pass
            
        return True
    
    def reconnect_wifi(self):
        """Attempt to reconnect to WiFi with backoff"""
        current_time = time.time()
        
        # Exponential backoff: wait longer between attempts
        min_wait = min(5 * (2 ** min(self.reconnect_attempts, 4)), 300)  # Max 5 minutes
        if current_time - self.last_reconnect_time < min_wait:
            return False
            
        self.last_reconnect_time = current_time
        
        try:
            if self.wlan:
                self.wlan.disconnect()
                time.sleep(1)
            
            success = self.connect_wifi(config.WIFI_SSID, config.WIFI_PASSWORD, max_wait=15)
            if success:
                self.logger.log("WIFI", "Reconnection successful", "INFO")
            return success
        except Exception as e:
            self.logger.log("WIFI", f"Reconnect failed: {e}", "ERROR")
            return False
    
    def recover_socket(self):
        """Recover from socket errors by reinitializing"""
        try:
            if self.socket:
                self.socket.close()
                time.sleep(1)
            
            return self.initialize_server(self.port)
        except Exception as e:
            self.logger.log("SERVER", f"Socket recovery failed: {e}", "ERROR")
            return False
    
    def shutdown(self):
        if self.socket:
            self.socket.close()
            self.logger.log("SERVER", "Web server shut down.", "INFO")

    def handle_test_page(self, client_socket):
        # ... (method unchanged)
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

    def handle_sensors_page(self, client_socket):
        """Handle the sensors status page"""
        try:
            from sensors_page import create_sensors_page
            sensors_html = create_sensors_page(self.sensor_manager, self.monitor)
            self.send_response(client_socket, sensors_html)
        except Exception as e:
            self.send_response(client_socket, f"<h1>Error loading sensors page: {e}</h1>", status_code=500)
