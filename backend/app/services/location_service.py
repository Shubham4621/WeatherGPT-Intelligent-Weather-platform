"""Shared, coordinate-first location resolution for weather products."""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ResolvedLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    city: str | None = None
    district: str | None = None
    state: str | None = None
    country: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str | None = None
    source: str
    resolution_method: Literal["provider_geocoding", "coordinates", "configured_reference", "district_registry"]
    location_type: Literal["district", "city", "generic"] = "generic"
    coordinate_role: Literal["district_headquarters", "geocoded_place", "user_coordinates", "configured_reference"] = "geocoded_place"
    coordinate_source: str | None = None
    matched_alias: str | None = None
    status: Literal["resolved"] = "resolved"


class LocationResolutionError(Exception):
    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status


_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "data" / "maharashtra_districts.json"
_COORDINATE_QUERY = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*[,/]\s*(-?\d+(?:\.\d+)?)\s*$")
_TRAILING_LOCATION_WORDS = (
    "state of maharashtra", "maharashtra state", "maharashtra", "bharat", "india", "district",
    "zilla", "zila", "jilha", "जिल्हा", "जिला", "महाराष्ट्र राज्य", "महाराष्ट्र", "भारत", "देश",
)


def normalize_location_name(value: str) -> str:
    """Normalize a full location label while keeping explicit foreign qualifiers intact."""
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    normalized = re.sub(r"[,;:/_]+", " ", normalized)
    normalized = re.sub(r"[-]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    changed = True
    while changed and normalized:
        changed = False
        for suffix in _TRAILING_LOCATION_WORDS:
            suffix = unicodedata.normalize("NFKC", suffix).casefold()
            if normalized == suffix:
                return ""
            if normalized.endswith(" " + suffix):
                normalized = normalized[: -(len(suffix) + 1)].strip()
                changed = True
                break
    return normalized


@lru_cache(maxsize=1)
def maharashtra_districts() -> tuple[dict, ...]:
    """Load and validate the maintainable district reference catalog once."""
    try:
        catalog = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
        districts = catalog["districts"]
        if catalog.get("schema_version") != 1 or len(districts) != 36:
            raise ValueError("expected schema version 1 and all 36 districts")
        keys: set[str] = set()
        for district in districts:
            key = normalize_location_name(district["normalized_name"])
            if not key or key in keys:
                raise ValueError("district normalized names must be unique")
            keys.add(key)
            if district.get("state") != "Maharashtra" or district.get("country") != "IN":
                raise ValueError("district state/country metadata is invalid")
            if not -90 <= float(district["latitude"]) <= 90 or not -180 <= float(district["longitude"]) <= 180:
                raise ValueError("district coordinates are outside geographic bounds")
            if not all(district.get("aliases", {}).get(language) is not None for language in ("en", "mr", "hi")):
                raise ValueError("every district must define aliases for en, mr, and hi")
        return tuple(districts)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("Maharashtra district registry failed validation") from exc


def find_maharashtra_district(query: str) -> tuple[dict, str] | None:
    """Match an exact district name or alias after removing recognized local suffixes."""
    normalized = normalize_location_name(query)
    if not normalized:
        return None
    for district in maharashtra_districts():
        aliases = [district["name"], *district.get("aliases", {}).get("en", []),
                   *district.get("aliases", {}).get("mr", []), *district.get("aliases", {}).get("hi", [])]
        for alias in aliases:
            if normalize_location_name(alias) == normalized:
                return district, alias
    return None


def find_maharashtra_district_in_text(text: str) -> str | None:
    """Return a canonical district named in a multilingual question, preferring longer aliases."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    aliases: list[tuple[int, str, str]] = []
    for district in maharashtra_districts():
        for alias in [district["name"], *district.get("aliases", {}).get("en", []),
                      *district.get("aliases", {}).get("mr", []), *district.get("aliases", {}).get("hi", [])]:
            aliases.append((len(alias), alias, district["name"]))
    for _, alias, canonical in sorted(aliases, reverse=True):
        pattern = r"(?<!\w)" + r"\s+".join(re.escape(part) for part in alias.casefold().split()) + r"(?!\w)"
        if re.search(pattern, folded):
            return canonical
    return None


class LocationService:
    """Resolve coordinates, Maharashtra districts, configured references, then OWM places."""

    def __init__(self) -> None:
        parts = urlsplit(settings.WEATHER_API_BASE_URL)
        self.base_url = f"{parts.scheme}://{parts.netloc}/geo/1.0"
        self.api_key = settings.WEATHER_API_KEY
        self.timeout = settings.WEATHER_API_TIMEOUT

    async def resolve(self, query: str) -> ResolvedLocation:
        query = query.strip()
        if not query:
            raise LocationResolutionError("location_not_found", "Enter a location name.")

        coordinate_match = _COORDINATE_QUERY.fullmatch(query)
        if coordinate_match:
            return self.from_coordinates(float(coordinate_match.group(1)), float(coordinate_match.group(2)), query)

        district_match = find_maharashtra_district(query)
        if district_match:
            district, alias = district_match
            coordinate_source = "OpenWeatherMap Geocoding API" if district["coordinate_source"] == "owm" else "Mumbai Suburban District, Government of Maharashtra"
            return ResolvedLocation(
                query=query, city=district["headquarters"], district=district["name"],
                state=district["state"], country=district["country"], latitude=district["latitude"],
                longitude=district["longitude"], source="WeatherGPT Maharashtra district registry",
                resolution_method="district_registry", location_type="district",
                coordinate_role="district_headquarters", coordinate_source=coordinate_source, matched_alias=alias,
            )

        configured = self._configured_reference(query)
        if configured:
            return configured

        if not self.api_key:
            raise LocationResolutionError("location_provider_unavailable", "Location provider is not configured.")
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/direct", params={"q": query, "limit": 5, "appid": self.api_key})
        except httpx.TimeoutException as exc:
            logger.warning("Location provider timed out", extra={"provider": "OpenWeatherMap"})
            raise LocationResolutionError("location_provider_unavailable", "Location provider timed out.") from exc
        except httpx.RequestError as exc:
            logger.warning("Location provider request failed", extra={"provider": "OpenWeatherMap", "error_type": type(exc).__name__})
            raise LocationResolutionError("location_provider_unavailable", "Location provider is unavailable.") from exc
        if response.status_code in (401, 403):
            raise LocationResolutionError("location_provider_unavailable", "Location provider authorization failed.")
        if response.status_code != 200:
            logger.warning("Location provider returned error", extra={"provider": "OpenWeatherMap", "status_code": response.status_code})
            raise LocationResolutionError("location_provider_unavailable", "Location provider is unavailable.")
        try:
            rows = response.json()
        except ValueError as exc:
            raise LocationResolutionError("location_provider_unavailable", "Location provider returned invalid data.") from exc
        if not isinstance(rows, list) or not rows:
            raise LocationResolutionError("location_not_found", "No matching location was found.")
        matches: list[ResolvedLocation] = []
        try:
            for row in rows:
                matches.append(ResolvedLocation(
                    query=query, city=row.get("name"), state=row.get("state"), country=row.get("country"),
                    latitude=row["lat"], longitude=row["lon"], source="OpenWeatherMap Geocoding API",
                    resolution_method="provider_geocoding", location_type="city" if row.get("name") else "generic",
                    coordinate_role="geocoded_place", coordinate_source="OpenWeatherMap Geocoding API"))
        except (KeyError, TypeError, ValueError) as exc:
            raise LocationResolutionError("location_provider_unavailable", "Location provider returned incomplete location data.") from exc
        # Disambiguate same-name places when they are genuinely distinct.
        unique = {(round(item.latitude, 5), round(item.longitude, 5), item.country) for item in matches}
        if len(unique) > 1:
            raise LocationResolutionError("location_ambiguous", "Several locations match. Add a state or country to narrow the search.")
        return matches[0]

    @staticmethod
    def from_coordinates(latitude: float, longitude: float, query: str | None = None) -> ResolvedLocation:
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise LocationResolutionError("invalid_coordinates", "Coordinates are outside valid latitude/longitude bounds.")
        return ResolvedLocation(query=query or f"{latitude},{longitude}", latitude=latitude, longitude=longitude,
            source="User-supplied coordinates", resolution_method="coordinates", location_type="generic",
            coordinate_role="user_coordinates", coordinate_source="User-supplied coordinates")

    @staticmethod
    def _configured_reference(query: str) -> ResolvedLocation | None:
        """Reuse the existing historical reference catalog after district matching."""
        from app.services.historical_weather_service import resolve_historical_coordinates

        candidates = [query, normalize_location_name(query)]
        for candidate in dict.fromkeys(item for item in candidates if item):
            point = resolve_historical_coordinates(candidate)
            if point is None:
                continue
            name = candidate.title()
            try:
                mappings = json.loads(settings.HISTORICAL_LOCATION_COORDINATES or "{}")
                for value in mappings.values() if isinstance(mappings, dict) else []:
                    if not isinstance(value, dict):
                        continue
                    names = [value.get("name", ""), *value.get("aliases", [])]
                    matched = next((str(item) for item in names if isinstance(item, str) and normalize_location_name(item) == normalize_location_name(candidate)), None)
                    if matched:
                        name = str(value.get("name") or matched)
                        break
            except (TypeError, ValueError):
                pass
            return ResolvedLocation(query=query, city=name, state="Maharashtra", country="IN",
                latitude=point[0], longitude=point[1], source="Configured WeatherGPT location reference",
                resolution_method="configured_reference", location_type="city",
                coordinate_role="configured_reference", coordinate_source="Configured WeatherGPT location reference")
        return None


location_service = LocationService()
