import time
import json
import sys
import threading
from datetime import datetime, timezone
import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# MQTT Configuration
MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPICS = [("iot/sensors/#", 0), ("iot/health/#", 0)]

# InfluxDB Configuration
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "IOT_Dashboard_Token_For_InfluxDB_Security_1234567890_ABCDEFGHIJ_"
INFLUX_ORG = "iot_org"
INFLUX_BUCKET = "iot_bucket"

# Global Statistics for Subscriber
start_time = time.time()
messages_processed = 0

# Clients
mqtt_client = None
db_client = None
write_api = None

def get_db_client():
    global db_client, write_api
    if db_client is None:
        try:
            db_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
            write_api = db_client.write_api(write_options=SYNCHRONOUS)
            print("Connected to InfluxDB successfully.", flush=True)
        except Exception as e:
            print(f"Failed to connect to InfluxDB: {e}", file=sys.stderr, flush=True)
            db_client = None
            write_api = None
    return write_api

def parse_iso_time(time_str):
    try:
        # ISO formats can end with Z or +00:00. replace Z with +00:00 to help python datetime
        if time_str.endswith("Z"):
            time_str = time_str[:-1] + "+00:00"
        return datetime.fromisoformat(time_str)
    except Exception:
        return datetime.now(timezone.utc)

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print("Subscriber connected to MQTT Broker successfully.", flush=True)
        client.subscribe(MQTT_TOPICS)
        print(f"Subscribed to topics: {MQTT_TOPICS}", flush=True)
    else:
        print(f"MQTT Connection failed with code {reason_code}", file=sys.stderr, flush=True)

def on_message(client, userdata, msg):
    global messages_processed
    messages_processed += 1
    
    api = get_db_client()
    if not api:
        return
        
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        topic = msg.topic
        
        if topic.startswith("iot/sensors/"):
            # Telemetry reading
            # Topic format: iot/sensors/<metric> (temperature/humidity/pressure)
            metric_type = topic.split("/")[-1]
            sensor_id = payload.get("sensor_id", "unknown")
            timestamp_str = payload.get("timestamp")
            value = float(payload.get("value", 0.0))
            unit = payload.get("unit", "")
            
            timestamp = parse_iso_time(timestamp_str)
            
            point = Point("telemetry") \
                .tag("sensor_id", sensor_id) \
                .tag("type", metric_type) \
                .tag("unit", unit) \
                .field("value", value) \
                .time(timestamp, WritePrecision.NS)
                
            api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
            
        elif topic == "iot/health/simulator":
            # Simulator health payload
            sensor_status = payload.get("status", "Offline")
            uptime = float(payload.get("uptime_seconds", 0.0))
            msg_count = int(payload.get("message_count", 0))
            timestamp = parse_iso_time(payload.get("timestamp"))
            
            point = Point("service_status") \
                .tag("service_name", "simulator") \
                .field("status", 1 if sensor_status == "Online" else 0) \
                .field("uptime_seconds", uptime) \
                .field("message_count", msg_count) \
                .time(timestamp, WritePrecision.NS)
                
            api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
            
    except Exception as e:
        print(f"Error processing message on topic {msg.topic}: {e}", file=sys.stderr, flush=True)

def write_subscriber_health_loop():
    while True:
        api = get_db_client()
        if api:
            try:
                utc_now = datetime.now(timezone.utc)
                uptime = round(time.time() - start_time, 1)
                
                point = Point("service_status") \
                    .tag("service_name", "subscriber") \
                    .field("status", 1) \
                    .field("uptime_seconds", uptime) \
                    .field("message_count", messages_processed) \
                    .time(utc_now, WritePrecision.NS)
                    
                api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
            except Exception as e:
                print(f"Failed to write subscriber health: {e}", file=sys.stderr, flush=True)
        time.sleep(5.0)

def main():
    global mqtt_client
    
    # Wait briefly for InfluxDB and MQTT to start
    print("Subscriber starting...", flush=True)
    time.sleep(2.0)
    
    # Start subscriber health reporting thread
    health_thread = threading.Thread(target=write_subscriber_health_loop, daemon=True)
    health_thread.start()
    
    mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    except Exception as e:
        print(f"Failed to connect to MQTT broker: {e}. Make sure it is running.", file=sys.stderr, flush=True)
        sys.exit(1)
        
    try:
        print("Subscriber running. Listening for messages. Press Ctrl+C to stop.", flush=True)
        mqtt_client.loop_forever()
    except KeyboardInterrupt:
        print("Subscriber stopping...", flush=True)
    finally:
        if db_client:
            db_client.close()
        print("Subscriber stopped.", flush=True)

if __name__ == '__main__':
    main()
