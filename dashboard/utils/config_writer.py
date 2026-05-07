"""
config_writer.py
----------------
Translate Streamlit dashboard state into Calliope YAML override files.
"""

from pathlib import Path
from typing import Optional

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
OVERRIDES_DIR = PROJECT_ROOT / "model" / "overrides"
OVERRIDES_DIR.mkdir(parents=True, exist_ok=True)


def demand_growth_from_ui(peninsular: float, sabah: float, sarawak: float) -> dict:
    return {"peninsular": peninsular / 100.0, "sabah": sabah / 100.0, "sarawak": sarawak / 100.0}


def tech_costs_from_ui(cost_table: dict) -> dict:
    result = {}
    for tech, costs in cost_table.items():
        entry = {}
        if "capex_usd_kw" in costs:
            entry["energy_cap"] = costs["capex_usd_kw"] * 1000
        if "opex_fixed_usd_kw_yr" in costs:
            entry["om_annual"] = costs["opex_fixed_usd_kw_yr"] * 1000
        if "opex_var_usd_mwh" in costs:
            entry["om_con"] = costs["opex_var_usd_mwh"] / 1000
        if entry:
            result[tech] = entry
    return result


def carbon_price_from_ui(trajectory: str, custom_value: Optional[float] = None) -> Optional[float]:
    presets = {"none": None, "low": 10.0, "medium": 50.0, "high": 100.0}
    if trajectory == "custom":
        return custom_value
    return presets.get(trajectory)


def re_targets_from_ui(target_table: dict) -> dict:
    return {int(yr): pct / 100.0 for yr, pct in target_table.items()}


def save_custom_scenario(name, base_scenario, demand_growth, tech_costs,
                         carbon_price_trajectory, re_targets, toggles) -> Path:
    slug = name.lower().replace(" ", "_").replace("-", "_")
    out_path = OVERRIDES_DIR / f"{slug}.yaml"
    config = {
        "overrides": {
            slug: {
                "model.name": f"Malaysia {name}",
                "_base_scenario": base_scenario,
                "_demand_growth": demand_growth,
                "_tech_costs": tech_costs,
                "_carbon_price_trajectory": carbon_price_trajectory,
                "_re_targets": {str(k): v for k, v in re_targets.items()},
                "_toggles": toggles,
            }
        }
    }
    with open(out_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    return out_path


def load_custom_scenario(name: str) -> dict:
    slug = name.lower().replace(" ", "_").replace("-", "_")
    path = OVERRIDES_DIR / f"{slug}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Scenario not found: {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    return data["overrides"][slug]


def list_saved_scenarios() -> list:
    yamls = list(OVERRIDES_DIR.glob("*.yaml"))
    exclude = {"cost_low", "cost_high"}
    return [p.stem for p in yamls if p.stem not in exclude]
