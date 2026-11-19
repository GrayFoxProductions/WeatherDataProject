from pathlib import Path
import pandas as pd


def csv_to_parquet(
    silver_folder: str | Path = "data/silver",
    gold_folder: str | Path = "data/gold",
) -> None:
    silver_path = Path(silver_folder)
    gold_path = Path(gold_folder)

    if not silver_path.exists():
        print(f"Silver folder not found: {silver_path}")
        return

    gold_path.mkdir(parents=True, exist_ok=True)

    csv_files = sorted(
        p for p in silver_path.iterdir() if p.is_file() and p.suffix.lower() == ".csv"
    )

    if not csv_files:
        print("No CSV files found in Silver layer.")
        return

    for csv_file in csv_files:
        parquet_file = gold_path / f"{csv_file.stem}.parquet"
        try:
            df = pd.read_csv(csv_file)
            df.to_parquet(parquet_file, index=False)
            print(f"[OK] Converted {csv_file} -> {parquet_file}")
        except Exception as exc:
            print(f"[ERR] Failed converting {csv_file.name}: {exc}")


def main() -> None:
    print("Converting Silver CSVs to Parquet...")
    csv_to_parquet()


if __name__ == "__main__":
    main()