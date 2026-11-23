import os
import sqlite3
import pandas as pd

from logger import get_logger

DB_PATH = "database/weather.db"
SILVER_DIR = "data/silver"
REQUIRED_COLS = ["timestamp", "temp", "city"]

logger = get_logger(__name__)


def extract_run_date(csv_path):
    """Extract run_date from filenames like clean_2025-01-23.csv, or return None if unparseable."""
    stem = os.path.splitext(os.path.basename(csv_path))[0]
    if stem.startswith("clean_"):
        candidate = stem.removeprefix("clean_")
        return candidate or None
    return None


def get_latest_silver_file():
    """Return the most recently modified CSV file from the silver folder."""
    if not os.path.isdir(SILVER_DIR):
        logger.error("Silver directory not found: %s", SILVER_DIR)
        raise FileNotFoundError(f"Directory not found: {SILVER_DIR}")

    csv_paths = [
        os.path.join(SILVER_DIR, f)
        for f in os.listdir(SILVER_DIR)
        if f.endswith(".csv") and os.path.isfile(os.path.join(SILVER_DIR, f))
    ]
    if not csv_paths:
        logger.warning("No CSV files found in silver directory: %s", SILVER_DIR)
        raise FileNotFoundError("No CSV files found in data/silver. Run your cleaning step first.")

    latest_path = max(csv_paths, key=os.path.getmtime)
    logger.info("Latest silver file determined (by mtime): %s", latest_path)
    return latest_path


def create_connection(db_path=DB_PATH):
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    logger.info("Creating SQLite connection to %s", db_path)
    return sqlite3.connect(db_path)


def create_table(conn):
    create_sql = """
    CREATE TABLE IF NOT EXISTS weather (
        timestamp TEXT NOT NULL,
        temp REAL,
        city TEXT NOT NULL,
        run_date TEXT,
        UNIQUE(timestamp, city)
    );
    """
    dedup_existing_sql = """
    DELETE FROM weather
    WHERE rowid NOT IN (
        SELECT MAX(rowid)
        FROM weather
        GROUP BY timestamp, city
    );
    """
    unique_index_sql = """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_weather_ts_city
    ON weather(timestamp, city);
    """
    cursor = conn.cursor()
    with conn:
        conn.execute(create_sql)

        # Backfill run_date column if upgrading an older table without it
        cursor.execute("PRAGMA table_info(weather);")
        columns = [col[1] for col in cursor.fetchall()]
        if "run_date" not in columns:
            logger.info("run_date column missing on weather table; adding it now.")
            conn.execute("ALTER TABLE weather ADD COLUMN run_date TEXT;")
            logger.info("Added run_date column to weather table.")

        conn.execute(dedup_existing_sql)
        conn.execute(unique_index_sql)
    logger.info("Ensured 'weather' table, run_date column, and unique index exist.")


def upsert_csv_to_sql(conn, csv_path):
    logger.info("Loading data from %s into SQLite...", csv_path)
    df = pd.read_csv(csv_path)

    missing = [col for col in REQUIRED_COLS if col not in df.columns]
    if missing:
        logger.error("Missing required columns in %s: %s", csv_path, missing)
        raise ValueError(f"Missing required columns in {csv_path}: {missing}")

    run_date = extract_run_date(csv_path)
    df = (
        df[REQUIRED_COLS]
        .dropna(subset=["timestamp", "city"])
        .drop_duplicates(subset=["timestamp", "city"], keep="last")
        .copy()
    )
    df["run_date"] = run_date
    logger.debug("Prepared %d unique rows for upsert (run_date=%s).", len(df), run_date)

    upsert_sql = """
    INSERT INTO weather (timestamp, temp, city, run_date)
    SELECT timestamp, temp, city, run_date
    FROM _weather_stage
    WHERE timestamp IS NOT NULL AND city IS NOT NULL
    ON CONFLICT(timestamp, city) DO UPDATE SET
        temp = excluded.temp,
        run_date = excluded.run_date;
    """

    with conn:
        conn.execute("DROP TABLE IF EXISTS _weather_stage;")
        df.to_sql("_weather_stage", conn, if_exists="replace", index=False)
        conn.execute(upsert_sql)
        conn.execute("DROP TABLE IF EXISTS _weather_stage;")

    logger.info("Upserted %d unique rows into 'weather' table (run_date=%s).", len(df), run_date)


def run_data_quality_checks(conn):
    """Run row-count, duplicate-key, and null-value checks on the weather table."""
    cursor = conn.cursor()

    # 1. Row-count check
    row_count = cursor.execute("SELECT COUNT(*) FROM weather;").fetchone()[0]
    if row_count == 0:
        logger.error("Data quality check failed: 'weather' table has 0 rows.")
        raise ValueError("Data quality check failed: 'weather' table has 0 rows.")

    # 2. Duplicate composite-key check
    dup_groups = cursor.execute(
        """
        SELECT timestamp, city, COUNT(*) AS cnt
        FROM weather
        GROUP BY timestamp, city
        HAVING COUNT(*) > 1;
        """
    ).fetchall()
    if dup_groups:
        logger.error("Data quality check failed: found %d duplicate (timestamp, city) keys.", len(dup_groups))
        raise ValueError(f"Data quality check failed: found {len(dup_groups)} duplicate (timestamp, city) keys.")

    # 3. Null / blank check on required columns
    null_counts = cursor.execute(
        """
        SELECT
            SUM(CASE WHEN timestamp IS NULL OR TRIM(timestamp) = '' THEN 1 ELSE 0 END) AS null_timestamp,
            SUM(CASE WHEN city IS NULL OR TRIM(city) = '' THEN 1 ELSE 0 END) AS null_city,
            SUM(CASE WHEN temp IS NULL THEN 1 ELSE 0 END) AS null_temp
        FROM weather;
        """
    ).fetchone()
    null_timestamp, null_city, null_temp = [n or 0 for n in null_counts]

    if null_timestamp > 0 or null_city > 0 or null_temp > 0:
        logger.error(
            "Data quality check failed: null/blank values detected "
            "(timestamp=%s, city=%s, temp=%s).",
            null_timestamp,
            null_city,
            null_temp,
        )
        raise ValueError(
            "Data quality check failed: null/blank values detected "
            f"(timestamp={null_timestamp}, city={null_city}, temp={null_temp})."
        )

    logger.info(
        "Data quality checks passed: %d rows, 0 duplicate keys, 0 nulls in %s.",
        row_count,
        REQUIRED_COLS,
    )


def quick_check(conn):
    cursor = conn.cursor()
    rows = cursor.execute(
        """
        SELECT timestamp, temp, city, run_date
        FROM weather
        ORDER BY timestamp DESC
        LIMIT 5;
        """
    ).fetchall()
    logger.info("Last 5 records:")
    for row in rows:
        logger.info("%s", row)


def main():
    logger.info("Connecting to SQLite database...")
    conn = create_connection()
    try:
        create_table(conn)
        csv_path = get_latest_silver_file()
        upsert_csv_to_sql(conn, csv_path)
        run_data_quality_checks(conn)
        quick_check(conn)
    except Exception:
        logger.exception("SQL load job failed.")
        raise
    finally:
        conn.close()
        logger.info("Connection closed.")


if __name__ == "__main__":
    main()
