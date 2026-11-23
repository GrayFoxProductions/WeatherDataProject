import os
import sqlite3
import pandas as pd

DB_PATH = "database/weather.db"
SILVER_DIR = "data/silver"
REQUIRED_COLS = ["timestamp", "temp", "city"]


def get_latest_silver_file():
    """Return the most recently modified CSV file from the silver folder."""
    if not os.path.isdir(SILVER_DIR):
        raise FileNotFoundError(f"Directory not found: {SILVER_DIR}")

    csv_paths = [
        os.path.join(SILVER_DIR, f)
        for f in os.listdir(SILVER_DIR)
        if f.endswith(".csv") and os.path.isfile(os.path.join(SILVER_DIR, f))
    ]
    if not csv_paths:
        raise FileNotFoundError("No CSV files found in data/silver. Run your cleaning step first.")

    return max(csv_paths, key=os.path.getmtime)


def create_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def create_table(conn):
    create_sql = """
    CREATE TABLE IF NOT EXISTS weather (
        timestamp TEXT NOT NULL,
        temp REAL,
        city TEXT NOT NULL,
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
    with conn:
        conn.execute(create_sql)
        conn.execute(dedup_existing_sql)
        conn.execute(unique_index_sql)


def upsert_csv_to_sql(conn, csv_path):
    print(f"Loading data from {csv_path} into SQLite...")
    df = pd.read_csv(csv_path)

    missing = [col for col in REQUIRED_COLS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in {csv_path}: {missing}")

    df = (
        df[REQUIRED_COLS]
        .dropna(subset=["timestamp", "city"])
        .drop_duplicates(subset=["timestamp", "city"], keep="last")
    )
    print(df.head())

    upsert_sql = """
    INSERT INTO weather (timestamp, temp, city)
    SELECT timestamp, temp, city
    FROM _weather_stage
    WHERE timestamp IS NOT NULL AND city IS NOT NULL
    ON CONFLICT(timestamp, city) DO UPDATE SET
        temp = excluded.temp;
    """

    with conn:
        conn.execute("DROP TABLE IF EXISTS _weather_stage;")
        df.to_sql("_weather_stage", conn, if_exists="replace", index=False)
        conn.execute(upsert_sql)
        conn.execute("DROP TABLE IF EXISTS _weather_stage;")

    print(f"✅ Upserted {len(df)} unique rows into 'weather' table.")


def run_data_quality_checks(conn):
    """Run row-count, duplicate-key, and null-value checks on the weather table."""
    cursor = conn.cursor()

    # 1. Row-count check
    row_count = cursor.execute("SELECT COUNT(*) FROM weather;").fetchone()[0]
    if row_count == 0:
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
        raise ValueError(
            "Data quality check failed: null/blank values detected "
            f"(timestamp={null_timestamp}, city={null_city}, temp={null_temp})."
        )

    print(
        f"✅ Data quality checks passed: {row_count} rows, "
        f"0 duplicate keys, 0 nulls in {REQUIRED_COLS}."
    )


def quick_check(conn):
    cursor = conn.cursor()
    rows = cursor.execute(
        """
        SELECT timestamp, temp, city
        FROM weather
        ORDER BY timestamp DESC
        LIMIT 5;
        """
    ).fetchall()
    print("Last 5 records:")
    for row in rows:
        print(row)


def main():
    print("Connecting to SQLite database...")
    conn = create_connection()
    try:
        create_table(conn)
        csv_path = get_latest_silver_file()
        upsert_csv_to_sql(conn, csv_path)
        run_data_quality_checks(conn)
        quick_check(conn)
    finally:
        conn.close()
        print("Connection closed.")


if __name__ == "__main__":
    main()