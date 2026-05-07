"""
Page 1 — Inputs
User sets: demand growth, technology costs, fuel prices, carbon price, RE targets
"""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Inputs | Malaysia Energy Model", layout="wide")
st.title("Model Inputs")
st.markdown("Configure the key parameters for your simulation. Changes here apply to all scenarios.")

# -------------------------------------------------------------------
# Section 1: Region selector
# -------------------------------------------------------------------
st.header("1. Regions")
regions_all = ["peninsular", "sabah", "sarawak"]
region_labels = {"peninsular": "Peninsular Malaysia (TNB)", "sabah": "Sabah (SESB)",
                 "sarawak": "Sarawak (Sarawak Energy)"}

selected = []
cols = st.columns(3)
for i, r in enumerate(regions_all):
    with cols[i]:
        if st.checkbox(region_labels[r], value=(r in st.session_state.get("regions_selected", regions_all))):
            selected.append(r)

st.session_state["regions_selected"] = selected if selected else regions_all

# -------------------------------------------------------------------
# Section 2: Demand growth
# -------------------------------------------------------------------
st.header("2. Demand Growth Rate (% CAGR, 2025–2050)")
st.markdown("Annual compound growth in electricity consumption per region.")

dg = st.session_state.get("demand_growth", {"peninsular": 3.5, "sabah": 4.5, "sarawak": 4.0})
col1, col2, col3 = st.columns(3)
with col1:
    dg["peninsular"] = st.slider("Peninsular Malaysia", 1.0, 7.0, dg["peninsular"], 0.1, format="%.1f%%")
with col2:
    dg["sabah"] = st.slider("Sabah", 1.0, 8.0, dg["sabah"], 0.1, format="%.1f%%")
with col3:
    dg["sarawak"] = st.slider("Sarawak", 1.0, 8.0, dg["sarawak"], 0.1, format="%.1f%%")
st.session_state["demand_growth"] = dg

# -------------------------------------------------------------------
# Section 3: Technology costs
# -------------------------------------------------------------------
st.header("3. Technology Capital Costs (USD/kW)")
st.markdown("CAPEX for new capacity investment. Defaults from IRENA 2023.")

cost_defaults = st.session_state.get("tech_costs", {})
cost_rows = {
    "solar_utility": "Utility Solar PV",
    "wind_onshore": "Onshore Wind",
    "battery_storage": "Battery Storage (per kW power)",
    "gas_ccgt": "Gas CCGT",
    "coal_existing": "Coal (existing, no new CAPEX)",
    "hydro_ror": "Run-of-River Hydro",
    "biomass_plant": "Biomass",
}

st.markdown("**CAPEX (USD/kW)**")
capex_cols = st.columns(4)
updated_costs = dict(cost_defaults)
tech_list = list(cost_rows.keys())
for i, tech in enumerate(tech_list):
    col = capex_cols[i % 4]
    default_capex = cost_defaults.get(tech, {}).get("capex_usd_kw", 0)
    with col:
        capex = st.number_input(
            cost_rows[tech], min_value=0, max_value=10000,
            value=int(default_capex), step=50, key=f"capex_{tech}"
        )
        if tech not in updated_costs:
            updated_costs[tech] = {}
        updated_costs[tech]["capex_usd_kw"] = capex

st.session_state["tech_costs"] = updated_costs

# -------------------------------------------------------------------
# Section 4: Fuel prices
# -------------------------------------------------------------------
st.header("4. Fuel Prices")
fp = st.session_state.get("fuel_prices", {"gas_usd_gj": 8.0, "coal_usd_tonne": 90.0})
col1, col2 = st.columns(2)
with col1:
    fp["gas_usd_gj"] = st.number_input("Natural gas (USD/GJ)", 3.0, 25.0, fp["gas_usd_gj"], 0.5)
with col2:
    fp["coal_usd_tonne"] = st.number_input("Coal (USD/tonne)", 40.0, 200.0, fp["coal_usd_tonne"], 5.0)
st.session_state["fuel_prices"] = fp

# -------------------------------------------------------------------
# Section 5: Carbon price
# -------------------------------------------------------------------
st.header("5. Carbon Price Trajectory")
st.markdown("Sets a shadow price on CO2 emissions to incentivise low-carbon technologies.")

carbon_preset = st.selectbox(
    "Carbon price level",
    options=["none", "low", "medium", "high", "custom"],
    index=["none", "low", "medium", "high", "custom"].index(
        st.session_state.get("carbon_price_trajectory", "none")
    ),
    format_func=lambda x: {
        "none": "None (0 USD/tCO2)",
        "low": "Low (~10 USD/tCO2 rising to 30 by 2050)",
        "medium": "Medium (~30 USD/tCO2 rising to 80 by 2050)",
        "high": "High (~50 USD/tCO2 rising to 150 by 2050)",
        "custom": "Custom",
    }[x]
)
st.session_state["carbon_price_trajectory"] = carbon_preset

if carbon_preset == "custom":
    custom_cp = st.number_input("Carbon price in 2025 (USD/tCO2)", 0, 300, 30, 5)
    st.session_state["carbon_price_custom"] = custom_cp

# -------------------------------------------------------------------
# Section 6: RE targets
# -------------------------------------------------------------------
st.header("6. Renewable Energy Share Targets (%)")
st.markdown(
    "Minimum RE share (% of **total installed capacity**) enforced per milestone year. "
    "Defaults follow Malaysia's NETR targets (31% in 2025 → 70% by 2050)."
)

re_defaults = st.session_state.get("re_targets", {2025: 31, 2030: 35, 2035: 40, 2040: 52, 2045: 62, 2050: 70})
years = [2025, 2030, 2035, 2040, 2045, 2050]
re_cols = st.columns(6)
re_updated = {}
for i, yr in enumerate(years):
    with re_cols[i]:
        val = st.number_input(str(yr), 0, 100, re_defaults.get(yr, 0), 1, key=f"re_{yr}")
        re_updated[yr] = val
st.session_state["re_targets"] = re_updated

# Validation
re_values = list(re_updated.values())
if any(re_values[i] > re_values[i+1] for i in range(len(re_values)-1) if re_values[i+1] > 0):
    st.warning("RE targets should be non-decreasing over time.")

st.success("Inputs saved. Proceed to the **Scenarios** page.")
