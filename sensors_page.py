# sensors_page.py - Dedicated sensors status page
import time
import config

def create_sensors_page(sensor_manager, monitor):
    """Create the sensors status page HTML"""
    try:
        # Get sensor status information
        sensor_status = sensor_manager.get_status()
        system_stats = monitor.check_system_health()
        readings = sensor_manager.get_readings()
        
        # Format last success time
        last_success = sensor_status.get('last_success', 0)
        if last_success > 0:
            success_time = time.localtime(last_success)
            success_str = f"{success_time[3]:02d}:{success_time[4]:02d}:{success_time[5]:02d}"
        else:
            success_str = "Never"
        
        # Determine status classes
        scd_status_class = 'status-ok' if sensor_status.get('initialized') else 'status-error'
        scd_status_text = 'Online' if sensor_status.get('initialized') else 'Offline'
        
        error_count = sensor_status.get('consecutive_errors', 0)
        if error_count == 0:
            error_class = 'status-ok'
        elif error_count < 5:
            error_class = 'status-warning'
        else:
            error_class = 'status-error'
        
        light_available = sensor_status.get('light_sensor_available', False)
        light_status_class = 'status-ok' if light_available else 'status-offline'
        light_status_text = 'Online' if light_available else 'Offline/Not Available'
        
        light_errors = sensor_status.get('light_sensor_errors', 0)
        light_consecutive_errors = sensor_status.get('light_sensor_consecutive_errors', 0)
        light_error_class = 'status-ok' if light_errors == 0 else 'status-warning'
        light_consecutive_class = 'status-ok' if light_consecutive_errors == 0 else 'status-warning' if light_consecutive_errors < 3 else 'status-error'
        
        # System health status
        mem_percent = system_stats.get('memory_percent', 0)
        if mem_percent < 70:
            mem_class = 'status-ok'
        elif mem_percent < 85:
            mem_class = 'status-warning'
        else:
            mem_class = 'status-error'
        
        storage_percent = system_stats.get('storage_percent', 0)
        if storage_percent < 75:
            storage_class = 'status-ok'
        elif storage_percent < 90:
            storage_class = 'status-warning'
        else:
            storage_class = 'status-error'
        
        current_time = time.localtime()
        time_str = f"{current_time[3]:02d}:{current_time[4]:02d}:{current_time[5]:02d}"
        
        # Create sensors status HTML
        sensors_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Sensor Status - Environmental Monitor</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: Arial, sans-serif; background: #f0f8ff; margin: 0; padding: 20px; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
        h1, h2 {{ text-align: center; color: #2c3e50; }}
        .sensor-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin: 20px 0; }}
        .sensor-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #e9ecef; }}
        .sensor-card h3 {{ margin: 0 0 15px; color: #2c3e50; }}
        .status-ok {{ color: #27ae60; font-weight: bold; }}
        .status-warning {{ color: #f39c12; font-weight: bold; }}
        .status-error {{ color: #e74c3c; font-weight: bold; }}
        .status-offline {{ color: #95a5a6; font-weight: bold; }}
        .detail-row {{ display: flex; justify-content: space-between; margin: 8px 0; }}
        .nav-links {{ text-align: center; margin: 20px 0; }}
        .nav-links a {{ margin: 0 10px; padding: 8px 16px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; }}
        .nav-links a:hover {{ background: #0056b3; }}
        .refresh-info {{ text-align: center; margin: 10px 0; color: #666; font-size: 0.9em; }}
    </style>
    <script>
        // Auto-refresh every 30 seconds
        setTimeout(function() {{ window.location.reload(); }}, 30000);
    </script>
</head>
<body>
    <div class="container">
        <h1>🔧 Sensor Status Dashboard</h1>
        
        <div class="nav-links">
            <a href="/">← Back to Main Dashboard</a>
            <a href="/test.html">Test Page</a>
            <a href="/csv">Download CSV</a>
        </div>
        
        <div class="refresh-info">
            Page auto-refreshes every 30 seconds | Last updated: {time_str}
        </div>
        
        <div class="sensor-grid">
            <div class="sensor-card">
                <h3>🌡️ SCD4X Environmental Sensor</h3>
                <div class="detail-row">
                    <span>Status:</span>
                    <span class="{scd_status_class}">{scd_status_text}</span>
                </div>
                <div class="detail-row">
                    <span>Consecutive Errors:</span>
                    <span class="{error_class}">{error_count}</span>
                </div>
                <div class="detail-row">
                    <span>Last Success:</span>
                    <span>{success_str}</span>
                </div>
                <div class="detail-row">
                    <span>I2C Address:</span>
                    <span>0x{config.SCD4X_I2C_ADDR:02X}</span>
                </div>"""
        
        # Add current readings if available
        if readings:
            co2, temp_c, temp_f, humidity, pressure, lux = readings
            sensors_html += f"""
                <div class="detail-row"><span>CO2:</span><span>{co2} PPM</span></div>
                <div class="detail-row"><span>Temperature:</span><span>{temp_c:.1f}°C / {temp_f:.1f}°F</span></div>
                <div class="detail-row"><span>Humidity:</span><span>{humidity:.1f}%</span></div>
                <div class="detail-row"><span>Pressure:</span><span>{pressure:.0f} hPa</span></div>"""
        else:
            sensors_html += '<div class="detail-row"><span>Readings:</span><span class="status-error">No Data Available</span></div>'
        
        sensors_html += f"""
            </div>
            
            <div class="sensor-card">
                <h3>💡 VEML7700 Light Sensor</h3>
                <div class="detail-row">
                    <span>Status:</span>
                    <span class="{light_status_class}">{light_status_text}</span>
                </div>
                <div class="detail-row">
                    <span>Total Errors:</span>
                    <span class="{light_error_class}">{light_errors}</span>
                </div>
                <div class="detail-row">
                    <span>Consecutive Errors:</span>
                    <span class="{light_consecutive_class}">{light_consecutive_errors}</span>
                </div>
                <div class="detail-row">
                    <span>I2C Address:</span>
                    <span>0x{config.VEML7700_I2C_ADDR:02X}</span>
                </div>"""
        
        # Add calibration info if light sensor is available
        if light_available:
            try:
                # Get calibration info from sensor manager's VEML7700 instance
                if hasattr(sensor_manager, 'veml7700') and sensor_manager.veml7700:
                    cal_info = sensor_manager.veml7700.get_calibration_info()
                    if 'error' not in cal_info:
                        cal_enabled = cal_info.get('enabled', False)
                        cal_status = 'Enabled' if cal_enabled else 'Disabled'
                        cal_class = 'status-ok' if cal_enabled else 'status-offline'
                        
                        sensors_html += f"""
                <div class="detail-row">
                    <span>Calibration:</span>
                    <span class="{cal_class}">{cal_status}</span>
                </div>"""
                        
                        if cal_enabled:
                            sensors_html += f"""
                <div class="detail-row">
                    <span>Cal. Offset:</span>
                    <span>{cal_info.get('offset', 0.0):.2f} lux</span>
                </div>
                <div class="detail-row">
                    <span>Cal. Multiplier:</span>
                    <span>{cal_info.get('multiplier', 1.0):.3f}</span>
                </div>"""
            except Exception as e:
                sensors_html += f"""
                <div class="detail-row">
                    <span>Calibration:</span>
                    <span class="status-error">Error: {e}</span>
                </div>"""
        
        # Add light reading if available
        if readings and light_available:
            sensors_html += f'<div class="detail-row"><span>Light Level:</span><span>{readings[5]:.1f} lux</span></div>'
        else:
            sensors_html += '<div class="detail-row"><span>Light Level:</span><span class="status-offline">N/A</span></div>'
        
        sensors_html += f"""
            </div>
            
            <div class="sensor-card">
                <h3>🖥️ System Health</h3>
                <div class="detail-row">
                    <span>Memory Usage:</span>
                    <span class="{mem_class}">{mem_percent:.1f}%</span>
                </div>
                <div class="detail-row">
                    <span>Storage Usage:</span>
                    <span class="{storage_class}">{storage_percent:.1f}%</span>
                </div>
                <div class="detail-row">
                    <span>Uptime:</span>
                    <span>{format_uptime(system_stats.get('uptime', 0))}</span>
                </div>
                <div class="detail-row">
                    <span>Device ID:</span>
                    <span>{config.DEVICE_ID}</span>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""
        
        return sensors_html
        
    except Exception as e:
        return f"<html><body><h1>Error generating sensors page: {e}</h1></body></html>"

def format_uptime(seconds):
    """Format uptime in a human-readable string."""
    try:
        if seconds < 0:
            return "0m 0s"
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