"""
myopic_chain.py
---------------
Myopic rolling optimization engine for Malaysia energy model.
"""

import json
import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import xarray as xr

PROJECT_ROOT = Path(__file__).parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

MILESTONE_YEARS = [2025, 2030, 2035, 2040, 2045, 2050]
ALL_REGIONS = ["peninsular", "sabah", "sarawak"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)


def extract_capacities(model_results, region):
    caps = {}
    try:
        energy_cap = model_results["energy_cap"]
        prefix = f"{region}::"
        for loc_tech in energy_cap.loc_techs.values:
            if str(loc_tech).startswith(prefix):
                tech = str(loc_tech).split("::", 1)[1]
                val = float(energy_cap.sel(loc_techs=loc_tech).values)
                if val > 0.01:
                    caps[tech] = val
    except Exception as e:
        log.warning(f"Could not extract capacities for {region}: {e}")
    return caps


def save_results(model_results, region, year, scenario, run_dir):
    out_path = run_dir / f"{region}_{year}.nc"
    clean_attrs = {k: (str(v) if v is None else v) for k, v in model_results.attrs.items()}
    model_results.assign_attrs(clean_attrs).to_netcdf(str(out_path))
    log.info(f"Saved results: {out_path}")
    return out_path


def run_single_region(region, year, scenario, prev_caps, run_dir,
                      demand_growth=None, carbon_price_override=None, tech_costs=None):
    from scripts.build_model import build_model, scale_demand_csv
    log.info(f"Starting: {region} {year} ({scenario})")
    try:
        scale_demand_csv(region, year, demand_growth=demand_growth)
        model = build_model(region, year, scenario=scenario, prev_caps=prev_caps,
                            demand_growth=demand_growth, carbon_price_override=carbon_price_override,
                            tech_costs=tech_costs)
        model.run()
        caps = extract_capacities(model.results, region)
        result_path = save_results(model.results, region, year, scenario, run_dir)
        log.info(f"Completed: {region} {year}")
        return {"region": region, "year": year, "caps": caps, "result_path": result_path, "success": True}
    except Exception as e:
        log.error(f"FAILED: {region} {year}: {e}", exc_info=True)
        return {"region": region, "year": year, "caps": prev_caps, "result_path": None, "success": False, "error": str(e)}


def run_myopic_chain(scenario="baseline", regions=None, demand_growth=None,
                    carbon_price_override=None, tech_costs=None, parallel=True, progress_callback=None):
    if regions is None:
        regions = ALL_REGIONS
    run_dir = RESULTS_DIR / scenario
    run_dir.mkdir(parents=True, exist_ok=True)
    carried_caps = {r: {} for r in regions}
    all_results = {r: {"caps_by_year": {}, "result_paths": []} for r in regions}

    for year in MILESTONE_YEARS:
        log.info(f"\n{'='*60}\nMilestone year: {year}\n{'='*60}")
        if parallel:
            from scripts.run_parallel import run_regions_parallel
            year_results = run_regions_parallel(regions=regions, year=year, scenario=scenario,
                                                prev_caps_by_region=carried_caps, run_dir=run_dir,
                                                demand_growth=demand_growth, carbon_price_override=carbon_price_override,
                                                tech_costs=tech_costs)
        else:
            year_results = []
            for region in regions:
                dgrowth = demand_growth.get(region) if demand_growth else None
                year_results.append(run_single_region(region, year, scenario, carried_caps[region], run_dir,
                                                      demand_growth=dgrowth, carbon_price_override=carbon_price_override,
                                                      tech_costs=tech_costs))
        for res in year_results:
            region = res["region"]
            carried_caps[region] = res["caps"]
            all_results[region]["caps_by_year"][year] = res["caps"]
            if res["result_path"]:
                all_results[region]["result_paths"].append(str(res["result_path"]))
            if progress_callback:
                progress_callback(year, region, "success" if res["success"] else "failed")

    summary_path = run_dir / "summary_caps.json"
    with open(summary_path, "w") as f:
        json.dump({r: {str(y): v for y, v in all_results[r]["caps_by_year"].items()} for r in all_results}, f, indent=2)
    log.info(f"Run complete. Summary: {summary_path}")
    return all_results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="baseline")
    parser.add_argument("--regions", nargs="+", default=["peninsular", "sabah", "sarawak"])
    parser.add_argument("--no-parallel", action="store_true")
    args = parser.parse_args()
    run_myopic_chain(scenario=args.scenario, regions=args.regions, parallel=not args.no_parallel)
