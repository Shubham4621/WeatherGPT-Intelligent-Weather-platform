# WeatherGPT

WeatherGPT is a conversational weather and climate information platform. The current repository contains a React/Vite frontend and a FastAPI backend, with provider-backed weather services, local IMD datasets, and source-labelled WeatherGPT analysis.

## Implemented capabilities

- Current conditions and operational forecasts from OpenWeatherMap (OWM).
- Natural-language chat with structured tools for supported current weather, forecast, warning, history, NWP, advisory, and agriculture questions. Ollama is the configured intent provider.
- Shared OWM location resolution for city searches and coordinate-aware data requests.
- Official IMD district warning lookup where verified district mappings and provider access are configured.
- Historical daily rainfall observations and climate analysis using the installed validated IMD rainfall extract and monthly IMD climatology.
- One-day WeatherGPT rainfall prediction using the existing model and validated rainfall dataset.
- NOAA/NCEP NOMADS GFS 0.25° point guidance through the NWP service.
- Weather GIS map with a base map and selected-location weather/model products.
- Deterministic, source-labelled weather-based agriculture guidance with local IMD station context where files are available.
- English, Hindi, and Marathi UI localization, plus browser speech input and output where supported.

The frontend includes Dashboard, Chat, Forecast, Alerts, Advisory, Historical, Climate Analysis, Rainfall Prediction, NWP, Weather Map, Agriculture, Aviation, Marine, and Settings views. Aviation and Marine currently explain that their data products are unavailable; they are not connected services.

## Keep the products distinct

| Product | Meaning and source |
| --- | --- |
| Official warnings | Warning facts from the official IMD district feed. A missing/unavailable lookup is not an all-clear. |
| Current observations and operational forecast | OWM observations and provider forecast, not IMD warnings or GFS output. |
| NWP guidance | NOAA/NCEP GFS model output with model run and valid times; not an observation, operational provider forecast, or warning. |
| Historical observations | Validated IMD gridded daily rainfall observations. Historical records are not forecasts. |
| Climatology | IMD 1991–2020 monthly normals. These are climatological normals, not observations. Rainfall is in mm; temperature normals are in °C. Native grid resolution varies by product. |
| Rainfall prediction | WeatherGPT model estimate from the installed validated rainfall dataset; not an IMD forecast or warning. |
| Advisory | WeatherGPT deterministic guidance based on available forecast/warning inputs; not an official warning or agency instruction. |

## Important coverage and access limits

- Historical daily observations currently cover one 0.25° rainfall grid cell near 21.00°N, 74.75°E, for 2013–2024. The supported named reference is Dhule; other locations return no data when outside the configured coverage distance.
- Validated daily Tmax/Tmin observations are not available. Historical temperature summaries, anomalies, and trends must not be inferred from climatology. Monthly Tmax/Tmin climatology is available independently on its native 0.5° grid.
- Historical trends are descriptive least-squares rainfall slopes over complete annual records, require at least eight years, and include no significance test.
- IMD warning lookup requires verified `IMD_DISTRICT_MAPPINGS` and accessible IMD feed data. A district without a verified mapping cannot be queried as an official warning location.
- GFS availability depends on NOMADS publication/network access and the installed ecCodes decoder. Map weather products are point data; no interpolated weather surface or warning polygon is implied. OpenStreetMap tiles require internet access and compliance with its tile policy.
- Station agriculture context uses local files under `data/raw/dhule_station/`; the service does not download live DSP data. The supplied observations are documented through 2025-12-31 and are stale for current conditions. Agriculture guidance is weather-based and uses heuristic rules, not crop/soil measurements or official agricultural advice.
- Aviation and Marine feeds are not integrated. OWM, Ollama, IMD, and NOMADS access depends on local configuration and external availability.
- `docker-compose.yml` starts only the backend. PostgreSQL/PostGIS and Redis are not configured production services. Production deployment, persistence, distributed caching, autoscaling, and operational monitoring remain deployment work.

## Run locally

Requirements: Python 3.11+ (3.12 recommended), Node.js/npm, an OWM API key for live provider weather/geocoding, and Ollama/model availability for natural-language chat.

Configure `backend/.env` from `backend/.env.example`; do not put provider secrets in frontend variables. Important settings include `WEATHER_API_KEY`, `LLM_PROVIDER`, `LLM_MODEL`, `LLM_BASE_URL`, and verified `IMD_DISTRICT_MAPPINGS` if official warnings are needed. Local file-backed history and climatology do not need provider credentials.

Start the API:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend in another terminal:

```powershell
cd frontend
npm install
npm run dev
```

The frontend defaults to `http://127.0.0.1:8000`; set `VITE_API_BASE_URL` only if the backend is hosted elsewhere. API docs are served at `/docs` and `/redoc`.

## Main APIs

- `GET /api/v1/weather/current`
- `GET /api/v1/weather/forecast`
- `POST /api/v1/chat`
- `GET /api/v1/weather/alerts`
- `GET /api/v1/location/resolve`
- `GET /api/v1/weather/history` (daily observations, monthly/annual analysis, comparisons, trends, and observed-month climatology/anomalies)
- `GET /api/v1/weather/climatology` (one month of IMD rainfall/Tmax/Tmin normals)
- `GET /api/v1/weather/rainfall-prediction`
- `GET /api/v1/weather/nwp`
- `GET /api/v1/weather/advisory`
- `POST /api/v1/agriculture/advice`
- `GET /api/v1/agriculture/stations/{station_id}/quality`

Historical requests accept `city` or `lat`/`lon` and require `start_date`/`end_date`. Climatology accepts a city or coordinates, a month, and an optional variable (`rainfall`, `tmax`, or `tmin`). Responses retain availability, provenance, coverage, grid selection, and limitations where applicable.

## Validation

Backend tests:

```powershell
cd backend
python -m pytest
```

Frontend tests and production build:

```powershell
cd frontend
npm test
npx tsc -b --pretty false
npm run build
```

Most provider-facing tests use deterministic fixtures. Passing tests do not establish live provider access or validate an external service at runtime.

## Data and documentation

Raw IMD data is treated as read-only. Validated derivatives and dataset catalogs live under `data/`; see the phase notes under `docs/` for source conventions, coverage, and validation limits. Phase 17 Climate Analysis details are in [docs/phase17-climate-analysis.md](docs/phase17-climate-analysis.md).
