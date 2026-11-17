import requests
import json
import logging
from datetime import datetime
import os
import time

# Configure logging to print clear timestamps and levels
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(asctime)s - %(message)s"
)

def fetch_weather(max_retries=4, initial_delay=2):
    """
    Fetches weather data from the updated Open-Meteo endpoint with 
    built-in retry logic and exponential backoff.
    """
    url = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude=47.6062&longitude=-122.3321"
        "&hourly=temperature_2m"
        "&timezone=America%2FLos_Angeles"
        "&wind_speed_unit=mph"
        "&temperature_unit=fahrenheit"
        "&precipitation_unit=inch"
    )
    
    for attempt in range(1, max_retries + 1):
        try:
            logging.info(f"Fetching weather data (Attempt {attempt}/{max_retries})...")
            response = requests.get(url, timeout=10)
            
            # Raise an exception for HTTP error codes (4xx, 5xx)
            response.raise_for_status()
            
            # Parse and return JSON data if successful
            return response.json()
            
        except requests.exceptions.Timeout:
            delay = initial_delay * (2 ** (attempt - 1))  # Exponential backoff: 2s, 4s, 8s, 16s...
            if attempt == max_retries:
                logging.error(f"Max retries ({max_retries}) reached. The request timed out permanently.")
                break
            logging.warning(f"Request timed out. Retrying in {delay} seconds...")
            time.sleep(delay)
            
        except requests.exceptions.HTTPError as http_err:
            status_code = response.status_code if 'response' in locals() else 'Unknown'
            logging.error(f"HTTP error occurred: {http_err} (Status Code: {status_code})")
            
            # Do not retry client errors (4xx) except for rate limiting (429)
            if 400 <= status_code < 500 and status_code != 429:
                break
                
            delay = initial_delay * (2 ** (attempt - 1))
            if attempt < max_retries:
                logging.warning(f"Retrying after HTTP error in {delay} seconds...")
                time.sleep(delay)
                
        except requests.exceptions.ConnectionError as conn_err:
            delay = initial_delay * (2 ** (attempt - 1))
            logging.warning(f"Connection error ({conn_err}). Retrying in {delay} seconds...")
            if attempt < max_retries:
                time.sleep(delay)
                
        except requests.exceptions.RequestException as req_err:
            logging.error(f"An unrecoverable request error occurred: {req_err}")
            break
            
    return None

def save_to_bronze(data):
    # Make sure the target directory exists
    os.makedirs("data/bronze", exist_ok=True)
    
    # File name format: data/bronze/YYYY-MM-DD.json
    filename = datetime.now().strftime("%Y-%m-%d.json")
    filepath = os.path.join("data/bronze", filename)
    
    try:
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[OK] Raw weather saved successfully to {filepath}")
    except IOError as e:
        logging.error(f"Failed to write data to disk: {e}")

def main():
    print("Starting weather ingestion pipeline...")
    weather = fetch_weather()
    
    if weather:
        save_to_bronze(weather)
    else:
        print("❌ Pipeline failed: No data received after all retry attempts.")

if __name__ == "__main__":
    main()
