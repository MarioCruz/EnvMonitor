# veml7700.py - Driver for VEML7700 Ambient Light Sensor
import time
import config

class VEML7700:
    """Driver for VEML7700 Ambient Light Sensor."""
    # ALS Command Register Bits (Register 0x00)
    ALS_SD_MASK = 0x01 # ALS shut down setting (0=on, 1=off)
    ALS_INT_EN_MASK = 0x02 # ALS interrupt enable setting
    ALS_PERS_MASK = 0x0C # ALS persistence protect number setting
    ALS_IT_MASK = 0xF0 # ALS integration time setting
    ALS_GAIN_MASK = 0x1800 # ALS gain setting (within word for reg 0x00)

    # Default configuration: ALS ON, Int Off, Pers 1, IT 100ms, Gain x1
    # Config word = 0x0010 (Gain=x1, IT=100ms, Pers=1, Int=off, SD=off)
    DEFAULT_CONFIG = 0x0010

    # Resolution factor based on IT and Gain (from datasheet)
    # This needs to match the DEFAULT_CONFIG !!
    # For IT=100ms, Gain=x1, the resolution is 0.0576 lux/count
    DEFAULT_RESOLUTION = 0.0576

    def __init__(self, i2c, addr=None):
        # Use safe defaults if config is not available
        try:
            default_addr = config.VEML7700_I2C_ADDR
            delay_ms = config.VEML7700_CONFIG_DELAY_MS
        except (NameError, AttributeError):
            default_addr = 0x10  # Standard VEML7700 address
            delay_ms = 100  # Safe default delay
            
        print(f"VEML7700: Initializing at address {hex(addr or default_addr)}...")
        self.i2c = i2c
        self.addr = addr if addr is not None else default_addr
        self._resolution = self.DEFAULT_RESOLUTION # Store resolution for current config

        try:
            # Apply default configuration
            config_bytes = self.DEFAULT_CONFIG.to_bytes(2, 'little')
            self.i2c.writeto_mem(self.addr, 0x00, config_bytes)
            print(f"VEML7700: Configured with {hex(self.DEFAULT_CONFIG)}")
            time.sleep(delay_ms / 1000.0) # Short delay after config write
        except OSError as e:
            print(f"VEML7700: I2C Error during initialization: {e}")
            raise # Re-raise error

    @property
    def lux(self):
        """Reads ambient light in lux."""
        try:
            # Read ALS data from register 0x04 (2 bytes, little-endian)
            data = self.i2c.readfrom_mem(self.addr, 0x04, 2)
            als_raw = int.from_bytes(data, 'little')

            # Apply resolution factor based on current configuration
            calculated_lux = als_raw * self._resolution
            
            # Apply calibration if enabled
            calibrated_lux = self._apply_calibration(calculated_lux)
            
            # print(f"VEML7700 Raw ALS: {als_raw}, Calculated Lux: {calculated_lux:.2f}, Calibrated: {calibrated_lux:.2f}") # Debug print
            return calibrated_lux
        except OSError as e:
            print(f"VEML7700: Error reading LUX data: {e}")
            return None # Return None on read error
        except Exception as e:
            print(f"VEML7700: Unexpected error reading LUX: {e}")
            return None

    def get_readings(self):
        """Get light sensor readings in a consistent format."""
        lux_value = self.lux
        if lux_value is not None:
            return {
                'lux': round(lux_value, 2),
                'status': 'OK'
            }
        else:
            return {
                'lux': 0.0,
                'status': 'ERROR'
            }

    def is_available(self):
        """Check if the sensor is available and responding."""
        try:
            # Try to read from the sensor
            data = self.i2c.readfrom_mem(self.addr, 0x04, 2)
            return True
        except OSError:
            return False
        except Exception:
            return False
    
    def reset_sensor(self):
        """Reset the sensor configuration"""
        try:
            print("VEML7700: Attempting sensor reset...")
            # Reconfigure with default settings
            config_bytes = self.DEFAULT_CONFIG.to_bytes(2, 'little')
            self.i2c.writeto_mem(self.addr, 0x00, config_bytes)
            # Use a safe default delay if config is not available
            try:
                delay_ms = config.VEML7700_CONFIG_DELAY_MS
            except (NameError, AttributeError):
                delay_ms = 100  # Safe default
            time.sleep(delay_ms / 1000.0)
            print("VEML7700: Reset successful")
            return True
        except Exception as e:
            print(f"VEML7700: Reset failed: {e}")
            return False
    
    def get_readings_with_retry(self, max_retries=3):
        """Get light readings with retry mechanism"""
        for attempt in range(max_retries):
            try:
                lux_value = self.lux
                if lux_value is not None:
                    return {
                        'lux': round(lux_value, 2),
                        'status': 'OK',
                        'attempts': attempt + 1
                    }
            except Exception as e:
                print(f"VEML7700: Read attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.1)  # Brief delay before retry
                    
        # All attempts failed
        return {
            'lux': 0.0,
            'status': 'ERROR',
            'attempts': max_retries
        }
    
    def _apply_calibration(self, raw_lux):
        """Apply calibration settings to raw lux reading"""
        try:
            # Check if calibration is enabled
            if not getattr(config, 'LIGHT_CALIBRATION_ENABLED', True):
                return raw_lux
            
            # Apply calibration formula: (raw * multiplier) + offset
            multiplier = getattr(config, 'LIGHT_CALIBRATION_MULTIPLIER', 1.0)
            offset = getattr(config, 'LIGHT_CALIBRATION_OFFSET', 0.0)
            
            calibrated = (raw_lux * multiplier) + offset
            
            # Apply min/max limits
            min_lux = getattr(config, 'LIGHT_CALIBRATION_MIN_LUX', 0.0)
            max_lux = getattr(config, 'LIGHT_CALIBRATION_MAX_LUX', 65535.0)
            
            # Clamp to valid range
            calibrated = max(min_lux, min(calibrated, max_lux))
            
            return calibrated
            
        except Exception as e:
            print(f"VEML7700: Calibration error: {e}")
            return raw_lux  # Return uncalibrated value on error
    
    def get_calibration_info(self):
        """Get current calibration settings"""
        try:
            return {
                'enabled': getattr(config, 'LIGHT_CALIBRATION_ENABLED', True),
                'offset': getattr(config, 'LIGHT_CALIBRATION_OFFSET', 0.0),
                'multiplier': getattr(config, 'LIGHT_CALIBRATION_MULTIPLIER', 1.0),
                'min_lux': getattr(config, 'LIGHT_CALIBRATION_MIN_LUX', 0.0),
                'max_lux': getattr(config, 'LIGHT_CALIBRATION_MAX_LUX', 65535.0)
            }
        except Exception as e:
            print(f"VEML7700: Error getting calibration info: {e}")
            return {'error': str(e)}