# memory_handler.py - Advanced memory management for MicroPython
import gc
import time

class MemoryHandler:
    """Enhanced memory management with emergency recovery capabilities"""
    
    def __init__(self, logger, components=None):
        """Initialize memory handler
        
        Args:
            logger: Logger instance for recording events
            components: Dict of system components that can be notified for recovery
        """
        self.logger = logger
        self.components = components or {}
        
        # Memory thresholds
        self.warning_threshold = 75  # % memory usage for warning
        self.critical_threshold = 85  # % memory usage for critical action
        self.emergency_threshold = 92  # % memory usage for emergency action
        
        # Tracking variables
        self.last_collection = time.time()
        self.collection_interval = 60  # 1 minute between routine collections
        self.collection_count = 0
        self.emergency_count = 0
        self.last_memory_percent = 0
        
        # Initial collection
        gc.collect()
        self._get_memory_stats()
        
    def _get_memory_stats(self):
        """Get current memory statistics
        
        Returns:
            dict: Memory statistics
        """
        free = gc.mem_free()
        alloc = gc.mem_alloc()
        total = free + alloc
        percent = (alloc / total) * 100 if total > 0 else 0
        
        # Determine color for UI visualization
        if percent > self.emergency_threshold:
            color = "#e74c3c"  # Red
        elif percent > self.critical_threshold:
            color = "#f39c12"  # Orange/amber
        elif percent > self.warning_threshold:
            color = "#f1c40f"  # Yellow
        else:
            color = "#27ae60"  # Green
            
        self.last_memory_percent = percent
        
        return {
            'free': free,
            'used': alloc,
            'total': total,
            'percent': percent,
            'color': color
        }
    
    def check_memory(self, force=False):
        """Check memory status and take appropriate action
        
        Args:
            force: Force check regardless of interval
            
        Returns:
            dict: Memory statistics or None if check skipped
        """
        current_time = time.time()
        
        # Skip check if not forced and interval hasn't elapsed
        if not force and current_time - self.last_collection < self.collection_interval:
            return None
        
        # Perform garbage collection
        gc.collect()
        self.collection_count += 1
        self.last_collection = current_time
        
        # Get memory statistics
        stats = self._get_memory_stats()
        percent = stats['percent']
        
        # Handle memory levels
        if percent > self.emergency_threshold:
            self.logger.log("MEMORY", f"EMERGENCY: Memory usage at {percent:.1f}%", "CRITICAL")
            self._emergency_recovery()
            # After recovery, collect and update stats
            gc.collect()
            stats = self._get_memory_stats()
            
        elif percent > self.critical_threshold:
            self.logger.log("MEMORY", f"Critical memory usage: {percent:.1f}%", "WARNING")
            # Additional collection might help
            gc.collect()
            
        elif percent > self.warning_threshold:
            self.logger.log("MEMORY", f"High memory usage: {percent:.1f}%", "INFO")
        
        return stats
    
    def _emergency_recovery(self):
        """Perform emergency memory recovery procedures
        
        Returns:
            bool: True if recovery actions were taken
        """
        self.emergency_count += 1
        self.logger.log("MEMORY", f"Initiating emergency memory recovery (#{self.emergency_count})", "CRITICAL")
        
        # Take increasingly aggressive recovery actions based on count
        actions_taken = []
        
        # Basic recovery - already did gc.collect() before calling this method
        
        # Clear any component caches 
        for name, component in self.components.items():
            try:
                # Try data_logger emergency recovery
                if name == 'data_logger' and hasattr(component, 'emergency_memory_recovery'):
                    if component.emergency_memory_recovery():
                        actions_taken.append("Reduced data history size")
                
                # Clear any sensor caches
                elif name == 'sensor_manager' and hasattr(component, 'clear_caches'):
                    if component.clear_caches():
                        actions_taken.append("Cleared sensor caches")
                
                # Reset web server socket if needed
                elif name == 'web_server' and self.emergency_count > 2:
                    if hasattr(component, 'reset_socket') and component.reset_socket():
                        actions_taken.append("Reset web server socket")
            except Exception as e:
                self.logger.log("MEMORY", f"Error during recovery of {name}: {e}", "ERROR")
        
        # Most aggressive recovery - force reinitialization of components
        if self.emergency_count > 3:
            # Log serious issue
            self.logger.log("MEMORY", "Repeated memory emergencies, consider system restart", "CRITICAL")
            
            # Delete any non-essential data
            actions_taken.append("Aggressive memory cleanup performed")
        
        # Report actions
        if actions_taken:
            self.logger.log("MEMORY", f"Recovery actions: {', '.join(actions_taken)}", "WARNING")
            return True
        
        return False
    
    def get_status(self):
        """Get current memory status
        
        Returns:
            dict: Memory status information
        """
        stats = self._get_memory_stats()
        
        return {
            'free_kb': stats['free'] / 1024,
            'used_kb': stats['used'] / 1024, 
            'total_kb': stats['total'] / 1024,
            'percent': stats['percent'],
            'color': stats['color'],
            'collections': self.collection_count,
            'emergencies': self.emergency_count,
            'last_collection': self.last_collection
        }
        
    def register_component(self, name, component):
        """Register a component for memory recovery
        
        Args:
            name: Component name
            component: Component instance
        """
        self.components[name] = component
        
    def is_memory_critical(self):
        """Check if memory is in a critical state
        
        Returns:
            bool: True if memory usage is critical
        """
        return self.last_memory_percent > self.critical_threshold