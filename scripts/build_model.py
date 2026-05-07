"""
build_model.py
--------------
Assemble a Calliope model object for a given region and milestone year.
"""

import copy
import json
from pathlib import Path
from typing import Optional

import calliope
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).parent.parent
MODEL_DIR = PROJECT_ROOT / "model"
ANNUAL_INPUTS_PATH = PROJECT_ROOT / "data" / "annual_inputs.json"


def _load_annual_inputs() -> Optional[dict]:
    if ANNUAL_INPUTS_PATH.exists():
        with open(ANNUAL_INPUTS_PATH) as f:
            return json.load(f)
    return None


RE_TARGETS = {
    "baseline": {2025: 0.20, 2030: 0.25, 2035: 0.30, 2040: 0.35, 2045: 0.40, 2050: 0.45},
    "netr_target": {2025: 0.31, 2030: 0.35, 2035: 0.40, 2040: 0.52, 2045: 0.62, 2050: 0.70},
    "accelerated_re": {2025: 0.35, 2030: 0.45, 2035: 0.55, 2040: 0.65, 2045: 0.75, 2050: 0.82},
}

RE_TECHS = ["solar_utility", "solar_rooftop", "wind_onshore", "hydro_large_existing", "hydro_ror", "biomass_plant"]

DEFAULT_DEMAND_GROWTH = {"peninsular": 0.035, "sabah": 0.045, "sarawak": 0.040}

COAL_RETIREMENT = {
    "peninsular": {2025: (12800, 12800), 2030: (0, 10000), 2035: (0, 7000), 2040: (0, 3000), 2045: (0, 0), 2050: (0, 0)},
    "sarawak": {2025: (920, 920), 2030: (0, 920), 2035: (0, 500), 2040: (0, 0), 2045: (0, 0), 2050: (0, 0)},
    "sabah": {yr: (0, 0) for yr in [2025, 2030, 2035, 2040, 2045, 2050]},
}

SOLAR_MAX_CAPACITY = {
    "peninsular": {2025: 7000, 2030: 15000, 2035: 22000, 2040: 30000, 2045: 37000, 2050: 40000},
    "sabah": {2025: 800, 2030: 1500, 2035: 2000, 2040: 2500, 2045: 3000, 2050: 3000},
    "sarawak": {2025: 500, 2030: 2000, 2035: 4000, 2040: 6000, 2045: 8000, 2050: 10000},
}

CARBON_PRICE = {
    "baseline": {2025: 0, 2030: 0, 2035: 0, 2040: 0, 2045: 0, 2050: 0},
    "netr_target": {2025: 10, 2030: 20, 2035: 35, 2040: 50, 2045: 65, 2050: 80},
    "accelerated_re": {2025: 25, 2030: 50, 2035: 80, 2040: 110, 2045: 135, 2050: 150},
}


def compute_demand_scale(region, milestone_year, base_year=2025, growth_rate=None):
    rate = growth_rate if growth_rate is not None else DEFAULT_DEMAND_GROWTH[region]
    return (1 + rate) ** (milestone_year - base_year)


