"""
charts.py
---------
Plotly figure builders for the Results dashboard page.
"""

from typing import Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

NETR_RE_TARGETS = {2025: 31, 2030: 35, 2035: 40, 2040: 52, 2045: 62, 2050: 70}

_LAYOUT = dict(plot_bgcolor="#1e2130", paper_bgcolor="#1e2130", font=dict(color="#e0e0e0"))
_GRID = dict(gridcolor="#2e3450", zerolinecolor="#2e3450")

TECH_COLORS = {
    "coal_existing": "#3d3d3d", "coal_new": "#666666", "gas_ccgt": "#e8734a",
    "gas_ocgt": "#f0a070", "diesel_genset": "#a05000", "solar_utility": "#f5c518",
    "solar_rooftop": "#ffd700", "wind_onshore": "#8bc34a", "hydro_large_existing": "#1a6bb5",
    "hydro_ror": "#2a9bd4", "biomass_plant": "#4caf50", "battery_storage": "#9c27b0",
    "hvdc_sabah_sarawak": "#ff5722",
}

TECH_LABELS = {
    "coal_existing": "Coal (existing)", "coal_new": "Coal (new)", "gas_ccgt": "Gas CCGT",
    "gas_ocgt": "Gas OCGT", "diesel_genset": "Diesel", "solar_utility": "Solar (utility)",
    "solar_rooftop": "Solar (rooftop)", "wind_onshore": "Wind", "hydro_large_existing": "Hydro (existing)",
    "hydro_ror": "Hydro (RoR)", "biomass_plant": "Biomass", "battery_storage": "Battery",
    "hvdc_sabah_sarawak": "HVDC cable",
}


def capacity_mix_chart(capacity_df: pd.DataFrame, region: str, title_suffix: str = "") -> go.Figure:
    fig = go.Figure()
    if capacity_df.empty:
        return _empty_chart("No capacity data available")
    cap_gw = capacity_df / 1000
    supply_techs = [t for t in cap_gw.columns if t != "demand_electricity" and cap_gw[t].sum() > 0.01]
    for tech in supply_techs:
        fig.add_trace(go.Bar(name=TECH_LABELS.get(tech, tech), x=cap_gw.index.astype(str), y=cap_gw[tech],
                             marker_color=TECH_COLORS.get(tech, "#888888"), hovertemplate="%{y:.1f} GW<extra>%{fullData.name}</extra>"))
    if "demand_electricity" in cap_gw.columns:
        fig.add_trace(go.Scatter(name="Peak Demand", x=cap_gw.index.astype(str), y=cap_gw["demand_electricity"],
                                 mode="lines+markers", line=dict(color="#ff4444", width=2, dash="dash"), marker=dict(size=7)))
    fig.update_layout(barmode="stack", title=f"Installed Capacity — {region.title()} {title_suffix}",
                      xaxis_title="Year", yaxis_title="Capacity (GW)", legend=dict(orientation="h", y=-0.2), height=420, **_LAYOUT)
    fig.update_xaxes(**_GRID); fig.update_yaxes(**_GRID)
    return fig


def generation_mix_chart(generation_df: pd.DataFrame, region: str) -> go.Figure:
    if generation_df.empty:
        return _empty_chart("No generation data available")
    fig = go.Figure()
    techs = [t for t in generation_df.columns if generation_df[t].sum() > 0.001]
    for tech in techs:
        fig.add_trace(go.Scatter(name=TECH_LABELS.get(tech, tech), x=generation_df.index.astype(str),
                                 y=generation_df[tech], mode="lines", stackgroup="one",
                                 fillcolor=TECH_COLORS.get(tech, "#888888"), line=dict(width=0.5, color=TECH_COLORS.get(tech, "#888888"))))
    fig.update_layout(title=f"Annual Generation Mix — {region.title()}", xaxis_title="Year",
                      yaxis_title="Generation (TWh)", legend=dict(orientation="h", y=-0.2), height=420, **_LAYOUT)
    fig.update_xaxes(**_GRID); fig.update_yaxes(**_GRID)
    return fig


