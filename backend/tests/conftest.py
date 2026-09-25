"""Shared test fixtures for WeatherGPT."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Async test client that talks to the FastAPI app in-process."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# --- Sample OpenWeatherMap JSON used by multiple tests ---

SAMPLE_OWM_RESPONSE = {
    "coord": {"lon": 74.78, "lat": 20.9},
    "weather": [
        {
            "id": 800,
            "main": "Clear",
            "description": "clear sky",
            "icon": "01d",
        }
    ],
    "base": "stations",
    "main": {
        "temp": 33.5,
        "feels_like": 35.2,
        "temp_min": 32.0,
        "temp_max": 35.0,
        "pressure": 1008,
        "humidity": 55,
    },
    "visibility": 10000,
    "wind": {"speed": 4.1, "deg": 220, "gust": 7.5},
    "clouds": {"all": 5},
    "dt": 1695550000,
    "sys": {
        "country": "IN",
        "sunrise": 1695510000,
        "sunset": 1695553000,
    },
    "timezone": 19800,
    "id": 1273293,
    "name": "Dhule",
    "cod": 200,
}
