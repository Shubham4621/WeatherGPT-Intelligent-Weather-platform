<<<<<<< HEAD
# WeatherGPT — AI-Powered Multilingual Weather Intelligence Platform

> **Phase 1 — Backend Foundation**

WeatherGPT is an intelligent conversational weather platform that provides
contextual weather intelligence through natural-language interaction.

---

## Technology Stack

| Layer | Technology |
| -------- | --------------------------------- |
| Backend | Python 3.12, FastAPI, Pydantic |
| Weather | OpenWeatherMap API |
| Database | PostgreSQL + PostGIS *(future)* |
| Cache | Redis *(future)* |
| Frontend | React + Vite + TypeScript *(future)* |
| AI (Phase 3) | Ollama intent extraction with a provider abstraction |
| Deploy | Docker, Docker Compose |

---

## Phase 1 Architecture

```
Client (curl / browser / Swagger)
 │
 ▼
FastAPI Backend (:8000)
 │
 ├── /health — health check
 ├── /api/v1/weather/current — current weather
 │
 ▼
OpenWeatherMap API
 │
 ▼
Normalized JSON response
```

---

## Quick Start

### Prerequisites

- Python 3.11+ (3.12 recommended)
- An [OpenWeatherMap API key](https://openweathermap.org/api) (free tier works)

### 1. Clone & enter the project

```bash
git clone <repo-url>
cd WeatherGPT
```

### 2. Create a virtual environment

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env and add your WEATHER_API_KEY
```

OpenWeatherMap's Current Weather API is used at
`https://api.openweathermap.org/data/2.5/weather`. City lookup uses `q`,
coordinate lookup uses `lat` and `lon`, the API key is sent as `appid`, and
`units=metric` returns Celsius and metres/second. Its free plan currently lists
60 calls/minute and 1,000,000 calls/month; account limits and pricing can change.
See the [Current Weather API documentation](https://openweathermap.org/api/current)
and [pricing page](https://openweathermap.org/price).

### 5. Start the backend

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API is now running at **http://localhost:8000**.

---

## Docker

```bash
# From project root
cd backend
cp .env.example .env      # edit .env with your API key
cd ..
docker-compose up --build
```

---

## Environment Variables

| Variable | Required | Description |
| ---------------------- | -------- | ----------------------------------- |
| `WEATHER_API_KEY` | **Yes** | OpenWeatherMap API key |
| `WEATHER_API_BASE_URL` | No | Provider base URL (has default) |
| `ENVIRONMENT` | No | `development` / `production` |
| `WEATHERGPT_DEBUG` | No | Application debug flag (`true` / `false`); generic shell `DEBUG` values are ignored |
| `DATABASE_URL` | No | PostgreSQL connection string *(future)* |
| `REDIS_URL` | No | Redis connection string *(future)* |
| `LLM_API_KEY` | No | LLM provider key *(future)* |

---

## API Endpoints

### Health

| Method | URL | Description |
| ------ | --------- | ------------- |
| GET | `/` | Root / status |
| GET | `/health` | Health check |

### Weather

| Method | URL | Description |
| ------ | ------------------------------ | ---------------------- |
| GET | `/api/v1/weather/current` | Current weather |

---

## API Usage Examples

### GET `/api/v1/weather/current`

**By city name:**

```bash
curl "http://localhost:8000/api/v1/weather/current?city=Dhule"
```

**By coordinates:**

```bash
curl "http://localhost:8000/api/v1/weather/current?lat=20.9&lon=74.78"
```

**Example response:**

```json
{
  "location": {
    "name": "Dhule",
    "country": "IN",
    "latitude": 20.9,
    "longitude": 74.78
  },
  "weather": {
    "temperature": 33.5,
    "feels_like": 35.2,
    "temp_min": 32.0,
    "temp_max": 35.0,
    "humidity": 55,
    "pressure": 1008,
    "wind_speed": 4.1,
    "wind_direction": 220,
    "wind_gust": 7.5,
    "visibility": 10000,
    "cloudiness": 5,
    "description": "clear sky",
    "icon": "01d"
  },
  "sun": {
    "sunrise": "2023-09-24T01:00:00Z",
    "sunset": "2023-09-24T12:56:40Z"
  },
  "source": "OpenWeatherMap",
  "observed_at": "2023-09-24T12:06:40Z"
}
```

**Error response (missing location):**

```json
{
  "error": "Provide either 'city' or both 'lat' and 'lon' query parameters.",
  "type": "weather_api_error"
}
```

---

## Interactive Documentation

Once the server is running:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## Running Tests

```bash
cd backend
pip install -r requirements.txt   # if not already installed
pytest -v
```

Tests use mocked HTTP responses by default, so they run without a live API key.
The Phase 1 integration test is mocked in this workspace because no
`WEATHER_API_KEY` was configured; run a live request with your key using the
example above.

---

## Project Structure

```
weathergpt/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── api/routes/
│   │   │   ├── health.py        # Health-check endpoints
│   │   │   └── weather.py       # Weather API endpoints
│   │   ├── core/
│   │   │   ├── config.py        # Pydantic Settings
│   │   │   ├── exceptions.py    # Custom exceptions
│   │   │   └── logging.py       # Structured JSON logging
│   │   ├── schemas/
│   │   │   └── weather.py       # Response models
│   │   ├── services/
│   │   │   └── weather_service.py  # Weather provider integration
│   │   ├── models/              # DB models (future)
│   │   ├── tools/               # AI tools (future)
│   │   ├── agents/              # LangGraph agents (future)
│   │   └── db/                  # Database layer (future)
│   ├── tests/
│   │   ├── conftest.py          # Shared fixtures
│   │   ├── test_health.py       # Health endpoint tests
│   │   ├── test_weather.py      # Weather endpoint tests
│   │   └── test_weather_service.py  # Service-layer tests
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── pytest.ini
│   └── .env.example
├── frontend/                    # React app (future)
├── data/                        # Data files (future)
├── docs/                        # Documentation (future)
├── docker-compose.yml
├── .gitignore
└── README.md
```

---

## License

TBD

---

## Phase 3 — AI Weather Intelligence

The existing current-weather dashboard remains the default view. Use **Chat** in the header to ask a natural-language current-weather question. The chat intent service classifies the request and city, the weather tool delegates to the existing `WeatherService`, and answers containing measurements are composed only from the normalized provider response. Unsupported forecast, alerts, history, climate, and map requests are identified as unavailable; no future-phase data is fabricated.

```text
React chat → POST /api/v1/chat → intent LLM → get_current_weather tool
    → existing WeatherService → OpenWeatherMap → normalized observation
    → grounded response
```

The LLM provider is isolated behind `LLMService`; Ollama is the Phase 3 adapter. The LLM extracts intent, city, and requested metric only. It does not generate weather facts or call the weather provider. This keeps measurements grounded even if model output is incorrect. The small orchestration is explicit rather than using LangGraph: this phase has one tool and two routing outcomes, so a graph would add setup without adding a useful branch or state transition. Additional tools can be added behind the agent/tool interfaces later.

### Configure the LLM

Install and run Ollama separately, then pull the configured model (the example uses `qwen3:4b`). Copy `backend/.env.example` to `backend/.env` if you have not already, and configure:

```dotenv
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:4b
LLM_BASE_URL=http://127.0.0.1:11434
LLM_TIMEOUT=45
LLM_API_KEY=
```

With Ollama installed and running, fetch the model once:

```sh
ollama pull qwen3:4b
```

`LLM_API_KEY` is optional for local Ollama. Do not put provider keys in frontend variables. The backend returns a controlled service error when Ollama is unavailable or produces an invalid intent response.

### Run the Phase 3 application

Start the backend and frontend in separate terminals:

```powershell
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```powershell
cd frontend
npm install
npm run dev
```

The frontend uses `VITE_API_BASE_URL` (default `http://127.0.0.1:8000`). The weather provider key stays in the backend environment.

### Chat API

`POST /api/v1/chat`

```json
{"message":"What is the weather in Dhule right now?"}
```

Weather response includes a grounded answer, intent, location, source, tool name, observation time, and normalized weather fields. For example questions:

- What is the weather in Dhule right now?
- How hot is it in Nashik?
- What is the humidity in Mumbai?
- Is it cloudy in Dhule right now?
- Give me a 7 day forecast. *(gracefully reported as not available)*

### Phase 3 validation

```powershell
cd backend
pytest
cd ../frontend
npm test
npm run build
```

Chat history is kept only in page memory and can be cleared. Current weather is the only supported data tool. There is no LangGraph, forecast, alerts, persistence, authentication, or other future-phase functionality in this release.
=======
# WeatherGPT-Intelligent-Weather-platform
AI-powered conversational weather platform providing real-time weather, forecasts, alerts, climate insights, and location-based decision support through natural language.

## Phase 8: Historical Weather

Historical observations use an independent provider interface and the API
`GET /api/v1/weather/history?city=Dhule&start_date=2025-07-01&end_date=2025-07-31`.
No historical provider is configured, so requests explicitly return
`status: unavailable`; forecast or current-weather data is never substituted.
See [Phase 8 historical weather documentation](docs/phase8-historical-weather.md)
for supported fields, aggregation and comparison rules, and provider limitations.
>>>>>>> b564e5608355f49e674299776f602fe9da06b647
