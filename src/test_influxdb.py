from influxdb_client import InfluxDBClient

client = InfluxDBClient(
    url="http://localhost:8086",
    token="IOT_Dashboard_Token_For_InfluxDB_Security_1234567890_ABCDEFGHIJ_",
    org="iot_org"
)
query_api = client.query_api()

query = 'from(bucket:"iot_bucket") |> range(start: -5m) |> filter(fn: (r) => r["_measurement"] == "telemetry")'
try:
    result = query_api.query(query=query)
    count = 0
    for table in result:
        for record in table.records:
            print(f"Time: {record.get_time()}, Sensor: {record.values.get('sensor_id')}, Metric: {record.values.get('type')}, Value: {record.get_value()} {record.values.get('unit')}")
            count += 1
            if count >= 10:  # Just show first 10
                break
        if count >= 10:
            break
    print(f"Total telemetry records found: {count}")
except Exception as e:
    print(f"Error querying InfluxDB: {e}")
finally:
    client.close()
