from unittest.mock import MagicMock

import httpx
import pytest

from app.services.location_service import (
    LocationResolutionError, LocationService, find_maharashtra_district, maharashtra_districts,
)


class FakeClient:
    rows = []
    status_code = 200
    error = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, *args, **kwargs):
        if self.error:
            raise self.error
        response = MagicMock()
        response.status_code = self.status_code
        response.json.return_value = self.rows
        return response


@pytest.fixture
def service(monkeypatch):
    value = LocationService()
    value.api_key = "test-key"
    monkeypatch.setattr("app.services.location_service.httpx.AsyncClient", FakeClient)
    FakeClient.rows = [{"name": "Nashik", "state": "Maharashtra", "country": "IN", "lat": 19.9975, "lon": 73.7898}]
    FakeClient.status_code = 200
    FakeClient.error = None
    return value


@pytest.mark.anyio
async def test_city_resolution_returns_provider_coordinates_and_metadata(service):
    FakeClient.rows = [{"name": "Springfield", "state": "Illinois", "country": "US", "lat": 39.78, "lon": -89.64}]
    resolved = await service.resolve(" Springfield, Illinois, US ")
    assert (resolved.city, resolved.state, resolved.country) == ("Springfield", "Illinois", "US")
    assert (resolved.latitude, resolved.longitude) == (39.78, -89.64)
    assert resolved.source == "OpenWeatherMap Geocoding API"
    assert resolved.location_type == "city"


@pytest.mark.anyio
async def test_city_not_found_and_ambiguous_are_explicit(service):
    FakeClient.rows = []
    with pytest.raises(LocationResolutionError, match="No matching") as not_found:
        await service.resolve("NoSuchPlace")
    assert not_found.value.status == "location_not_found"
    FakeClient.rows = [{"name": "Springfield", "country": "US", "lat": 1, "lon": 2},
                       {"name": "Springfield", "country": "US", "lat": 3, "lon": 4}]
    with pytest.raises(LocationResolutionError) as ambiguous:
        await service.resolve("Springfield")
    assert ambiguous.value.status == "location_ambiguous"


@pytest.mark.anyio
async def test_provider_failure_does_not_leak_response_or_key(service):
    FakeClient.status_code = 403
    with pytest.raises(LocationResolutionError) as result:
        await service.resolve("Springfield, Illinois")
    assert result.value.status == "location_provider_unavailable"
    assert "test-key" not in str(result.value)


def test_coordinate_resolution_accepts_world_boundaries_and_rejects_out_of_range(service):
    assert service.from_coordinates(-90, 180).resolution_method == "coordinates"
    assert service.from_coordinates(90, -180).latitude == 90
    for lat, lon in ((-90.01, 0), (0, 180.01)):
        with pytest.raises(LocationResolutionError) as result:
            service.from_coordinates(lat, lon)
        assert result.value.status == "invalid_coordinates"


@pytest.mark.anyio
async def test_coordinate_query_is_resolved_before_district_or_provider(service):
    resolved = await service.resolve("20.25, 73.75")
    assert resolved.resolution_method == "coordinates"
    assert resolved.coordinate_role == "user_coordinates"
    assert (resolved.latitude, resolved.longitude) == (20.25, 73.75)


@pytest.mark.parametrize("district", maharashtra_districts(), ids=lambda item: item["name"])
@pytest.mark.anyio
async def test_every_district_canonical_and_state_qualified_name_resolves_locally(service, district):
    for query in (district["name"], f"{district['name']} district, Maharashtra"):
        resolved = await service.resolve(query)
        assert resolved.resolution_method == "district_registry"
        assert resolved.location_type == "district"
        assert resolved.coordinate_role == "district_headquarters"
        assert resolved.district == district["name"]
        assert resolved.state == "Maharashtra" and resolved.country == "IN"
        assert (resolved.latitude, resolved.longitude) == (district["latitude"], district["longitude"])


@pytest.mark.parametrize("language", ("mr", "hi"))
@pytest.mark.parametrize("district", maharashtra_districts(), ids=lambda item: item["name"])
@pytest.mark.anyio
async def test_defined_marathi_and_hindi_aliases_resolve(service, district, language):
    aliases = district["aliases"][language]
    if not aliases:
        pytest.skip("No additional alias is defined for this language")
    resolved = await service.resolve(aliases[0])
    assert resolved.district == district["name"]
    assert resolved.state == "Maharashtra" and resolved.country == "IN"
    assert resolved.resolution_method == "district_registry"


@pytest.mark.anyio
async def test_maharashtra_name_variants_and_foreign_qualifier(service):
    for query in ("नाशिक जिल्हा", "नासिक महाराष्ट्र", "Nashik, Maharashtra"):
        assert (await service.resolve(query)).district == "Nashik"
    FakeClient.rows = [{"name": "Akola", "state": "Uttar Pradesh", "country": "IN", "lat": 26.0, "lon": 80.0}]
    resolved = await service.resolve("Akola, Uttar Pradesh")
    assert resolved.resolution_method == "provider_geocoding"
    assert resolved.state == "Uttar Pradesh"


def test_district_registry_has_36_unique_records_and_keeps_mumbai_districts_distinct():
    districts = maharashtra_districts()
    assert len(districts) == 36
    assert len({item["normalized_name"] for item in districts}) == 36
    assert find_maharashtra_district("Mumbai City")[0]["name"] == "Mumbai City"
    assert find_maharashtra_district("Mumbai Suburban")[0]["name"] == "Mumbai Suburban"
    assert find_maharashtra_district("Mumbai") is None


@pytest.mark.anyio
async def test_location_endpoint_reports_structured_not_found(client, monkeypatch):
    from app.api.routes import weather
    async def missing(_query):
        raise LocationResolutionError("location_not_found", "No matching location was found.")
    monkeypatch.setattr(weather.location_service, "resolve", missing)
    response = await client.get("/api/v1/location/resolve", params={"q": "Nowhere"})
    assert response.status_code == 422
    assert response.json()["status"] == "location_not_found"
