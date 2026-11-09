"""Build a state-date electricity + weather panel without imputing missing values.

Run from repository root:
    python scripts/build_dataset.py

Source files are read directly from data/raw/ by default. They are never moved or modified.
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "data_config.yaml"

def resolve_project_path(value: str | Path) -> Path:
    """Resolve configured relative paths from the repository root, not the shell CWD."""
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()

def load_config(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}

DATE_CANDIDATES = ("date", "datetime", "time", "timestamp")
ELECTRICITY = {
    "energy_met_mu": "corrected_daily_energy_met_MU.csv",
    "peak_met_mw": "corrected_peak_met_MW.csv",
    "peak_unmet_mw": "peak_unmet_MW.csv",
}
ORIGINALS = {
    "corrected_daily_energy_met_MU.csv": "daily_energy_met_MU.csv",
    "corrected_peak_met_MW.csv": "peak_met_MW.csv",
}
EXCLUDED_ELECTRICITY_COLUMNS = {"total", "amnsil", "damodar valley corporation"}


def norm(value: str) -> str:
    s = str(value).strip().lower().replace("&", "and")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

ALIASES = {
    "nct of delhi": "delhi", "delhi": "delhi",
    "andaman and nicobar": "andaman and nicobar islands",
    "andaman and nicobar islands": "andaman and nicobar islands",
    "dadra and nagar haveli": "dadra and nagar haveli",
    "daman and diu": "daman and diu",
    "jammu and kashmir": "jammu and kashmir",
}

def canonical_state(value: str) -> str:
    n = norm(value)
    return ALIASES.get(n, n)

def find_date_col(df: pd.DataFrame) -> str:
    by_norm = {norm(c): c for c in df.columns}
    for candidate in DATE_CANDIDATES:
        if candidate in by_norm:
            return by_norm[candidate]
    raise ValueError(f"No date column found. Columns: {list(df.columns)}")

def read_dates(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    dc = find_date_col(df)
    df = df.rename(columns={dc: "date"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    bad = int(df["date"].isna().sum())
    if bad:
        raise ValueError(f"{path.name}: {bad} invalid/missing dates; inspect source before proceeding")
    return df

def electricity_wide_to_long(path: Path, value_col: str, weather_states: set[str]) -> tuple[pd.DataFrame, list[str]]:
    df = read_dates(path)
    state_cols, ignored = [], []
    for col in df.columns:
        if col == "date":
            continue
        key = canonical_state(col)
        if key in weather_states:
            state_cols.append(col)
        else:
            ignored.append(col)
    if not state_cols:
        raise ValueError(f"No state columns matched weather state list in {path.name}")
    out = df.melt(id_vars="date", value_vars=state_cols, var_name="state_source", value_name=value_col)
    out["state"] = out["state_source"].map(canonical_state)
    out = out.drop(columns="state_source")
    out[value_col] = pd.to_numeric(out[value_col], errors="coerce")
    if out.duplicated(["state", "date"]).any():
        raise ValueError(f"Duplicate state/date keys in {path.name}")
    return out, ignored

def main():
    ap = argparse.ArgumentParser(description="Build the GridSense state-date panel without modifying raw CSVs.")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG), help="YAML configuration file (default: configs/data_config.yaml).")
    ap.add_argument("--raw-dir", default=None, help="Optional override for the existing raw-data folder.")
    ap.add_argument("--interim-dir", default=None)
    ap.add_argument("--processed-dir", default=None)
    ap.add_argument("--audit-dir", default=None)
    args = ap.parse_args()
    config = load_config(Path(args.config).expanduser().resolve())
    data_cfg = config.get("dataset", {})
    raw = resolve_project_path(args.raw_dir or data_cfg.get("raw_dir", "data/raw"))
    interim = resolve_project_path(args.interim_dir or data_cfg.get("interim_dir", "data/interim"))
    processed = resolve_project_path(args.processed_dir or data_cfg.get("processed_dir", "data/processed"))
    audit = resolve_project_path(args.audit_dir or data_cfg.get("audit_dir", "reports/data_audit"))
    for p in (interim, processed, audit): p.mkdir(parents=True, exist_ok=True)
    if not raw.exists(): raise FileNotFoundError(f"Raw data folder not found: {raw.resolve()}")
    if not any(raw.glob("*.csv")):
        raise FileNotFoundError(f"No CSV files found directly inside {raw.resolve()}. The pipeline does not move or copy source files.")

    # Detect state weather files by schema, excluding India-wide weighted UTCI.
    weather_frames, weather_files = [], []
    for path in sorted(raw.glob("*.csv")):
        if path.name.lower().startswith("weighted_daily_mean_utci") or path.name in set(ELECTRICITY.values()) | set(ORIGINALS.values()) | {"peak_met_MW.csv", "peak_unmet_MW.csv"}:
            continue
        try: df = read_dates(path)
        except (ValueError, pd.errors.ParserError, UnicodeDecodeError): continue
        if "2m_temperature_mean" not in df.columns: continue
        df["state"] = canonical_state(path.stem)
        for c in df.columns:
            if c not in ("date", "state"):
                df[c] = pd.to_numeric(df[c], errors="coerce")
        if df.duplicated(["state", "date"]).any(): raise ValueError(f"Duplicate weather keys: {path.name}")
        weather_frames.append(df); weather_files.append(path.name)
    if not weather_frames: raise RuntimeError(f"No state weather files found in {raw.resolve()}")
    weather = pd.concat(weather_frames, ignore_index=True, sort=False)
    states = set(weather["state"].unique())
    weather.to_csv(interim / "weather_long.csv", index=False)

    # Compare original and corrected versions; corrected files are used for the panel.
    comparison = {}
    for corrected, original in ORIGINALS.items():
        cp, op = raw / corrected, raw / original
        if cp.exists() and op.exists():
            cdf, odf = read_dates(cp), read_dates(op)
            common = sorted(set(cdf.columns) & set(odf.columns) - {"date"})
            comparison[corrected] = {
                "original_file": original,
                "same_shape": list(cdf.shape) == list(odf.shape),
                "common_columns": len(common),
                "numeric_values_different": int(sum(
                    (pd.to_numeric(cdf[c], errors="coerce") != pd.to_numeric(odf[c], errors="coerce")).fillna(False).sum()
                    for c in common if len(cdf) == len(odf)
                )) if len(cdf) == len(odf) else None,
            }

    elec_frames, ignored_columns = [], {}
    missing_electricity_files = []
    for value_col, filename in ELECTRICITY.items():
        path = raw / filename
        if not path.exists():
            missing_electricity_files.append(filename); continue
        frame, ignored = electricity_wide_to_long(path, value_col, states)
        elec_frames.append(frame); ignored_columns[filename] = ignored
    if not elec_frames: raise RuntimeError("No electricity files found; expected corrected energy/peak and peak unmet files")
    electricity = elec_frames[0]
    for frame in elec_frames[1:]:
        electricity = electricity.merge(frame, on=["state", "date"], how="outer", validate="one_to_one")
    electricity.to_csv(interim / "electricity_long.csv", index=False)

    # Outer join preserves weather-only and electricity-only observations.
    panel = electricity.merge(weather, on=["state", "date"], how="outer", validate="one_to_one", indicator=True)
    merge_counts = {str(k): int(v) for k, v in panel["_merge"].value_counts().items()}
    panel["has_electricity_record"] = panel["_merge"].isin(["both", "left_only"])
    panel["has_weather_record"] = panel["_merge"].isin(["both", "right_only"])
    panel["energy_missing"] = panel.get("energy_met_mu", pd.Series(index=panel.index, dtype=float)).isna()
    panel["peak_met_missing"] = panel.get("peak_met_mw", pd.Series(index=panel.index, dtype=float)).isna()
    panel["weather_missing"] = panel["_merge"].eq("left_only")
    panel = panel.drop(columns="_merge").sort_values(["state", "date"]).reset_index(drop=True)
    panel.to_csv(processed / "state_daily_panel.csv", index=False)

    # Keep India-level weighted UTCI separate; it is not a state-level variable.
    weighted = raw / "weighted_daily_mean_utci_india.csv"
    if weighted.exists(): read_dates(weighted).to_csv(processed / "india_weighted_utci.csv", index=False)

    # Audits: coverage, missingness, key uniqueness, join counts.
    state_summary = panel.groupby("state").agg(
        rows=("date", "size"), start_date=("date", "min"), end_date=("date", "max"),
        energy_missing=("energy_missing", "sum"), peak_met_missing=("peak_met_missing", "sum"),
        weather_missing=("weather_missing", "sum"),
    ).reset_index()
    state_summary.to_csv(audit / "state_coverage_and_missingness.csv", index=False)
    missingness = panel.isna().sum().sort_values(ascending=False).rename("missing_count").to_frame()
    missingness["missing_pct"] = (missingness["missing_count"] / len(panel) * 100).round(3)
    missingness.to_csv(audit / "column_missingness.csv")
    report = {
        "weather_files_used": weather_files, "weather_state_count": len(states),
        "electricity_rows": int(len(electricity)), "weather_rows": int(len(weather)),
        "panel_rows": int(len(panel)), "panel_states": int(panel.state.nunique()),
        "panel_start": str(panel.date.min().date()), "panel_end": str(panel.date.max().date()),
        "duplicate_state_date_keys": int(panel.duplicated(["state", "date"]).sum()),
        "merge_counts": merge_counts,
        "missing_electricity_files": missing_electricity_files,
        "ignored_electricity_columns_non_state_or_unmatched": ignored_columns,
        "original_vs_corrected_comparison": comparison,
        "imputation_performed": False,
        "outputs": ["data/interim/weather_long.csv", "data/interim/electricity_long.csv", "data/processed/state_daily_panel.csv", "reports/data_audit/state_coverage_and_missingness.csv", "reports/data_audit/column_missingness.csv"],
    }
    (audit / "build_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("weather_state_count", "electricity_rows", "weather_rows", "panel_rows", "panel_states", "panel_start", "panel_end", "missing_electricity_files", "imputation_performed")}, indent=2))
    print(f"\nRaw input (read-only): {raw}")
    print(f"Saved panel: {processed / 'state_daily_panel.csv'}")
    print(f"Audit report: {audit / 'build_report.json'}")

if __name__ == "__main__": main()
