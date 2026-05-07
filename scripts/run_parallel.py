"""
run_parallel.py
---------------
Multiprocessing launcher for running regional models simultaneously.
"""

import argparse
import logging
import multiprocessing as mp
import sys
import time
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

log = logging.getLogger(__name__)


def _worker(kwargs):
    from scripts.myopic_chain import run_single_region
    return run_single_region(**kwargs)


def run_regions_parallel(regions, year, scenario, prev_caps_by_region, run_dir,
                         demand_growth=None, carbon_price_override=None, tech_costs=None, n_workers=3):
    n_workers = min(n_workers, mp.cpu_count(), len(regions))
    tasks = []
    for region in regions:
        dgrowth = demand_growth.get(region) if demand_growth else None
        tasks.append({"region": region, "year": year, "scenario": scenario,
                      "prev_caps": prev_caps_by_region.get(region, {}), "run_dir": run_dir,
                      "demand_growth": dgrowth, "carbon_price_override": carbon_price_override,
                      "tech_costs": tech_costs})
    t0 = time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=n_workers) as pool:
        results = pool.map(_worker, tasks)
    log.info(f"Year {year} complete in {time.time()-t0:.1f}s")
    return results


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stdout)
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["baseline", "netr_target", "accelerated_re"], default="baseline")
    parser.add_argument("--regions", nargs="+", default=["peninsular", "sabah", "sarawak"])
    parser.add_argument("--no-parallel", action="store_true")
    parser.add_argument("--demand-growth-peninsular", type=float, default=None)
    parser.add_argument("--demand-growth-sabah", type=float, default=None)
    parser.add_argument("--demand-growth-sarawak", type=float, default=None)
    args = parser.parse_args()
    demand_growth = {}
    if args.demand_growth_peninsular: demand_growth["peninsular"] = args.demand_growth_peninsular
    if args.demand_growth_sabah: demand_growth["sabah"] = args.demand_growth_sabah
    if args.demand_growth_sarawak: demand_growth["sarawak"] = args.demand_growth_sarawak
    from scripts.myopic_chain import run_myopic_chain
    t_start = time.time()
    run_myopic_chain(scenario=args.scenario, regions=args.regions,
                     demand_growth=demand_growth or None, parallel=not args.no_parallel)
    log.info(f"\nTotal runtime: {(time.time()-t_start)/60:.1f} minutes")


if __name__ == "__main__":
    main()
