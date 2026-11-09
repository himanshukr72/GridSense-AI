from pathlib import Path
import pandas as pd

PANEL = Path("data/processed/state_daily_panel.csv")
OUT = Path("reports/data_audit")
OUT.mkdir(parents=True, exist_ok=True)

def main():
    if not PANEL.exists():
        raise FileNotFoundError("Run scripts/build_dataset.py first.")
    df = pd.read_csv(PANEL, parse_dates=["date"])
    if df[["state", "date"]].isna().any().any():
        raise ValueError("Null state/date keys found.")
    dup = df.duplicated(["state", "date"], keep=False)
    if dup.any():
        df.loc[dup].to_csv(OUT/"duplicate_state_date_rows.csv", index=False)
        raise ValueError("Duplicate state/date keys; see audit file.")
    coverage = df.groupby("state").agg(
        rows=("date", "size"), first_date=("date", "min"),
        last_date=("date", "max"), unique_dates=("date", "nunique")
    ).reset_index()
    coverage.to_csv(OUT/"state_coverage.csv", index=False)
    missing = df.groupby("state").apply(lambda g: g.isna().mean(), include_groups=False).reset_index()
    missing.to_csv(OUT/"missingness_by_state.csv", index=False)
    print(coverage.to_string(index=False))
    print(f"Validation passed. Reports: {OUT.resolve()}")

if __name__ == "__main__":
    main()
