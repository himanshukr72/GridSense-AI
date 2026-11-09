from pathlib import Path
import json
import pandas as pd

RAW = Path("data/raw/zenodo")
OUT = Path("reports/data_audit")
OUT.mkdir(parents=True, exist_ok=True)
DATE_NAMES = {"date", "datetime", "time", "timestamp"}

def inspect(path):
    sample = pd.read_csv(path, nrows=50)
    date_cols = [c for c in sample.columns if c.lower() in DATE_NAMES]
    rows, nulls, lo, hi = 0, {c: 0 for c in sample.columns}, None, None
    for chunk in pd.read_csv(path, chunksize=100_000):
        rows += len(chunk)
        for col in chunk.columns:
            nulls[col] = nulls.get(col, 0) + int(chunk[col].isna().sum())
        if date_cols:
            dates = pd.to_datetime(chunk[date_cols[0]], errors="coerce").dropna()
            if len(dates):
                lo = dates.min() if lo is None else min(lo, dates.min())
                hi = dates.max() if hi is None else max(hi, dates.max())
    return {"file": path.name, "rows": rows, "columns": list(sample.columns),
            "dtypes_sample": {k: str(v) for k, v in sample.dtypes.items()},
            "null_counts": nulls, "date_column_candidate": date_cols[0] if date_cols else None,
            "min_date": str(lo) if lo is not None else None,
            "max_date": str(hi) if hi is not None else None,
            "file_size_bytes": path.stat().st_size}

def main():
    if not RAW.exists():
        raise FileNotFoundError("Run python scripts/download_zenodo.py first.")
    paths = sorted(RAW.glob("*.csv"))
    if not paths:
        raise FileNotFoundError(f"No CSV files found in {RAW}")
    report = [inspect(p) for p in paths]
    pd.DataFrame([{"file": x["file"], "rows": x["rows"],
                   "columns_count": len(x["columns"]), "file_size_bytes": x["file_size_bytes"],
                   "date_column": x["date_column_candidate"], "min_date": x["min_date"],
                   "max_date": x["max_date"]} for x in report]).to_csv(OUT/"file_inventory.csv", index=False)
    (OUT/"schema_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(pd.read_csv(OUT/"file_inventory.csv").to_string(index=False))
    print(f"Audit saved in {OUT.resolve()}")

if __name__ == "__main__":
    main()
