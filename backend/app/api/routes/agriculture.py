"""Weather-based agricultural decision support routes."""
from fastapi import APIRouter, HTTPException

from app.schemas.agriculture import AgricultureAdviceResponse, AgricultureRequest, StationQualityReport
from app.services.agriculture_service import AgricultureIntelligenceService
from app.services.imd_station_service import station_quality_report
from app.api.routes.weather import weather_service, nwp_service, historical_weather_service, imd_climatology_service, imd_alert_service

router = APIRouter(prefix="/agriculture", tags=["Agriculture"])
agriculture_service = AgricultureIntelligenceService(weather=weather_service, nwp=nwp_service,
    history=historical_weather_service, climatology=imd_climatology_service, alerts=imd_alert_service)


@router.post("/advice", response_model=AgricultureAdviceResponse)
async def get_agriculture_advice(request: AgricultureRequest) -> AgricultureAdviceResponse:
    return await agriculture_service.advise(request)


@router.get("/stations/{station_id}/quality", response_model=StationQualityReport)
def get_station_quality(station_id: str) -> StationQualityReport:
    result = station_quality_report(station_id)
    if result is None:
        raise HTTPException(status_code=404, detail={"status": "station_not_configured", "station_id": station_id})
    return result

