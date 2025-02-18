import os
import re
from datetime import datetime, timedelta
from pymavlink import mavutil
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable

# ======================== 1. PROCESS NODE DATA ========================
print("Processing node CSV files...")

# Path to the main data folder
data_folder = "data/2025-01-23 09-25-36"

# Find all folders starting with "node" dynamically
node_folders = [folder for folder in os.listdir(data_folder) if folder.startswith("node")]

# Initialize an empty DataFrame for node data
node_data = pd.DataFrame()

# Dictionary to store each node’s average lat/lon
node_avg_locations = {}

# Function to extract 'drone' probability value from a text field
def extract_drone_value(text):
    match = re.search(r"drone:\s*([\d\.]+)", str(text))
    return float(match.group(1)) if match else np.nan  # Convert to float

# Loop through each node folder
for folder in node_folders:
    folder_path = os.path.join(data_folder, folder)
    node_name = folder  # Use folder name dynamically

    # Lists to store lat/lon for this specific node
    node_latitudes = []
    node_longitudes = []

    # Check if folder and CSV files exist
    for file in os.listdir(folder_path):
        if file.lower().endswith(".csv"):
            file_path = os.path.join(folder_path, file)
            print(f"Processing {file_path}...")

            # Read CSV
            df = pd.read_csv(file_path, header=None, dtype=str, encoding="utf-8")

            # Select relevant columns (Timestamp, DroneProb, Status, Latitude, Longitude)
            df = df.iloc[:, [7, 4, 9, 5, 6]].copy()
            df.columns = ["Timestamp", "DroneProb", "Status", "Latitude", "Longitude"]

            # Convert Timestamp to datetime
            df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")

            # Convert Latitude and Longitude to float
            df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
            df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

            # Remove "Invalid" rows before checking for "Valid"
            df = df[~df["Status"].str.contains("Invalid", na=False)]
            df = df[df["Status"].str.contains("Valid", na=False)]

            # **DEBUG: Print first few rows of valid lat/lon data**
            print(f"\nValid Latitude/Longitude for {node_name}:")
            print(df[["Latitude", "Longitude"]].head(5))  # Print first 5 rows

            # Extract drone probability value
            df[node_name] = df["DroneProb"].apply(extract_drone_value)

            # Store valid ground lat/lon for averaging for this specific node
            node_latitudes.extend(df["Latitude"].dropna().tolist())
            node_longitudes.extend(df["Longitude"].dropna().tolist())

            # Keep only Timestamp & node value
            df = df[["Timestamp", node_name]]

            # Merge into main node DataFrame
            if node_data.empty:
                node_data = df
            else:
                node_data = pd.merge(node_data, df, on="Timestamp", how="outer")

    # Compute the average latitude and longitude for this node
    if node_latitudes and node_longitudes:
        avg_lat = np.mean(node_latitudes)
        avg_lon = np.mean(node_longitudes)
        node_avg_locations[node_name] = (avg_lat, avg_lon)

        # **DEBUG: Print computed averages**
        print(f"\nComputed Averages for {node_name}: Latitude = {avg_lat}, Longitude = {avg_lon}\n")

# Ensure node data is sorted by timestamp, fill empty cells with 0's
node_data = node_data.sort_values("Timestamp")
node_data.fillna(0, inplace=True)


# ======================== 2. PROCESS DRONE DATA ========================
print("Processing drone data...")

# Extract datetime from folder name
folder_datetime = os.path.basename(data_folder)  # e.g., "2025-01-23 09-25-36"

# Dynamically set bin file path based on detected folder name
bin_file = os.path.join(data_folder, "drone", f"{folder_datetime}.bin")

print(f"Looking for bin file: {bin_file}")  # Debugging print

# Ensure the file exists
if not os.path.exists(bin_file):
    print(f"Error: Drone log file '{bin_file}' not found!")
    exit()

# Connect to the binary log file
mav = mavutil.mavlink_connection(bin_file, robust_parsing=True)

# Store GPS data
drone_data = []

# Read messages and extract only GPS position & time
while True:
    msg = mav.recv_match(type="GPS", blocking=False)
    if msg is None:
        break
    msg_dict = msg.to_dict()

    # Ensure required fields exist
    if all(key in msg_dict for key in ["GMS", "GWk", "Lat", "Lng"]):
        drone_data.append(msg_dict)

# Convert to DataFrame
if not drone_data:
    print("No drone GPS data found.")
    exit()

df_drone = pd.DataFrame(drone_data)

# Convert GPS time to UTC
gps_epoch = datetime(1980, 1, 6)  # GPS Epoch start date
leap_seconds = 18  # GPS time is ahead of UTC by 18 sec

df_drone["Timestamp"] = df_drone.apply(
    lambda row: gps_epoch + timedelta(weeks=row["GWk"], milliseconds=row["GMS"] - (leap_seconds * 1000)),
    axis=1
)

# Convert lat/lon (fix: remove incorrect division)
df_drone["Latitude"] = pd.to_numeric(df_drone["Lat"], errors="coerce")
df_drone["Longitude"] = pd.to_numeric(df_drone["Lng"], errors="coerce")

# ======================== 3. MERGE DATA (FIRST FIT NODE DATA, THEN DRONE) ========================
print("Merging node and drone data...")

# Merge node data first (ensuring timestamps are matched correctly)
df_final = node_data.copy()

# Merge drone data by finding the closest timestamp for each node entry
df_final = pd.merge_asof(df_final.sort_values("Timestamp"), df_drone.sort_values("Timestamp"),
                         on="Timestamp", direction="nearest")


# ======================== 4. SAVE TO CSV ========================
output_file = os.path.join(data_folder, "flight_data.csv")
df_final.to_csv(output_file, index=False)

print(f"Data successfully merged and saved to {output_file}")


# ======================== 5. PLOT THE DATA (2D) ========================
print(f"Using datetime for plot: {folder_datetime}")  # Debugging print

fig, ax = plt.subplots(figsize=(10, 7))

# Plot each node's average location as an 'X'
for node, (avg_lat, avg_lon) in node_avg_locations.items():
    ax.scatter(avg_lon, avg_lat, marker="x", s=150, linewidths=3, label=f"{node} Avg Location", zorder=2)

# Compute max node value per timestamp for color mapping
node_columns = [col for col in df_final.columns if col.startswith("node")]
df_final["MaxNode"] = df_final[node_columns].max(axis=1)

# Get overall min and max for color normalization
min_val = df_final["MaxNode"].min()
max_val = df_final["MaxNode"].max()

# Prevent division by zero
if min_val == max_val:
    min_val, max_val = 0, 1

norm = Normalize(vmin=min_val, vmax=max_val)
cmap = plt.get_cmap("RdYlGn")

# Plot drone path with color mapping
sc = ax.scatter(
    df_final["Longitude"], df_final["Latitude"], 
    c=df_final["MaxNode"], cmap=cmap, norm=norm, 
    marker="o", s=15, label="Drone Path", zorder=3
)

# Add colorbar
sm = ScalarMappable(norm=norm, cmap=cmap)
sm.set_array(df_final["MaxNode"])
cbar = fig.colorbar(sm, ax=ax, pad=0.01)
cbar.set_label("Scaled Node Values")

# Labels and title
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.set_title(f"2D Drone Data for: {folder_datetime}")
ax.legend()

plt.savefig(f'flight_2D_{folder_datetime}.png')
plt.show()
