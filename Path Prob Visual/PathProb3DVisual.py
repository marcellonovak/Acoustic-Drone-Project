import os
import re
from datetime import datetime, timedelta
from pymavlink import mavutil
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
from mpl_toolkits.mplot3d import Axes3D  # Import for 3D plotting

# ======================== 1. PROCESS NODE DATA ========================
print("Processing node CSV files...")

# Path to the main data folder
# data_folder = "data/2025-01-23 09-25-36"
data_folder = "data/2025-01-23 09-25-36"

# Find all folders starting with "node" dynamically
node_folders = [folder for folder in os.listdir(data_folder) if folder.startswith("node")]

# Initialize an empty DataFrame for node data
node_data = pd.DataFrame()

# Function to extract 'drone' probability value from a text field
def extract_drone_value(text):
    match = re.search(r"drone:\s*([\d\.]+)", str(text))
    return float(match.group(1)) if match else np.nan  # Convert to float

# Loop through each node folder
for folder in node_folders:
    folder_path = os.path.join(data_folder, folder)
    node_name = folder  # Use folder name dynamically

    # Check if folder and CSV files exist
    for file in os.listdir(folder_path):
        if file.lower().endswith(".csv"):
            file_path = os.path.join(folder_path, file)
            print(f"Processing {file_path}...")

            # Read CSV
            df = pd.read_csv(file_path, header=None, dtype=str, encoding="utf-8")

            # Select correct column for Drone Probability
            df = df.iloc[:, [7, 4, 9]].copy()
            df.columns = ["Timestamp", "DroneProb", "Status"]

            # Convert Timestamp to datetime
            df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")

            # Remove "Invalid" rows before checking for "Valid"
            df = df[~df["Status"].str.contains("Invalid", na=False)]
            df = df[df["Status"].str.contains("Valid", na=False)]

            # Extract drone probability value, keep only timestamp and node value
            df[node_name] = df["DroneProb"].apply(extract_drone_value)
            df = df[["Timestamp", node_name]]

            # Merge into main node DataFrame
            if node_data.empty:
                node_data = df
            else:
                node_data = pd.merge(node_data, df, on="Timestamp", how="outer")

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
    if all(key in msg_dict for key in ["GMS", "GWk", "Lat", "Lng", "Alt"]):
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

# Convert lat/lon/alt
df_drone["Latitude"] = df_drone["Lat"] / 1e7
df_drone["Longitude"] = df_drone["Lng"] / 1e7
df_drone["Altitude"] = df_drone["Alt"] / 100  # Convert cm to meters

# Keep only required columns
df_drone = df_drone[["Timestamp", "Latitude", "Longitude", "Altitude"]]


# ======================== 3. MERGE DATA (FIRST FIT NODE DATA, THEN DRONE) ========================
print("Merging node and drone data...")

# Merge node data first (ensuring timestamps are matched correctly)
df_final = node_data.copy()

# Merge drone data by finding the closest timestamp for each node entry
df_final = pd.merge_asof(df_final.sort_values("Timestamp"), df_drone.sort_values("Timestamp"),
                         on="Timestamp", direction="nearest")


# ======================== 4. SAVE TO CSV ========================
output_file = os.path.join(data_folder, "merged_flight_data_fixed.csv")
df_final.to_csv(output_file, index=False)

print(f"Data successfully merged and saved to {output_file}")


# ======================== 5. PLOT THE DATA ========================

# Get node columns dynamically (ignore non-numeric columns like Timestamp, Latitude, etc.)
node_columns = [col for col in df_final.columns if col.startswith("node")]

# Extract datetime from folder name
print(f"Using datetime for plot: {folder_datetime}")  # Debugging print

# Ensure we have necessary GPS and node data
if all(col in df_final.columns for col in ["Longitude", "Latitude", "Altitude"]) and node_columns:
    print("Plotting 3D drone flight path...")
    print(f"Using node columns: {node_columns}")  # Debugging print

    # Compute max value across all node columns dynamically
    df_final["MaxNode"] = df_final[node_columns].max(axis=1)

    # Get overall min and max of node columns for color normalization
    min_val = df_final[node_columns].min().min()
    max_val = df_final[node_columns].max().max()

    # Prevent division by zero if no valid data
    if min_val == max_val:
        min_val, max_val = 0, 1

    norm = Normalize(vmin=min_val, vmax=max_val)
    cmap = plt.get_cmap("RdYlGn")  # Red to Green colormap

    # Create 3D figure and axis
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection="3d")

    # Convert dataframe to numpy arrays for plotting
    xs = df_final["Longitude"].to_numpy()
    ys = df_final["Latitude"].to_numpy()
    zs = df_final["Altitude"].to_numpy()
    colors = cmap(norm(df_final["MaxNode"].to_numpy()))

    # Plot points with color mapping
    ax.scatter(xs, ys, zs, c=colors, marker="o", s=15)  # s=15 sets point size

    # Create color bar
    sm = ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array(df_final["MaxNode"])
    cbar = fig.colorbar(sm, ax=ax, pad=0.1)
    cbar.set_label("Scaled Node Values")

    # Set labels and title
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_zlabel("Altitude (m)")
    ax.set_title(f"3D Drone Data for: {folder_datetime}")

    # Plot the data
    plt.show()

else:
    print("No GPS data available for plotting.")