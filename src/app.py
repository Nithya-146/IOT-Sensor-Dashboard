import os
import sys
import time
from datetime import datetime, timezone
import pandas as pd
import numpy as np

import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from influxdb_client import InfluxDBClient

# InfluxDB Connection Setup
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "IOT_Dashboard_Token_For_InfluxDB_Security_1234567890_ABCDEFGHIJ_"
INFLUX_ORG = "iot_org"
INFLUX_BUCKET = "iot_bucket"

try:
    db_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    query_api = db_client.query_api()
except Exception as e:
    print(f"Error connecting to InfluxDB client: {e}", file=sys.stderr)
    sys.exit(1)

# Initialize Dash application with bootstrap styles
app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.DARKLY,
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"
    ],
    assets_folder="assets",
    title="Live IoT Sensor Dashboard"
)

# HELPER FUNCTIONS TO QUERY DATA

def get_telemetry_df(range_str="-5m"):
    """Fetches and pivots telemetry data from InfluxDB into a clean DataFrame."""
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: {range_str})
      |> filter(fn: (r) => r["_measurement"] == "telemetry")
      |> pivot(rowKey:["_time"], columnKey: ["type"], valueColumn: "_value")
    '''
    try:
        df = query_api.query_data_frame(query=query)
        if isinstance(df, list):
            df = pd.concat(df, ignore_index=True)
        if df is None or df.empty:
            return pd.DataFrame(columns=["time", "temperature", "humidity", "pressure"])
        
        # Clean columns
        df = df.rename(columns={"_time": "time"})
        df["time"] = pd.to_datetime(df["time"]).dt.tz_convert('Asia/Kolkata') # Set local time (Kolkata)
        
        cols_to_keep = ["time"]
        for c in ["temperature", "humidity", "pressure"]:
            if c in df.columns:
                cols_to_keep.append(c)
            else:
                df[c] = np.nan
                cols_to_keep.append(c)
                
        df = df[cols_to_keep]
        return df.sort_values("time")
    except Exception as e:
        print(f"Error querying telemetry: {e}", file=sys.stderr)
        return pd.DataFrame(columns=["time", "temperature", "humidity", "pressure"])

def get_service_statuses():
    """Queries service status logs from InfluxDB."""
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -2m)
      |> filter(fn: (r) => r["_measurement"] == "service_status")
      |> last()
    '''
    statuses = {
        "simulator": {"status": "Offline", "uptime": 0.0, "messages": 0, "last_seen": "Never"},
        "subscriber": {"status": "Offline", "uptime": 0.0, "messages": 0, "last_seen": "Never"}
    }
    try:
        tables = query_api.query(query=query)
        for table in tables:
            for record in table.records:
                service = record.values.get("service_name")
                field = record.get_field()
                val = record.get_value()
                
                # Format time locally
                local_time = record.get_time().astimezone().strftime("%Y-%m-%d %H:%M:%S")
                
                if service in statuses:
                    statuses[service]["last_seen"] = local_time
                    statuses[service]["status"] = "Online"
                    
                    if field == "status":
                        statuses[service]["status"] = "Online" if val == 1 else "Offline"
                    elif field == "uptime_seconds":
                        statuses[service]["uptime"] = val
                    elif field == "message_count":
                        statuses[service]["messages"] = val
    except Exception as e:
        print(f"Error querying service status: {e}", file=sys.stderr)
    return statuses

def get_current_readings():
    """Queries the latest reading for each sensor."""
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -2m)
      |> filter(fn: (r) => r["_measurement"] == "telemetry")
      |> last()
    '''
    readings = {
        "temperature": {"value": 0.0, "time": "Never"},
        "humidity": {"value": 0.0, "time": "Never"},
        "pressure": {"value": 0.0, "time": "Never"}
    }
    try:
        tables = query_api.query(query=query)
        for table in tables:
            for record in table.records:
                metric = record.values.get("type")
                val = record.get_value()
                local_time = record.get_time().astimezone().strftime("%H:%M:%S")
                if metric in readings:
                    readings[metric]["value"] = val
                    readings[metric]["time"] = local_time
    except Exception as e:
        print(f"Error querying current readings: {e}", file=sys.stderr)
    return readings

def get_alert_logs():
    """Queries temperature alerts (values > 80) in the last 24h."""
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -24h)
      |> filter(fn: (r) => r["_measurement"] == "telemetry")
      |> filter(fn: (r) => r["type"] == "temperature")
      |> filter(fn: (r) => r["_value"] > 80.0)
      |> sort(columns: ["_time"], desc: true)
      |> limit(n: 50)
    '''
    alerts = []
    try:
        tables = query_api.query(query=query)
        for table in tables:
            for record in table.records:
                local_time = record.get_time().astimezone().strftime("%Y-%m-%d %H:%M:%S")
                alerts.append({
                    "timestamp": local_time,
                    "sensor": record.values.get("sensor_id"),
                    "value": record.get_value(),
                    "unit": record.values.get("unit"),
                    "message": "Critical temperature threshold exceeded!"
                })
    except Exception as e:
        print(f"Error querying alert logs: {e}", file=sys.stderr)
    return alerts

