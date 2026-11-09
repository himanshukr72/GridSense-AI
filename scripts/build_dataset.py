from pathlib import Path
import pandas as pd

RAW, INTERIM, PROCESSED = Path("data/raw/zenodo"), Path("data/interim"), Path("data/processed")
DATE_CANDIDATES = ["date", "Date", "datetime", "time", "timestamp"]
ELEC_FILES = {
    "daily_energy_met_MU": "corrected_daily_energy_met_MU.csv",
    "peak_met_MW": "corrected_peak_met_MW.csv",
    "peak_unmet_MW": "peak_unmet_MW.csv",
}

def date_col(df):
    cols = {c.lower(): c for c in df.columns}
    for name in DATE_CANDIDATES:
        if name.lower() in cols:
            return cols[name.lower()]
    raise ValueError(f"No date column found; columns are {list(df.columns)}")

def wide_to_long(path, value_name):
    df = pd.read_csv(path)
    dc = date_col(df)
    df[dc] = pd.to_datetime(df[dc], errors="coerce")
    states = [c for c in df.columns if c != dc]
    out = df.melt(id_vars=[dc], value_vars=states, var_name="state", value_name=value_name)
    out = out.rename(columns={dc: "date"})
    out["state"] = out["state"].astype(str).str.strip()
    out[value_name] = pd.to_numeric(out[value_name], errors="coerce")
    out = out.dropna(subset=["date"])
    if out.duplicated(["state", "date"]).any():
        raise ValueError(f"Duplicate state/date key in {path.name}")
    return out

def main():
    INTERIM.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    elec = []
    for var, fname in ELEC_FILES.items():
        p = RAW / fname
        if p.exists():
            elec.append(wide_to_long(p, var))
        else:
            print(f"WARNING: missing optional file {fname}")
    if not elec:
        raise RuntimeError("No expected wide electricity files found; inspect schema first.")
    electricity = elec[0]
    for frame in elec[1:]:
        electricity = electricity.merge(frame, on=["state", "date"], how="outer", validate="one_to_one")
    electricity.to_csv(INTERIM/"electricity_long.csv", index=False)

    weather_frames = []
    excluded = set(ELEC_FILES.values()) | {"daily_energy_met_MU.csv", "peak_met_MW.csv"}
    for p in sorted(RAW.glob("*.csv")):
        if p.name in excluded or p.name.lower().startswith("weighted_daily_mean_utci"):
            continue
        try:
            df = pd.read_csv(p)
            dc = date_col(df)
        except (ValueError, pd.errors.ParserError, UnicodeDecodeError):
            continue
        df = df.rename(columns={dc: "date"})
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["state"] = p.stem
        df = df.dropna(subset=["date"])
        if df.duplicated(["state", "date"]).any():
            raise ValueError(f"Duplicate weather state/date key in {p.name}")
        weather_frames.append(df)
    if not weather_frames:
        raise RuntimeError("No state weather files detected; inspect schema report.")
    weather = pd.concat(weather_frames, ignore_index=True, sort=False)
    weather.to_csv(INTERIM/"weather_long.csv", index=False)
    panel = electricity.merge(weather, on=["state", "date"], how="outer",
                              suffixes=("", "_weather"), validate="one_to_one")
    panel = panel.sort_values(["state", "date"])
    panel.to_csv(PROCESSED/"state_daily_panel.csv", index=False)
    print(f"Electricity rows={len(electricity):,}; weather rows={len(weather):,}; panel rows={len(panel):,}")
    print(f"States={panel.state.nunique()}; saved {PROCESSED/'state_daily_panel.csv'}")

if __name__ == "__main__":
    main()
