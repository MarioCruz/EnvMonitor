# sensor_manager.py - Manages sensors and readings with improved error handling
import time
import machine
import config
from utils import feed_watchdog, RetryWithBackoff, validate_sensor_reading

class SensorManager:
    """Manages sensor initialization, readings, and error handling with robust recovery"""
    
    def __init__(self, i2c, monitor, logger):
        """Initialize sensor manager
        
        Args:
            i2c: I2C interface for sensors
            monitor: System monitor for tracking errors
            logger: Logger for recording events
        """
        self.i2c = i2c
        self.monitor = monitor
        self.logger = logger
        self.scd4x = None
        self.veml7700 = None
        self.consecutive_errors = 0
        self.light_sensor_available = False
        self.light_sensor_errors = 0
        self.light_sensor_consecutive_errors = 0
        self.last_light_reset_time = 0
        self.last_good_reading = {
            'co2': 800,  # Default typical indoor CO2 level
            'temp_c': 20,
            'temp_f': 68,
            'humidity': 50,
            'pressure': 1013,  # Default pressure value in hPa
            'lux': 100.0  # Default light level
        }
        self.last_successful_read = 0
        self.min_read_interval = 5  # Minimum seconds between readings
        
        # Initialize sensors with retry logic
        self._initialize_sensor()
        self._initialize_light_sensor()
    
    def _initialize_sensor(self):
        """Initialize the CO2 sensor with reset and proper delays
        
        Returns:
            bool: True if initialized successfully, False on error
        """
        self.logger.log("SENSOR", "Initializing CO2 sensor...")
        
        # Try multiple initialization attempts
        for attempt in range(3):
            try:
                from scd4x import SCD4X
                
                # Create sensor instance
                self.scd4x = SCD4X(self.i2c)
                
                # Stop any ongoing measurements first
                try:
                    self.scd4x.stop_periodic_measurement()
                    time.sleep(1)  # Allow time for command to complete
                except Exception as e:
                    self.logger.log("SENSOR", f"Error stopping measurements: {e}", "WARNING")
                    # Continue anyway
                
                # Perform a soft reset for clean initialization
                try:
                    self._send_command(0x3646)  # SCD4X_REINIT command
                    time.sleep(2)  # Allow device to reset
                except Exception as e:
                    self.logger.log("SENSOR", f"Error during soft reset: {e}", "WARNING")
                
                # Set ambient pressure for altitude compensation
                try:
                    self.scd4x.set_ambient_pressure(1013)
                    time.sleep(0.1)  # Small delay after command
                except Exception as e:
                    self.logger.log("SENSOR", f"Error setting pressure: {e}", "WARNING")
                
                # Start periodic measurement
                self.scd4x.start_periodic_measurement()
                
                # Allow time for first measurement with timeout protection
                print("[Sensor] Waiting for sensor to be ready...")
                for wait_count in range(10):  # Max 10 seconds
                    time.sleep(1)
                    if wait_count % 2 == 0:  # Print every 2 seconds
                        print(f"[Sensor] Still waiting... ({wait_count + 1}/10)")
                
                # Test reading to ensure everything is working
                print("[Sensor] Testing sensor readings...")
                if self._test_sensor_reading():
                    self.logger.log("SENSOR", "CO2 sensor initialized successfully", "INFO")
                    print("[Sensor] ✓ Sensor is working!")
                    self.consecutive_errors = 0
                    return True
                else:
                    raise Exception("Sensor test reading failed - Check connections")
                    
            except Exception as e:
                self.logger.log("SENSOR", f"Sensor initialization attempt {attempt+1} failed: {str(e)}", "WARNING")
                
                # Clean up before retry
                self.scd4x = None
                time.sleep(2)  # Wait before retrying
                
                # Try to reset I2C bus if this isn't the first attempt
                if attempt > 0:
                    self._reset_i2c_bus()
        
        # If we get here, all attempts failed
        self.logger.log("SENSOR", "Sensor initialization failed after multiple attempts", "ERROR")
        self.monitor.record_error("Sensor Init")
        return False
    
    def _initialize_light_sensor(self):
        """Initialize the VEML7700 light sensor (optional)
        
        Returns:
            bool: True if initialized successfully, False on error
        """
        self.logger.log("SENSOR", "Initializing light sensor...")
        
        try:
            from veml7700 import VEML7700
            
            # Create light sensor instance
            self.veml7700 = VEML7700(self.i2c)
            
            # Test if sensor is responding
            if self.veml7700.is_available():
                self.light_sensor_available = True
                self.logger.log("SENSOR", "VEML7700 light sensor initialized successfully", "INFO")
                print("[Sensor] ✓ Light sensor is working!")
                return True
            else:
                raise Exception("Light sensor not responding")
                
        except Exception as e:
            self.logger.log("SENSOR", f"Light sensor initialization failed: {str(e)}", "WARNING")
            print("[Sensor] ⚠ Light sensor not available (optional)")
            self.veml7700 = None
            self.light_sensor_available = False
            return False
    
    def _reset_light_sensor(self):
        """Reset light sensor when errors occur"""
        current_time = time.time()
        
        # Prevent too frequent reset attempts
        if current_time - self.last_light_reset_time < config.VEML7700_RESET_DELAY:
            return False
            
        self.logger.log("SENSOR", "Attempting light sensor reset", "WARNING")
        self.last_light_reset_time = current_time
        
        try:
            if self.veml7700:
                # Try to reset the existing sensor
                if self.veml7700.reset_sensor():
                    self.light_sensor_consecutive_errors = 0
                    self.logger.log("SENSOR", "Light sensor reset successful", "INFO")
                    return True
            
            # If reset failed, try to reinitialize
            return self._initialize_light_sensor()
            
        except Exception as e:
            self.logger.log("SENSOR", f"Light sensor reset failed: {e}", "ERROR")
            return False
    
    def _send_command(self, cmd, cmd_delay=0):
        """Send a raw command to the sensor
        
        Args:
            cmd: Command code
            cmd_delay: Optional delay after sending
        """
        cmd_bytes = bytearray(2)
        cmd_bytes[0] = (cmd >> 8) & 0xFF
        cmd_bytes[1] = cmd & 0xFF
        self.i2c.writeto(0x62, cmd_bytes)  # Hard-coded address for simplicity
        time.sleep(0.01)  # Small delay after every command
        if cmd_delay > 0:
            time.sleep(cmd_delay)
    
    def _test_sensor_reading(self):
        """Test sensor with timeout protection for middle schoolers"""
        try:
            # Wait for data with clear feedback
            print("[Sensor] Checking if data is ready...")
            for wait_attempt in range(6):  # Max 3 seconds
                if self.scd4x.data_ready:
                    print("[Sensor] Data is ready!")
                    break
                time.sleep(0.5)
                if wait_attempt % 2 == 1:  # Print every second
                    print(f"[Sensor] Waiting for data... ({wait_attempt + 1}/6)")
            else:
                print("[Sensor] ✗ Sensor data not ready - check wiring")
                return False
            
            # Try to read with feedback
            print("[Sensor] Reading sensor values...")
            co2 = self.scd4x.CO2
            temp = self.scd4x.temperature
            humid = self.scd4x.relative_humidity
            
            print(f"[Sensor] Got readings: CO2={co2}, Temp={temp:.1f}°C, Humidity={humid:.1f}%")
            
            # Check for reasonable values
            if 300 <= co2 <= 5000 and -10 <= temp <= 60 and 0 <= humid <= 100:
                print("[Sensor] ✓ All readings look good!")
                return True
            else:
                print(f"[Sensor] ✗ Readings seem wrong - CO2 should be 300-5000, got {co2}")
                return False
            
        except Exception as e:
            print(f"[Sensor] ✗ Error reading sensor: {e}")
            self.logger.log("SENSOR", f"Sensor test failed: {e}", "WARNING")
            return False
    
    def _reset_i2c_bus(self):
        """Simplified I2C bus reset"""
        self.logger.log("SENSOR", "Resetting I2C bus", "WARNING")
        try:
            # Deinitialize current I2C
            try:
                self.i2c.deinit()
            except:
                pass
                
            time.sleep(2)  # Longer delay for stability
            
            # Recreate I2C with default config values
            self.i2c = machine.I2C(
                1, 
                scl=machine.Pin(config.I2C_SCL_PIN), 
                sda=machine.Pin(config.I2C_SDA_PIN), 
                freq=config.I2C_FREQUENCY
            )
            
            time.sleep(1)
            
            # Test if reset worked
            devices = self.i2c.scan()
            if 0x62 in devices:  # SCD4X address
                self.logger.log("SENSOR", "I2C reset successful", "INFO")
            else:
                self.logger.log("SENSOR", "I2C reset - sensor not found", "WARNING")
            
        except Exception as e:
            self.logger.log("SENSOR", f"I2C reset failed: {e}", "ERROR")
    
    @RetryWithBackoff(max_retries=2, base_delay=1)
    def reset_sensor(self):
        """Reset sensor when errors occur
        
        Returns:
            bool: True if reset successfully, False on error
        """
        self.logger.log("SENSOR", "Attempting sensor reset", "WARNING")
        try:
            # Stop measurement if sensor is active
            if self.scd4x:
                try:
                    self.scd4x.stop_periodic_measurement()
                    time.sleep(1)
                except:
                    pass
            
            # Reset I2C bus
            self._reset_i2c_bus()
            
            # Reinitialize sensor
            return self._initialize_sensor()
            
        except Exception as e:
            self.logger.log("SENSOR", "Sensor reset failed", "ERROR", str(e))
            return False
    
    def get_readings(self):
        """Get sensor readings with robust error handling and recovery
        
        Returns:
            tuple: (co2, temp_c, temp_f, humidity, pressure, lux) or None on critical failure
        """
        feed_watchdog()
        
        # Check minimum interval between reads to avoid overwhelming the sensor
        current_time = time.time()
        time_since_last = current_time - self.last_successful_read
        
        if time_since_last < self.min_read_interval and self.last_successful_read > 0:
            # Too soon since last successful read, return last good reading
            return (
                self.last_good_reading['co2'],
                self.last_good_reading['temp_c'],
                self.last_good_reading['temp_f'],
                self.last_good_reading['humidity'],
                self.last_good_reading['pressure'],
                self.last_good_reading['lux']
            )
        
        # Simplified reading with basic retry
        for attempt in range(2):  # Reduced attempts
            try:
                # Check if sensor is initialized
                if not self.scd4x:
                    if not self._initialize_sensor():
                        raise RuntimeError("Sensor not initialized")
                
                # Wait for data to be ready (simplified)
                for _ in range(6):  # Reduced wait time
                    if self.scd4x.data_ready:
                        break
                    time.sleep(0.5)
                else:
                    raise RuntimeError("Sensor data not ready")

                # Get readings from sensor
                co2 = self.scd4x.CO2
                temp_c = self.scd4x.temperature
                temp_f = (temp_c * 9/5) + 32
                humidity = self.scd4x.relative_humidity
                pressure = self.last_good_reading['pressure']
                
                # Get light reading if available with enhanced error handling
                lux = self.last_good_reading['lux']  # Default to last good reading
                if self.light_sensor_available and self.veml7700:
                    try:
                        # Use retry mechanism from enhanced driver
                        light_result = self.veml7700.get_readings_with_retry(config.VEML7700_RETRY_ATTEMPTS)
                        
                        if light_result['status'] == 'OK':
                            lux = light_result['lux']
                            self.light_sensor_consecutive_errors = 0  # Reset consecutive error count
                        else:
                            # Reading failed after retries
                            self.light_sensor_errors += 1
                            self.light_sensor_consecutive_errors += 1
                            self.logger.log("SENSOR", f"Light sensor read failed after {light_result['attempts']} attempts", "WARNING")
                            
                            # Check if we need to reset the sensor
                            if self.light_sensor_consecutive_errors >= config.VEML7700_MAX_ERRORS:
                                self.logger.log("SENSOR", f"Light sensor has {self.light_sensor_consecutive_errors} consecutive errors, attempting reset", "WARNING")
                                if self._reset_light_sensor():
                                    # Try reading again after reset
                                    try:
                                        reset_result = self.veml7700.get_readings_with_retry(1)
                                        if reset_result['status'] == 'OK':
                                            lux = reset_result['lux']
                                    except:
                                        pass  # Use last good reading
                                else:
                                    # Reset failed, mark sensor as unavailable
                                    self.light_sensor_available = False
                                    self.logger.log("SENSOR", "Light sensor reset failed, marking as unavailable", "ERROR")
                            
                    except Exception as e:
                        self.light_sensor_errors += 1
                        self.light_sensor_consecutive_errors += 1
                        self.logger.log("SENSOR", f"Light sensor critical error: {e}", "ERROR")
                
                # Basic validation
                if not (300 <= co2 <= 5000 and -10 <= temp_c <= 60 and 0 <= humidity <= 100):
                    raise ValueError(f"Invalid readings: CO2={co2}, Temp={temp_c}, Humidity={humidity}")
                
                # Validate light reading if available
                if lux is not None and not validate_sensor_reading(lux, 'light'):
                    self.logger.log("SENSOR", f"Invalid light reading: {lux} lux", "WARNING")
                    lux = self.last_good_reading['lux']  # Use last good reading

                # Success - reset error counter and update readings
                self.consecutive_errors = 0
                self.last_successful_read = current_time
                
                self.last_good_reading.update({
                    'co2': co2, 'temp_c': temp_c, 'temp_f': temp_f,
                    'humidity': humidity, 'pressure': pressure, 'lux': lux
                })
                
                return co2, temp_c, temp_f, humidity, pressure, lux

            except Exception as e:
                self.consecutive_errors += 1
                self.logger.log("SENSOR", f"Reading attempt {attempt+1} failed: {str(e)}", "WARNING")
                if attempt == 0:  # Only sleep between attempts
                    time.sleep(1)

        # All attempts failed - try sensor reset if many consecutive errors
        if self.consecutive_errors >= 5:
            self.logger.log("SENSOR", "Multiple failures, attempting sensor reset", "WARNING")
            self.reset_sensor()

        # Return last good reading
        return (
            self.last_good_reading['co2'],
            self.last_good_reading['temp_c'],
            self.last_good_reading['temp_f'],
            self.last_good_reading['humidity'],
            self.last_good_reading['pressure'],
            self.last_good_reading['lux']
        )

    def clear_caches(self):
        """Clear any caches to free memory"""
        # We don't have much to clear, but this is a hook for the memory handler
        return True
    
    def get_status(self):
        """Get sensor status information
        
        Returns:
            dict: Sensor status information
        """
        return {
            'initialized': self.scd4x is not None,
            'consecutive_errors': self.consecutive_errors,
            'last_reading': self.last_good_reading,
            'last_success': self.last_successful_read,
            'light_sensor_available': self.light_sensor_available,
            'light_sensor_errors': self.light_sensor_errors,
            'light_sensor_consecutive_errors': self.light_sensor_consecutive_errors,
            'status': "OK" if self.consecutive_errors == 0 else
                     "Warning" if self.consecutive_errors < 3 else
                     "Error" if self.consecutive_errors < 9 else "Critical"
        }