import glob
import os
import re
import tkinter as tk
from tkinter import filedialog

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.widgets import Button
from mpl_toolkits.mplot3d import Axes3D
import pandas as pd

# Ensure we're using the TkAgg backend
matplotlib.use("TkAgg")

###############################################################################
# 1) GLOBALS / INITIAL STATES
###############################################################################
dataframes = []   # list of (filename, df) for current folder
current_index = 0
total_files = 0

current_scatter = None
cbar = None
page_text = None

fig = None
ax = None

# Global state for toggle
show_invalid_points = False

# No folder selected initially
folder_selected = None

# Resolve ./data relative to the script's directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

# Basic Red->Green colormap
colors = [(1, 0, 0), (0, 1, 0)]
cmap = LinearSegmentedColormap.from_list("RedGreen", colors)

###############################################################################
# 2) HELPER FUNCTIONS
###############################################################################
def read_and_prepare_csv(file_path):
    """
    Reads a CSV file and filters rows based on the checkbox state.
    """
    global show_invalid_points
    df = pd.read_csv(file_path, header=None)

    # If there's an extra column
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
    df["z"] = df.groupby(["latitude", "longitude"]).cumcount()

    # Apply the filter based on the checkbox state
    if not show_invalid_points:
        df = df[df["status"] == "Valid"]

    return df


def load_folder(folder_path):
    """
    Loads all CSV files from the specified folder, updates globals,
    and plots the first CSV if available.
    """
    global dataframes, current_index, total_files, folder_selected, current_scatter, cbar, page_text

    # Find all CSV files in the folder
    csv_pattern = os.path.join(folder_path, "*.CSV")
    csv_files = sorted(glob.glob(csv_pattern))

    # Read all CSV files
    data_list = []
    for fp in csv_files:
        df_temp = read_and_prepare_csv(fp)
        data_list.append((os.path.basename(fp), df_temp))

    # Update global state
    dataframes.clear()
    dataframes.extend(data_list)
    current_index = 0
    total_files = len(dataframes)
    folder_selected = folder_path

    # Clear the 3D axes and reset
    ax.clear()  # Clear the axes
    current_scatter = None  # Reset the scatter plot reference
    cbar = None  # Reset the colorbar reference
    page_text = None  # Reset the page text reference

    # If no files were loaded, show a default message
    if total_files == 0:
        ax.set_title(f"No CSV files found in {folder_path}")
        plt.draw()
    else:
        plot_csv(current_index)


###############################################################################
# 3) MAIN PLOTTING / FLIP LOGIC
###############################################################################
def plot_csv(index):
    """
    Plot the dataframes[index] in 3D, re-using the global scatter, colorbar, etc.
    """
    global current_scatter, cbar, page_text

    if not dataframes:
        ax.clear()
        ax.set_title("No CSV loaded.")
        plt.draw()
        return

    file_name, df = dataframes[index]

    # Reload the data with the current toggle state
    file_path = os.path.join(folder_selected, file_name)
    df = read_and_prepare_csv(file_path)

    # Clear the previous scatter plot
    if current_scatter is not None:
        current_scatter.remove()
        current_scatter = None

    # Clear the previous colorbar if it exists
    if cbar is not None:
        cbar.remove()
        cbar = None

    # Min/Max for coloring
    drone_min = df["drone"].min()
    drone_max = df["drone"].max()
    norm = mcolors.Normalize(vmin=drone_min, vmax=drone_max)

    # Marker sizes
    base_size = 10
    scaling_factor = 300
    if drone_max > drone_min:
        normalized_drone = (df["drone"] - drone_min) / (drone_max - drone_min)
        marker_sizes = base_size + (scaling_factor * normalized_drone)
    else:
        marker_sizes = [base_size] * len(df)

    # Create scatter
    sc = ax.scatter(
        df["longitude"],
        df["latitude"],
        df["z"],
        c=df["drone"],
        s=marker_sizes,
        cmap=cmap,
        norm=norm,
        alpha=0.8
    )
    current_scatter = sc

    # Title
    ax.set_title(f"{file_name} 3D Scatter Data")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_zlabel("Stack Index")

    # Create new colorbar
    if cbar is None:
        cbar = fig.colorbar(sc, ax=ax, pad=0.1, shrink=0.6)
    else:
        cbar.update_normal(sc)
    cbar.set_ticks([drone_min, drone_max])
    cbar.set_ticklabels([f"Min ({drone_min})", f"Max ({drone_max})"])
    cbar.set_label("Drone Data (Red = Low, Green = High)")

    # Page X/Y
    if page_text is not None:
        page_text.remove()
    page_number = index + 1
    page_str = f"Page {page_number}/{total_files}"
    page_text = fig.text(
        0.97, 0.01,
        page_str,
        fontsize=12,
        color='black',
        ha='right'
    )

    plt.subplots_adjust(left=0.1, right=0.85, top=0.85, bottom=0.1)
    plt.draw()


