import time
import json
import random
import math
import sys
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

BROKER = "127.0.0.1"
PORT = 1883
CLIENT_ID = "iot_sensor_simulator"

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print("Simulator connected to MQTT Broker successfully.", flush=True)
    else:
        print(f"Simulator connection failed with code {reason_code}", file=sys.stderr, flush=True)

def main():
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id=CLIENT_ID)
    client.on_connect = on_connect
    
    # Try connecting to the local broker
    try:
        client.connect(BROKER, PORT, keepalive=60)
    except Exception as e:
        print(f"Failed to connect to broker: {e}. Make sure services are running.", file=sys.stderr, flush=True)
        sys.exit(1)
        
    client.loop_start()
    
    print("Simulator starting transmission. Press Ctrl+C to stop.", flush=True)
    
    start_time = time.time()
    tick = 0
    try:
        while True:
            utc_now = datetime.now(timezone.utc).isoformat()
            
            # 1. Temperature Simulation
            temp_base = 65.0 + 10.0 * math.sin(tick / 50.0)
            temp_noise = random.uniform(-1.5, 1.5)
            if tick % 45 in [15, 16, 17]: # Spikes
                temp_spike = random.uniform(15.0, 22.0)
            else:
                temp_spike = 0.0
            temperature = round(temp_base + temp_noise + temp_spike, 2)
            
            # 2. Humidity Simulation
            humidity_base = 60.0 + 15.0 * math.cos(tick / 80.0)
            humidity = round(max(30.0, min(95.0, humidity_base + random.uniform(-2.0, 2.0))), 2)
            
            # 3. Pressure Simulation
            pressure_base = 1013.25 + 5.0 * math.sin(tick / 120.0)
            pressure = round(pressure_base + random.uniform(-0.5, 0.5), 2)
            
            # Build payloads
            payloads = {
                "iot/sensors/temperature": {
                    "sensor_id": "temp_sensor_01",
                    "timestamp": utc_now,
                    "value": temperature,
                    "unit": "°C"
                },
                "iot/sensors/humidity": {
                    "sensor_id": "hum_sensor_01",
                    "timestamp": utc_now,
                    "value": humidity,
                    "unit": "%"
                },
                "iot/sensors/pressure": {
                    "sensor_id": "pres_sensor_01",
                    "timestamp": utc_now,
                    "value": pressure,
                    "unit": "hPa"
                }
            }
            
            # Publish payloads
            for topic, data in payloads.items():
                payload_str = json.dumps(data)
                res = client.publish(topic, payload_str, qos=0)
                if res.rc != mqtt.MQTT_ERR_SUCCESS:
                    print(f"Failed to publish to {topic}: code {res.rc}", file=sys.stderr, flush=True)
            
            # Publish simulator health every 5 seconds
            if tick % 5 == 0:
                health_payload = {
                    "service_name": "simulator",
                    "timestamp": utc_now,
                    "status": "Online",
                    "uptime_seconds": round(time.time() - start_time, 1),
                    "message_count": tick * 3
                }
                client.publish("iot/health/simulator", json.dumps(health_payload), qos=0)
            
            # Log progress locally
            if tick % 10 == 0:
                print(f"[Simulator] Published readings: T={temperature}°C, H={humidity}%, P={pressure} hPa", flush=True)
                
            tick += 1
            time.sleep(1.0)
            
    except KeyboardInterrupt:
        print("Simulator stopping...", flush=True)
    finally:
        client.loop_stop()
        client.disconnect()
        print("Simulator stopped.", flush=True)

if __name__ == '__main__':
    main()
