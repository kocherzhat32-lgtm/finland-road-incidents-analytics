# Databricks notebook source
# 1. Check data types and basic info of the dataframe
print("Dataset Info:")
print(messages_df.info())

# 2. Check for missing values per column
missing_values = messages_df.isnull().sum()
print("\nColumns with missing values:")
print(missing_values[missing_values > 0])

# 3. Directly target the actual traffic situation types column
target_col = 'properties.situationType'

if target_col in messages_df.columns:
    print(f"\nTop values in '{target_col}':")
    print(messages_df[target_col].value_counts().head(10))
else:
    print(f"Column '{target_col}' not found in dataframe.")

# COMMAND ----------

# 1. Check the distribution of traffic situation types
situation_counts = messages_df['properties.situationType'].value_counts()
print("Traffic Situation Types Distribution:")
print(situation_counts)

# 2. Visualize the distribution using a clean bar chart
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style="whitegrid")
plt.figure(figsize=(10, 4))
situation_counts.plot(kind='bar', color='teal')
plt.title("Distribution of Traffic Situation Types")
plt.xlabel("Situation Type")
plt.ylabel("Count")
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.show()

# COMMAND ----------

# 1. Let's inspect the structure of 'properties.announcements' for the first record
import json

sample_announcement = messages_df['properties.announcements'].iloc[0]
print("Sample announcement raw structure:")
print(sample_announcement)

# 2. If it's stored as a JSON string (due to our earlier conversion), let's parse it to see text details
if isinstance(sample_announcement, str):
    parsed_announcement = json.loads(sample_announcement)
    print("\nParsed announcement details:")
    print(json.dumps(parsed_announcement, indent=2, ensure_ascii=False))

# COMMAND ----------

# DBTITLE 1,Cell 4
import json
import requests
import pandas as pd

# Load data from the Fintraffic API if not already loaded in the workspace memory
if 'messages_df' not in globals():
    url = "https://tie.digitraffic.fi/api/traffic-message/v1/messages"
    headers = {
        "User-Agent": "FintrafficRiskAnalyticsProject",
        "Accept": "application/json"
    }
    response = requests.get(url, headers=headers, timeout=10)
    data = response.json()
    messages_df = pd.json_normalize(data['features'])
    
    # Flatten nested lists and dictionaries into JSON string format for safe DataFrame storage
    for col in messages_df.columns:
        if messages_df[col].apply(lambda x: isinstance(x, (list, dict))).any():
            messages_df[col] = messages_df[col].apply(lambda x: json.dumps(x) if isinstance(x, (list, dict)) else None)

# 1. Helper function to extract the title of the first announcement
def get_title(x):
    try:
        data = json.loads(x) if isinstance(x, str) else x
        return data[0].get('title') if data else None
    except:
        return None

# 2. Helper function to extract the start time of the traffic event
def get_start_time(x):
    try:
        data = json.loads(x) if isinstance(x, str) else x
        if data and isinstance(data, list):
            return data[0].get('timeAndDuration', {}).get('startTime')
        return None
    except:
        return None

# 3. Helper function to extract the end time of the traffic event
def get_end_time(x):
    try:
        data = json.loads(x) if isinstance(x, str) else x
        if data and isinstance(data, list):
            return data[0].get('timeAndDuration', {}).get('endTime')
        return None
    except:
        return None

# 4. Add structured columns to the dataframe
messages_df['announcement_title'] = messages_df['properties.announcements'].apply(get_title)
messages_df['start_time'] = messages_df['properties.announcements'].apply(get_start_time)
messages_df['end_time'] = messages_df['properties.announcements'].apply(get_end_time)

# 5. Convert start and end times to proper Pandas datetime format
messages_df['start_time'] = pd.to_datetime(messages_df['start_time'], errors='coerce')
messages_df['end_time'] = pd.to_datetime(messages_df['end_time'], errors='coerce')

# 6. Configure pandas display settings to prevent columns from being hidden
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

# 7. Preview the final structured dataset with titles and timestamps
print("Dataset preview with titles, start times, and end times:")
print(messages_df[['announcement_title', 'start_time', 'end_time']].head(10))

# COMMAND ----------

import re

# 1. Extract road numbers from announcement titles using a simple regex pattern
def extract_road(title):
    if not title:
        return "Other"
    match = re.search(r'Tie\s+\d+', title)
    return match.group(0) if match else "Other"

messages_df['road'] = messages_df['announcement_title'].apply(extract_road)

# 2. Aggregate incidents by road to see where risks are concentrated
road_summary = messages_df['road'].value_counts().reset_index()
road_summary.columns = ['Road', 'Incident_Count']

# 3. Display the clean summary table for our portfolio
print("Top Roads by Traffic Incidents:")
display(road_summary.head(10))

# COMMAND ----------

import matplotlib.pyplot as plt
import seaborn as sns

# 1. Set the visual style for a professional look
sns.set_theme(style="whitegrid")
plt.figure(figsize=(10, 6))

# 2. Filter out 'Other' and select the top 10 actual numbered roads for the chart
clean_road_summary = road_summary[road_summary['Road'] != 'Other']
top_roads = clean_road_summary.head(10)

# 3. Create a clean horizontal bar chart
ax = sns.barplot(x='Incident_Count', y='Road', data=top_roads, palette="Blues_r")

# 4. Add titles and labels for portfolio presentation
plt.title("Top 10 Finnish Numbered Roads by Traffic Incidents", fontsize=14, fontweight='bold', pad=15)
plt.xlabel("Number of Incidents", fontsize=12)
plt.ylabel("Road", fontsize=12)

# 5. Display the plot
plt.tight_layout()
plt.show()