def on_toggle_invalid_points(event):
    """
    Toggles the inclusion of invalid points in the plot.
    """
    global show_invalid_points
    show_invalid_points = not show_invalid_points
    print(f"Show Invalid Points: {show_invalid_points}")
    plot_csv(current_index)


def on_key_press(event):
    """
    Left/Right arrow to flip among CSVs
    """
    global current_index
    if event.key == 'right':
        if dataframes:
            current_index = (current_index + 1) % total_files
            plot_csv(current_index)
    elif event.key == 'left':
        if dataframes:
            current_index = (current_index - 1) % total_files
            plot_csv(current_index)


###############################################################################
# 4) BUTTONS AND TOGGLE LOGIC
###############################################################################
def on_browse_clicked(event):
    """
    Callback when the user presses the 'Browse Subfolder' button.
    Opens a folder dialog restricted to subfolders of ./data relative to the script's directory.
    """
    global folder_selected

    # Open a folder dialog starting in ./data
    root = tk.Tk()
    root.withdraw()
    folder_selected_temp = filedialog.askdirectory(initialdir=DATA_DIR, title="Select a Subfolder in ./data")
    root.destroy()

    # Debug: Print raw selected folder
    print(f"Raw Selected Folder: {folder_selected_temp}")

    if not folder_selected_temp:
        print("Folder selection canceled.")
        return

    # Normalize paths and convert to lowercase for comparison
    folder_selected_temp = os.path.normpath(os.path.abspath(folder_selected_temp)).lower()
    data_dir = os.path.normpath(os.path.abspath(DATA_DIR)).lower()

    # Debug: Print resolved paths
    print(f"Resolved Selected Folder: {folder_selected_temp}")
    print(f"Resolved Data Directory: {data_dir}")

    # Check if the selected folder is within ./data relative to the script
    if not folder_selected_temp.startswith(data_dir + os.sep):
        print("Invalid selection. Please choose a subfolder within ./data.")
        return

    # Valid selection, update folder_selected
    folder_selected = folder_selected_temp
    print(f"Valid selection: Loading data from {folder_selected}")

    # Load the selected subfolder
    load_folder(folder_selected)


###############################################################################
# 5) MAIN FUNCTION
###############################################################################
def main():
    global fig, ax
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')
    ax.set_title("No folder loaded yet")

    fig.canvas.mpl_connect('key_press_event', on_key_press)

    # Add Browse Subfolder button
    button_ax = fig.add_axes([0.6, 0.92, 0.15, 0.06])
    browse_button = Button(button_ax, "Browse Subfolder")
    browse_button.on_clicked(on_browse_clicked)

    # Add Toggle Invalid Points button
    toggle_ax = fig.add_axes([0.8, 0.92, 0.15, 0.06])
    toggle_button = Button(toggle_ax, "Toggle Invalid Points")
    toggle_button.on_clicked(on_toggle_invalid_points)

    plt.subplots_adjust(left=0.1, right=0.9, top=0.85, bottom=0.1)
    plt.show()


if __name__ == "__main__":
    main()