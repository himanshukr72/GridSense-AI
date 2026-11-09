# GridSense AI

**Agentic AI-Powered Electricity Supply Intelligence & Grid Stress Forecasting Platform**

GridSense AI combines five modules of time-series econometrics with forecasting, risk analysis, APIs, PostgreSQL, and an evidence-grounded agentic AI interface.

## Dataset
- Source: https://zenodo.org/records/14983362
- DOI: https://doi.org/10.5281/zenodo.14983362
- Title: *Daily electricity demand data for Indian states (2014–2024)*
- Authors: Kieran Hunt and Hannah Bloomfield.
- Electricity variables: `daily_energy_met_MU`, `peak_met_MW`, `peak_unmet_MW`.
- State weather files include daily meteorological measurements.

Use the corrected daily-energy and peak-met files recommended by the dataset authors, unless conducting your own QC. Preserve raw files unchanged. Do not commit raw data, secrets, database volumes, or large model artifacts. Check the record for licence/rights before redistributing data.

## Architecture
```text
Zenodo CSVs -> Audit/ETL -> PostgreSQL
                    |           |
                    v           v
            Five-module       FastAPI
            econometrics        |
                    |       LangGraph agents <-> RAG/Qdrant
                    v           |
             Forecast/risk      |
                    +-----------+
                         |
                    React UI
```

## Repository layout
- `configs/`: YAML configuration.
- `data/`: local raw, interim and processed data (Git-ignored).
- `notebooks/`: academic experiments organized by syllabus module.
- `src/gridsense/`: reusable data, econometrics, forecasting, risk, agents, RAG and database code.
- `backend/`: FastAPI.
- `frontend/`: React/Vite.
- `scripts/`: download, inspect, build and validate dataset.
- `tests/`: automated tests.
- `reports/`, `artifacts/`: generated outputs (mostly Git-ignored).

## Phase 1 — Setup (Windows PowerShell)
Requirements: Python 3.11, Git, Node.js 20+, Docker Desktop, VS Code.

```powershell
git clone https://github.com/<YOUR_GITHUB_USERNAME>/GridSense-AI.git
cd GridSense-AI
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
docker compose up -d postgres qdrant
pytest
uvicorn backend.main:app --reload
```
API docs: http://127.0.0.1:8000/docs

Frontend in a second terminal:
```powershell
cd frontend
npm install
npm run dev
```

If PowerShell blocks activation, use Command Prompt: `.venv\Scripts\activate.bat`.

## Phase 2 — Data engineering
Run these commands from the repository root:

```bash
python scripts/download_zenodo.py
python scripts/inspect_dataset.py
python scripts/build_dataset.py
python scripts/validate_dataset.py
```

1. Download all files listed by the Zenodo record API to `data/raw/zenodo/`.
2. Inspect `reports/data_audit/file_inventory.csv` and `schema_report.json`.
3. Check the actual column names, date coverage, file sizes, nulls and duplicates.
4. Build long-form electricity and weather data. The starter builder expects wide electricity files with date + state columns and one state weather CSV per state. If the audit shows a different schema, update the mappings before proceeding.
5. Review `state_coverage.csv`, `missingness_by_state.csv` and join coverage. Do not assume all states have equally complete electricity data.
6. Document the analytical sample separately for each method. Cointegration requires suitable integration orders and overlapping dates; GARCH needs an appropriate stationary input; spectral analysis needs consistently sampled data.

## Five-module research plan
| Module | Methods | Outputs |
|---|---|---|
| 1. Non-stationarity | DF, ADF, PP, seasonal unit-root/HEGY, ARIMA/SARIMA | Test tables, decomposition, forecasts |
| 2. Non-stationary regression | Engle–Granger, ECM, VAR, Johansen, VECM, Granger causality | Cointegration and adjustment results |
| 3. Structural breaks | Quandt–Andrews, Bai–Perron, Perron unit-root extension | Break dates and regime estimates |
| 4. Volatility | ARCH-LM, ARCH/GARCH, EGARCH, GJR/TGARCH, GARCH-M | Conditional variance and persistence |
| 5. Spectral analysis | Periodogram, spectral density, AR/MA/ARMA spectra | Dominant frequencies and periodicity |

State deterministic terms, lag selection, seasonal period, sample window and significance level for every test. Report diagnostics and limitations.

## Forecasting and AI safeguards
Use chronological splits or rolling-origin evaluation. Do not use realized future weather as a predictor unless it would have been available at forecast time. Define grid-stress indicators transparently and validate them against observed shortfall information; do not label arbitrary scores as failure probabilities.

The LangGraph assistant should call approved analytical tools and read-only, parameterized database queries. RAG is for dataset/methodology documentation; numerical results must come from analytical functions or stored results, not free-form LLM generation.

## Citation
Hunt, K., & Bloomfield, H. (2025). *Daily electricity demand data for Indian states (2014–2024)*. Zenodo. https://doi.org/10.5281/zenodo.14983362

## Status
- [x] Phase 1 scaffold
- [ ] Phase 2 data engineering
- [ ] Phase 3 five-module econometric research
- [ ] Phase 4 forecasting and risk
- [ ] Phase 5 backend/database
- [ ] Phase 6 RAG and agentic AI
- [ ] Phase 7 React dashboard
- [ ] Phase 8 deployment and CI/CD
