import json
from datetime import datetime
from pathlib import Path
import pandas as pd

from logger import get_logger

logger = get_logger(__name__)


def get_latest_bronze_file(bronze_folder="data/bronze"):
    """
    Finds the most recent JSON file in the bronze folder using pathlib.
    """
    bronze_path = Path(bronze_folder)
    if not bronze_path.exists():
        logger.error("Bronze folder not found: %s", bronze_folder)
        raise FileNotFoundError(f"Bronze folder not found: {bronze_folder}")

    json_files = list(bronze_path.glob("*.json"))
    if not json_files:
        logger.warning("No JSON files found in bronze layer: %s", bronze_folder)
        raise FileNotFoundError("No JSON files found in bronze layer.")

    latest_file = max(json_files, key=lambda f: f.stat().st_mtime)
    logger.info("Latest bronze file determined: %s", latest_file)
    return latest_file


def clean_weather_data(filepath, city_name="Seattle", run_date=None):
    """
    Loads raw Open-Meteo JSON and transforms it into a Pandas DataFrame.
    """
    logger.info("Cleaning weather data from %s for city=%s", filepath, city_name)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw_json = json.load(f)
    except Exception:
        logger.exception("Failed to read or parse JSON from %s", filepath)
        raise

    hourly = raw_json.get("hourly", {})
    if not hourly or "time" not in hourly or "temperature_2m" not in hourly:
        logger.error("Missing 'hourly' data or required keys in %s", filepath)
        raise ValueError("Missing 'hourly' data or required keys in JSON.")

    effective_run_date = run_date or datetime.now().strftime("%Y-%m-%d")

    df = pd.DataFrame({
        "timestamp": hourly["time"],
        "temp": hourly["temperature_2m"],
    })
    df["city"] = city_name
    df["run_date"] = effective_run_date

    logger.info("Cleaned %d rows with run_date=%s", len(df), effective_run_date)
    return df


def save_to_silver(df, silver_folder="data/silver", run_date=None):
    """
    Saves the cleaned DataFrame to a CSV file in the silver layer.
    """
    silver_path = Path(silver_folder)
    silver_path.mkdir(parents=True, exist_ok=True)

    effective_run_date = run_date or datetime.now().strftime("%Y-%m-%d")
    filepath = silver_path / f"clean_{effective_run_date}.csv"

    try:
        df.to_csv(filepath, index=False)
        logger.info("Cleaned data saved to %s", filepath)
    except Exception:
        logger.exception("Failed to save silver CSV to %s", filepath)
        raise

    return filepath


def main():
    logger.info("Bronze-to-silver cleaning job started")
    run_date = datetime.now().strftime("%Y-%m-%d")

    try:
        bronze_path = get_latest_bronze_file()
        df = clean_weather_data(bronze_path, city_name="Seattle", run_date=run_date)
        output_path = save_to_silver(df, run_date=run_date)
        logger.info(
            "Silver layer updated successfully (%d rows written to %s)",
            len(df),
            output_path,
        )
    except Exception as e:
        logger.exception("Pipeline failed: %s", e)


if __name__ == "__main__":
    main()
