"""Tests for health-check endpoints."""

import pytest


@pytest.mark.anyio
async def test_root_endpoint(client):
    """GET / should return app name and status."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert "name" in data
    assert "version" in data


@pytest.mark.anyio
async def test_health_endpoint(client):
    """GET /health should return healthy status."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