def emissions_chart(emissions_by_region: dict, scenario: str, show_netr_target: bool = True) -> go.Figure:
    fig = go.Figure()
    colors = {"peninsular": "#e74c3c", "sabah": "#3498db", "sarawak": "#2ecc71"}
    total = None
    for region, em_series in emissions_by_region.items():
        if em_series.empty:
            continue
        fig.add_trace(go.Scatter(name=region.title(), x=em_series.index.astype(str), y=em_series.values,
                                 mode="lines+markers", line=dict(color=colors.get(region, "#888"), width=2)))
        total = em_series if total is None else total.add(em_series, fill_value=0)
    if total is not None:
        fig.add_trace(go.Scatter(name="Total Malaysia", x=total.index.astype(str), y=total.values,
                                 mode="lines+markers", line=dict(color="#2c3e50", width=3)))
    if show_netr_target:
        fig.add_trace(go.Scatter(name="NETR Pathway Target", x=[str(y) for y in [2025,2030,2035,2040,2045,2050]],
                                 y=[120,100,80,55,30,10], mode="lines", line=dict(color="#e67e22", width=2, dash="dot")))
    fig.update_layout(title=f"CO2 Emissions Trajectory — {scenario.replace('_',' ').title()}",
                      xaxis_title="Year", yaxis_title="CO2 Emissions (Mt CO2)",
                      legend=dict(orientation="h", y=-0.2), height=400, **_LAYOUT)
    fig.update_xaxes(**_GRID); fig.update_yaxes(**_GRID)
    return fig


def cost_breakdown_chart(cost_df: pd.DataFrame, region: str) -> go.Figure:
    if cost_df.empty:
        return _empty_chart("No cost data available")
    fig = go.Figure()
    cost_colors = {"capex_annualised": "#2980b9", "opex_fixed": "#8e44ad", "opex_variable": "#e74c3c", "fuel": "#e67e22"}
    for col in cost_df.columns:
        fig.add_trace(go.Bar(name=col.replace("_", " ").title(), x=cost_df.index.astype(str),
                             y=cost_df[col], marker_color=cost_colors.get(col, "#888")))
    fig.update_layout(barmode="stack", title=f"System Cost Breakdown — {region.title()} (M USD/year)",
                      xaxis_title="Year", yaxis_title="Cost (M USD/year)",
                      legend=dict(orientation="h", y=-0.2), height=400, **_LAYOUT)
    fig.update_xaxes(**_GRID); fig.update_yaxes(**_GRID)
    return fig


def curtailment_chart(curtailment_by_region: dict) -> go.Figure:
    fig = go.Figure()
    colors = {"peninsular": "#e74c3c", "sabah": "#3498db", "sarawak": "#2ecc71"}
    for region, series in curtailment_by_region.items():
        if series.empty:
            continue
        fig.add_trace(go.Scatter(name=region.title(), x=series.index.astype(str), y=series.values,
                                 mode="lines+markers", line=dict(color=colors.get(region, "#888"), width=2)))
    fig.update_layout(title="Renewable Curtailment (%)", xaxis_title="Year", yaxis_title="Curtailment (%)", height=350, **_LAYOUT)
    fig.update_xaxes(**_GRID); fig.update_yaxes(**_GRID)
    return fig