def build_override_dict(region, milestone_year, scenario="baseline", prev_caps=None,
                        demand_growth=None, carbon_price_override=None, tech_costs=None):
    if prev_caps is None:
        prev_caps = {}
    overrides = {"locations": {region: {"techs": {}}}, "links": {}}
    loc = overrides["locations"][region]["techs"]
    annual = _load_annual_inputs()
    yr_str = str(milestone_year)

    if annual:
        coal_cap = annual["capacity"][region]["coal_existing"][yr_str]
        prev_years = [y for y in [2025, 2030, 2035, 2040, 2045, 2050] if y < milestone_year]
        if prev_years:
            coal_prev = annual["capacity"][region]["coal_existing"][str(max(prev_years))]
            coal_max = max(coal_cap, coal_prev)
        else:
            coal_max = coal_cap
        coal_min = coal_cap
        if coal_min == coal_max:
            loc["coal_existing"] = {"constraints": {"energy_cap_equals": coal_cap}}
        else:
            loc["coal_existing"] = {"constraints": {"energy_cap_min": coal_min, "energy_cap_max": coal_max}}
    else:
        coal_min, coal_max = COAL_RETIREMENT.get(region, {}).get(milestone_year, (0, 0))
        if coal_min == coal_max:
            loc["coal_existing"] = {"constraints": {"energy_cap_equals": coal_max}}
        else:
            loc["coal_existing"] = {"constraints": {"energy_cap_min": coal_min, "energy_cap_max": coal_max}}
    loc["coal_new"] = {"constraints": {"energy_cap_max": 0}}

    if annual:
        cap_data = annual["capacity"][region]

        def _set_cap(tech_key, loc_tech):
            val = cap_data.get(tech_key, {}).get(yr_str)
            if val is not None:
                loc.setdefault(loc_tech, {"constraints": {}})["constraints"]["energy_cap_max"] = val

        def _set_min(tech_key, loc_tech):
            val = cap_data.get(tech_key, {}).get(yr_str)
            if val is not None and val > 0:
                loc.setdefault(loc_tech, {"constraints": {}})["constraints"]["energy_cap_min"] = val

        _set_cap("solar_utility_max", "solar_utility")
        _set_cap("solar_rooftop_max", "solar_rooftop")
        _set_cap("wind_onshore_max", "wind_onshore")
        _set_cap("biomass_max", "biomass_plant")
        _set_cap("battery_max", "battery_storage")
        _set_min("gas_ccgt", "gas_ccgt")
        _set_min("gas_ocgt", "gas_ocgt")
        _set_min("hydro_large_existing", "hydro_large_existing")
        _set_min("hydro_ror_min", "hydro_ror")
        _set_min("diesel_genset", "diesel_genset")

        fp = annual["fuel_prices"].get(yr_str, {})
        gas_price = fp.get("gas_usd_gj", 10.0)
        coal_price = fp.get("coal_usd_tonne", 100.0)
        coal_gj_per_t = 26.0
        for tech, eff, var_om in [("gas_ccgt", 0.52, 3.0), ("gas_ocgt", 0.35, 4.0),
                                   ("coal_existing", 0.38, 4.0), ("coal_new", 0.42, 3.0)]:
            if "gas" in tech:
                fuel_cost = 3.6 * gas_price / eff
            else:
                fuel_cost = 3.6 * coal_price / (coal_gj_per_t * eff)
            om_con = round(fuel_cost + var_om, 2)
            loc.setdefault(tech, {}).setdefault("costs", {}).setdefault("monetary", {})["om_con"] = om_con
    else:
        solar_max = SOLAR_MAX_CAPACITY.get(region, {}).get(milestone_year)
        if solar_max is not None:
            loc.setdefault("solar_utility", {"constraints": {}})["constraints"]["energy_cap_max"] = solar_max
            loc.setdefault("solar_rooftop", {"constraints": {}})["constraints"]["energy_cap_max"] = int(solar_max * 0.15)

    _no_carryforward = {"coal_existing", "coal_new", "demand_electricity"}
    for tech, cap in prev_caps.items():
        if cap > 0 and tech not in _no_carryforward:
            existing_max = loc.get(tech, {}).get("constraints", {}).get("energy_cap_max")
            if existing_max is not None and cap > existing_max:
                cap = existing_max
            loc.setdefault(tech, {"constraints": {}})["constraints"]["energy_cap_min"] = cap

    if tech_costs:
        for tech, cost_dict in tech_costs.items():
            loc.setdefault(tech, {"costs": {"monetary": {}}}).setdefault("costs", {}).setdefault("monetary", {})
            for cost_key, cost_val in cost_dict.items():
                loc[tech]["costs"]["monetary"][cost_key] = cost_val

    if region in ("sabah", "sarawak"):
        if annual:
            hvdc_cap = annual["hvdc_mw"].get(yr_str, 0)
        else:
            hvdc_cap = 1000 if (milestone_year >= 2035 and scenario != "baseline") else 0
        if hvdc_cap > 0:
            overrides["links"]["sabah,sarawak"] = {
                "techs": {"hvdc_sabah_sarawak": {"constraints": {"energy_cap_max": hvdc_cap}}}
            }

    re_target = RE_TARGETS.get(scenario, RE_TARGETS["baseline"]).get(milestone_year, 0)
    return overrides, re_target


def build_model(region, milestone_year, scenario="baseline", prev_caps=None,
                demand_growth=None, carbon_price_override=None, tech_costs=None, n_rep_days=24):
    override_dict, re_target = build_override_dict(region, milestone_year, scenario, prev_caps,
                                                    demand_growth, carbon_price_override, tech_costs)
    if re_target > 0:
        override_dict["group_constraints"] = {
            "min_renewable_share": {"locs": [region], "techs": RE_TECHS, "energy_cap_share_min": re_target}
        }
    import datetime
    TS_BASE_YEAR = 2025
    start_dt = datetime.date(TS_BASE_YEAR, 1, 1)
    end_dt = start_dt + datetime.timedelta(days=n_rep_days - 1)
    subset_end = f"{end_dt.year}-{end_dt.month:02d}-{end_dt.day:02d} 23:00:00"
    subset_start = f"{TS_BASE_YEAR}-01-01 00:00:00"
    run_yaml_path = MODEL_DIR / f"_run_{region}_{milestone_year}_{scenario}.yaml"
    run_config = {
        "import": ["techs/supply.yaml", "techs/storage.yaml", "techs/demand.yaml",
                   "techs/transmission.yaml", f"locations/{region}.yaml"],
        "model": {"name": f"Malaysia {region.title()} {milestone_year} ({scenario})",
                  "calliope_version": "0.6.10", "timeseries_data_path": f"timeseries/{region}",
                  "subset_time": [subset_start, subset_end]},
        "run": {"mode": "plan", "solver": "appsi_highs", "solver_options": {}, "backend": "pyomo",
                "objective_options": {"cost_class": {"monetary": 1}, "sense": "minimize"}},
    }
    with open(run_yaml_path, "w") as f:
        yaml.dump(run_config, f, default_flow_style=False, sort_keys=False)
    model = calliope.Model(str(run_yaml_path), override_dict=override_dict)
    return model


def scale_demand_csv(region, milestone_year, demand_growth=None):
    base_path = MODEL_DIR / "timeseries" / f"demand_{region}.csv"
    if not base_path.exists():
        raise FileNotFoundError(f"Base demand CSV not found: {base_path}")
    scale = compute_demand_scale(region, milestone_year, growth_rate=demand_growth)
    df = pd.read_csv(base_path, index_col=0, parse_dates=True)
    df.columns = [region]
    df_scaled = df * scale
    region_ts_dir = MODEL_DIR / "timeseries" / region
    region_ts_dir.mkdir(parents=True, exist_ok=True)
    out_path = region_ts_dir / "demand.csv"
    df_scaled.to_csv(out_path)


if __name__ == "__main__":
    m = build_model("peninsular", 2025, scenario="baseline")
    print(m)
