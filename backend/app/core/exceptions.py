"""Custom exception classes for WeatherGPT."""


class WeatherGPTError(Exception):
    """Base exception for WeatherGPT."""

    def __init__(self, detail: str = "An unexpected error occurred", status_code: int = 500):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class WeatherAPIError(WeatherGPTError):
    """Raised for client-facing weather request errors (4xx)."""

    def __init__(self, detail: str = "Bad weather request", status_code: int = 400):
        super().__init__(detail=detail, status_code=status_code)


class WeatherProviderError(WeatherGPTError):
    """Raised when the upstream weather provider fails (5xx)."""

    def __init__(
        self, detail: str = "Weather provider is currently unavailable", status_code: int = 502
    ):
        super().__init__(detail=detail, status_code=status_code)
