"""
Page 4 — Results
Interactive visualization of simulation outputs.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Results | Malaysia Energy Model", layout="wide")
st.title("Results")

PROJECT_ROOT = Path(__file__).parent.parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"

available_scenarios = [d.name for d in RESULTS_DIR.iterdir() if d.is_dir()] if RESULTS_DIR.exists() else []

if not available_scenarios:
    st.warning("No results found. Run the simulation on the **Run** page first.")
    st.stop()

col_scen, col_region = st.columns([2, 2])
with col_scen:
    scenario = st.selectbox(
        "Scenario",
        options=available_scenarios,
        index=available_scenarios.index(st.session_state.get("selected_scenario", available_scenarios[0]))
        if st.session_state.get("selected_scenario") in available_scenarios else 0,
    )
with col_region:
    region_display = st.selectbox(
        "Region (for per-region charts)",
        options=["peninsular", "sabah", "sarawak"],
        format_func=lambda x: x.title(),
    )

import sys
sys.path.insert(0, str(PROJECT_ROOT))
from scripts.postprocess import load_scenario_results, get_diurnal_mix

@st.cache_data(show_spinner="Loading results...")
def load_results(scenario: str):
    return load_scenario_results(scenario)

results = load_results(scenario)

if not results or all(v["capacity_mix"].empty for v in results.values()):
    st.error(f"No data loaded for scenario '{scenario}'. Results files may be missing or corrupt.")
    st.stop()

tab_cap, tab_gen, tab_emit, tab_cost, tab_batt, tab_download = st.tabs([
    "Capacity Mix", "Generation Mix", "Emissions", "Costs", "Battery KPIs", "Download"
])

from dashboard.utils.charts import (
    capacity_mix_chart, generation_mix_chart, emissions_chart,
    cost_breakdown_chart, curtailment_chart, battery_kpi_chart, re_share_chart,
    diurnal_mix_chart,
)

with tab_cap:
    st.subheader(f"Installed Capacity — {region_display.title()}")
    cap_df = results.get(region_display, {}).get("capacity_mix", pd.DataFrame())
    st.plotly_chart(capacity_mix_chart(cap_df, region_display), use_container_width=True)

    st.subheader("All Regions — Capacity Summary (GW)")
    summary_rows = []
    for r in ["peninsular", "sabah", "sarawak"]:
        c = results.get(r, {}).get("capacity_mix", pd.DataFrame())
        if not c.empty:
            total = c.sum(axis=1) / 1000
            for yr in total.index:
                summary_rows.append({"Region": r.title(), "Year": yr, "Total Capacity (GW)": round(total[yr], 1)})
    if summary_rows:
        st.dataframe(pd.DataFrame(summary_rows).pivot(index="Year", columns="Region", values="Total Capacity (GW)"))

with tab_gen:
    col_gen1, col_gen2 = st.columns(2)
    with col_gen1:
        gen_df = results.get(region_display, {}).get("generation_mix", pd.DataFrame())
        st.plotly_chart(generation_mix_chart(gen_df, region_display), use_container_width=True)
    with col_gen2:
        gen_all = {r: results.get(r, {}).get("generation_mix", pd.DataFrame()) for r in ["peninsular", "sabah", "sarawak"]}
        st.plotly_chart(re_share_chart(gen_all, scenario), use_container_width=True)

    curt_all = {r: results.get(r, {}).get("curtailment", pd.Series(dtype=float)) for r in ["peninsular", "sabah", "sarawak"]}
    st.plotly_chart(curtailment_chart(curt_all), use_container_width=True)

    st.subheader(f"Diurnal Generation Profile — {region_display.title()}")
    diurnal_year = st.select_slider("Select milestone year", options=[2025, 2030, 2035, 2040, 2045, 2050], value=2030, key="diurnal_year")
    diurnal_df = get_diurnal_mix(scenario, region_display, diurnal_year)
    st.plotly_chart(diurnal_mix_chart(diurnal_df, region_display, diurnal_year), use_container_width=True)

with tab_emit:
    em_all = {r: results.get(r, {}).get("emissions", pd.Series(dtype=float)) for r in ["peninsular", "sabah", "sarawak"]}
    st.plotly_chart(emissions_chart(em_all, scenario), use_container_width=True)
    em_df = pd.DataFrame(em_all).rename(columns=str.title)
    if not em_df.empty:
        em_df["Total"] = em_df.sum(axis=1)
        em_df.index.name = "Year"
        st.dataframe(em_df.round(1))

with tab_cost:
    cost_df = results.get(region_display, {}).get("system_cost", pd.DataFrame())
    st.plotly_chart(cost_breakdown_chart(cost_df, region_display), use_container_width=True)
    gen_df = results.get(region_display, {}).get("generation_mix", pd.DataFrame())
    if not cost_df.empty and not gen_df.empty:
        total_cost = cost_df.sum(axis=1)
        total_gen = gen_df.sum(axis=1)
        lcoe = (total_cost * 1e6) / (total_gen * 1e6)
        lcoe_df = pd.DataFrame({"LCOE (USD/MWh)": lcoe.round(1)})
        st.markdown(f"**System LCOE — {region_display.title()}**")
        st.line_chart(lcoe_df)

with tab_batt:
    st.subheader(f"Battery Storage KPIs — {region_display.title()}")
    batt_df = results.get(region_display, {}).get("battery_kpis", pd.DataFrame())
    st.plotly_chart(battery_kpi_chart(batt_df, region_display), use_container_width=True)
    if not batt_df.empty:
        st.dataframe(batt_df.round(2))
    else:
        st.info("Battery KPI data not available (battery may not have been deployed).")

with tab_download:
    st.subheader("Download Results")
    for r in ["peninsular", "sabah", "sarawak"]:
        res = results.get(r, {})
        cap = res.get("capacity_mix", pd.DataFrame())
        gen = res.get("generation_mix", pd.DataFrame())
        em = res.get("emissions", pd.Series(dtype=float))
        if not cap.empty:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.download_button(f"Capacity mix ({r.title()})", data=cap.to_csv().encode(), file_name=f"{scenario}_{r}_capacity.csv", mime="text/csv")
            with col2:
                st.download_button(f"Generation mix ({r.title()})", data=gen.to_csv().encode(), file_name=f"{scenario}_{r}_generation.csv", mime="text/csv")
            with col3:
                st.download_button(f"Emissions ({r.title()})", data=em.to_frame("emissions_MtCO2").to_csv().encode(), file_name=f"{scenario}_{r}_emissions.csv", mime="text/csv")
    st.markdown("---")
    st.info("NetCDF result files (full model output) are stored in `results/{scenario}/` directory.")
