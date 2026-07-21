import sys
import os
from influxdb_client import InfluxDBClient

# Set up paths
sys.path.append(os.path.join(os.path.dirname(__file__)))

# Now import the functions from app.py
from app import get_current_readings, update_live_metrics, update_slow_metrics, get_alert_logs

def test_callbacks():
    print("Testing get_current_readings()...")
    try:
        readings = get_current_readings()
        print("Readings:", readings)
    except Exception as e:
        print("get_current_readings failed:", e)

    print("\nTesting update_live_metrics(0)...")
    try:
        res = update_live_metrics(0)
        print("update_live_metrics returned tuple of length:", len(res))
        print("Temp value:", res[0])
        print("Hum value:", res[1])
        print("Press value:", res[2])
        print("Gauge figures types:", type(res[3]), type(res[4]), type(res[5]))
        print("Live chart figure type:", type(res[6]))
        print("Alert Div type:", type(res[7]))
        print("Alert class:", res[8])
    except Exception as e:
        print("update_live_metrics failed:", e)

    print("\nTesting update_slow_metrics(0, 0)...")
    try:
        res = update_slow_metrics(0, 0)
        print("update_slow_metrics returned tuple of length:", len(res))
        print("Hist chart figure type:", type(res[0]))
        print("Health content elements count:", len(res[1]))
        print("Broker badge class:", res[2])
        print("DB badge class:", res[4])
    except Exception as e:
        print("update_slow_metrics failed:", e)

    print("\nTesting get_alert_logs()...")
    try:
        alerts = get_alert_logs()
        print(f"Found {len(alerts)} alerts.")
    except Exception as e:
        print("get_alert_logs failed:", e)

if __name__ == '__main__':
    test_callbacks()
