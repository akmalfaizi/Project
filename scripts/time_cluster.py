"""
time_cluster.py
---------------
Generate 24 representative days from full-year hourly time series using k-means clustering.

Usage:
    python scripts/time_cluster.py --region peninsular --year 2025
"""

import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.preprocessing import MinMaxScaler
from sklearn.cluster import KMeans

PROJECT_ROOT = Path(__file__).parent.parent
TIMESERIES_DIR = PROJECT_ROOT / "model" / "timeseries"
N_CLUSTERS = 24


def load_raw_timeseries(region):
    files = {
        "demand": TIMESERIES_DIR / f"demand_{region}_raw.csv",
        "solar_cf": TIMESERIES_DIR / f"solar_cf_{region}_raw.csv",
        "wind_cf": TIMESERIES_DIR / f"wind_cf_{region}_raw.csv",
        "hydro_cf": TIMESERIES_DIR / f"hydro_cf_{region}_raw.csv",
    }
    dfs = {}
    for key, path in files.items():
        if path.exists():
            dfs[key] = pd.read_csv(path, index_col=0, parse_dates=True).squeeze()
        else:
            print(f"  WARNING: {path} not found")
    return pd.DataFrame(dfs)


def reshape_to_daily(df):
    n_days = len(df) // 24
    return df.values[:n_days * 24].reshape(n_days, 24 * df.shape[1])


def run_kmeans(daily_matrix, n_clusters=N_CLUSTERS, random_state=42):
    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(daily_matrix)
    km = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10, max_iter=300)
    labels = km.fit_predict(scaled)
    return labels, scaler.inverse_transform(km.cluster_centers_)


def build_clustered_timeseries(labels, centres, columns, year=2025):
    n_clusters, _ = centres.shape
    n_vars = len(columns)
    centres_3d = centres.reshape(n_clusters, 24, n_vars)
    base = pd.Timestamp(f"{year}-01-01")
    dfs = []
    for i in range(n_clusters):
        day_start = base + pd.Timedelta(days=i)
        idx = pd.date_range(day_start, periods=24, freq="h")
        dfs.append(pd.DataFrame(centres_3d[i], index=idx, columns=columns))
    ts = pd.concat(dfs)
    unique, counts = np.unique(labels, return_counts=True)
    weight_map = dict(zip(unique, counts))
    weights = pd.DataFrame({"cluster": range(n_clusters),
                             "weight": [weight_map.get(i, 0) for i in range(n_clusters)],
                             "start_date": [base + pd.Timedelta(days=i) for i in range(n_clusters)]})
    return ts, weights


def split_and_save(ts, weights, region):
    for col in ts.columns:
        ts[[col]].to_csv(TIMESERIES_DIR / f"{col}_{region}.csv")
    weights.to_csv(TIMESERIES_DIR / f"cluster_weights_{region}.csv", index=False)


def cluster_region(region, year=2025):
    print(f"\nClustering region: {region}")
    df = load_raw_timeseries(region)
    if df.empty:
        print(f"  ERROR: No data for {region}")
        return
    labels, centres = run_kmeans(reshape_to_daily(df))
    ts, weights = build_clustered_timeseries(labels, centres, list(df.columns), year=year)
    split_and_save(ts, weights, region)
    print(f"  Done: {region}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", choices=["peninsular", "sabah", "sarawak", "all"], default="all")
    parser.add_argument("--year", type=int, default=2025)
    args = parser.parse_args()
    regions = ["peninsular", "sabah", "sarawak"] if args.region == "all" else [args.region]
    for r in regions:
        cluster_region(r, year=args.year)


if __name__ == "__main__":
    main()
