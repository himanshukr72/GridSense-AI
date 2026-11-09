"""Validate the integrated GridSense panel and write audit reports."""
from pathlib import Path
import argparse
import yaml
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "data_config.yaml"

def resolve_path(value):
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--panel", default=None, help="Optional panel CSV override.")
    args = parser.parse_args()
    with Path(args.config).expanduser().resolve().open("r", encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle) or {}
    dataset = cfg.get("dataset", {})
    panel_path = resolve_path(args.panel or (Path(dataset.get("processed_dir", "data/processed")) / "state_daily_panel.csv"))
    out = resolve_path(dataset.get("audit_dir", "reports/data_audit"))
    out.mkdir(parents=True, exist_ok=True)
    if not panel_path.exists():
        raise FileNotFoundError(f"Panel not found: {panel_path}. Run scripts/build_dataset.py first.")
    df = pd.read_csv(panel_path, parse_dates=["date"])
    if df[["state", "date"]].isna().any().any():
        raise ValueError("Null state/date keys found.")
    dup = df.duplicated(["state", "date"], keep=False)
    if dup.any():
        df.loc[dup].to_csv(out / "duplicate_state_date_rows.csv", index=False)
        raise ValueError("Duplicate state/date keys; see duplicate_state_date_rows.csv")
    coverage = df.groupby("state").agg(
        rows=("date", "size"), first_date=("date", "min"),
        last_date=("date", "max"), unique_dates=("date", "nunique")
    ).reset_index()
    coverage.to_csv(out / "state_coverage.csv", index=False)
    missing = df.groupby("state").apply(lambda group: group.isna().mean(), include_groups=False).reset_index()
    missing.to_csv(out / "missingness_by_state.csv", index=False)
    print(coverage.to_string(index=False))
    print(f"Validation passed. Panel: {panel_path}")
    print(f"Reports: {out}")

if __name__ == "__main__":
    main()
