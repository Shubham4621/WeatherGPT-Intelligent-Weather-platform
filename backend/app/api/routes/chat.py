"""Natural-language current-weather chat endpoint."""

from fastapi import APIRouter, Depends

from app.agents.weather_agent import WeatherAgent
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["Chat"])


def get_weather_agent() -> WeatherAgent:
    return WeatherAgent()


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, agent: WeatherAgent = Depends(get_weather_agent)) -> ChatResponse:
    """Answer a supported current-weather question using live provider data."""
    return await agent.answer(request.message, language=request.language)
