# web_template.py - Final correction for storage progress bar color
from machine import unique_id
import sys
import config
import gc
import time

def format_uptime(seconds):
    days = seconds // (24 * 3600); seconds %= (24 * 3600)
    hours = seconds // 3600; seconds %= 3600
    minutes = seconds // 60
    if days > 0: return f"{int(days)}d {int(hours)}h"
    elif hours > 0: return f"{int(hours)}h {int(minutes)}m"
    else: return f"{int(minutes)}m {int(seconds // 1)}s"

HTML_HEADER = """<!DOCTYPE html><html><head><title>Environmental Monitor v{version}</title><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><script src="https://cdn.jsdelivr.net/npm/apexcharts"></script><style>body{{font-family:Arial,sans-serif;background:#f0f8ff;margin:0;padding:0}}#main-container{{max-width:800px;margin:20px auto;background:#fff;padding:20px;box-shadow:0 0 10px rgba(0,0,0,.1);border-radius:8px}}h1,h2{{text-align:center;color:#2c3e50}}.readings-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:15px;margin-bottom:20px}}.reading-card{{background:#f8f9fa;padding:15px;border-radius:8px;text-align:center;border:1px solid #e9ecef}}.label{{font-size:.9em;color:#6c757d}}.value{{font-size:1.8em;font-weight:700;margin:5px 0}}.status{{font-size:.8em}}.toggle-btn{{font-size:.7em;padding:3px 8px;margin-top:5px;cursor:pointer;border:1px solid #007bff;background-color:#007bff;color:#fff;border-radius:12px}}.chart-container{{padding:10px;background:#fff;border:1px solid #ccc;border-radius:5px;margin-bottom:20px}}.system-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:15px}}.system-card{{background:#f8f9fa;border-radius:8px;padding:15px}}.system-card h3{{margin:0 0 10px;font-size:1rem;color:#2c3e50}}.progress-bar{{width:100%;height:8px;background:#ecf0f1;border-radius:4px;overflow:hidden;margin:10px 0}}.progress{{height:100%;transition:width .3s ease}}.system-details{{display:flex;justify-content:space-between;font-size:.8rem;color:#666;margin-top:8px}}.footer{{text-align:center;margin-top:20px;font-size:.9em;color:#7f8c8d}}</style></head><body><div id="main-container">"""
HTML_TITLE = "<h1>Environmental Monitor v{version}</h1>"
HTML_READINGS_GRID = """<div class="readings-grid"><div class="reading-card"><div class="label">Temperature</div><div id="temp-value" class="value" style="color:#2980b9" data-c="--" data-f="--">--.-°C</div><div id="temp-status" class="status">Normal</div><button id="temp-toggle" class="toggle-btn">Show °F</button></div><div class="reading-card"><div class="label">CO2 Level</div><div id="co2-value" class="value" style="color:#27ae60">---- PPM</div><div id="co2-status" class="status">Good</div></div><div class="reading-card"><div class="label">Humidity</div><div id="humidity-value" class="value" style="color:#8e44ad">--.-%</div><div id="humidity-status" class="status">Normal</div></div><div class="reading-card"><div class="label">Pressure</div><div id="pressure-value" class="value" style="color:#2c3e50">---- hPa</div><div class="status">Atmospheric</div></div></div>"""
HTML_CHART_SECTION = """<div class="chart-container"><h2>Temperature & Humidity Trends</h2><div id="chart-temp-humidity"></div></div><div class="chart-container"><h2>CO2 Air Quality Trends</h2><div id="chart-co2"></div></div>"""

