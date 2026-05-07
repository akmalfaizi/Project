"""
postprocess.py
--------------
Aggregate NetCDF results into summary DataFrames for the Streamlit dashboard.
"""

import json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import xarray as xr

PROJECT_ROOT = Path(__file__).parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"

MILESTONE_YEARS = [2025, 2030, 2035, 2040, 2045, 2050]
ALL_REGIONS = ["peninsular", "sabah", "sarawak"]

EMISSION_FACTORS = {
    "coal_existing": 0.88, "coal_new": 0.80, "gas_ccgt": 0.35, "gas_ocgt": 0.55,
    "diesel_genset": 0.65, "solar_utility": 0.0, "solar_rooftop": 0.0, "wind_onshore": 0.0,
    "hydro_large_existing": 0.0, "hydro_ror": 0.0, "biomass_plant": 0.05,
    "battery_storage": 0.0, "hvdc_sabah_sarawak": 0.0,
}


def load_nc(scenario, region, year):
    path = RESULTS_DIR / scenario / f"{region}_{year}.nc"
    if path.exists():
        return xr.open_dataset(str(path))
    return None


def _parse_loc_tech(lt):
    parts = str(lt).split("::", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else (parts[0], "")


def _parse_loc_tech_carrier(ltc):
    parts = str(ltc).split("::")
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    return parts[0], ":".join(parts[1:]), ""


def get_capacity_mix(scenario, region):
    rows = {}
    for year in MILESTONE_YEARS:
        ds = load_nc(scenario, region, year)
        if ds is None: continue
        try:
            ec = ds["energy_cap"]
            row = {}
            for lt in ec.loc_techs.values:
                r, tech = _parse_loc_tech(lt)
                if r == region:
                    row[tech] = float(ec.sel(loc_techs=lt).values)
            rows[year] = row
        except Exception:
            pass
    return pd.DataFrame(rows).T.fillna(0) if rows else pd.DataFrame()


def get_generation_mix(scenario, region):
    rows = {}
    for year in MILESTONE_YEARS:
        ds = load_nc(scenario, region, year)
        if ds is None: continue
        try:
            cp = ds["carrier_prod"]
            weights = _load_weights(region, year)
            gen_twh = {}
            for ltc in cp.loc_tech_carriers_prod.values:
                r, tech, carrier = _parse_loc_tech_carrier(ltc)
                if r != region or carrier != "electricity": continue
                ts_values = np.where(cp.sel(loc_tech_carriers_prod=ltc).values > 0,
                                     cp.sel(loc_tech_carriers_prod=ltc).values, 0)
                gen_twh[tech] = (_apply_weights(ts_values, weights) if weights is not None else ts_values.sum()) / 1e6
            rows[year] = gen_twh
        except Exception:
            pass
    return pd.DataFrame(rows).T.fillna(0) if rows else pd.DataFrame()


def get_emissions(scenario, region):
    gen = get_generation_mix(scenario, region)
    if gen.empty: return pd.Series(dtype=float)
    return pd.Series({year: sum(gen.loc[year, tech] * EMISSION_FACTORS.get(tech, 0)
                                for tech in gen.columns) for year in gen.index})


def get_system_cost(scenario, region):
    rows = {}
    for year in MILESTONE_YEARS:
        ds = load_nc(scenario, region, year)
        if ds is None: continue
        try:
            capex = sum(float(ds["cost_investment"].sel(costs="monetary", loc_techs_investment_cost=lt).values)
                        for lt in ds["cost_investment"].loc_techs_investment_cost.values
                        if _parse_loc_tech(lt)[0] == region) if "cost_investment" in ds else 0.0
            opex = sum(float(ds["cost_var"].sel(costs="monetary", loc_techs_om_cost=lt).values.sum())
                       for lt in ds["cost_var"].loc_techs_om_cost.values
                       if _parse_loc_tech(lt)[0] == region) if "cost_var" in ds else 0.0
            rows[year] = {"capex_annualised": capex / 1e6, "opex_variable": opex / 1e6}
        except Exception:
            rows[year] = {"capex_annualised": 0, "opex_variable": 0}
    return pd.DataFrame(rows).T.fillna(0)


def get_curtailment(scenario, region):
    return pd.Series({year: 0 for year in MILESTONE_YEARS if load_nc(scenario, region, year) is not None})


def get_battery_kpis(scenario, region):
    rows = {}
    for year in MILESTONE_YEARS:
        ds = load_nc(scenario, region, year)
        if ds is None: continue
        try:
            batt_lt = f"{region}::battery_storage"
            batt_ltc = f"{region}::battery_storage::electricity"
            if "storage" not in ds or batt_lt not in ds["storage"].loc_techs_store.values: continue
            soc = ds["storage"].sel(loc_techs_store=batt_lt).values
            storage_cap = float(ds["storage_cap"].sel(loc_techs_store=batt_lt).values)
            energy_cap = next((float(ds["energy_cap"].sel(loc_techs=lt).values)
                               for lt in ds["energy_cap"].loc_techs.values if str(lt) == batt_lt), 0.0)
            if storage_cap > 0 and energy_cap > 0:
                avg_soc = float(np.mean(soc / storage_cap))
                cp = ds["carrier_prod"]
                discharge = np.where(cp.sel(loc_tech_carriers_prod=batt_ltc).values > 0,
                                     cp.sel(loc_tech_carriers_prod=batt_ltc).values, 0) \
                    if batt_ltc in cp.loc_tech_carriers_prod.values else np.zeros(len(ds.timesteps))
                rows[year] = {"cycles_per_year": discharge.sum() / storage_cap, "avg_soc": avg_soc,
                              "duration_utilisation": avg_soc, "capacity_factor": float(np.mean(discharge > 0.01 * energy_cap)),
                              "installed_mw": energy_cap, "installed_mwh": storage_cap}
        except Exception:
            pass
    return pd.DataFrame(rows).T if rows else pd.DataFrame()


def get_diurnal_mix(scenario, region, year):
    ds = load_nc(scenario, region, year)
    if ds is None: return pd.DataFrame()
    try:
        cp = ds["carrier_prod"]
        hours = 24
        n_days = len(ds.timesteps) // hours
        tech_profiles = {}
        for ltc in cp.loc_tech_carriers_prod.values:
            r, tech, carrier = _parse_loc_tech_carrier(ltc)
            if r != region or carrier != "electricity": continue
            vals = np.where(cp.sel(loc_tech_carriers_prod=ltc).values > 0,
                            cp.sel(loc_tech_carriers_prod=ltc).values, 0)
            tech_profiles[tech] = vals.reshape(n_days, hours).mean(axis=0)
        cc = ds["carrier_con"]
        for ltc in cc.loc_tech_carriers_con.values:
            r, tech, carrier = _parse_loc_tech_carrier(ltc)
            if r != region or carrier != "electricity" or "demand" not in tech: continue
            vals = abs(cc.sel(loc_tech_carriers_con=ltc).values)
            tech_profiles["demand_electricity"] = vals.reshape(n_days, hours).mean(axis=0)
        if not tech_profiles: return pd.DataFrame()
        df = pd.DataFrame(tech_profiles, index=range(hours))
        df.index.name = "hour"
        return df
    except Exception:
        return pd.DataFrame()


def _load_weights(region, year):
    path = PROJECT_ROOT / "model" / "timeseries" / f"cluster_weights_{region}.csv"
    return pd.read_csv(path) if path.exists() else None


def _apply_weights(ts_values, weights):
    n_clusters = len(weights)
    hours_per_cluster = len(ts_values) // n_clusters
    return sum(ts_values[i*hours_per_cluster:(i+1)*hours_per_cluster].sum() * weights.iloc[i]["weight"]
               for i in range(n_clusters))


def load_scenario_results(scenario, regions=None):
    if regions is None: regions = ALL_REGIONS
    return {region: {"capacity_mix": get_capacity_mix(scenario, region),
                     "generation_mix": get_generation_mix(scenario, region),
                     "emissions": get_emissions(scenario, region),
                     "system_cost": get_system_cost(scenario, region),
                     "curtailment": get_curtailment(scenario, region),
                     "battery_kpis": get_battery_kpis(scenario, region)} for region in regions}
