# scd4x.py - Enhanced SCD4X CO2 sensor driver with improved reliability
from machine import I2C
import time
import struct
from micropython import const
import config

# Constants for SCD4X
SCD4X_DEFAULT_ADDR = const(0x62)

# Command registers
_SCD4X_REINIT = const(0x3646)
_SCD4X_FACTORYRESET = const(0x3632)
_SCD4X_FORCEDRECAL = const(0x362F)
_SCD4X_SELFTEST = const(0x3639)
_SCD4X_DATAREADY = const(0xE4B8)
_SCD4X_STOPPERIODICMEASUREMENT = const(0x3F86)
_SCD4X_STARTPERIODICMEASUREMENT = const(0x21B1)
_SCD4X_STARTLOWPOWERPERIODICMEASUREMENT = const(0x21AC)
_SCD4X_READMEASUREMENT = const(0xEC05)
_SCD4X_SERIALNUMBER = const(0x3682)
_SCD4X_GETTEMPOFFSET = const(0x2318)
_SCD4X_SETTEMPOFFSET = const(0x241D)
_SCD4X_GETALTITUDE = const(0x2322)
_SCD4X_SETALTITUDE = const(0x2427)
_SCD4X_SETPRESSURE = const(0xE000)
_SCD4X_PERSISTSETTINGS = const(0x3615)
_SCD4X_GETASCE = const(0x2313)
_SCD4X_SETASCE = const(0x2416)
_SCD4X_MEASURESINGLESHOT = const(0x219D)
_SCD4X_MEASURESINGLESHOTRHTONLY = const(0x2196)