# CHART CREATION HELPERS

def create_gauge(value, val_min, val_max, title, unit, color):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={'suffix': f" {unit}", 'font': {'size': 26, 'color': '#f8fafc', 'family': 'Outfit'}},
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': title, 'font': {'size': 14, 'color': '#94a3b8', 'family': 'Outfit', 'weight': 'bold'}},
        gauge={
            'axis': {'range': [val_min, val_max], 'tickwidth': 1, 'tickcolor': "#475569"},
            'bar': {'color': color},
            'bgcolor': "rgba(255, 255, 255, 0.03)",
            'borderwidth': 1,
            'bordercolor': "rgba(255, 255, 255, 0.08)",
            'steps': [
                {'range': [val_min, val_max], 'color': 'rgba(0,0,0,0)'}
            ],
            'threshold': {
                'line': {'color': "#ef4444", 'width': 4},
                'thickness': 0.75,
                'value': 80.0 if title == "Temperature" else (val_max + 1)
            }
        }
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=15, r=15, t=30, b=15),
        height=140
    )
    return fig

# DASHBOARD LAYOUT DEFINITION

app.layout = dbc.Container([
    dcc.Interval(id='live-update-interval', interval=1000, n_intervals=0),
    dcc.Interval(id='slow-update-interval', interval=15000, n_intervals=0), # Queries historical data and status slower
    
    # Header Row
    dbc.Row([
        dbc.Col([
            html.Div([
                html.I(className="fa-solid fa-microchip text-primary me-2 fs-3"),
                html.H1("IoT Telemetry Analytics", className="dashboard-title d-inline-block m-0 fs-2")
            ], className="d-flex align-items-center"),
            html.P("Live Telemetry & Anomaly Monitoring Console", className="text-secondary m-0 mt-1")
        ], md=8),
        dbc.Col([
            html.Div([
                html.Div([
                    html.Span("Broker: ", className="text-secondary font-weight-500"),
                    html.Span([html.Span(className="status-dot"), " Online"], id="broker-status-badge", className="status-badge status-online ms-1")
                ], className="me-3"),
                html.Div([
                    html.Span("InfluxDB: ", className="text-secondary font-weight-500"),
                    html.Span([html.Span(className="status-dot"), " Online"], id="db-status-badge", className="status-badge status-online ms-1")
                ])
            ], className="d-flex justify-content-md-end align-items-center h-100 mt-3 mt-md-0")
        ], md=4)
    ], className="py-4 border-bottom border-secondary mb-4"),
    
    # Active Alert Banner Row
    dbc.Row([
        dbc.Col(id="active-alert-col", width=12, className="mb-4 d-none")
    ]),
    
    # Metric KPI Gauge Row
    dbc.Row([
        # Temperature Card
        dbc.Col([
            html.Div([
                dbc.Row([
                    dbc.Col([
                        html.Span("Temperature", className="metric-label"),
                        html.Div([
                            html.Span("0.0", id="live-temp-value", className="metric-value"),
                            html.Span("°C", className="metric-unit")
                        ], className="d-flex align-items-baseline mt-2"),
                        html.Div([
                            html.I(className="fa-solid fa-triangle-exclamation text-danger me-1"),
                            html.Span("Threshold: > 80°C", className="text-secondary fs-7")
                        ], className="mt-2")
                    ], width=7),
                    dbc.Col([
                        dcc.Graph(id="temp-gauge", config={"displayModeBar": False})
                    ], width=5)
                ])
            ], className="glass-card card-temperature h-100")
        ], lg=4, md=6, className="mb-4"),
        
        # Humidity Card
        dbc.Col([
            html.Div([
                dbc.Row([
                    dbc.Col([
                        html.Span("Humidity", className="metric-label"),
                        html.Div([
                            html.Span("0.0", id="live-hum-value", className="metric-value"),
                            html.Span("%", className="metric-unit")
                        ], className="d-flex align-items-baseline mt-2"),
                        html.Div([
                            html.I(className="fa-solid fa-circle-check text-success me-1"),
                            html.Span("Nominal Range: 30-95%", className="text-secondary fs-7")
                        ], className="mt-2")
                    ], width=7),
                    dbc.Col([
                        dcc.Graph(id="hum-gauge", config={"displayModeBar": False})
                    ], width=5)
                ])
            ], className="glass-card card-humidity h-100")
        ], lg=4, md=6, className="mb-4"),
        
        # Pressure Card
        dbc.Col([
            html.Div([
                dbc.Row([
                    dbc.Col([
                        html.Span("Atm. Pressure", className="metric-label"),
                        html.Div([
                            html.Span("0.0", id="live-press-value", className="metric-value"),
                            html.Span("hPa", className="metric-unit")
                        ], className="d-flex align-items-baseline mt-2"),
                        html.Div([
                            html.I(className="fa-solid fa-circle-check text-success me-1"),
                            html.Span("Standard: ~1013 hPa", className="text-secondary fs-7")
                        ], className="mt-2")
                    ], width=7),
                    dbc.Col([
                        dcc.Graph(id="press-gauge", config={"displayModeBar": False})
                    ], width=5)
                ])
            ], className="glass-card card-pressure h-100")
        ], lg=4, md=12, className="mb-4")
    ]),
    
    # Charts Section
    dbc.Row([
        # Live Charts Column
        dbc.Col([
            html.Div([
                html.Div([
                    html.H5([html.I(className="fa-solid fa-wave-square text-primary me-2"), "Live Real-Time Stream"], className="m-0 fs-6"),
                    html.Span("Updating live (last 5 min)", className="text-secondary fs-8")
                ], className="d-flex justify-content-between align-items-center mb-3"),
                dcc.Graph(id="live-charts-figure", config={"displayModeBar": False})
            ], className="glass-card h-100")
        ], lg=6, className="mb-4"),
        
        # Historical Trend Column
        dbc.Col([
            html.Div([
                html.Div([
                    html.H5([html.I(className="fa-solid fa-clock-history text-info me-2"), "24-Hour Historical Trend"], className="m-0 fs-6"),
                    html.Span("Averaged over 5m intervals", className="text-secondary fs-8")
                ], className="d-flex justify-content-between align-items-center mb-3"),
                dcc.Graph(id="historical-charts-figure", config={"displayModeBar": False})
            ], className="glass-card h-100")
        ], lg=6, className="mb-4")
    ]),
    
    # Health Panel & Alert Logs
    dbc.Row([
        # Sensor Health Status
        dbc.Col([
            html.Div([
                html.H5([html.I(className="fa-solid fa-heartbeat text-success me-2"), "Sensor Health Status Panel"], className="mb-4 fs-6"),
                html.Div(id="health-panel-content")
            ], className="glass-card h-100")
        ], lg=5, className="mb-4"),
        
        # Threshold Alert Log
        dbc.Col([
            html.Div([
                html.Div([
                    html.H5([html.I(className="fa-solid fa-list-check text-warning me-2"), "Active Alert Logs (Last 24h)"], className="m-0 fs-6"),
                    dbc.Button([html.I(className="fa-solid fa-rotate me-1"), "Refresh"], id="refresh-alert-btn", size="sm", color="secondary", className="fs-8")
                ], className="d-flex justify-content-between align-items-center mb-3"),
                html.Div([
                    html.Table([
                        html.Thead([
                            html.Tr([
                                html.Th("Timestamp"),
                                html.Th("Sensor"),
                                html.Th("Value"),
                                html.Th("Condition")
                            ])
                        ]),
                        html.Tbody(id="alert-log-table-body")
                    ], className="alert-table")
                ], className="scroll-container")
            ], className="glass-card h-100")
        ], lg=7, className="mb-4")
    ], className="mb-5")
], fluid=True, style={"maxWidth": "1400px"})