HTML_SYSTEM_SECTION = """
<h2>System Status</h2>
<div class="system-grid">
    <div class="system-card">
        <h3>Memory Usage</h3>
        <div class="progress-bar">
            <div id="mem-progress" class="progress"></div>
        </div>
        <div class="system-details">
            <span id="mem-detail">Used: --.- KB</span>
        </div>
    </div>
    <div class="system-card">
        <h3>Storage</h3>
        <div class="progress-bar">
            <div id="storage-progress" class="progress"></div>
        </div>
        <div class="system-details">
             <span id="storage-detail">--% Used</span>
        </div>
    </div>
    <div class="system-card">
        <h3>System Info</h3>
        <div class="system-details" style="flex-direction:column;align-items:flex-start;">
            <span>Device: <b id="device-model">--</b></span>
            <span>Uptime: <b id="uptime-value">--</b></span>
            <span>Version: v{version}</span>
        </div>
    </div>
</div>
"""

HTML_FOOTER = """
<div class="footer"><p>Last Updated: <span id="last-updated">Never</span><br>Download: <a href="/csv">CSV</a> | <a href="/json">JSON</a></p></div>
</div>
<script>
document.addEventListener('DOMContentLoaded', function() {{
    let isCelsius = true;
    const chart1Options = {{ series: [], chart: {{ id: 'temp-humidity-chart', height: 350, type: 'line', toolbar: {{ show: false }} }}, stroke: {{ curve: 'smooth', width: 2 }}, xaxis: {{ type: 'category', categories: [] }}, yaxis: [ {{ seriesName: 'Temperature', title: {{ text: "Temp (°C)", style: {{ color: '#008FFB' }} }}, labels: {{ style: {{ colors: '#008FFB' }} }} }}, {{ seriesName: 'Humidity', opposite: true, title: {{ text: "Humidity (%)", style: {{ color: '#8e44ad' }} }}, labels: {{ style: {{ colors: '#8e44ad' }} }} }} ], colors: ['#008FFB', '#8e44ad'], noData: {{ text: 'Loading...' }} }};
    const chart1 = new ApexCharts(document.querySelector("#chart-temp-humidity"), chart1Options);
    chart1.render();
    const chart2Options = {{ series: [], chart: {{ id: 'co2-chart', height: 250, type: 'area', toolbar: {{ show: false }} }}, stroke: {{ curve: 'smooth', width: 2 }}, xaxis: {{ type: 'category', categories: [] }}, yaxis: {{ title: {{ text: 'CO2 (PPM)' }} }}, colors: ['#00E396'], dataLabels: {{ enabled: false }}, noData: {{ text: 'Loading...' }} }};
    const chart2 = new ApexCharts(document.querySelector("#chart-co2"), chart2Options);
    chart2.render();

    function updateHistoryCharts() {{
        fetch('/api/history').then(r => r.json()).then(data => {{
            chart1.updateSeries([ {{ name: 'Temperature', data: data.temperatures }}, {{ name: 'Humidity', data: data.humidities }} ]);
            chart1.updateOptions({{ xaxis: {{ categories: data.timestamps }} }});
            chart2.updateSeries([ {{ name: 'CO2', data: data.co2_levels }} ]);
            chart2.updateOptions({{ xaxis: {{ categories: data.timestamps }} }});
        }}).catch(err => console.error("History fetch error:", err));
    }}

    const tempValueEl = document.getElementById('temp-value');
    const tempToggleBtn = document.getElementById('temp-toggle');
    tempToggleBtn.addEventListener('click', () => {{ isCelsius = !isCelsius; updateTempDisplay(); }});
    function updateTempDisplay() {{
        const tempC = tempValueEl.getAttribute('data-c');
        const tempF = tempValueEl.getAttribute('data-f');
        tempValueEl.innerHTML = isCelsius ? `${{tempC}}°C` : `${{tempF}}°F`;
        tempToggleBtn.innerText = isCelsius ? 'Show °F' : 'Show °C';
    }}

    // --- THIS IS THE CORRECTED JAVASCRIPT FUNCTION ---
    function updateLiveData() {{
        fetch('/api/data').then(r => r.json()).then(data => {{
            // Temperature, CO2, Humidity, Pressure (unchanged)
            tempValueEl.setAttribute('data-c', data.temp_c.toFixed(1));
            tempValueEl.setAttribute('data-f', data.temp_f.toFixed(1));
            updateTempDisplay();
            const tempStatus = document.getElementById('temp-status');
            if (data.temp_c > {temp_high} || data.temp_c < {temp_low}) {{ tempStatus.innerText = 'Warning'; tempStatus.style.color = '#e74c3c'; }} else {{ tempStatus.innerText = 'Normal'; tempStatus.style.color = '#27ae60'; }}
            const co2Value = document.getElementById('co2-value');
            co2Value.innerText = `${{data.co2}} PPM`;
            const co2Status = document.getElementById('co2-status');
            if (data.co2 >= {co2_danger}) {{ co2Value.style.color = '#e74c3c'; co2Status.innerText = 'Danger'; co2Status.style.color = '#e74c3c'; }}
            else if (data.co2 >= {co2_warning}) {{ co2Value.style.color = '#f39c12'; co2Status.innerText = 'Warning'; co2Status.style.color = '#f39c12'; }}
            else {{ co2Value.style.color = '#27ae60'; co2Status.innerText = 'Good'; co2Status.style.color = '#27ae60'; }}
            document.getElementById('humidity-value').innerText = `${{data.humidity.toFixed(1)}}%`;
            document.getElementById('pressure-value').innerText = `${{data.pressure}} hPa`;

            // System Info (unchanged)
            document.getElementById('device-model').innerText = data.device_model;
            document.getElementById('uptime-value').innerText = data.uptime_str;
            
            // System Bars - CORRECTED LOGIC
            const memProgress = document.getElementById('mem-progress');
            memProgress.style.width = data.memory_percent.toFixed(1) + '%';
            memProgress.style.backgroundColor = data.memory_percent > 85 ? '#e74c3c' : data.memory_percent > 70 ? '#f39c12' : '#27ae60';
            document.getElementById('mem-detail').innerText = `Used: ${{data.memory_used_kb.toFixed(1)}} KB`;

            const storageProgress = document.getElementById('storage-progress');
            storageProgress.style.width = data.storage_percent.toFixed(1) + '%';
            storageProgress.style.backgroundColor = data.storage_percent > 90 ? '#e74c3c' : data.storage_percent > 75 ? '#f39c12' : '#27ae60';
            document.getElementById('storage-detail').innerText = `${{data.storage_percent.toFixed(1)}}% Used`;
            
            document.getElementById('last-updated').innerText = new Date().toLocaleTimeString();
        }}).catch(err => console.error("Live data fetch error:", err));
    }}
    
    updateLiveData(); updateHistoryCharts();
    setInterval(updateLiveData, 10000); setInterval(updateHistoryCharts, 60000);
}});
</script>
</body></html>
"""

# The create_html and send_chunked_html functions are unchanged.
def create_html(config_obj):
    gc.collect()
    version = config_obj.VERSION
    html_parts = [
        HTML_HEADER.format(version=version),
        HTML_TITLE.format(version=version),
        HTML_READINGS_GRID,
        HTML_CHART_SECTION,
        HTML_SYSTEM_SECTION.format(version=version),
        HTML_FOOTER.format(
            temp_high=config_obj.TEMP_HIGH, temp_low=config_obj.TEMP_LOW,
            co2_danger=config_obj.CO2_DANGER, co2_warning=config_obj.CO2_WARNING,
            humidity_high=config_obj.HUMIDITY_HIGH, humidity_low=config_obj.HUMIDITY_LOW
        )
    ]
    return ''.join(html_parts)

def send_chunked_html(client_socket, html_content):
    try:
        headers = b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n"
        client_socket.sendall(headers + html_content.encode())
    except Exception as e:
        print(f"Error in send_chunked_html: {e}")
    finally:
        client_socket.close()