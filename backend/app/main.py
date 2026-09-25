"""WeatherGPT — FastAPI Application Entry Point."""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import chat, health, weather
from app.core.config import settings
from app.core.exceptions import WeatherAPIError, WeatherProviderError
from app.core.logging import get_logger
from app.services.llm_service import LLMServiceError

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    logger.info(
        "WeatherGPT backend starting",
        extra={"version": settings.APP_VERSION, "environment": settings.ENVIRONMENT},
    )
    yield
    logger.info("WeatherGPT backend shutting down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="AI-Powered Multilingual Weather Intelligence Platform",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS — allow the future React frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Request timing middleware ---
    @app.middleware("http")
    async def log_request_timing(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "Request completed",
            extra={
                "method": request.method,
                "path": str(request.url.path),
                "status_code": response.status_code,
                "elapsed_ms": elapsed_ms,
            },
        )
        return response

    # --- Exception handlers ---
    @app.exception_handler(WeatherAPIError)
    async def weather_api_error_handler(request: Request, exc: WeatherAPIError):
        logger.warning(
            "Weather API error",
            extra={"detail": exc.detail, "status_code": exc.status_code},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail, "type": "weather_api_error"},
        )

    @app.exception_handler(WeatherProviderError)
    async def weather_provider_error_handler(
        request: Request, exc: WeatherProviderError
    ):
        logger.error(
            "Weather provider error",
            extra={"detail": exc.detail, "status_code": exc.status_code},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail, "type": "weather_provider_error"},
        )

    @app.exception_handler(LLMServiceError)
    async def llm_service_error_handler(request: Request, exc: LLMServiceError):
        logger.warning(
            "LLM service error",
            extra={"status_code": exc.status_code, "error_type": exc.error_type},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail, "type": "llm_service_error"},
        )

    # --- Routes ---
    app.include_router(health.router)
    app.include_router(chat.router, prefix=settings.API_V1_PREFIX)
    app.include_router(
        weather.router,
        prefix=settings.API_V1_PREFIX,
    )

    return app


app = create_app()
