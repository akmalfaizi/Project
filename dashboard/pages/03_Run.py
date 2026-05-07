"""
Page 3 — Run
Launch simulation, show live progress bar and log stream.
"""

import subprocess
import sys
import time
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Run | Malaysia Energy Model", layout="wide")
st.title("Run Simulation")

PROJECT_ROOT = Path(__file__).parent.parent.parent

# -------------------------------------------------------------------
# Run summary
# -------------------------------------------------------------------
scenario = st.session_state.get("selected_scenario", "netr_target")
regions = st.session_state.get("regions_selected", ["peninsular", "sabah", "sarawak"])
demand_growth = st.session_state.get("demand_growth", {})
carbon_price = st.session_state.get("carbon_price_trajectory", "none")
re_targets = st.session_state.get("re_targets", {})

st.markdown("### Simulation Configuration")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Scenario", scenario.replace("_", " ").title())
    st.metric("Regions", ", ".join(r.title() for r in regions))
with col2:
    st.metric("Milestone years", "2025 → 2030 → 2035 → 2040 → 2045 → 2050")
    st.metric("Carbon price", carbon_price.title())
with col3:
    st.metric("Peninsular demand CAGR", f"{demand_growth.get('peninsular', 3.5):.1f}%")
    st.metric("Estimated runtime", "~60-90 min")

st.divider()

# -------------------------------------------------------------------
# Pre-run checks
# -------------------------------------------------------------------
st.markdown("### Pre-run Checks")
checks_passed = True

ts_dir = PROJECT_ROOT / "model" / "timeseries"
missing_ts = []
for region in regions:
    for ftype in ["demand", "solar_cf", "hydro_cf"]:
        f = ts_dir / f"{ftype}_{region}.csv"
        if not f.exists():
            missing_ts.append(str(f.name))

if missing_ts:
    st.warning(
        f"Missing time series files: {', '.join(missing_ts)}. "
        "Run `python scripts/fetch_data.py` then `python scripts/time_cluster.py` first."
    )
    checks_passed = False
    if st.button("Fetch & cluster data now", type="secondary"):
        with st.spinner("Fetching data from NASA POWER and synthesizing profiles..."):
            r1 = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "scripts" / "fetch_data.py"),
                 "--no-nasa"],  # Use synthetic solar for speed
                cwd=str(PROJECT_ROOT), capture_output=True, text=True
            )
            if r1.returncode == 0:
                r2 = subprocess.run(
                    [sys.executable, str(PROJECT_ROOT / "scripts" / "time_cluster.py")],
                    cwd=str(PROJECT_ROOT), capture_output=True, text=True
                )
                if r2.returncode == 0:
                    st.success("Data ready.")
                    st.rerun()
                else:
                    st.error(f"Clustering failed:\n{r2.stderr}")
            else:
                st.error(f"Fetch failed:\n{r1.stderr}")
else:
    st.success("All time series files found.")

# -------------------------------------------------------------------
# Launch button
# -------------------------------------------------------------------
st.divider()
st.markdown("### Launch Simulation")

if not checks_passed:
    st.info("Fix data issues above before running.")
else:
    col_run, col_stop = st.columns([2, 1])
    with col_run:
        run_clicked = st.button("Run Simulation", type="primary", use_container_width=True,
                                disabled=st.session_state.get("sim_running", False))
    with col_stop:
        stop_clicked = st.button("Stop", type="secondary",
                                 disabled=not st.session_state.get("sim_running", False))

    if stop_clicked and st.session_state.get("sim_proc"):
        st.session_state["sim_proc"].terminate()
        st.session_state["sim_running"] = False
        st.warning("Simulation stopped by user.")

    if run_clicked:
        st.session_state["sim_running"] = True
        st.session_state["run_completed"] = False

        # Build CLI args
        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "run_parallel.py"),
            "--scenario", scenario,
            "--regions", *regions,
        ]
        dg = demand_growth
        if dg.get("peninsular"):
            cmd += ["--demand-growth-peninsular", str(dg["peninsular"] / 100)]
        if dg.get("sabah"):
            cmd += ["--demand-growth-sabah", str(dg["sabah"] / 100)]
        if dg.get("sarawak"):
            cmd += ["--demand-growth-sarawak", str(dg["sarawak"] / 100)]

        proc = subprocess.Popen(
            cmd, cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        st.session_state["sim_proc"] = proc

        # Live log display
        log_box = st.empty()
        progress_bar = st.progress(0, text="Starting...")
        logs = []
        MILESTONE_YEARS = [2025, 2030, 2035, 2040, 2045, 2050]
        year_idx = 0

        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                logs.append(line.rstrip())
                log_box.text_area("Simulation log", "\n".join(logs[-60:]), height=300)
                # Update progress bar based on milestone years seen in log
                for i, yr in enumerate(MILESTONE_YEARS):
                    if str(yr) in line and i > year_idx:
                        year_idx = i
                        pct = (i + 1) / len(MILESTONE_YEARS)
                        progress_bar.progress(pct, text=f"Year {yr} ({i+1}/{len(MILESTONE_YEARS)})")

        return_code = proc.poll()
        st.session_state["sim_running"] = False

        if return_code == 0:
            progress_bar.progress(1.0, text="Complete!")
            st.session_state["run_completed"] = True
            st.session_state["active_scenario_name"] = scenario
            st.success("Simulation complete. Go to the **Results** page to explore outputs.")
            st.balloons()
        else:
            st.error(f"Simulation failed (exit code {return_code}). Check log above.")
