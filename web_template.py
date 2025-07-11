# web_template.py - Corrected JavaScript String Formatting (Final v2)
from machine import unique_id
import sys
import config
import gc
import time

def format_uptime(seconds):
    # (No changes to this function)
    days = seconds // (24 * 3600)
    seconds %= (24 * 3600)
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    if days > 0: return f"{int(days)}d {int(hours)}h {int(minutes)}m"
    elif hours > 0: return f"{int(hours)}h {int(minutes)}m"
    else: return f"{int(minutes)}m {int(seconds)}s"

# (HTML_HEADER, HTML_TITLE, HTML_READINGS_GRID, HTML_CHART_SECTION, HTML_SYSTEM_SECTION are unchanged)
HTML_HEADER = """<!DOCTYPE html>
<html>
<head>
    <title>Environmental Monitor v{version}</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdn.jsdelivr.net/npm/apexcharts"></script>
    <style>
        body {{ font-family: Arial, sans-serif; background: #f0f8ff; margin: 0; padding: 0; }}
        #main-container {{ max-width: 800px; margin: 20px auto; background: #ffffff; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1); border-radius: 8px; }}
        h1, h2 {{ text-align: center; color: #2c3e50; }}
        .readings-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 20px; }}
        .reading-card {{ background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #e9ecef; }}
        .reading-card .label {{ font-size: 0.9em; color: #6c757d; }}
        .reading-card .value {{ font-size: 1.8em; font-weight: bold; margin: 5px 0; }}
        .reading-card .status {{ font-size: 0.8em; }}
        .toggle-btn {{ font-size: 0.7em; padding: 3px 8px; margin-top: 5px; cursor: pointer; border: 1px solid #007bff; background-color: #007bff; color: white; border-radius: 12px; transition: background-color 0.2s; }}
        .toggle-btn:hover {{ background-color: #0056b3; }}
        #chart {{ padding: 10px; background: #fff; border: 1px solid #ccc; border-radius: 5px; margin-bottom: 20px; }}
        .system-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 15px; }}
        .system-card {{ background: #f8f9fa; border-radius: 8px; padding: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .system-card h3 {{ margin: 0 0 10px 0; font-size: 1rem; color: #2c3e50; }}
        .progress-bar {{ width: 100%; height: 8px; background: #ecf0f1; border-radius: 4px; overflow: hidden; margin: 10px 0; }}
        .progress {{ height: 100%; transition: width 0.3s ease; }}
        .system-details {{ display: flex; justify-content: space-between; font-size: 0.8rem; color: #666; margin-top: 8px; }}
        .footer {{ text-align: center; margin-top: 20px; font-size: 0.9em; color: #7f8c8d; }}
    </style>
</head>
<body><div id="main-container">
"""
HTML_TITLE = "<h1>Environmental Monitor v{version}</h1>"
HTML_READINGS_GRID = """
<div class="readings-grid">
    <div class="reading-card">
        <div class="label">Temperature</div>
        <div id="temp-value" class="value" style="color: #2980b9;" data-c="--" data-f="--">--.-°C</div>
        <div id="temp-status" class="status">Normal</div>
        <button id="temp-toggle" class="toggle-btn">Show °F</button>
    </div>
    <div class="reading-card">
        <div class="label">CO2 Level</div>
        <div id="co2-value" class="value" style="color: #27ae60;">---- PPM</div>
        <div id="co2-status" class="status">Good</div>
    </div>
    <div class="reading-card">
        <div class="label">Humidity</div>
        <div id="humidity-value" class="value" style="color: #8e44ad;">--.-%</div>
        <div id="humidity-status" class="status">Normal</div>
    </div>
    <div class="reading-card">
        <div class="label">Pressure</div>
        <div id="pressure-value" class="value" style="color: #2c3e50;">---- hPa</div>
        <div class="status">Atmospheric</div>
    </div>
</div>
"""
HTML_CHART_SECTION = """
<h2>Sensor Data Chart (Last 3 Hours)</h2>
<div id="chart"></div>
"""
HTML_SYSTEM_SECTION = """
<h2>System Status</h2>
<div class="system-grid">
    <div class="system-card">
        <h3>Memory Usage</h3>
        <div class="progress-bar">
            <div id="mem-progress" class="progress" style="width: 0%; background: #27ae60;"></div>
        </div>
        <div class="system-details">
            <span id="mem-detail">Used: --.- KB</span>
        </div>
    </div>
    <div class="system-card">
        <h3>Storage</h3>
        <div class="progress-bar">
            <div id="storage-progress" class="progress" style="width: 0%; background: #27ae60;"></div>
        </div>
    </div>
    <div class="system-card">
        <h3>System Info</h3>
        <div class="system-details" style="flex-direction: column; align-items: flex-start;">
            <span>Uptime: <b id="uptime-value">--</b></span>
            <span>Version: v{version}</span>
        </div>
    </div>
</div>
"""

