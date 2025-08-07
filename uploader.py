# uploader.py - Updated with rounding for temperature and humidity
import urequests
import json
import network
import config

def upload_data_to_server(sensor_data):
    """Upload sensor data to server with minimal overhead"""
    # Check network connection
    wlan = network.WLAN(network.STA_IF)
    if not wlan.isconnected():
        return False

    # Build simplified payload
    payload = {
        "Temperature (C)": round(sensor_data.get('temperature_c', 0), 1),
        "Humidity (%)": round(sensor_data.get('humidity_percent', 0)),
        "CO2 (ppm)": sensor_data.get('co2_ppm', 0),
        "Pressure (Pa)": sensor_data.get('pressure_hpa', 0) * 100,
        "Light (lux)": round(sensor_data.get('light_lux', 0), 1),
        "ID": config.DEVICE_ID,
        "software_date": config.SOFTWARE_DATE
    }

    try:
        if config.UPLOAD_DEBUG_MODE:
            print(f"[Upload] Sending data to: {config.UPLOAD_URL}")
            print(f"[Upload] Payload: {json.dumps(payload, indent=2)}")
        
        response = urequests.post(
            config.UPLOAD_URL,
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )
        
        # Accept both 200 (OK) and 201 (Created) as success
        success = response.status_code in [200, 201]
        
        if config.UPLOAD_DEBUG_MODE:
            print(f"[Upload] Response status: {response.status_code}")
            try:
                response_text = response.text
                print(f"[Upload] Response body: {response_text}")
            except:
                print(f"[Upload] Could not read response body")
            
            if success:
                print(f"[Upload] ✓ Upload successful")
            else:
                print(f"[Upload] ✗ Upload failed with status {response.status_code}")
        
        response.close()
        return success
        
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        if config.UPLOAD_DEBUG_MODE:
            print(f"[Upload] Error Type: {error_type}")
            print(f"[Upload] Error Message: {error_msg}")
            print(f"[Upload] Error Args: {e.args}")
            # Log more specific error types for debugging
            if "ETIMEDOUT" in error_msg:
                print(f"[Upload] Network timeout - check internet connection")
            elif "ECONNRESET" in error_msg:
                print(f"[Upload] Connection reset by server")
            elif "EHOSTUNREACH" in error_msg:
                print(f"[Upload] Host unreachable - check server URL")
            elif "keyword" in error_msg:
                print(f"[Upload] Function call error - check urequests parameters")
        else:
            print(f"[Upload] Error: {error_msg}")
        return False