import sys
import os
from influxdb_client import InfluxDBClient

INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "IOT_Dashboard_Token_For_InfluxDB_Security_1234567890_ABCDEFGHIJ_"
INFLUX_ORG = "iot_org"
INFLUX_BUCKET = "iot_bucket"

try:
    db_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    query_api = db_client.query_api()
    print("Connected to InfluxDB.")
except Exception as e:
    print(f"Connection failed: {e}")
    sys.exit(1)

# Test telemetry query
import pandas as pd
import numpy as np

def test_telemetry():
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -5m)
      |> filter(fn: (r) => r["_measurement"] == "telemetry")
      |> pivot(rowKey:["_time"], columnKey: ["type"], valueColumn: "_value")
    '''
    try:
        df = query_api.query_data_frame(query=query)
        print("Raw query result type:", type(df))
        if isinstance(df, list):
            print("Result is a list of len:", len(df))
            df = pd.concat(df, ignore_index=True)
        print("DF empty?", df.empty if df is not None else "None")
        if df is not None and not df.empty:
            print("DF columns:", df.columns)
            df = df.rename(columns={"_time": "time"})
            # Let's test tz_convert
            try:
                df["time"] = pd.to_datetime(df["time"]).dt.tz_convert('Asia/Kolkata')
                print("TimeZone conversion succeeded.")
            except Exception as ex:
                print("TimeZone conversion failed:", ex)
        else:
            print("No data found or df is None")
    except Exception as e:
        print("Query execution failed:", e)

def test_health():
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -2m)
      |> filter(fn: (r) => r["_measurement"] == "service_status")
      |> last()
    '''
    try:
        tables = query_api.query(query=query)
        print("Service status tables count:", len(tables))
    except Exception as e:
        print("Service status query failed:", e)

if __name__ == '__main__':
    test_telemetry()
    test_health()
    db_client.close()
