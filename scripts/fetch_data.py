"""
fetch_data.py
-------------
Fetch and process input time series data for all three Malaysia regions.

Usage:
    python scripts/fetch_data.py --region all
    python scripts/fetch_data.py --no-nasa
"""

import argparse
import time
import numpy as np
import pandas as pd
import requests
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TIMESERIES_DIR = PROJECT_ROOT / "model" / "timeseries"
TIMESERIES_DIR.mkdir(parents=True, exist_ok=True)

NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/hourly/point"

REGION_COORDS = {
    "peninsular": {"lat": 3.8, "lon": 101.7},
    "sabah": {"lat": 5.9, "lon": 116.1},
    "sarawak": {"lat": 1.55, "lon": 110.35},
}

REGION_DEMAND = {
    "peninsular": {"peak_mw": 20500, "annual_twh": 120.0},
    "sabah": {"peak_mw": 1200, "annual_twh": 7.5},
    "sarawak": {"peak_mw": 3200, "annual_twh": 20.0},
}

HYDRO_MONTHLY_CF = {
    "peninsular": [0.55, 0.50, 0.45, 0.40, 0.45, 0.50, 0.55, 0.55, 0.60, 0.65, 0.70, 0.65],
    "sabah": [0.60, 0.55, 0.50, 0.45, 0.40, 0.38, 0.40, 0.42, 0.48, 0.55, 0.62, 0.65],
    "sarawak": [0.75, 0.70, 0.65, 0.60, 0.55, 0.55, 0.55, 0.55, 0.58, 0.62, 0.70, 0.78],
}


def fetch_nasa_solar(lat, lon, year=2022):
    params = {"parameters": "ALLSKY_SFC_SW_DWN", "community": "RE", "longitude": lon,
              "latitude": lat, "start": f"{year}0101", "end": f"{year}1231",
              "format": "JSON", "time-standard": "UTC", "header": "true"}
    resp = requests.get(NASA_POWER_URL, params=params, timeout=60)
    resp.raise_for_status()
    raw = resp.json()["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"]
    ghi = np.array(list(raw.values()), dtype=float)
    ghi = np.where(ghi < 0, 0, ghi)
    cf = np.clip((ghi / 1000.0) * 0.80, 0, 1)
    idx = pd.date_range(f"{year}-01-01", periods=len(cf), freq="h")
    return pd.Series(cf, index=idx, name="solar_cf").iloc[:8760]


def synthesize_demand(region, year=2025):
    annual_twh = REGION_DEMAND[region]["annual_twh"]
    peak_mw = REGION_DEMAND[region]["peak_mw"]
    idx = pd.date_range(f"{year}-01-01", periods=8760, freq="h")
    hours = np.arange(8760)
    hour_of_day = hours % 24
    day_of_year = hours // 24
    daily_shape = (0.60 + 0.20 * np.exp(-((hour_of_day - 10) ** 2) / 8)
                   + 0.30 * np.exp(-((hour_of_day - 20) ** 2) / 6)
                   - 0.10 * np.exp(-((hour_of_day - 4) ** 2) / 4))
    daily_shape = np.clip(daily_shape, 0.45, 1.0)
    seasonal = 1.0 + 0.08 * np.sin(2 * np.pi * (day_of_year % 365 - 60) / 365)
    dow_factor = np.where(idx.dayofweek >= 5, 0.88, 1.0)
    profile = daily_shape * seasonal * dow_factor
    profile = profile / profile.max()
    demand_mw = profile * peak_mw
    actual_twh = demand_mw.sum() / 1e6
    demand_mw = demand_mw * (annual_twh / actual_twh)
    return pd.Series(-demand_mw, index=idx, name="demand")


def synthesize_hydro_cf(region, year=2025):
    idx = pd.date_range(f"{year}-01-01", periods=8760, freq="h")
    monthly_cf = HYDRO_MONTHLY_CF[region]
    cf_hourly = np.array([monthly_cf[ts.month - 1] + np.random.normal(0, 0.03) for ts in idx])
    return pd.Series(np.clip(cf_hourly, 0.1, 0.95), index=idx, name="hydro_cf")


def synthesize_wind_cf(region, year=2025):
    idx = pd.date_range(f"{year}-01-01", periods=8760, freq="h")
    mean_cf = {"sarawak": 0.05, "sabah": 0.18, "peninsular": 0.12}[region]
    hour_of_day = np.arange(8760) % 24
    diurnal = 1.0 - 0.3 * np.sin(2 * np.pi * (hour_of_day - 6) / 24)
    cf = np.clip(mean_cf * diurnal + np.random.normal(0, 0.02, 8760), 0, 0.6)
    return pd.Series(cf, index=idx, name="wind_cf")


def fetch_and_save_region(region, year=2025, use_nasa=True):
    print(f"\nProcessing region: {region} (year={year})")
    lat = REGION_COORDS[region]["lat"]
    lon = REGION_COORDS[region]["lon"]
    solar_path = TIMESERIES_DIR / f"solar_cf_{region}_raw.csv"
    if not solar_path.exists():
        if use_nasa:
            try:
                solar = fetch_nasa_solar(lat, lon, year=year - 3)
                solar.to_frame().to_csv(solar_path)
                time.sleep(1)
                use_nasa = True
            except Exception as e:
                print(f"  NASA API failed ({e}), synthesizing solar CF instead")
                use_nasa = False
        if not use_nasa:
            idx = pd.date_range(f"{year}-01-01", periods=8760, freq="h")
            hour = np.arange(8760) % 24
            day = np.arange(8760) // 24
            ghi = np.where((hour >= 6) & (hour <= 18),
                           4.5 * np.sin(np.pi * (hour - 6) / 12) * (1 + 0.05 * np.sin(2 * np.pi * day / 365)), 0) * 0.80
            pd.Series(np.clip(ghi, 0, 0.85), index=idx, name="solar_cf").to_frame().to_csv(solar_path)
    for name, fn, path in [
        ("demand", lambda: synthesize_demand(region, year), TIMESERIES_DIR / f"demand_{region}_raw.csv"),
        ("hydro", lambda: synthesize_hydro_cf(region, year), TIMESERIES_DIR / f"hydro_cf_{region}_raw.csv"),
        ("wind", lambda: synthesize_wind_cf(region, year), TIMESERIES_DIR / f"wind_cf_{region}_raw.csv"),
    ]:
        if not path.exists():
            fn().to_frame().to_csv(path)
            print(f"  Saved: {path}")
        else:
            print(f"  {name.title()} already exists: {path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", choices=["peninsular", "sabah", "sarawak", "all"], default="all")
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--no-nasa", action="store_true")
    args = parser.parse_args()
    regions = ["peninsular", "sabah", "sarawak"] if args.region == "all" else [args.region]
    for r in regions:
        fetch_and_save_region(r, year=args.year, use_nasa=not args.no_nasa)
    print("\nAll data fetched. Run time_cluster.py next.")


if __name__ == "__main__":
    main()
