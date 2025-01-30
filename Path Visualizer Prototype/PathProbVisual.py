import os
import glob
import re
import pandas as pd
import matplotlib.pyplot as plt


def read_and_prepare_csv(file_path):
    """
    Reads a CSV file, extracts relevant columns, and filters for valid rows.
    """
    # Read the CSV file
    df = pd.read_csv(file_path, header=None)

    # Ensure the correct number of columns
    if df.shape[1] > 13:
        df = df.iloc[:, :13]

    df.columns = [
        "index", "id", "type", "background", "drone",
        "latitude", "longitude", "timestamp", "unknown1",
        "status", "unknown2", "unknown3", "value"
    ]

    # Extract numeric drone value
    def extract_drone_value(drone_str):
        match = re.search(r"drone:\s*([0-9.]+)", str(drone_str))
        return float(match.group(1)) if match else None

    df["drone"] = df["drone"].apply(extract_drone_value)
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

    return df[["latitude", "longitude", "drone", "timestamp", "status"]]


def load_data(data_dir):
    """
    Loads all CSV files from subdirectories and processes them.
    """
    if not os.path.exists(data_dir):
        raise FileNotFoundError(f"The data directory '{data_dir}' does not exist.")

    data = {}

    # Iterate over subdirectories in the data directory
    for subdir in os.listdir(data_dir):
        subdir_path = os.path.join(data_dir, subdir)
        if os.path.isdir(subdir_path):
            csv_files = glob.glob(os.path.join(subdir_path, "*.CSV"))
            subdir_data = pd.DataFrame()

            # Process each CSV file
            for csv_file in csv_files:
                df = read_and_prepare_csv(csv_file)
                subdir_data = pd.concat([subdir_data, df], ignore_index=True)

            if not subdir_data.empty:
                data[subdir] = subdir_data

    return data


def plot_all_data(data):
    """
    Creates a single plot window for all subfolder data.
    """
    # Create a new figure
    plt.figure(figsize=(18, 6))

    # Plot mode of lat/lon
    plt.subplot(1, 2, 1)
    for subdir, df in data.items():
        valid_df = df[df["status"] == "Valid"]  # Filter valid rows
        lat_mode = valid_df["latitude"].mode()[0]
        lon_mode = valid_df["longitude"].mode()[0]
        plt.scatter(lon_mode, lat_mode, label=f"Mode ({subdir})")
    plt.title("Mode of Latitude and Longitude")
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.legend()
    plt.grid(True)

    # Plot drone data over time
    plt.subplot(1, 2, 2)
    for subdir, df in data.items():
        
        # Reset back to ALL rows, invalid or not
        valid_df = df
        valid_df["timestamp"] = pd.to_datetime(
            valid_df["timestamp"],
            format="%Y-%m-%d %H:%M:%S",  # Specify the expected format
            errors="coerce"  # Invalid timestamps will be set to NaT (99:99:99)
        )
        valid_df = valid_df.sort_values("timestamp")  # Ensure data is sorted by time
        plt.plot(valid_df["timestamp"], valid_df["drone"], label=f"Drone Data ({subdir})")
    
    # Set x-axis limits based on the combined valid data
    all_valid_timestamps = pd.concat([df[df["status"] == "Valid"]["timestamp"] for df in data.values()])
    all_valid_timestamps = pd.to_datetime(all_valid_timestamps, format="%Y-%m-%d %H:%M:%S", errors="coerce")
    plt.xlim(all_valid_timestamps.min(), all_valid_timestamps.max())
    
    plt.yscale("log")  # Set y-axis to logarithmic scale
    plt.title("Drone Data Over Time (Valid Rows Only)")
    plt.xlabel("Timestamp")
    plt.ylabel("Drone Probability (Log Scale)")
    plt.legend()
    plt.grid(True)

    # Show the plot
    plt.tight_layout()
    plt.show()


def main():
    """
    Main execution function.
    """
    # Resolve the data directory relative to the script
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(SCRIPT_DIR, "data")

    try:
        # Load data from the data directory
        data = load_data(DATA_DIR)

        if not data:
            print("No valid data found in the subfolders.")
            return

        # Create a single plot window for all subfolder data
        plot_all_data(data)

    except FileNotFoundError as e:
        print(e)
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()