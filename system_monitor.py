# system_monitor.py - Monitors system health and status
import gc
import os
import time
from utils import feed_watchdog

# Define format_uptime locally to avoid import issues
def format_uptime(seconds):
    """Convert seconds to days, hours, minutes, seconds"""
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

class SystemMonitor:
    """Monitors system health, performance, and maintains stats"""
    
    def __init__(self, logger):
        """Initialize system monitor
        
        Args:
            logger: Logger for recording events
        """
        self.logger = logger
        self.start_time = time.time()
        self.last_check = time.time()
        self.last_error_reset = time.time()
        
        # Initialize measurement counters
        self.total_measurements = 0
        self.failed_measurements = 0
        
        # Initialize error tracking
        self.error_counts = {}
        self.error_reset_interval = 3600  # Reset error counts hourly
        
        # System health metrics
        self.health_stats = {
            'uptime': 0,
            'memory_free': 0,
            'memory_used': 0,
            'memory_total': 0,
            'memory_percent': 0,
            'storage_free': 0,
            'storage_used': 0,
            'storage_total': 0,
            'storage_percent': 0,
            'cpu_temp': 0,
            'refresh_rate': 30,  # Default refresh rate in seconds
            'last_update': time.time()
        }
        
        # Initialize daily stats
        self.daily_stats = {
            'min_temp': float('inf'),
            'max_temp': float('-inf'),
            'min_co2': float('inf'),
            'max_co2': float('-inf'),
            'min_humidity': float('inf'),
            'max_humidity': float('-inf'),
            'min_pressure': float('inf'),
            'max_pressure': float('-inf'),
            'last_reset': time.localtime()[2]  # day of month
        }
        
        # Initial health check
        self.check_system_health()
        
        self.logger.log("SYSTEM", "System monitor initialized", "INFO")
    
    def get_uptime(self):
        """Get system uptime in seconds
        
        Returns:
            float: Uptime in seconds
        """
        return time.time() - self.start_time
    
    def get_memory_usage(self):
        """Get memory usage statistics
        
        Returns:
            dict: Memory usage statistics
        """
        # Force garbage collection for accurate readings
        gc.collect()
        
        free_mem = gc.mem_free()
        allocated_mem = gc.mem_alloc()
        total_mem = free_mem + allocated_mem
        percent_used = (allocated_mem / total_mem) * 100 if total_mem > 0 else 0
        
        # Determine color for UI based on usage
        if percent_used > 90:
            color = "#e74c3c"  # Red
        elif percent_used > 75:
            color = "#f39c12"  # Orange
        else:
            color = "#27ae60"  # Green
        
        return {
            'free': free_mem,
            'used': allocated_mem,
            'total': total_mem,
            'percent': percent_used,
            'color': color
        }
    
    def get_storage_info(self):
        """Get storage information
        
        Returns:
            dict: Storage statistics
        """
        try:
            stat = os.statvfs('/')
            block_size = stat[0]
            total_blocks = stat[2]
            free_blocks = stat[3]
            
            total = block_size * total_blocks
            free = block_size * free_blocks
            used = total - free
            percent_used = (used / total) * 100 if total > 0 else 0
            
            # Determine color for UI based on usage
            if percent_used > 90:
                color = "#e74c3c"  # Red
            elif percent_used > 75:
                color = "#f39c12"  # Orange
            else:
                color = "#27ae60"  # Green
            
            return {
                'free': free,
                'used': used,
                'total': total,
                'percent': percent_used,
                'color': color
            }
        except Exception as e:
            self.logger.log("SYSTEM", "Storage info error", "ERROR", str(e))
            # Return defaults on error
            return {
                'free': 0,
                'used': 0,
                'total': 1,
                'percent': 0,
                'color': "#e74c3c"
            }
    
    def get_cpu_temperature(self):
        """Get CPU temperature if available
        
        Returns:
            float: CPU temperature in Celsius or 0 if unavailable
        """
        try:
            # Try to read internal temperature sensor if available
            # This is hardware-dependent and may not work on all Pico boards
            try:
                import machine
                # Try Pico W internal temperature sensor
                temp_sensor = machine.ADC(4)
                # Calculate CPU temperature (see Pico datasheet)
                conv_factor = 3.3 / (65535)
                reading = temp_sensor.read_u16() * conv_factor
                cpu_temp = 27 - (reading - 0.706) / 0.001721
                return cpu_temp
            except:
                return 0
        except:
            return 0
    
    def update_daily_stats(self, temp, co2, humidity, pressure=None):
        """Update daily min/max statistics
        
        Args:
            temp: Temperature in Celsius
            co2: CO2 concentration in ppm
            humidity: Relative humidity in percent
            pressure: Atmospheric pressure in hPa
        """
        # Check if day has changed and reset stats if needed
        current_day = time.localtime()[2]
        if current_day != self.daily_stats['last_reset']:
            # Reset stats for new day
            self.daily_stats = {
                'min_temp': temp,
                'max_temp': temp,
                'min_co2': co2,
                'max_co2': co2,
                'min_humidity': humidity,
                'max_humidity': humidity,
                'min_pressure': pressure if pressure is not None else 1013,
                'max_pressure': pressure if pressure is not None else 1013,
                'last_reset': current_day
            }
            self.logger.log("SYSTEM", "Daily statistics reset for new day", "INFO")
        else:
            # Update min/max values
            if not isinstance(temp, str):  # Ensure values are not strings
                self.daily_stats['min_temp'] = min(self.daily_stats['min_temp'], temp)
                self.daily_stats['max_temp'] = max(self.daily_stats['max_temp'], temp)
            
            if not isinstance(co2, str):
                self.daily_stats['min_co2'] = min(self.daily_stats['min_co2'], co2)
                self.daily_stats['max_co2'] = max(self.daily_stats['max_co2'], co2)
            
            if not isinstance(humidity, str):
                self.daily_stats['min_humidity'] = min(self.daily_stats['min_humidity'], humidity)
                self.daily_stats['max_humidity'] = max(self.daily_stats['max_humidity'], humidity)
            
            if pressure is not None and not isinstance(pressure, str):
                self.daily_stats['min_pressure'] = min(self.daily_stats['min_pressure'], pressure)
                self.daily_stats['max_pressure'] = max(self.daily_stats['max_pressure'], pressure)
    
    def record_error(self, error_location):
        """Record errors by location and track consecutive errors
        
        Args:
            error_location: Source of the error
        """
        # Reset error counts if interval has passed
        current_time = time.time()
        if current_time - self.last_error_reset > self.error_reset_interval:
            self.error_counts = {}
            self.last_error_reset = current_time
        
        # Update counter for this error location
        if error_location in self.error_counts:
            self.error_counts[error_location] += 1
        else:
            self.error_counts[error_location] = 1
        
        # Log critical errors
        if self.error_counts[error_location] >= 3:
            self.logger.log(
                "SYSTEM", 
                f"Critical error: {error_location} ({self.error_counts[error_location]} consecutive errors)", 
                "CRITICAL"
            )
    
    def update_measurement_stats(self, success=True):
        """Update measurement statistics
        
        Args:
            success: Whether measurement was successful
        """
        self.total_measurements += 1
        if not success:
            self.failed_measurements += 1
    
    def check_system_health(self):
        """Check overall system health
        
        Returns:
            dict: System health statistics
        """
        feed_watchdog()
        
        try:
            # Update statistics
            self.health_stats.update({
                'uptime': self.get_uptime(),
                'cpu_temp': self.get_cpu_temperature(),
                'total_measurements': self.total_measurements,
                'failed_measurements': self.failed_measurements,
                'last_update': time.time()
            })
            
            # Update memory statistics
            memory_stats = self.get_memory_usage()
            self.health_stats.update({
                'memory_free': memory_stats['free'],
                'memory_used': memory_stats['used'],
                'memory_total': memory_stats['total'],
                'memory_percent': memory_stats['percent'],
                'memory_color': memory_stats['color']
            })
            
            # Update storage statistics
            storage_stats = self.get_storage_info()
            self.health_stats.update({
                'storage_free': storage_stats['free'],
                'storage_used': storage_stats['used'],
                'storage_total': storage_stats['total'],
                'storage_percent': storage_stats['percent'],
                'storage_color': storage_stats['color']
            })
            
            # Issue warnings for high memory usage
            if memory_stats['percent'] > 90:
                self.logger.log("SYSTEM", f"Critical memory usage: {memory_stats['percent']:.1f}%", "CRITICAL")
                gc.collect()  # Force garbage collection
            elif memory_stats['percent'] > 75:
                self.logger.log("SYSTEM", f"High memory usage: {memory_stats['percent']:.1f}%", "WARNING")
            
            # Issue warnings for high storage usage
            if storage_stats['percent'] > 90:
                self.logger.log("SYSTEM", f"Critical storage usage: {storage_stats['percent']:.1f}%", "CRITICAL")
            elif storage_stats['percent'] > 75:
                self.logger.log("SYSTEM", f"High storage usage: {storage_stats['percent']:.1f}%", "WARNING")
            
            return self.health_stats
            
        except Exception as e:
            self.logger.log("SYSTEM", "Error checking system health", "ERROR", str(e))
            return self.health_stats