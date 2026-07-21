import os
import sys
import time
import subprocess
import urllib.request
import urllib.error
import json
import threading

# Base directory paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVICES_DIR = os.path.join(BASE_DIR, "services")
INFLUX_DIR = os.path.join(SERVICES_DIR, "influxdb")
INFLUX_DATA_DIR = os.path.join(INFLUX_DIR, "data")

# Create directories
os.makedirs(INFLUX_DATA_DIR, exist_ok=True)

# Settings
INFLUX_PORT = 8086
MQTT_PORT = 1883

INFLUX_ORG = "iot_org"
INFLUX_BUCKET = "iot_bucket"
INFLUX_TOKEN = "IOT_Dashboard_Token_For_InfluxDB_Security_1234567890_ABCDEFGHIJ_"
INFLUX_USER = "admin"
INFLUX_PASSWORD = "password12345"

processes = []

def log(msg):
    print(f"[Services Manager] {msg}", flush=True)

def run_mqtt_broker():
    log("Starting Python MQTT Broker...")
    broker_script = os.path.join(BASE_DIR, "src", "broker.py")
    proc = subprocess.Popen(
        [sys.executable, broker_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    processes.append(("MQTT Broker", proc))
    
    # Thread to read output
    def read_output():
        for line in proc.stdout:
            print(f"[MQTT Broker LOG] {line.strip()}", flush=True)
            
    threading.Thread(target=read_output, daemon=True).start()

def run_influxdb():
    log("Starting InfluxDB...")
    influx_exe = os.path.join(INFLUX_DIR, "influxd.exe")
    
    # Environment variables to keep InfluxDB local
    env = os.environ.copy()
    env["INFLUXD_ENGINE_PATH"] = os.path.join(INFLUX_DATA_DIR, "engine")
    env["INFLUXD_BOLT_PATH"] = os.path.join(INFLUX_DATA_DIR, "influxd.bolt")
    env["INFLUXD_HTTP_BIND_ADDRESS"] = f":{INFLUX_PORT}"
    
    proc = subprocess.Popen(
        [influx_exe],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    processes.append(("InfluxDB", proc))
    
    # Thread to read output
    def read_output():
        for line in proc.stdout:
            # We don't print every database log line to avoid log pollution,
            # but we can print startup progress.
            if "Listening" in line or "Unauthorized" in line or "Error" in line:
                print(f"[InfluxDB LOG] {line.strip()}", flush=True)
            
    threading.Thread(target=read_output, daemon=True).start()

def wait_and_setup_influxdb():
    url = f"http://localhost:{INFLUX_PORT}/api/v2/setup"
    health_url = f"http://localhost:{INFLUX_PORT}/health"
    
    log("Waiting for InfluxDB to become responsive...")
    for _ in range(30):
        try:
            with urllib.request.urlopen(health_url, timeout=2) as response:
                if response.status == 200:
                    log("InfluxDB health check passed.")
                    break
        except Exception:
            time.sleep(1)
    else:
        log("Error: InfluxDB did not become ready in time.")
        return

    # Call setup API
    setup_payload = {
        "username": INFLUX_USER,
        "password": INFLUX_PASSWORD,
        "org": INFLUX_ORG,
        "bucket": INFLUX_BUCKET,
        "token": INFLUX_TOKEN
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(setup_payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            log("InfluxDB setup completed successfully.")
            log(f"Configured Bucket: {INFLUX_BUCKET}, Org: {INFLUX_ORG}")
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        if e.code == 412 or "already" in body.lower():
            log("InfluxDB has already been set up. Skipping initial setup.")
        else:
            log(f"InfluxDB setup failed: HTTP {e.code} - {body}")
    except Exception as e:
        log(f"InfluxDB setup error: {e}")

def main():
    try:
        run_mqtt_broker()
        run_influxdb()
        
        # Run InfluxDB setup in separate thread
        threading.Thread(target=wait_and_setup_influxdb, daemon=True).start()
        
        log("Services running. Press Ctrl+C to stop.")
        while True:
            # Check if subprocesses are still alive
            for name, proc in processes:
                if proc.poll() is not None:
                    log(f"Warning: {name} terminated with exit code {proc.returncode}")
                    processes.remove((name, proc))
            time.sleep(2)
            
    except KeyboardInterrupt:
        log("Shutting down services...")
    finally:
        for name, proc in processes:
            try:
                log(f"Stopping {name}...")
                proc.terminate()
                proc.wait(timeout=3)
            except Exception as e:
                log(f"Failed to stop {name}: {e}")
                proc.kill()
        log("Services stopped.")

if __name__ == '__main__':
    main()
