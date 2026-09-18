# Databricks notebook source
# MAGIC %sql
# MAGIC -- 1. Create the schema (database) for our project if it does not exist
# MAGIC CREATE SCHEMA IF NOT EXISTS fintraffic_risk_db
# MAGIC COMMENT 'Schema for real-time Finnish traffic risk and infrastructure analytics';
# MAGIC
# MAGIC -- 2. Set the created schema as active by default
# MAGIC USE SCHEMA fintraffic_risk_db;
# MAGIC
# MAGIC -- 3. Create the Delta table for raw/processed traffic incidents from Fintraffic API
# MAGIC CREATE TABLE IF NOT EXISTS traffic_incidents (
# MAGIC     situation_id STRING,
# MAGIC     situation_type STRING,
# MAGIC     announcement_title STRING,
# MAGIC     road_number STRING,
# MAGIC     municipality STRING,
# MAGIC     start_time TIMESTAMP,
# MAGIC     end_time TIMESTAMP,
# MAGIC     data_updated_time TIMESTAMP
# MAGIC )
# MAGIC USING DELTA
# MAGIC COMMENT 'Processed live traffic incidents and road work risks from Fintraffic API';
# MAGIC
# MAGIC -- 4. Create a Unity Catalog Volume for storing raw snapshots or logs if needed
# MAGIC CREATE VOLUME IF NOT EXISTS raw_traffic_vol
# MAGIC COMMENT 'Volume for storing raw JSON snapshots from Fintraffic API';

# COMMAND ----------

# DBTITLE 1,Cell 2
import requests
import pandas as pd
import json

# 1. Fetch live traffic messages from Fintraffic API
url = "https://tie.digitraffic.fi/api/traffic-message/v1/messages"
headers = {
    "User-Agent": "FintrafficRiskAnalyticsProject",
    "Accept": "application/json"
}

response = requests.get(url, headers=headers, timeout=10)
data = response.json()

# 2. Flatten the nested JSON structure into a clean tabular DataFrame
messages_df = pd.json_normalize(data['features'])

# 3. Convert complex types (lists, dicts) to JSON strings for Arrow compatibility
for col in messages_df.columns:
    if messages_df[col].apply(lambda x: isinstance(x, (list, dict))).any():
        messages_df[col] = messages_df[col].apply(lambda x: json.dumps(x) if isinstance(x, (list, dict)) else None)

# 4. Print all flattened column names to verify exact names
print("Available columns in the dataset:")
print(messages_df.columns.tolist())

# 5. Quick preview of the first few rows
display(messages_df.head(10))

# COMMAND ----------

import datetime
import json
import pandas as pd
from pyspark.sql import functions as F

# 1. Get the current date (e.g., '2026-09-16')
current_date = datetime.date.today().isoformat()

# 2. Extract fields from the API data to match the Delta table schema
records = []
for _, row in messages_df.iterrows():
    announcements = json.loads(row['properties.announcements']) if pd.notna(row['properties.announcements']) else []
    ann = announcements[0] if announcements else {}
    road_address = ann.get('locationDetails', {}).get('roadAddressLocation', {}).get('primaryPoint', {})
    time_and_duration = ann.get('timeAndDuration', {})
    road_num = road_address.get('roadAddress', {}).get('road')
    records.append({
        'situation_id': row.get('properties.situationId'),
        'situation_type': row.get('properties.situationType'),
        'announcement_title': ann.get('title'),
        'road_number': str(road_num) if road_num is not None else None,
        'municipality': road_address.get('municipality'),
        'start_time': time_and_duration.get('startTime'),
        'end_time': time_and_duration.get('endTime'),
        'data_updated_time': row.get('properties.dataUpdatedTime'),
    })

clean_df = pd.DataFrame(records)

# 3. Convert to Spark DataFrame, cast timestamps, and add the snapshot date
spark_df = spark.createDataFrame(clean_df) \
    .withColumn("start_time", F.to_timestamp("start_time")) \
    .withColumn("end_time", F.to_timestamp("end_time")) \
    .withColumn("data_updated_time", F.to_timestamp("data_updated_time")) \
    .withColumn("snapshot_date", F.lit(current_date))

# 4. Save the data to your Delta table using append mode (with schema auto-merge enabled just in case)
(
    spark_df.write
    .format("delta")
    .mode("append")
    .option("mergeSchema", "true")
    .saveAsTable("fintraffic_risk_db.traffic_incidents")
)

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT snapshot_date, COUNT(*) as total_events 
# MAGIC FROM fintraffic_risk_db.traffic_incidents 
# MAGIC GROUP BY snapshot_date;

# COMMAND ----------

spark.sql("DELETE FROM fintraffic_risk_db.traffic_incidents WHERE snapshot_date IS NULL")