# sensor_manager.py - Manages sensors and readings with improved error handling
import time
import machine
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
        self.consecutive_errors = 0
        self.last_good_reading = {
            'co2': 800,  # Default typical indoor CO2 level
            'temp_c': 20,
            'temp_f': 68,
            'humidity': 50,
            'pressure': 1013  # Default pressure value in hPa
        }
        self.last_successful_read = 0
        self.min_read_interval = 5  # Minimum seconds between readings
        
        # Initialize sensor with retry logic
        self._initialize_sensor()
    
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
                
                # Allow sufficient time for first measurement (essential!)
                time.sleep(5)
                
                # Test reading to ensure everything is working
                if self._test_sensor_reading():
                    self.logger.log("SENSOR", "CO2 sensor initialized successfully", "INFO")
                    self.consecutive_errors = 0
                    return True
                else:
                    raise Exception("Sensor test reading failed")
                    
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
        """Test if we can successfully read from the sensor
        
        Returns:
            bool: True if reading succeeded
        """
        try:
            # Ensure data is ready
            for _ in range(10):  # Try for up to 5 seconds
                if self.scd4x.data_ready:
                    break
                time.sleep(0.5)
            
            # Try to read
            co2 = self.scd4x.CO2
            temp = self.scd4x.temperature
            humid = self.scd4x.relative_humidity
            
            # Check for reasonable values
            if 300 <= co2 <= 5000 and -10 <= temp <= 60 and 0 <= humid <= 100:
                return True
            return False
            
        except Exception as e:
            self.logger.log("SENSOR", f"Sensor test reading failed: {e}", "WARNING")
            return False
    
    def _reset_i2c_bus(self):
        """Reset the I2C bus when communication fails"""
        self.logger.log("SENSOR", "Resetting I2C bus", "WARNING")
        try:
            # Try to deinitialize I2C
            try:
                self.i2c.deinit()
            except:
                pass
                
            # Small delay
            time.sleep(1)
            
            # Recreate I2C with same parameters
            pins = self.i2c._pins if hasattr(self.i2c, '_pins') else None
            freq = getattr(self.i2c, '_freq', 100000)
            
            if pins:
                scl_pin, sda_pin = pins
            else:
                # Fallback to default pins from config
                scl_pin = machine.Pin(27)
                sda_pin = machine.Pin(26)
            
            # Recreate with reduced frequency and explicit buffer size
            self.i2c = machine.I2C(1, scl=scl_pin, sda=sda_pin, freq=freq, bufsize=64)
            
            # Enable internal pullups on pins
            scl_pin.init(machine.Pin.PULL_UP)
            sda_pin.init(machine.Pin.PULL_UP)
            
            time.sleep(0.5)
            
            # Scan to see if devices are present
            devices = self.i2c.scan()
            self.logger.log("SENSOR", f"I2C reset complete. Devices found: {[hex(d) for d in devices]}")
            
        except Exception as e:
            self.logger.log("SENSOR", f"I2C bus reset failed: {e}", "ERROR")
    
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
            tuple: (co2, temp_c, temp_f, humidity, pressure) or None on critical failure
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
                self.last_good_reading['pressure']
            )
        
        # Try to get readings with multiple attempts
        for attempt in range(3):
            try:
                # Check if sensor is initialized
                if not self.scd4x:
                    if attempt == 0:  # Only try to initialize on first attempt
                        if not self._initialize_sensor():
                            raise RuntimeError("Sensor not initialized")
                    else:
                        raise RuntimeError("Sensor not initialized")
                
                # Wait for data to be ready with timeout
                data_ready = False
                for _ in range(10):  # Try for up to 5 seconds
                    if self.scd4x.data_ready:
                        data_ready = True
                        break
                    time.sleep(0.5)
                
                if not data_ready:
                    raise RuntimeError("Sensor data not ready")

                # Get readings from sensor
                co2 = self.scd4x.CO2
                temp_c = self.scd4x.temperature
                temp_f = (temp_c * 9/5) + 32
                humidity = self.scd4x.relative_humidity
                pressure = self.last_good_reading['pressure']  # Use default pressure
                
                # Validate readings using utility function
                if not validate_sensor_reading(co2, 'co2'):
                    raise ValueError(f"Invalid CO2 reading: {co2}")
                if not validate_sensor_reading(temp_c, 'temperature'):
                    raise ValueError(f"Invalid temperature reading: {temp_c}")
                if not validate_sensor_reading(humidity, 'humidity'):
                    raise ValueError(f"Invalid humidity reading: {humidity}")

                # Reset error counter on successful reading
                self.consecutive_errors = 0
                self.last_successful_read = current_time
                
                # Update last good reading
                self.last_good_reading = {
                    'co2': co2,
                    'temp_c': temp_c,
                    'temp_f': temp_f,
                    'humidity': humidity,
                    'pressure': pressure
                }
                
                return co2, temp_c, temp_f, humidity, pressure

            except Exception as e:
                self.consecutive_errors += 1
                self.monitor.record_error("Sensor Reading")
                self.logger.log("SENSOR", f"Reading error: {str(e)}", "ERROR")
                
                # Sleep between attempts
                time.sleep(1 * (attempt + 1))
                
                # On second attempt, try to reset data_ready
                if attempt == 1:
                    try:
                        # Try to read measurement without checking data_ready
                        self._send_command(0xEC05, cmd_delay=0.001)  # SCD4X_READMEASUREMENT
                        time.sleep(0.5)
                    except:
                        pass

        # If we got here, all attempts failed
        
        # Attempt recovery if multiple consecutive errors
        if self.consecutive_errors >= 3 and self.consecutive_errors % 3 == 0:
            # Try to reset sensor every 3 errors
            recovery_successful = self.reset_sensor()
            if not recovery_successful and self.consecutive_errors >= 9:
                # If reset failed and we've had many errors, report critical error
                self.logger.log("SENSOR", "Sensor recovery failed after multiple attempts", "CRITICAL")
                
                # Emergency I2C bus reset
                if self.consecutive_errors >= 12:
                    self._reset_i2c_bus()

        # Return last good reading when error occurs
        return (
            self.last_good_reading['co2'],
            self.last_good_reading['temp_c'],
            self.last_good_reading['temp_f'],
            self.last_good_reading['humidity'],
            self.last_good_reading['pressure']
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
            'status': "OK" if self.consecutive_errors == 0 else 
                     "Warning" if self.consecutive_errors < 3 else 
                     "Error" if self.consecutive_errors < 9 else "Critical"
        }