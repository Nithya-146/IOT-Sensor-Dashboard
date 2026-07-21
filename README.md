# Live IoT Sensor Monitoring Dashboard

A premium, real-time IoT Telemetry Analytics dashboard styled with a dark glassmorphic design. This project simulates temperature, humidity, and pressure sensors, streams the data via an MQTT broker, stores it in InfluxDB time-series database, and visualizes live streams alongside 24-hour trends on a Plotly Dash dashboard.

## ⚡ Tech Stack
- **Language**: Python 3.14
- **MQTT Broker**: amqtt (Embedded Python MQTT Broker)
- **Time-Series DB**: InfluxDB OSS 2.7.12
- **Dashboard Framework**: Plotly Dash
- **UI Styling**: Bootstrap + Custom Glassmorphism CSS

---

## 🏛️ Architecture & Data Flow

```mermaid
graph LR
    subgraph Sensors (Simulator)
        T[Temp Sensor] -->|Publish| MQTT
        H[Hum Sensor] -->|Publish| MQTT
        P[Pres Sensor] -->|Publish| MQTT
    end

    subgraph Broker
        MQTT[amqtt Broker:1883]
    end

    subgraph Ingestion
        MQTT -->|Subscribe| Sub[Subscriber Service]
        Sub -->|Write Points| Influx[InfluxDB:8086]
    end

    subgraph Visualization
        Dash[Dash Application:8050] -->|Flux Query| Influx
    end
```

1. **Simulator** publishes sensor telemetry (JSON format) to MQTT topics (`iot/sensors/temperature`, etc.) every second.
2. **Subscriber** listens to MQTT topics, processes payloads, and writes time-series records to InfluxDB.
3. **Dash Dashboard** queries current/historical metrics and service health statistics from InfluxDB and displays them in real-time.

---

## 🚀 Getting Started

### 1. Installation & Environment Setup
Clone the repository and install the Python dependencies:
```bash
git clone https://github.com/Nithya-146/IOT-Sensor-Dashboard.git
cd IOT-Sensor-Dashboard
pip install -r requirements.txt
```

### 2. Start the Local Infrastructure (MQTT + InfluxDB)
To start the MQTT broker and InfluxDB instances:
```bash
python src/services_manager.py
```
This manager script will:
- Start the local Python MQTT broker on `localhost:1883`.
- Start InfluxDB on `localhost:8086`.
- Programmatically run the initial InfluxDB configuration (creating organization `iot_org`, bucket `iot_bucket`, and security token).

### 3. Start Ingestion & Simulation
Start the subscriber service to listen for MQTT messages and write them to InfluxDB:
```bash
python src/subscriber.py
```
Then, start the IoT sensor simulator to begin streaming data:
```bash
python src/simulator.py
```

### 4. Launch the Dashboard
Start the Plotly Dash web server:
```bash
python src/app.py
```
Open your browser and navigate to:
**[http://127.0.0.1:8050/](http://127.0.0.1:8050/)**

---

## 💎 Features & Custom Styling
- **Real-Time Indicators**: Clean radial gauges that monitor current conditions.
- **Visual Alert System**: Flashing warnings when temperatures cross critical thresholds (> 80°C).
- **Persistent Alert Logs**: Log entries queried dynamically from historical data in InfluxDB.
- **Sensor Uptime & Health Grid**: Tracks the connectivity and message throughput of all services.
- **Historical Analysis**: Dual-axis line charts showing the relationship of metrics over a 24-hour window.
