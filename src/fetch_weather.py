import json
import os
import time
from datetime import datetime
import requests

from src.logger import get_logger

logger = get_logger(__name__)


def fetch_weather(
    latitude: float = 47.6062,
    longitude: float = -122.3321,
    max_retries: int = 4,
    initial_delay: float = 2.0,
    timeout: float = 10.0,
) -> dict | None:
    """Fetch hourly temperature data from Open-Meteo with exponential backoff."""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={latitude}&longitude={longitude}"
        "&hourly=temperature_2m"
        "&timezone=America%2FLos_Angeles"
        "&wind_speed_unit=mph"
        "&temperature_unit=fahrenheit"
        "&precipitation_unit=inch"
    )

    for attempt in range(1, max_retries + 1):
        delay = initial_delay * (2 ** (attempt - 1))
        logger.info("Fetching weather data (attempt %d/%d)", attempt, max_retries)

        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            logger.info("Weather API call successful")
            return data

        except requests.exceptions.Timeout:
            if attempt == max_retries:
                logger.error("Request timed out after %d attempts", max_retries)
                break
            logger.warning("Request timed out; retrying in %.1fs", delay)
            time.sleep(delay)

        except requests.exceptions.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            logger.error("HTTP error: %s (status=%s)", exc, status_code)

            # Do not retry client errors except rate limits (429)
            if status_code is not None and 400 <= status_code < 500 and status_code != 429:
                break

            if attempt == max_retries:
                logger.error("HTTP error persisted after %d attempts", max_retries)
                break

            logger.warning("Retrying after HTTP error in %.1fs", delay)
            time.sleep(delay)

        except requests.exceptions.ConnectionError as exc:
            if attempt == max_retries:
                logger.error("Connection error persisted after %d attempts: %s", max_retries, exc)
                break
            logger.warning("Connection error (%s); retrying in %.1fs", exc, delay)
            time.sleep(delay)

        except requests.exceptions.RequestException as exc:
            logger.error("Unrecoverable request error: %s", exc)
            break

    return None


def save_to_bronze(data: dict, base_dir: str = "data/bronze") -> str | None:
    """Persist raw weather JSON to the bronze layer and return the saved path."""
    if not data:
        logger.warning("Skipping bronze save: empty or missing payload")
        return None

    os.makedirs(base_dir, exist_ok=True)
    filename = f"{datetime.now().strftime('%Y-%m-%d')}.json"
    filepath = os.path.join(base_dir, filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info("Saved raw weather JSON to %s", filepath)
        return filepath
    except OSError as exc:
        logger.error("Failed to write weather data to %s: %s", filepath, exc)
        return None


def main() -> None:
    logger.info("Fetch weather job started")
    weather = fetch_weather()

    if weather and save_to_bronze(weather):
        logger.info("Fetch weather job finished successfully")
    else:
        logger.error("Fetch weather job failed")


if __name__ == "__main__":
    main()