# CALLBACKS FOR REAL-TIME INTERACTION

@app.callback(
    [
        Output("live-temp-value", "children"),
        Output("live-hum-value", "children"),
        Output("live-press-value", "children"),
        Output("temp-gauge", "figure"),
        Output("hum-gauge", "figure"),
        Output("press-gauge", "figure"),
        Output("live-charts-figure", "figure"),
        Output("active-alert-col", "children"),
        Output("active-alert-col", "className")
    ],
    [Input("live-update-interval", "n_intervals")]
)
def update_live_metrics(n):
    readings = get_current_readings()
    temp_val = readings["temperature"]["value"]
    hum_val = readings["humidity"]["value"]
    press_val = readings["pressure"]["value"]
    
    # 1. Create Gauges
    temp_fig = create_gauge(temp_val, 20.0, 110.0, "Temperature", "°C", "#ef4444")
    hum_fig = create_gauge(hum_val, 0.0, 100.0, "Humidity", "%", "#06b6d4")
    press_fig = create_gauge(press_val, 950.0, 1050.0, "Pressure", "hPa", "#10b981")
    
    # 2. Query Live Chart DataFrame (last 5 min)
    df_live = get_telemetry_df("-5m")
    
    live_charts = go.Figure()
    if not df_live.empty:
        live_charts.add_trace(go.Scatter(
            x=df_live["time"], y=df_live["temperature"],
            mode="lines", name="Temperature", line=dict(color="#ef4444", width=2.5, shape="spline")
        ))
        live_charts.add_trace(go.Scatter(
            x=df_live["time"], y=df_live["humidity"],
            mode="lines", name="Humidity", line=dict(color="#06b6d4", width=2.5, shape="spline"),
            yaxis="y2"
        ))
    
    live_charts.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=40, t=20, b=30),
        height=280,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#94a3b8")),
        hovermode="x unified",
        xaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(color="#64748b")),
        yaxis=dict(
            title=dict(text="Temp (°C)", font=dict(color="#ef4444")), tickfont=dict(color="#ef4444"),
            gridcolor="rgba(255,255,255,0.04)", zeroline=False
        ),
        yaxis2=dict(
            title=dict(text="Humidity (%)", font=dict(color="#06b6d4")), tickfont=dict(color="#06b6d4"),
            overlaying="y", side="right", zeroline=False
        )
    )
    
    # 3. Handle Alert Flashing
    alert_div = None
    alert_class = "mb-4 d-none"
    
    if temp_val > 80.0:
        alert_div = html.Div([
            html.Div([
                html.I(className="fa-solid fa-circle-exclamation fs-4 me-3"),
                html.Span(f"ANOMALY WARNING: Critical Temperature of {temp_val}°C detected! (Limit: 80°C)", className="fs-5 fw-bold")
            ], className="d-flex align-items-center")
        ], className="alert-banner")
        alert_class = "mb-4"
        
    return (
        f"{temp_val:.1f}", 
        f"{hum_val:.1f}", 
        f"{press_val:.1f}",
        temp_fig, 
        hum_fig, 
        press_fig,
        live_charts,
        alert_div,
        alert_class
    )

