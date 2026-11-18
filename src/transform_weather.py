import json
from datetime import datetime
from pathlib import Path
import pandas as pd

# Updated changes
# 1) Robust File Sorting: files.sort() sorts alphabetically. If your filenames follow a timestamp format (e.g., weather_2026-03-30.json), this works great. However, if filenames vary, sorting by file modification time using os.path.getmtime is safer.
# 2) Path Management: Using pathlib instead of os.path provides a more modern, object-oriented way to handle file paths across different operating systems.
# 3) Logging: Replacing print() statements with Python's built-in logging module will give you better control over log levels (INFO, WARNING, ERROR) and timestamps if this pipeline runs as an automated cron job.


def get_latest_bronze_file(bronze_folder="data/bronze"):
    """
    Finds the most recent JSON file in the bronze folder using pathlib.
    """
    bronze_path = Path(bronze_folder)
    if not bronze_path.exists():
        raise FileNotFoundError(f"Bronze folder not found: {bronze_folder}")
    
    json_files = list(bronze_path.glob("*.json"))
    if not json_files:
        raise FileNotFoundError("No JSON files found in bronze layer.")
    
    # Safely get the latest file based on modification time
    latest_file = max(json_files, key=lambda f: f.stat().st_mtime)
    return latest_file

def clean_weather_data(filepath, city_name="Edmonton"):
    """
    Loads raw Open-Meteo JSON and transforms it into a Pandas DataFrame.
    """
    with open(filepath, "r") as f:
        raw_json = json.load(f)
        
    hourly = raw_json.get("hourly", {})
    if not hourly or "time" not in hourly or "temperature_2m" not in hourly:
        raise ValueError("Missing 'hourly' data or required keys in JSON.")
        
    # Build the DataFrame directly from dictionaries (avoids explicit for-loops)
    df = pd.DataFrame({
        "timestamp": hourly["time"],
        "temp": hourly["temperature_2m"]
    })
    
    # Vectorized assignment for the city column
    df["city"] = city_name
    return df

def save_to_silver(df, silver_folder="data/silver"):
    """
    Saves the cleaned DataFrame to a CSV file in the silver layer.
    """
    silver_path = Path(silver_folder)
    silver_path.mkdir(parents=True, exist_ok=True)
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    filepath = silver_path / f"clean_{today_str}.csv"
    
    # Export to CSV without writing the DataFrame index
    df.to_csv(filepath, index=False)
    print(f"[OK] Cleaned data saved to {filepath}")

def main():
    print("Loading latest bronze file...")
    try:
        bronze_path = get_latest_bronze_file()
        print(f"Using bronze file: {bronze_path}")
        
        print("Transforming weather data with Pandas...")
        df = clean_weather_data(bronze_path, city_name="Edmonton")
        print(f"Total rows processed: {len(df)}")
        
        print("Saving to silver layer as CSV...")
        save_to_silver(df)
        print("Silver layer updated successfully.")
    except Exception as e:
        print(f"[ERROR] Pipeline failed: {e}")

if __name__ == "__main__":
    main()
