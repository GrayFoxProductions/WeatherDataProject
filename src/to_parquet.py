import json
import logging
from pathlib import Path
import pandas as pd


def setup_logging(log_file: Path = Path("logs/pipeline.log")) -> logging.Logger:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("silver_transform")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        formatter = logging.Formatter("%(levelname)s:%(asctime)s - %(message)s")
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)

    return logger


def flatten_open_meteo_json(payload: dict) -> pd.DataFrame:
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        raise ValueError("Missing or invalid 'hourly' object in Bronze payload.")

    timestamps = hourly.get("time")
    temperatures = hourly.get("temperature_2m")

    if not isinstance(timestamps, list) or not isinstance(temperatures, list):
        raise ValueError("'hourly.time' and 'hourly.temperature_2m' must be lists.")

    if len(timestamps) != len(temperatures):
        raise ValueError(
            f"Length mismatch between 'time' ({len(timestamps)}) and "
            f"'temperature_2m' ({len(temperatures)})."
        )

    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "temperature_2m_f": temperatures,
        }
    )

    # Parse ISO timestamps and coerce temperature to numeric
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["temperature_2m_f"] = pd.to_numeric(df["temperature_2m_f"], errors="coerce")

    # Drop invalid or missing rows and sort chronologically
    df = df.dropna(subset=["timestamp", "temperature_2m_f"]).sort_values("timestamp")

    # Enrich with location metadata when present
    if "latitude" in payload:
        df["latitude"] = payload["latitude"]
    if "longitude" in payload:
        df["longitude"] = payload["longitude"]
    if "timezone" in payload:
        df["timezone"] = payload["timezone"]

    return df.reset_index(drop=True)


def bronze_to_silver(
    bronze_folder: Path = Path("data/bronze"),
    silver_folder: Path = Path("data/silver"),
    logger: logging.Logger | None = None,
) -> None:
    log = logger or setup_logging()

    if not bronze_folder.exists():
        log.warning(f"Bronze folder not found: {bronze_folder}")
        return

    silver_folder.mkdir(parents=True, exist_ok=True)

    json_files = sorted(
        p for p in bronze_folder.iterdir()
        if p.is_file() and p.suffix.lower() == ".json"
    )

    if not json_files:
        log.info("No JSON files found in Bronze layer.")
        return

    for json_path in json_files:
        csv_path = silver_folder / f"{json_path.stem}.csv"
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                payload = json.load(f)

            df = flatten_open_meteo_json(payload)
            df.to_csv(csv_path, index=False)
            log.info(f"[OK] Transformed {json_path.name} -> {csv_path} ({len(df)} rows)")
        except Exception as exc:
            log.error(f"[ERR] Failed transforming {json_path.name}: {exc}")


def main() -> None:
    logger = setup_logging()
    logger.info("Starting Bronze-to-Silver transformation...")
    bronze_to_silver(logger=logger)


if __name__ == "__main__":
    main()