@app.callback(
    [
        Output("historical-charts-figure", "figure"),
        Output("health-panel-content", "children"),
        Output("broker-status-badge", "className"),
        Output("broker-status-badge", "children"),
        Output("db-status-badge", "className"),
        Output("db-status-badge", "children")
    ],
    [
        Input("slow-update-interval", "n_intervals"),
        Input("live-update-interval", "n_intervals")  # Use live trigger for faster initial boot
    ]
)
def update_slow_metrics(n_slow, n_live):
    # Fetch 24h historical telemetry averaged in 5m windows
    query_hist = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -24h)
      |> filter(fn: (r) => r["_measurement"] == "telemetry")
      |> aggregateWindow(every: 5m, fn: mean, createEmpty: false)
      |> pivot(rowKey:["_time"], columnKey: ["type"], valueColumn: "_value")
    '''
    
    # 1. Historical Chart
    hist_fig = go.Figure()
    try:
        df_hist = query_api.query_data_frame(query=query_hist)
        if isinstance(df_hist, list):
            df_hist = pd.concat(df_hist, ignore_index=True)
            
        if df_hist is not None and not df_hist.empty:
            df_hist = df_hist.rename(columns={"_time": "time"})
            df_hist["time"] = pd.to_datetime(df_hist["time"]).dt.tz_convert('Asia/Kolkata')
            
            # Setup columns if missing
            for col in ["temperature", "humidity", "pressure"]:
                if col not in df_hist.columns:
                    df_hist[col] = np.nan
            
            df_hist = df_hist.sort_values("time")
            
            hist_fig.add_trace(go.Scatter(
                x=df_hist["time"], y=df_hist["temperature"],
                mode="lines", name="Temperature", line=dict(color="#ef4444", width=2, shape="spline")
            ))
            hist_fig.add_trace(go.Scatter(
                x=df_hist["time"], y=df_hist["pressure"],
                mode="lines", name="Pressure", line=dict(color="#10b981", width=2, shape="spline"),
                yaxis="y2"
            ))
    except Exception as e:
        print(f"Historical query error: {e}", file=sys.stderr)
        
    hist_fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=40, t=20, b=30),
        height=280,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#94a3b8")),
        hovermode="x unified",
        xaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(color="#64748b")),
        yaxis=dict(
            title=dict(text="Temp (°C)", font=dict(color="#ef4444")), tickfont=dict(color="#ef4444"),
            gridcolor="rgba(255,255,255,0.04)", zeroline=False
        ),
        yaxis2=dict(
            title=dict(text="Pressure (hPa)", font=dict(color="#10b981")), tickfont=dict(color="#10b981"),
            overlaying="y", side="right", zeroline=False
        )
    )
    
    # 2. Service health query
    services = get_service_statuses()
    
    # Format Health Panel Card
    health_elems = []
    
    for s_name, data in services.items():
        is_online = data["status"] == "Online"
        badge_class = "status-badge status-online" if is_online else "status-badge status-offline"
        badge_text = "Online" if is_online else "Offline"
        
        # Calculate pretty uptime
        uptime_sec = data["uptime"]
        if uptime_sec > 3600:
            uptime_str = f"{uptime_sec/3600:.1f} hours"
        elif uptime_sec > 60:
            uptime_str = f"{uptime_sec/60:.1f} mins"
        else:
            uptime_str = f"{uptime_sec:.1f} secs"
            
        health_elems.append(
            html.Div([
                html.Div([
                    html.Div([
                        html.Strong(s_name.capitalize(), className="fs-6"),
                        html.Div(f"Uptime: {uptime_str if is_online else 'N/A'}", className="text-secondary fs-8 mt-1"),
                        html.Div(f"Messages: {data['messages']:,}" if is_online else "", className="text-secondary fs-8")
                    ]),
                    html.Div([
                        html.Span([html.Span(className="status-dot"), f" {badge_text}"], className=badge_class),
                        html.Div(f"Seen: {data['last_seen'].split()[-1] if is_online else 'Never'}", className="text-secondary fs-8 text-end mt-1")
                    ], className="text-end")
                ], className="d-flex justify-content-between align-items-center")
            ], className="mb-3 pb-3 border-bottom border-secondary")
        )
        
    # Determine local infrastructure statuses
    is_broker_online = services["simulator"]["status"] == "Online" or services["subscriber"]["status"] == "Online"
    is_db_online = services["subscriber"]["status"] == "Online"
    
    broker_class = "status-badge status-online" if is_broker_online else "status-badge status-offline"
    broker_text = [html.Span(className="status-dot"), " Online"] if is_broker_online else [html.Span(className="status-dot"), " Offline"]
    
    db_class = "status-badge status-online" if is_db_online else "status-badge status-offline"
    db_text = [html.Span(className="status-dot"), " Online"] if is_db_online else [html.Span(className="status-dot"), " Offline"]
    
    return hist_fig, health_elems, broker_class, broker_text, db_class, db_text

@app.callback(
    Output("alert-log-table-body", "children"),
    [
        Input("slow-update-interval", "n_intervals"),
        Input("refresh-alert-btn", "n_clicks"),
        Input("live-update-interval", "n_intervals") # Load alerts immediately on startup
    ]
)
def update_alert_logs(n_slow, n_clicks, n_live):
    alerts = get_alert_logs()
    
    if not alerts:
        return [html.Tr([
            html.Td("No active alerts", colSpan=4, className="text-center text-secondary py-4")
        ])]
        
    rows = []
    for alert in alerts:
        rows.append(html.Tr([
            html.Td(alert["timestamp"]),
            html.Td(alert["sensor"]),
            html.Td(f"{alert['value']:.2f} {alert['unit']}", className="text-danger fw-bold"),
            html.Td(alert["message"], className="text-warning")
        ]))
    return rows

if __name__ == '__main__':
    # Start Dash Server
    print("Starting Live Dashboard Web Server on http://127.0.0.1:8050...", flush=True)
    app.run(debug=False, port=8050)
