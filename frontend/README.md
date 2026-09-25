# WeatherGPT frontend — Phase 3

React + Vite + TypeScript dashboard and current-weather assistant, connected to the existing FastAPI service.

## Requirements

- Node.js 20 or newer
- Python environment for the backend
- `backend/.env` configured with `WEATHER_API_KEY` (the key stays on the backend)

## Setup and run

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

The frontend reads `VITE_API_BASE_URL` from its environment. The example points to `http://127.0.0.1:8000`; change it only if the FastAPI server uses another local address. Never put the OpenWeatherMap or LLM key in a `VITE_` variable.

In a separate terminal, start FastAPI:

```powershell
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open the Vite URL shown in its terminal (usually `http://localhost:5173`). The **Dashboard** retains the city search and current-weather cards. Select **Chat** to ask a question such as “What is the humidity in Dhule?” or choose one of the suggested prompts. The chat calls `POST /api/v1/chat`; the backend classifies intent with Ollama, calls the existing weather service for supported current-weather requests, and returns normalized facts with provider and observation time.

Run Ollama locally and pull the model configured in `backend/.env` (default `qwen3:4b`). See the root README for backend LLM configuration and chat API details. Forecasts, alerts, history, and unrelated questions are reported as unsupported; the chat does not invent their data.

## Build and tests

```powershell
npm run build
npm test
```
