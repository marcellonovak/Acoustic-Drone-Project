import os
import re
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
from pymavlink import mavutil
from pyproj import Transformer


# ======================== 1. CHECK DATA FOLDER EXISTENCE ========================
data_folder = "data/2025-01-23 09-25-36"
if not os.path.exists(data_folder):
    print(f"Error: Data folder '{data_folder}' not found!")
    exit()


# ======================== 2. PROCESS NODE DATA ========================
print("Processing node CSV files...")

# Find all folders starting with "node" dynamically
node_folders = [folder for folder in os.listdir(data_folder) if folder.startswith("node")]

# Initialize a node dataframe and a lat/lon dictionary
node_data = pd.DataFrame()
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

            # Read CSV, select relevant columns (Timestamp, DroneProb, Status, Latitude, Longitude)
            df = pd.read_csv(file_path, header=None, dtype=str, encoding="utf-8")
            df = df.iloc[:, [7, 4, 9, 5, 6]].copy()
            df.columns = ["Timestamp", "DroneProb", "Status", "Latitude", "Longitude"]

            # Convert timestamp to datetime, convert lat/lon to float
            df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
            df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
            df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

            # Remove "Invalid" rows before checking for "Valid"
            df = df[~df["Status"].str.contains("Invalid", na=False)]
            df = df[df["Status"].str.contains("Valid", na=False)]

            # Extract drone probability value, store lat/lon for this node
            df[node_name] = df["DroneProb"].apply(extract_drone_value)
            node_latitudes.extend(df["Latitude"].dropna().tolist())
            node_longitudes.extend(df["Longitude"].dropna().tolist())
            df = df[["Timestamp", node_name]]  # Keep only timestamp and node prob

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
        print(f"Computed Averages for {node_name}: Latitude = {avg_lat}, Longitude = {avg_lon}\n")

# Ensure node data is sorted by timestamp, fill empty cells with 0's
node_data = node_data.sort_values("Timestamp")
node_data.fillna(0, inplace=True)


# ======================== 3. PROCESS DRONE DATA ========================
print("Processing drone data...")

# Extract datetime from folder name
folder_datetime = os.path.basename(data_folder)

# Dynamically set bin file path based on detected folder name
bin_file = os.path.join(data_folder, "drone", f"{folder_datetime}.bin")

# Ensure the file exists
print(f"Looking for bin file: {bin_file}")  # Debugging print
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

# Convert lat/lon
df_drone["Latitude"] = pd.to_numeric(df_drone["Lat"], errors="coerce")
df_drone["Longitude"] = pd.to_numeric(df_drone["Lng"], errors="coerce")

# Set origin as the first valid drone data point
origin_lat = df_drone["Latitude"].iloc[0]
origin_lon = df_drone["Longitude"].iloc[0]

# Convert lat/lon to meters using pyproj
transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
df_drone["X_meters"], df_drone["Y_meters"] = transformer.transform(df_drone["Longitude"], df_drone["Latitude"])
origin_x, origin_y = transformer.transform(origin_lon, origin_lat)

# Adjust coordinates so the first point is the origin
df_drone["X_meters"] -= origin_x
df_drone["Y_meters"] -= origin_y


# ======================== 4. MERGE DATA ========================
print("Merging node and drone data...")

df_final = pd.merge_asof(node_data.sort_values("Timestamp"), df_drone.sort_values("Timestamp"),
                         on="Timestamp", direction="nearest")

# Compute MaxNode only if node columns exist
node_columns = [col for col in df_final.columns if col.startswith("node")]
df_final["MaxNode"] = df_final[node_columns].max(axis=1) if node_columns else 0


# ======================== 5. PLOT THE DATA (2D) ========================
print(f"Using datetime for plot: {folder_datetime}")

fig, ax = plt.subplots(figsize=(10, 7))

# Plot each node's average location as an 'X' under both lines
for i, (node, (avg_lat, avg_lon)) in enumerate(node_avg_locations.items()):
    x_m, y_m = transformer.transform(avg_lon, avg_lat)
    x_m -= origin_x
    y_m -= origin_y
    ax.scatter(x_m, y_m, marker="x", s=150, linewidths=3, label=f"{node} Avg Location", zorder=1)

# Plot black line UNDER the drone points
ax.plot(df_final["X_meters"], df_final["Y_meters"], color="black", linewidth=1, zorder=2)

# Plot drone path points
sc = ax.scatter(df_final["X_meters"], df_final["Y_meters"], c=df_final["MaxNode"], cmap="RdYlGn",
                norm=Normalize(vmin=df_final["MaxNode"].min(), vmax=df_final["MaxNode"].max()),
                marker="o", s=15, label="Drone Path", zorder=3)

fig.colorbar(sc, ax=ax, pad=0.01).set_label("Scaled Node Values")
ax.set_xlabel("Latitude Distance (meters)")
ax.set_ylabel("Longitude Distance (meters)")
ax.set_title(f"2D Drone Data for: {folder_datetime}")
ax.legend()
ax.grid(True)

plt.savefig(f'flight_2D_{folder_datetime}.png')
plt.show()
