"""
Page 2 — Scenarios
Select base scenario, configure overrides/toggles, save as named scenario.
"""

import streamlit as st

st.set_page_config(page_title="Scenarios | Malaysia Energy Model", layout="wide")
st.title("Scenarios")
st.markdown("Choose a base scenario and configure optional overrides.")

# -------------------------------------------------------------------
# Base scenario selection
# -------------------------------------------------------------------
st.header("Base Scenario")

SCENARIO_DESCRIPTIONS = {
    "baseline": (
        "**Business as Usual** — No new coal post-2030. "
        "Moderate RE growth driven by economics. No carbon price. "
        "Coal retires at end of economic life."
    ),
    "netr_target": (
        "**NETR Target** — Aligned with Malaysia's National Energy Transition Roadmap. "
        "Coal phased out by 2040 (Peninsular) and 2045 (Sarawak). "
        "RE targets: 31% (2025) → 70% (2050). "
        "Carbon price trajectory applied."
    ),
    "accelerated_re": (
        "**Accelerated RE** — Aggressive low-carbon push. "
        "Coal phase-out by 2035. 80%+ RE by 2050. "
        "High carbon price. Maximum solar and storage deployment."
    ),
}

scenario_choice = st.radio(
    "Select base scenario",
    options=list(SCENARIO_DESCRIPTIONS.keys()),
    index=list(SCENARIO_DESCRIPTIONS.keys()).index(
        st.session_state.get("selected_scenario", "netr_target")
    ),
    format_func=lambda x: {
        "baseline": "Business as Usual",
        "netr_target": "NETR Target (Recommended)",
        "accelerated_re": "Accelerated RE",
    }[x],
    horizontal=True,
)
st.markdown(SCENARIO_DESCRIPTIONS[scenario_choice])
st.session_state["selected_scenario"] = scenario_choice

# -------------------------------------------------------------------
# Override toggles
# -------------------------------------------------------------------
st.header("Optional Overrides")
st.markdown("These toggles modify the base scenario.")

toggles = st.session_state.get("toggles", {})
col1, col2 = st.columns(2)

with col1:
    toggles["early_coal_retirement"] = st.toggle(
        "Early coal retirement (all coal retired by 2035)",
        value=toggles.get("early_coal_retirement", False),
        help="Forces coal capacity to zero in Peninsular and Sarawak by 2035 milestone year.",
    )
    toggles["enable_hvdc_2030"] = st.toggle(
        "Enable Sabah-Sarawak HVDC from 2030",
        value=toggles.get("enable_hvdc_2030", False),
        help="Allows the model to invest in the Sabah-Sarawak HVDC cable from 2030 (5 years earlier than default 2035).",
    )

with col2:
    toggles["hydrogen_peakers"] = st.toggle(
        "Enable hydrogen peakers from 2040",
        value=toggles.get("hydrogen_peakers", False),
        help="Adds hydrogen-fired gas turbines as a low-carbon peaking option from 2040 onwards. "
             "Uses the gas_ocgt tech with H2 fuel cost assumptions.",
    )
    toggles["retire_diesel_2030"] = st.toggle(
        "Phase out diesel generators by 2030",
        value=toggles.get("retire_diesel_2030", False),
        help="Forces diesel capacity to zero by 2030 in Sabah and Sarawak; "
             "replaced by solar+battery in remote areas.",
    )

st.session_state["toggles"] = toggles

# -------------------------------------------------------------------
# Save as named scenario
# -------------------------------------------------------------------
st.header("Save Scenario")
st.markdown("Save your current configuration (inputs + base scenario + overrides) as a named scenario.")

col_name, col_btn = st.columns([3, 1])
with col_name:
    scenario_name = st.text_input(
        "Scenario name",
        value=st.session_state.get("active_scenario_name") or f"My {scenario_choice.replace('_', ' ').title()}",
        placeholder="e.g. High Growth NETR",
    )
with col_btn:
    st.write("")  # spacing
    st.write("")
    if st.button("Save Scenario", type="primary"):
        from dashboard.utils.config_writer import (
            save_custom_scenario, demand_growth_from_ui,
            tech_costs_from_ui, carbon_price_from_ui, re_targets_from_ui,
        )
        try:
            saved_path = save_custom_scenario(
                name=scenario_name,
                base_scenario=scenario_choice,
                demand_growth=st.session_state.get("demand_growth", {}),
                tech_costs=tech_costs_from_ui(st.session_state.get("tech_costs", {})),
                carbon_price_trajectory=st.session_state.get("carbon_price_trajectory", "none"),
                re_targets=re_targets_from_ui(st.session_state.get("re_targets", {})),
                toggles=toggles,
            )
            st.session_state["active_scenario_name"] = scenario_name
            st.success(f"Scenario saved: `{saved_path.name}`")
        except Exception as e:
            st.error(f"Failed to save scenario: {e}")

# Show existing saved scenarios
from dashboard.utils.config_writer import list_saved_scenarios
saved = list_saved_scenarios()
if saved:
    st.markdown(f"**Saved scenarios:** {', '.join(f'`{s}`' for s in saved)}")

st.info("Once satisfied, proceed to the **Run** page to launch the simulation.")