class SCD4X:
    """Driver for Sensirion SCD4X CO2 sensor with enhanced error handling"""
    
    def __init__(self, i2c, address=None):
        """Initialize the SCD4X CO2 sensor
        
        Args:
            i2c: I2C bus instance
            address: Optional I2C address override
        """
        print("[SCD4X] Initializing SCD4X CO2 sensor")
        self.i2c = i2c
        self.address = address if address is not None else config.SCD4X_I2C_ADDR
        self._buffer = bytearray(18)
        self._cmd = bytearray(2)
        self._crc_buffer = bytearray(2)

        self._temperature = None
        self._relative_humidity = None
        self._co2 = None
        self._pressure = config.SENSOR_PRESSURE

        # Add delay before first command
        time.sleep(config.SENSOR_RETRY_DELAY)
        
        self._init_sensor()
        
    def _init_sensor(self):
        """Initialize the sensor with proper error handling"""
        for attempt in range(3):  # Try up to 3 times
            try:
                print(f"[SCD4X] Initialization attempt {attempt+1}/3")
                
                # Try to stop any ongoing measurements
                try:
                    self.stop_periodic_measurement()
                except OSError as e:
                    print(f"[SCD4X] Initial stop measurement failed: {e}")
                    self._soft_reset()
                    time.sleep(config.SENSOR_RETRY_DELAY)
                    self.stop_periodic_measurement()
                
                # Configure sensor with settings from config
                if self.initialize_with_config():
                    print("[SCD4X] Sensor initialized successfully")
                    return True
            except Exception as e:
                print(f"[SCD4X] Initialization error: {e}")
                if attempt < 2:  # Don't sleep after last attempt
                    time.sleep(config.SENSOR_RETRY_DELAY)
                    
        print("[SCD4X] Failed to initialize after multiple attempts")
        return False

    def _soft_reset(self):
        """Perform a soft reset of the sensor"""
        try:
            print("[SCD4X] Performing soft reset")
            self._send_command(_SCD4X_REINIT, cmd_delay=0.02)
        except Exception as e:
            print(f"[SCD4X] Soft reset error: {e}")
        time.sleep(config.SENSOR_RETRY_DELAY)

    def _send_command(self, cmd, cmd_delay=0):
        """Send command to the sensor with retry logic
        
        Args:
            cmd: Command code
            cmd_delay: Delay after sending command
        """
        retry_count = config.MAX_CONSECUTIVE_ERRORS
        while retry_count > 0:
            try:
                self._cmd[0] = (cmd >> 8) & 0xFF
                self._cmd[1] = cmd & 0xFF
                self.i2c.writeto(self.address, self._cmd)
                time.sleep(0.01)  # Small delay after I2C operation
                if cmd_delay > 0:
                    time.sleep(cmd_delay)
                return
            except OSError as e:
                retry_count -= 1
                if retry_count == 0:
                    print(f"[SCD4X] Command failed after retries: {e}")
                    raise e
                print(f"[SCD4X] Command retry after error")
                time.sleep(config.SENSOR_RETRY_DELAY)

    def _set_command_value(self, cmd, value, cmd_delay=0):
        """Send command with value to the sensor
        
        Args:
            cmd: Command code
            value: Value to send
            cmd_delay: Delay after sending command
        """
        retry_count = config.MAX_CONSECUTIVE_ERRORS
        while retry_count > 0:
            try:
                self._buffer[0] = (cmd >> 8) & 0xFF
                self._buffer[1] = cmd & 0xFF
                self._crc_buffer[0] = self._buffer[2] = (value >> 8) & 0xFF
                self._crc_buffer[1] = self._buffer[3] = value & 0xFF
                self._buffer[4] = self._crc8(self._crc_buffer)
                self.i2c.writeto(self.address, self._buffer[:5])
                time.sleep(0.01)  # Small delay after I2C operation
                if cmd_delay > 0:
                    time.sleep(cmd_delay)
                return
            except OSError as e:
                retry_count -= 1
                if retry_count == 0:
                    print(f"[SCD4X] Command with value failed: {e}")
                    raise e
                print(f"[SCD4X] Command with value retry")
                time.sleep(config.SENSOR_RETRY_DELAY)

    def _read_reply(self, num):
        """Read reply from the sensor
        
        Args:
            num: Number of bytes to read
        """
        retry_count = config.MAX_CONSECUTIVE_ERRORS
        while retry_count > 0:
            try:
                read_data = self.i2c.readfrom(self.address, num)
                for i in range(num):
                    self._buffer[i] = read_data[i]
                self._check_buffer_crc(self._buffer[:num])
                return
            except OSError as e:
                retry_count -= 1
                if retry_count == 0:
                    print(f"[SCD4X] Read reply failed: {e}")
                    raise e
                print(f"[SCD4X] Read reply retry")
                time.sleep(config.SENSOR_RETRY_DELAY)

    def _check_buffer_crc(self, buf):
        """Check CRC of received data"""
        for i in range(0, len(buf), 3):
            if i+2 < len(buf) and self._crc8(buf[i:i+2]) != buf[i+2]:
                raise RuntimeError("CRC check failed")

    @staticmethod
    def _crc8(buffer):
        """Calculate CRC-8 checksum"""
        crc = 0xFF
        for byte in buffer:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = (crc << 1) ^ 0x31
                else:
                    crc <<= 1
        return crc & 0xFF

    def stop_periodic_measurement(self):
        """Stop periodic measurement."""
        self._send_command(_SCD4X_STOPPERIODICMEASUREMENT, cmd_delay=0.5)

    def start_periodic_measurement(self):
        """Start periodic measurement."""
        self._send_command(_SCD4X_STARTPERIODICMEASUREMENT)
        time.sleep(1)

    def get_temperature_offset(self):
        """Get the current temperature offset in degrees C."""
        self._send_command(_SCD4X_GETTEMPOFFSET, cmd_delay=0.001)
        self._read_reply(3)
        temp_offset_raw = struct.unpack_from(">H", self._buffer[0:2])[0]
        return temp_offset_raw * 175.0 / 65535.0

    def set_temperature_offset(self, offset_c):
        """Set temperature offset in degrees C."""
        if offset_c < 0 or offset_c > 175:
            raise ValueError("Offset must be between 0 and 175 degrees C")
        offset_raw = int(offset_c * 65535 / 175)
        self._set_command_value(_SCD4X_SETTEMPOFFSET, offset_raw)

    @property
    def data_ready(self):
        """Check if data is ready to be read."""
        try:
            self._send_command(_SCD4X_DATAREADY, cmd_delay=0.001)
            self._read_reply(3)
            return not ((self._buffer[0] & 0x07 == 0) and (self._buffer[1] == 0))
        except Exception as e:
            print(f"[SCD4X] Error checking data ready: {e}")
            return False

    def _read_data(self):
        """Internal method to read sensor data."""
        retry_count = config.MAX_CONSECUTIVE_ERRORS
        while retry_count > 0:
            try:
                self._send_command(_SCD4X_READMEASUREMENT, cmd_delay=0.001)
                self._read_reply(9)
                
                self._co2 = struct.unpack_from(">H", self._buffer[0:2])[0]
                temp_raw = struct.unpack_from(">H", self._buffer[3:5])[0]

                if temp_raw == 0:
                    self._temperature = -45
                elif temp_raw == 65535:
                    self._temperature = 130
                else:
                    self._temperature = -45 + 175 * (temp_raw / 65535)

                # Apply temperature offset from config
                self._temperature += config.TEMP_OFFSET

                humi_raw = struct.unpack_from(">H", self._buffer[6:8])[0]
                self._relative_humidity = 100 * (humi_raw / 65535)

                # Validate readings
                if not self._validate_readings():
                    raise ValueError("Readings outside valid ranges")

                return
            except Exception as e:
                retry_count -= 1
                if retry_count == 0:
                    print(f"[SCD4X] Error reading data: {e}")
                    raise
                print("[SCD4X] Retrying data read")
                time.sleep(config.SENSOR_RETRY_DELAY)

    def _validate_readings(self):
        """Validate all sensor readings against config ranges."""
        return (
            config.VALID_CO2_RANGE[0] <= self._co2 <= config.VALID_CO2_RANGE[1] and
            config.VALID_TEMP_RANGE[0] <= self._temperature <= config.VALID_TEMP_RANGE[1] and
            config.VALID_HUMIDITY_RANGE[0] <= self._relative_humidity <= config.VALID_HUMIDITY_RANGE[1]
        )

    @property
    def CO2(self):
        """Get CO2 measurement in ppm."""
        if self.data_ready:
            self._read_data()
        return self._co2

    @property
    def temperature(self):
        """Get temperature in degrees Celsius."""
        if self.data_ready:
            self._read_data()
        return self._temperature

    @property
    def relative_humidity(self):
        """Get relative humidity in percent."""
        if self.data_ready:
            self._read_data()
        return self._relative_humidity

    @property
    def pressure(self):
        """Get the last set pressure value in hPa."""
        return self._pressure

    def set_ambient_pressure(self, pressure):
        """Set ambient pressure in hPa."""
        if not (config.VALID_PRESSURE_RANGE[0] <= pressure <= config.VALID_PRESSURE_RANGE[1]):
            raise ValueError(f"Pressure must be between {config.VALID_PRESSURE_RANGE[0]} and {config.VALID_PRESSURE_RANGE[1]} hPa")
        self._pressure = pressure
        self._set_command_value(_SCD4X_SETPRESSURE, pressure)
    
    def set_altitude(self, altitude):
        """Set altitude in meters."""
        if altitude < 0 or altitude > 65535:
            raise ValueError("Altitude must be between 0 and 65535 meters")
        self._set_command_value(_SCD4X_SETALTITUDE, altitude)

    def factory_reset(self):
        """Perform a factory reset."""
        self._send_command(_SCD4X_FACTORYRESET, cmd_delay=1.2)

    def self_test(self):
        """Perform a self-test."""
        self._send_command(_SCD4X_SELFTEST, cmd_delay=10)
        self._read_reply(3)
        return (self._buffer[0] << 8) | self._buffer[1]

    def get_serial_number(self):
        """Get the serial number of the sensor."""
        self._send_command(_SCD4X_SERIALNUMBER, cmd_delay=0.001)
        self._read_reply(9)
        return (self._buffer[0] << 40) | (self._buffer[1] << 32) | (self._buffer[3] << 24) | \
               (self._buffer[4] << 16) | (self._buffer[6] << 8) | self._buffer[7]

    def persist_settings(self):
        """Persist settings to EEPROM."""
        self._send_command(_SCD4X_PERSISTSETTINGS, cmd_delay=0.8)

    def initialize_with_config(self):
        """Initialize sensor with settings from config file."""
        try:
            print("[SCD4X] Configuring sensor with settings from config")
            self.set_altitude(config.SENSOR_ALTITUDE)
            self.set_ambient_pressure(config.SENSOR_PRESSURE)
            self.set_temperature_offset(config.TEMP_OFFSET)
            self.start_periodic_measurement()
            print(f"[SCD4X] Waiting {config.SENSOR_INIT_DELAY}s for first measurement")
            time.sleep(config.SENSOR_INIT_DELAY)
            return True
        except Exception as e:
            print(f"[SCD4X] Error initializing sensor with config: {e}")
            return False