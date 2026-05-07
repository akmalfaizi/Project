# Malaysia Energy System Model 2025–2050

A **Calliope**-based long-term capacity expansion model covering Malaysia's three power grids:
**Peninsular Malaysia** (TNB), **Sabah** (SESB), and **Sarawak** (Sarawak Energy) — from 2025 to 2050.

Aligned with Malaysia's **National Energy Transition Roadmap (NETR)**:
31% RE by 2025 → 40% by 2035 → **70% RE by 2050**.

---

## Features

- Multi-region myopic rolling optimisation across 6 milestone years (2025–2050)
- Three physically separate grids modelled independently, with optional Sabah–Sarawak HVDC interconnector
- Streamlit dashboard for interactive scenario configuration, simulation launch, and results exploration
- Time-series clustering (24 representative days from 8,760 hourly timesteps) for tractable LP solves
- Technology cost learning curves sourced from IRENA 2023

---

## Project Structure

```
malaysia_calliope/
├── model/
│   ├── techs/           # Technology definitions (supply, storage, demand, transmission)
│   ├── locations/       # Regional node definitions (peninsular, sabah, sarawak)
│   ├── timeseries/      # Clustered hourly time-series CSVs
│   ├── scenarios/       # Scenario YAML overrides
│   └── overrides/       # Optional policy & cost overrides
├── scripts/
│   ├── fetch_data.py    # NASA POWER API + synthetic profile generation
│   ├── time_cluster.py  # K-means time clustering (24 representative days)
│   ├── build_model.py   # Assemble Calliope model per region + milestone year
│   ├── myopic_chain.py  # Myopic rolling optimisation chain
│   ├── run_parallel.py  # Parallel regional runs
│   ├── postprocess.py   # Post-processing: NetCDF → summary DataFrames
│   └── time_cluster.py  # Temporal aggregation utility
├── dashboard/
│   ├── app.py           # Streamlit entry point
│   ├── pages/           # Dashboard pages: Inputs, Scenarios, Run, Results, Data
│   └── utils/           # Chart helpers and config writers
├── data/
│   ├── raw/             # Raw input data (capacity, fuel prices, demand)
│   └── processed/       # Cleaned inputs ready for model ingestion
├── results/
│   ├── baseline/        # Baseline scenario outputs (NetCDF + JSON summaries)
│   └── netr_target/     # NETR-aligned scenario outputs
└── requirements.txt
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Install a solver

**GLPK** (free):
```bash
conda install -c conda-forge glpk
```

**HiGHS** (faster — recommended):
```bash
pip install highspy
```

### 3. Fetch and prepare input data

```bash
python scripts/fetch_data.py --no-nasa
python scripts/time_cluster.py
```

### 4. Run a scenario

```bash
python scripts/run_parallel.py --scenario baseline
python scripts/run_parallel.py --scenario netr_target
```

### 5. Launch the dashboard

```bash
streamlit run dashboard/app.py
```

---

## Scenarios

| Scenario | Description |
|----------|-------------|
| `baseline` | Business as usual. No new coal post-2030. Moderate RE growth. |
| `netr_target` | NETR-aligned. 70% RE by 2050. Coal phased out by 2040. Carbon price trajectory applied. |
| `accelerated_re` | Aggressive decarbonisation. Coal exits by 2035. 80%+ RE by 2050. |

---

## License

MIT License. See [LICENSE](LICENSE) for details.
