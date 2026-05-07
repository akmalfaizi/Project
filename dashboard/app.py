"""
app.py — Malaysia Energy Model Dashboard (Streamlit entry point)

Run with:
    cd malaysia_calliope
    streamlit run dashboard/app.py
"""

import streamlit as st

st.set_page_config(
    page_title="Malaysia Energy Model 2025-2050",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Malaysia Energy System Model 2025–2050")
st.markdown("""
Welcome to the **Malaysia Calliope Energy Model** dashboard.

This tool models long-term capacity expansion across Malaysia's three power grids:
**Peninsular Malaysia** (TNB), **Sabah** (SESB), and **Sarawak** (Sarawak Energy)
from 2025 to 2050, aligned with the **National Energy Transition Roadmap (NETR)**.

---

### How to use this tool

| Step | Page | Description |
|------|------|-------------|
| 1 | **Inputs** | Set demand growth, technology costs, fuel prices, carbon price, and RE targets |
| 2 | **Scenarios** | Choose a base scenario and configure optional overrides |
| 3 | **Run** | Launch the simulation and monitor progress |
| 4 | **Results** | Explore capacity mix, generation, costs, emissions, and battery KPIs |

Use the sidebar to navigate between pages.
""")

st.info(
    "Start on the **Inputs** page to configure your simulation parameters, "
    "then proceed through the steps above.",
    icon="ℹ️",
)

# Session state defaults
defaults = {
    "demand_growth": {"peninsular": 3.5, "sabah": 4.5, "sarawak": 4.0},
    "tech_costs": {
        "solar_utility": {"capex_usd_kw": 650, "opex_fixed_usd_kw_yr": 8, "opex_var_usd_mwh": 0},
        "wind_onshore": {"capex_usd_kw": 1300, "opex_fixed_usd_kw_yr": 30, "opex_var_usd_mwh": 0},
        "battery_storage": {"capex_usd_kw": 200, "opex_fixed_usd_kw_yr": 6, "opex_var_usd_mwh": 0},
        "gas_ccgt": {"capex_usd_kw": 900, "opex_fixed_usd_kw_yr": 25, "opex_var_usd_mwh": 3},
        "coal_existing": {"capex_usd_kw": 0, "opex_fixed_usd_kw_yr": 30, "opex_var_usd_mwh": 4},
    },
    "fuel_prices": {"gas_usd_gj": 8.0, "coal_usd_tonne": 90.0},
    "carbon_price_trajectory": "none",
    "re_targets": {2025: 31, 2030: 35, 2035: 40, 2040: 52, 2045: 62, 2050: 70},
    "selected_scenario": "netr_target",
    "regions_selected": ["peninsular", "sabah", "sarawak"],
    "toggles": {
        "early_coal_retirement": False,
        "enable_hvdc_2030": False,
        "hydrogen_peakers": False,
        "retire_diesel_2030": False,
    },
    "run_completed": False,
    "active_scenario_name": None,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

st.sidebar.success("Navigate using the pages above.")
