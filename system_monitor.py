# system_monitor.py - Corrected with the missing record_error method
import gc
import os
import time
from utils import feed_watchdog

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

class SystemMonitor:
    def __init__(self, logger):
        self.logger = logger
        self.start_time = time.time()
        self.total_measurements = 0
        self.failed_measurements = 0
        self.health_stats = {
            'uptime': 0,
            'memory_percent': 0,
            'memory_used': 0,
            'storage_percent': 0,
            'cpu_temp': 0,
            'device_model': 'Unknown'
        }
        self.check_system_health()
    
    def record_error(self, component_name="Unknown"):
        """Record a system error"""
        self.failed_measurements += 1

    def get_device_model(self):
        """Gets the board model name from os.uname()."""
        try:
            model_string = os.uname().machine
            if "Pico W" in model_string:
                return "Raspberry Pi Pico W"
            else:
                return model_string.split(" with ")[0]
        except Exception:
            return "Unknown"

    def get_cpu_temperature(self):
        """Get CPU temperature if available"""
        try:
            import machine
            sensor_temp = machine.ADC(4)
            conversion_factor = 3.3 / 65535
            reading = sensor_temp.read_u16() * conversion_factor
            return 27 - (reading - 0.706) / 0.001721
        except:
            return 0

    def check_system_health(self):
        """System health check with basic monitoring"""
        feed_watchdog()
        try:
            gc.collect()
            mem_free, mem_alloc = gc.mem_free(), gc.mem_alloc()
            mem_total = mem_free + mem_alloc
            mem_percent = (mem_alloc / mem_total) * 100 if mem_total > 0 else 0
            
            # Log memory warnings
            if mem_percent > 85:
                self.logger.log("MEMORY", f"Critical memory usage: {mem_percent:.1f}%", "WARNING")
            elif mem_percent > 75:
                self.logger.log("MEMORY", f"High memory usage: {mem_percent:.1f}%", "INFO")
            
            # Simplified storage check
            try:
                s = os.statvfs('/')
                storage_total = s[0] * s[2]
                storage_free = s[0] * s[3]
                storage_percent = ((storage_total - storage_free) / storage_total) * 100
                
                if storage_percent > 90:
                    self.logger.log("STORAGE", f"Critical storage: {storage_percent:.1f}%", "WARNING")
            except:
                storage_percent = 0

            self.health_stats.update({
                'uptime': time.time() - self.start_time,
                'memory_percent': mem_percent,
                'memory_used': mem_alloc,
                'storage_percent': storage_percent,
                'device_model': self.get_device_model()
            })
            return self.health_stats
        except Exception as e:
            self.logger.log("SYSTEM", f"Health check error: {e}", "ERROR")
            return self.health_stats