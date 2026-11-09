"""
Inspect CSV files stored directly inside data/raw/.

Run from the repository root:
    python scripts/inspect_dataset.py

The script creates:
    reports/data_audit/file_inventory.csv
    reports/data_audit/schema_report.json
"""
from pathlib import Path
import json

import pandas as pd

# Resolve paths from this script, so the command works regardless of current directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "reports" / "data_audit"

DATE_NAMES = {"date", "datetime", "time", "timestamp"}
CHUNK_SIZE = 100_000


def find_date_column(columns):
    """Return the first column matching a common date/time name."""
    lookup = {str(column).strip().lower(): column for column in columns}
    for name in DATE_NAMES:
        if name in lookup:
            return lookup[name]
    return None


def inspect_csv(path: Path) -> dict:
    """Inspect one CSV without loading the complete file into memory."""
    try:
        sample = pd.read_csv(path, nrows=100)
    except Exception as exc:
        raise RuntimeError(f"Could not read {path.name}: {exc}") from exc

    date_column = find_date_column(sample.columns)
    row_count = 0
    null_counts = {column: 0 for column in sample.columns}
    min_date = None
    max_date = None
    invalid_date_count = 0

    try:
        for chunk in pd.read_csv(path, chunksize=CHUNK_SIZE):
            row_count += len(chunk)

            for column in chunk.columns:
                null_counts[column] = (
                    null_counts.get(column, 0) + int(chunk[column].isna().sum())
                )

            if date_column is not None and date_column in chunk.columns:
                parsed_dates = pd.to_datetime(
                    chunk[date_column], errors="coerce"
                )
                invalid_date_count += int(parsed_dates.isna().sum())
                valid_dates = parsed_dates.dropna()

                if not valid_dates.empty:
                    chunk_min = valid_dates.min()
                    chunk_max = valid_dates.max()
                    min_date = chunk_min if min_date is None else min(min_date, chunk_min)
                    max_date = chunk_max if max_date is None else max(max_date, chunk_max)

    except Exception as exc:
        raise RuntimeError(f"Error while scanning {path.name}: {exc}") from exc

    missing_percent = {
        column: round((count / row_count) * 100, 3) if row_count else 0.0
        for column, count in null_counts.items()
    }

    return {
        "file": str(path.relative_to(PROJECT_ROOT)),
        "rows": row_count,
        "columns": [str(column) for column in sample.columns],
        "column_count": len(sample.columns),
        "dtypes_sample": {
            str(column): str(dtype)
            for column, dtype in sample.dtypes.items()
        },
        "null_counts": null_counts,
        "missing_percent": missing_percent,
        "date_column_candidate": date_column,
        "invalid_or_missing_date_count": (
            invalid_date_count if date_column is not None else None
        ),
        "min_date": str(min_date) if min_date is not None else None,
        "max_date": str(max_date) if max_date is not None else None,
        "file_size_bytes": path.stat().st_size,
    }


def main():
    if not RAW_DIR.exists():
        raise FileNotFoundError(
            f"Raw data folder does not exist: {RAW_DIR}\n"
            "Create data/raw/ and place your downloaded CSV files there."
        )

    # Search directly inside data/raw/. Use rglob if files are later organized
    # into subfolders.
    csv_files = sorted(path for path in RAW_DIR.glob("*.csv") if path.is_file())

    if not csv_files:
        raise FileNotFoundError(
            f"No CSV files found directly inside: {RAW_DIR}\n"
            "Place your Zenodo CSV files in data/raw/ and run this script again."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Found {len(csv_files)} CSV files in {RAW_DIR}")
    print("Inspecting files. Large files may take a little time...\n")

    reports = []
    for index, path in enumerate(csv_files, start=1):
        print(f"[{index}/{len(csv_files)}] {path.name}")
        reports.append(inspect_csv(path))

    inventory = pd.DataFrame(
        [
            {
                "file": report["file"],
                "rows": report["rows"],
                "columns_count": report["column_count"],
                "file_size_bytes": report["file_size_bytes"],
                "date_column": report["date_column_candidate"],
                "min_date": report["min_date"],
                "max_date": report["max_date"],
            }
            for report in reports
        ]
    )

    inventory_path = OUTPUT_DIR / "file_inventory.csv"
    schema_path = OUTPUT_DIR / "schema_report.json"

    inventory.to_csv(inventory_path, index=False)
    schema_path.write_text(
        json.dumps(reports, indent=2, default=str),
        encoding="utf-8",
    )

    print("\n========== FILE INVENTORY ==========")
    print(inventory.to_string(index=False))
    print("\nAudit completed successfully.")
    print(f"Inventory: {inventory_path}")
    print(f"Schema report: {schema_path}")


if __name__ == "__main__":
    main()
