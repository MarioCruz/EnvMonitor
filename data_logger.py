# data_logger.py - Logs sensor data to filesystem with memory optimizations
import time
import gc
import config
from utils import CircularBuffer, ensure_directory, feed_watchdog, format_datetime

class DataLogger:
    """Logs sensor data to filesystem and maintains history"""
    
    def __init__(self, monitor, logger, log_dir=config.LOG_DIRECTORY):
        """Initialize data logger
        
        Args:
            monitor: System monitor for status tracking
            logger: Logger for recording events
            log_dir: Directory for log files
        """
        self.monitor = monitor
        self.logger = logger
        self.log_dir = log_dir
        self.log_filename = f"{log_dir}/{config.SENSOR_LOG_FILE}"
        
        # Timestamp tracking
        self.last_log_time = time.time()
        self.log_interval = config.LOG_INTERVAL
        
        # Reduced history buffer (12 entries = 3 hours at 15 minute intervals)
        # This reduces memory usage compared to the original 24 entries
        self.data_history = CircularBuffer(12)
        
        # Log file parameters
        self.max_log_size = config.MAX_LOG_SIZE
        self.max_backup_files = config.MAX_LOG_FILES
        
        # Initialize log file and directory
        self._ensure_log_directory()
        self._ensure_log_file()
        
        # Load recent history from log file
        self.load_history()
    
    def _ensure_log_directory(self):
        """Create log directory if it doesn't exist"""
        ensure_directory(self.log_dir)
    
    def _ensure_log_file(self):
        """Create log file with header if it doesn't exist"""
        try:
            try:
                import os
                os.stat(self.log_filename)
            except OSError:
                with open(self.log_filename, 'w') as f:
                    f.write("DateTime,Temperature_C,Temperature_F,CO2_PPM,Humidity%,Pressure\n")
                    
                self.logger.log("LOGGER", f"Created new log file: {self.log_filename}", "INFO")
        except Exception as e:
            self.logger.log("LOGGER", "Error creating log file", "ERROR", str(e))
    
    def _rotate_logs(self):
        """Rotate log files if main log exceeds size limit
        
        Returns:
            bool: True if rotation succeeded, False otherwise
        """
        try:
            import os
            
            # Check current log size
            try:
                size = os.stat(self.log_filename)[6]
                if size < self.max_log_size:
                    return False
            except OSError:
                return False
            
            # Generate timestamp for backup filename
            t = time.localtime()
            timestamp = f"{t[0]}{t[1]:02d}{t[2]:02d}-{t[3]:02d}{t[4]:02d}"
            
            # Extract base filename without path
            base_name = self.log_filename.split('/')[-1]
            backup_name = f"{base_name}.{timestamp}"
            backup_path = f"{self.log_dir}/{backup_name}"
            
            # Rename current log to backup
            os.rename(self.log_filename, backup_path)
            
            # Create new log file with header
            self._ensure_log_file()
            
            # Clean up old backups
            self._cleanup_old_logs(base_name)
            
            self.logger.log("LOGGER", f"Rotated log file, new backup: {backup_name}", "INFO")
            return True
            
        except Exception as e:
            self.logger.log("LOGGER", "Log rotation failed", "ERROR", str(e))
            return False
    
    def _cleanup_old_logs(self, base_name):
        """Delete oldest log backups if too many exist
        
        Args:
            base_name: Base log filename
        """
        try:
            import os
            
            # List all log backup files
            backup_files = []
            for filename in os.listdir(self.log_dir):
                if filename.startswith(base_name + '.'):
                    backup_files.append(filename)
            
            # Sort files by name (includes timestamp)
            backup_files.sort()
            
            # Remove oldest files if we have too many
            while len(backup_files) > self.max_backup_files:
                oldest = backup_files.pop(0)
                try:
                    os.remove(f"{self.log_dir}/{oldest}")
                    self.logger.log("LOGGER", f"Deleted old log backup: {oldest}", "INFO")
                except OSError:
                    pass
        except Exception as e:
            self.logger.log("LOGGER", "Log cleanup error", "ERROR", str(e))
    
    def load_history(self):
        """Load recent history from log file - memory optimized version"""
        feed_watchdog()
        gc.collect()  # Free memory before operation
        
        try:
            import os
            
            # Check if file exists
            try:
                os.stat(self.log_filename)
            except OSError:
                return
            
            # Memory-efficient reading of last few lines
            with open(self.log_filename, 'r') as f:
                # Skip header
                f.readline()
                
                # Use a temporary buffer to store lines
                # Reduce to the exact number of lines we need (12)
                lines = []
                for line in f:
                    lines.append(line)
                    if len(lines) > 12:  # Reduced from 24 to 12
                        # Keep only the last lines
                        lines.pop(0)
                
                # Parse lines into history
                for line in lines:
                    try:
                        if line.strip() and not line.startswith('#'):
                            parts = line.strip().split(',')
                            # Ensure we have all fields
                            if len(parts) >= 6:
                                entry = {
                                    'timestamp': parts[0],
                                    'temp_c': float(parts[1]),
                                    'temp_f': float(parts[2]),
                                    'co2': int(parts[3]),
                                    'humidity': float(parts[4]),
                                    'pressure': float(parts[5])
                                }
                                self.data_history.append(entry)
                    except (ValueError, IndexError) as e:
                        self.logger.log("LOGGER", f"Error parsing log line: {line.strip()}", "WARNING", str(e))
                
            self.logger.log("LOGGER", f"Loaded {len(lines)} history entries", "INFO")
            
            # Free memory after operation
            del lines
            gc.collect()
                
        except Exception as e:
            self.logger.log("LOGGER", "Error loading history", "ERROR", str(e))
    
    def log_data(self, temp_c, temp_f, co2, humidity, pressure):
        """Log sensor data if interval has elapsed
        
        Args:
            temp_c: Temperature in Celsius
            temp_f: Temperature in Fahrenheit
            co2: CO2 concentration in ppm
            humidity: Relative humidity in percent
            pressure: Atmospheric pressure in hPa
            
        Returns:
            bool: True if data was logged, False otherwise
        """
        current_time = time.time()
        
        # Only log at specified interval
        if current_time - self.last_log_time < self.log_interval:
            return False
        
        # Collect garbage before writing to file
        gc.collect()
        
        try:
            # Check if we need to rotate logs
            self._rotate_logs()
            
            # Format timestamp
            timestamp = format_datetime(time.localtime())
            
            # Create data record with only necessary data
            # Storing only core values to reduce memory usage
            data = {
                'timestamp': timestamp,
                'temp_c': round(float(temp_c), 1),  # Round to reduce memory footprint
                'temp_f': round(float(temp_f), 1),
                'co2': int(co2),                    # Convert to int to save memory
                'humidity': round(float(humidity), 1),
                'pressure': round(float(pressure), 0)  # Round to integer for pressure
            }
            
            # Add to history
            self.data_history.append(data)
            
            # Write to file efficiently
            try:
                log_line = f"{timestamp},{data['temp_c']:.1f},{data['temp_f']:.1f},{data['co2']},{data['humidity']:.1f},{data['pressure']:.1f}\n"
                with open(self.log_filename, 'a') as f:
                    f.write(log_line)
            except Exception as e:
                self.logger.log("LOGGER", "Error writing to log", "ERROR", str(e))
                return False
            
            self.last_log_time = current_time
            gc.collect()  # Help manage memory
            
            # Log to console occasionally
            self.logger.log(
                "DATA", 
                f"Logged: CO2={co2}ppm, Temp={temp_c:.1f}°C, Humidity={humidity:.1f}%", 
                "INFO"
            )
            
            return True
            
        except Exception as e:
            self.logger.log("LOGGER", "Logging error", "ERROR", str(e))
            return False
    
    def get_history(self):
        """Get recent history entries
        
        Returns:
            list: Recent history entries
        """
        return self.data_history.get_all()
    
    def get_daily_statistics(self):
        """Calculate daily statistics from history - memory optimized
        
        Returns:
            dict: Daily min/max values
        """
        try:
            if not self.data_history or len(self.data_history) == 0:
                # Return defaults if no history
                return {
                    'min_temp': 20.0,
                    'max_temp': 20.0,
                    'min_co2': 800,
                    'max_co2': 800,
                    'min_humidity': 50.0,
                    'max_humidity': 50.0,
                    'min_pressure': 1013,
                    'max_pressure': 1013
                }
            
            # Process data more efficiently
            entries = self.data_history.get_all()
            
            # Extract values directly into lists for better memory usage
            temps = [entry['temp_c'] for entry in entries]
            co2s = [entry['co2'] for entry in entries]
            humidities = [entry['humidity'] for entry in entries]
            pressures = [entry['pressure'] for entry in entries]
            
            # Calculate stats
            stats = {
                'min_temp': min(temps),
                'max_temp': max(temps),
                'min_co2': min(co2s),
                'max_co2': max(co2s),
                'min_humidity': min(humidities),
                'max_humidity': max(humidities),
                'min_pressure': min(pressures),
                'max_pressure': max(pressures)
            }
            
            # Force cleanup
            del temps, co2s, humidities, pressures
            gc.collect()
            
            return stats
            
        except Exception as e:
            self.logger.log("LOGGER", "Error calculating statistics", "ERROR", str(e))
            # Return defaults on error
            return {
                'min_temp': 20.0,
                'max_temp': 20.0,
                'min_co2': 800,
                'max_co2': 800,
                'min_humidity': 50.0,
                'max_humidity': 50.0,
                'min_pressure': 1013,
                'max_pressure': 1013
            }
    
    def emergency_memory_recovery(self):
        """Reduce memory usage in low-memory situations"""
        try:
            # Clear history to minimum number of entries
            if len(self.data_history) > 4:
                # Create a new minimal buffer
                temp_data = list(self.data_history)[-4:]  # Keep only most recent 4 entries
                self.data_history = CircularBuffer(4)  # Reduce buffer size
                for entry in temp_data:
                    self.data_history.append(entry)
                
                self.logger.log("LOGGER", "Emergency memory recovery activated - history reduced", "WARNING")
                gc.collect()
                return True
            return False
        except Exception as e:
            self.logger.log("LOGGER", f"Emergency memory recovery failed: {e}", "ERROR")
            return False
    
    def get_log_status(self):
        """Get current log file status - memory optimized
        
        Returns:
            dict: Log file status information
        """
        try:
            import os
            
            try:
                stats = os.stat(self.log_filename)
                size = stats[6]  # Size in bytes
                
                return {
                    'size_kb': size / 1024,
                    'percent_full': (size / self.max_log_size) * 100,
                    'rotation_needed': size >= self.max_log_size,
                    'entries': len(self.data_history)
                }
            except OSError:
                return {
                    'size_kb': 0,
                    'percent_full': 0,
                    'rotation_needed': False,
                    'entries': 0
                }
                
        except Exception as e:
            self.logger.log("LOGGER", "Error getting log status", "ERROR", str(e))
            return {
                'size_kb': 0,
                'percent_full': 0,
                'rotation_needed': False,
                'entries': 0,
                'error': str(e)
            }