
# 3D Data Plotter

This project is a Python application for visualizing CSV data in 3D. The data is organized into subfolders within a `data` directory. Each subfolder contains CSV files that the application can process and display interactively.

## Features
- Visualize CSV data in a 3D scatter plot.
- Navigate through multiple datasets using keyboard controls.
- Toggle display options for invalid points.
- Browse and select subfolders dynamically.

---

## Installation

### Prerequisites
- Python 3.8 or higher
- `pip` package manager

### Steps to Install
1. Clone or download this repository to your local machine.
2. Navigate to the project directory in your terminal.
3. Install the required dependencies using the following command:
   ```bash
   pip install -r requirements.txt
   ```
4. Ensure the `data` directory exists in the same directory as the script.

---

## Folder Structure

The `data` folder is used to store subfolders containing the CSV files to be processed. Below is an example structure:

```
./data
├───node1
│       DATA0.CSV
│       DATA1.CSV
│       DATA2.CSV
│
├───node2
│       DATA0.CSV
│       DATA1.CSV
│       DATA2.CSV
│       DATA3.CSV
│
└───node3
        DATA0.CSV
        DATA1.CSV
        DATA2.CSV
        DATA3.CSV
        DATA4.CSV
```

- Each subfolder (e.g., `node1`, `node2`) represents a data group.
- Each file (e.g., `DATA0.CSV`) is a CSV file containing data to be visualized.

---

## Usage

1. Run the application:
   ```bash
   python PathProbVisual.py.py
   ```
2. Use the **"Browse Subfolder"** button to select a subfolder within the `data` directory.
3. Navigate through the datasets:
   - Use the **Right Arrow** key to go to the next dataset.
   - Use the **Left Arrow** key to go to the previous dataset.
4. Toggle the display of invalid points using the **checkbox** in the interface.

---

## Notes

- CSV files should have a maximum of 13 columns, with the following structure:
  ```
  index, id, type, background, drone, latitude, longitude, timestamp, unknown1, status, unknown2, unknown3, value
  ```
- The application automatically filters invalid data points based on the `status` column unless toggled otherwise.

---

## License

This project is licensed under the MIT License. See the LICENSE file for details.
