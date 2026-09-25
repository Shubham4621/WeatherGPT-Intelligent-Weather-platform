from datetime import datetime, timezone

import httpx
import pytest

from app.core.config import settings
from app.services.imd_alert_service import AlertProviderUnavailable, ImdAlertService, UnsupportedAlertLocation


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr(settings, "IMD_DHULE_OBJ_ID", "9001")
    svc = ImdAlertService()
    svc.ttl = 0
    return svc


def payload(codes="2,4", color=2):
    return [{"Obj_id": "9001", "Date": "2026-09-24", "UTC": "10:30", "District": "Dhule", **{f"Day_{d}": (codes if d == 1 else "1") for d in range(1, 6)}, **{f"Day{d}_Color": (color if d == 1 else 4) for d in range(1, 6)}}]


def test_multiple_warning_codes_and_source_normalize(service):
    result = service._normalize(payload(), "Dhule", "Maharashtra", "9001")
    assert [item.warning_type for item in result.forecast_days[0].warnings] == ["Heavy Rain", "Thunderstorm & Lightning, Squall etc"]
    assert result.forecast_days[0].severity == "Orange"
    assert result.source.startswith("India Meteorological Department")
    assert result.issued_at == datetime(2026, 9, 24, 10, 30, tzinfo=timezone.utc)


@pytest.mark.parametrize("color,name", [(1, "Red"), (2, "Orange"), (3, "Yellow"), (4, "Green"), (8, None)])
def test_color_mapping_preserves_code(service, color, name):
    day = service._normalize(payload("9", color), "Dhule", "Maharashtra", "9001").forecast_days[0]
    assert day.severity == name and day.severity_code == color


def test_no_warning_is_not_an_active_alert(service):
    day = service._normalize(payload("1", 4), "Dhule", "Maharashtra", "9001").forecast_days[0]
    assert day.warnings == [] and not day.is_active


def test_unknown_warning_code_is_preserved(service):
    item = service._normalize(payload("99", 9), "Dhule", "Maharashtra", "9001").forecast_days[0]
    assert item.warnings[0].warning_code == 99
    assert "Unknown IMD warning" in item.warnings[0].warning_type
    assert item.severity_code == 9


def test_missing_fields_are_rejected(service):
    with pytest.raises(ValueError):
        service._normalize([{"Obj_id": "9001"}], "Dhule", "Maharashtra", "9001")


def test_city_normalization_and_unverified_mapping(monkeypatch):
    monkeypatch.setattr(settings, "IMD_DHULE_OBJ_ID", "")
    svc = ImdAlertService()
    with pytest.raises(AlertProviderUnavailable):
        svc.resolve_district("DHULE, Maharashtra")
    with pytest.raises(UnsupportedAlertLocation):
        svc.resolve_district("Nashik")


@pytest.mark.anyio
async def test_timeout_is_controlled(service, monkeypatch):
    async def timeout(*args, **kwargs):
        raise httpx.TimeoutException("timeout")
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        get = timeout
    monkeypatch.setattr("app.services.imd_alert_service.httpx.AsyncClient", lambda **kwargs: Client())
    with pytest.raises(AlertProviderUnavailable):
        await service.get_alerts("Dhule")


@pytest.mark.anyio
@pytest.mark.parametrize("status,body", [(403, "blocked"), (200, "not-json"), (200, "[]")])
async def test_provider_errors_are_controlled(service, monkeypatch, status, body):
    class Response:
        status_code = status
        def json(self):
            if body == "not-json": raise ValueError("invalid json")
            return body
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def get(self, *args, **kwargs): return Response()
    monkeypatch.setattr("app.services.imd_alert_service.httpx.AsyncClient", lambda **kwargs: Client())
    with pytest.raises(AlertProviderUnavailable):
        await service.get_alerts("Dhule")