def battery_kpi_chart(kpi_df: pd.DataFrame, region: str) -> go.Figure:
    if kpi_df.empty:
        return _empty_chart(f"No battery data for {region.title()}")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if "installed_mw" in kpi_df.columns:
        fig.add_trace(go.Bar(name="Installed Capacity (GW)", x=kpi_df.index.astype(str),
                             y=kpi_df["installed_mw"] / 1000, marker_color="#9c27b0", opacity=0.6), secondary_y=False)
    if "cycles_per_year" in kpi_df.columns:
        fig.add_trace(go.Scatter(name="Cycles/year", x=kpi_df.index.astype(str), y=kpi_df["cycles_per_year"],
                                 mode="lines+markers", line=dict(color="#ff5722", width=2)), secondary_y=True)
    if "avg_soc" in kpi_df.columns:
        fig.add_trace(go.Scatter(name="Avg SoC", x=kpi_df.index.astype(str), y=kpi_df["avg_soc"] * 100,
                                 mode="lines+markers", line=dict(color="#3498db", width=2, dash="dot")), secondary_y=True)
    fig.update_layout(title=f"Battery Storage KPIs — {region.title()}", height=380,
                      legend=dict(orientation="h", y=-0.2), **_LAYOUT)
    fig.update_xaxes(**_GRID)
    fig.update_yaxes(title_text="Capacity (GW)", secondary_y=False, **_GRID)
    fig.update_yaxes(title_text="Cycles / SoC (%)", secondary_y=True, **_GRID)
    return fig


def re_share_chart(generation_by_region: dict, scenario: str) -> go.Figure:
    RE_TECHS = {"solar_utility", "solar_rooftop", "wind_onshore", "hydro_large_existing", "hydro_ror", "biomass_plant"}
    fig = go.Figure()
    colors = {"peninsular": "#e74c3c", "sabah": "#3498db", "sarawak": "#2ecc71"}
    for region, gen_df in generation_by_region.items():
        if gen_df.empty:
            continue
        total = gen_df.sum(axis=1)
        re_total = gen_df[[c for c in gen_df.columns if c in RE_TECHS]].sum(axis=1)
        re_pct = (re_total / total * 100).fillna(0)
        fig.add_trace(go.Scatter(name=region.title(), x=re_pct.index.astype(str), y=re_pct.values,
                                 mode="lines+markers", line=dict(color=colors.get(region, "#888"), width=2)))
    fig.add_trace(go.Scatter(name="NETR Target", x=[str(y) for y in NETR_RE_TARGETS], y=list(NETR_RE_TARGETS.values()),
                             mode="lines", line=dict(color="#e67e22", width=2, dash="dot")))
    fig.update_layout(title=f"RE Share (%) vs NETR Target — {scenario.replace('_',' ').title()}",
                      xaxis_title="Year", yaxis_title="RE Share (%)", yaxis=dict(range=[0, 100]),
                      height=380, **_LAYOUT)
    fig.update_xaxes(**_GRID); fig.update_yaxes(**_GRID)
    return fig


def diurnal_mix_chart(diurnal_df: pd.DataFrame, region: str, year: int) -> go.Figure:
    if diurnal_df.empty:
        return _empty_chart(f"No diurnal data for {region.title()} {year}")
    fig = go.Figure()
    techs = [t for t in diurnal_df.columns if t != "demand_electricity" and diurnal_df[t].sum() > 0.01]
    hours = [f"{h:02d}:00" for h in diurnal_df.index]
    for tech in techs:
        fig.add_trace(go.Scatter(name=TECH_LABELS.get(tech, tech), x=hours, y=diurnal_df[tech], mode="lines",
                                 stackgroup="one", fillcolor=TECH_COLORS.get(tech, "#888888"),
                                 line=dict(width=0.5, color=TECH_COLORS.get(tech, "#888888"))))
    if "demand_electricity" in diurnal_df.columns:
        fig.add_trace(go.Scatter(name="Demand", x=hours, y=diurnal_df["demand_electricity"], mode="lines",
                                 line=dict(color="#ff4444", width=2, dash="dash")))
    fig.update_layout(title=f"Diurnal Generation Mix — {region.title()} {year} (avg. representative day)",
                      xaxis_title="Hour of Day", yaxis_title="Generation (MW)",
                      legend=dict(orientation="h", y=-0.25), height=420, **_LAYOUT)
    fig.update_xaxes(**_GRID); fig.update_yaxes(**_GRID)
    return fig


def _empty_chart(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False, font=dict(size=16, color="#888"))
    fig.update_layout(height=300)
    return fig