# *** THIS IS THE CORRECTED SECTION ***
# All JavaScript curly braces are now escaped by doubling them up: {{ and }}
HTML_FOOTER = """
<div class="footer">
    <p>Last Updated: <span id="last-updated">Never</span><br>
    Download: <a href="/csv">CSV</a> | <a href="/json">JSON</a></p>
</div>
</div> <!-- End main-container -->
<script>
document.addEventListener('DOMContentLoaded', function() {{
    
    let isCelsius = true;

    var chartOptions = {{
        series: [],
        chart: {{
            height: 350,
            type: 'line',
            animations: {{ enabled: true, easing: 'linear', dynamicAnimation: {{ speed: 1000 }} }},
            toolbar: {{ show: false }}
        }},
        dataLabels: {{ enabled: false }},
        stroke: {{ curve: 'smooth', width: 2 }},
        title: {{ text: 'Sensor Trends', align: 'left' }},
        grid: {{ row: {{ colors: ['#f3f3f3', 'transparent'], opacity: 0.5 }} }},
        xaxis: {{ type: 'category', categories: [] }},
        yaxis: [
            {{ seriesName: 'Temperature', title: {{ text: "Temp (°C)" }} }},
            {{ seriesName: 'CO2', opposite: true, title: {{ text: "CO2 (PPM)" }} }}
        ],
        tooltip: {{ x: {{ format: 'HH:mm:ss' }} }},
        noData: {{ text: 'Loading historical data...' }}
    }};
    var chart = new ApexCharts(document.querySelector("#chart"), chartOptions);
    chart.render();

    function updateHistoryChart() {{
        fetch('/api/history')
            .then(response => response.json())
            .then(data => {{
                chart.updateSeries([
                    {{ name: 'Temperature', data: data.temperatures }},
                    {{ name: 'CO2', data: data.co2_levels }}
                ]);
                chart.updateOptions({{ xaxis: {{ categories: data.timestamps }} }});
            }}).catch(err => console.error("History fetch error:", err));
    }}

    const tempValueElement = document.getElementById('temp-value');
    const tempToggleButton = document.getElementById('temp-toggle');

    tempToggleButton.addEventListener('click', () => {{
        isCelsius = !isCelsius;
        updateTemperatureDisplay();
    }});

    function updateTemperatureDisplay() {{
        const tempC = tempValueElement.getAttribute('data-c');
        const tempF = tempValueElement.getAttribute('data-f');
        if (isCelsius) {{
            tempValueElement.innerHTML = `${{tempC}}°C`;
            tempToggleButton.innerText = 'Show °F';
        }} else {{
            tempValueElement.innerHTML = `${{tempF}}°F`;
            tempToggleButton.innerText = 'Show °C';
        }}
    }}
    
    function updateLiveData() {{
        fetch('/api/data')
            .then(response => response.json())
            .then(data => {{
                tempValueElement.setAttribute('data-c', data.temp_c.toFixed(1));
                tempValueElement.setAttribute('data-f', data.temp_f.toFixed(1));
                updateTemperatureDisplay();

                const tempStatus = document.getElementById('temp-status');
                if (data.temp_c > {temp_high} || data.temp_c < {temp_low}) {{
                    tempStatus.innerText = 'Warning'; tempStatus.style.color = '#e74c3c';
                }} else {{
                    tempStatus.innerText = 'Normal'; tempStatus.style.color = '#27ae60';
                }}

                const co2Value = document.getElementById('co2-value');
                co2Value.innerText = `${{data.co2}} PPM`;
                const co2Status = document.getElementById('co2-status');
                if (data.co2 >= {co2_danger}) {{
                    co2Value.style.color = '#e74c3c'; co2Status.innerText = 'Danger'; co2Status.style.color = '#e74c3c';
                }} else if (data.co2 >= {co2_warning}) {{
                    co2Value.style.color = '#f39c12'; co2Status.innerText = 'Warning'; co2Status.style.color = '#f39c12';
                }} else {{
                    co2Value.style.color = '#27ae60'; co2Status.innerText = 'Good'; co2Status.style.color = '#27ae60';
                }}

                document.getElementById('humidity-value').innerText = `${{data.humidity.toFixed(1)}}%`;
                const humidityStatus = document.getElementById('humidity-status');
                if (data.humidity > {humidity_high} || data.humidity < {humidity_low}) {{
                    humidityStatus.innerText = 'Warning'; humidityStatus.style.color = '#e74c3c';
                }} else {{
                    humidityStatus.innerText = 'Normal'; humidityStatus.style.color = '#27ae60';
                }}
                
                document.getElementById('pressure-value').innerText = `${{data.pressure}} hPa`;
                document.getElementById('uptime-value').innerText = data.uptime_str;
                document.getElementById('mem-progress').style.width = data.memory_percent.toFixed(1) + '%';
                document.getElementById('mem-detail').innerText = `Used: ${{data.memory_used_kb.toFixed(1)}} KB`;
                document.getElementById('storage-progress').style.width = data.storage_percent.toFixed(1) + '%';
                document.getElementById('last-updated').innerText = new Date().toLocaleTimeString();
            }}).catch(err => {{
                console.error("Live data fetch error:", err);
                document.getElementById('last-updated').innerText = "Update Failed";
            }});
    }}

    updateLiveData();
    updateHistoryChart();
    setInterval(updateLiveData, 10000);
    setInterval(updateHistoryChart, 60000);
}});
</script>
</body>
</html>
"""

def create_html(config_obj):
    """Create the initial HTML shell. Data will be populated by JavaScript."""
    gc.collect()
    version = config_obj.VERSION
    
    html_parts = [
        HTML_HEADER.format(version=version),
        HTML_TITLE.format(version=version),
        HTML_READINGS_GRID,
        HTML_CHART_SECTION,
        HTML_SYSTEM_SECTION.format(version=version),
        HTML_FOOTER.format(
            temp_high=config_obj.TEMP_HIGH,
            temp_low=config_obj.TEMP_LOW,
            co2_danger=config_obj.CO2_DANGER,
            co2_warning=config_obj.CO2_WARNING,
            humidity_high=config_obj.HUMIDITY_HIGH,
            humidity_low=config_obj.HUMIDITY_LOW
        )
    ]
    return ''.join(html_parts)

def send_chunked_html(client_socket, html_content):
    # (No changes to this function)
    try:
        if html_content is None:
            client_socket.send(b"HTTP/1.1 500 Internal Server Error\r\n\r\nError")
            client_socket.close()
            return
        headers = b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n"
        client_socket.sendall(headers + html_content.encode())
        client_socket.close()
    except Exception as e:
        print(f"Error in send_chunked_html: {e}")
        try: client_socket.close()
        except: pass