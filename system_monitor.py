# system_monitor.py - Monitors system health and status
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
        """Check overall system health"""
        feed_watchdog()
        try:
            gc.collect()
            mem_free, mem_alloc = gc.mem_free(), gc.mem_alloc()
            mem_total = mem_free + mem_alloc
            mem_percent = (mem_alloc / mem_total) * 100 if mem_total > 0 else 0
            
            s = os.statvfs('/')
            storage_total = s[0] * s[2]
            storage_free = s[0] * s[3]
            storage_used = storage_total - storage_free
            storage_percent = (storage_used / storage_total) * 100 if storage_total > 0 else 0

            self.health_stats.update({
                'uptime': time.time() - self.start_time,
                'cpu_temp': self.get_cpu_temperature(),
                'total_measurements': self.total_measurements,
                'failed_measurements': self.failed_measurements,
                'device_model': self.get_device_model(),
                'memory_percent': mem_percent,
                'memory_used': mem_alloc,
                'storage_percent': storage_percent,
            })
            return self.health_stats
        except Exception as e:
            self.logger.log("SYSTEM", f"Error checking system health: {e}", "ERROR")
            return self.health_stats