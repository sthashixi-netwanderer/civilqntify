"""QThread worker for non-blocking weather data fetching.

Fetches weather data from Open-Meteo or WeatherAPI in a background thread
to avoid blocking the UI.
"""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from app.weather.weather_service import WeatherService, WeatherServiceError
from app.weather.weatherapi_service import WeatherAPIService, WeatherAPIError


class WeatherWorker(QThread):
    """Worker thread for fetching current weather from Open-Meteo API."""

    weather_ready = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._latitude: float = 0.0
        self._longitude: float = 0.0
        self._city_name: str = ""

    def set_params(self, latitude: float, longitude: float, city_name: str = "") -> None:
        self._latitude = latitude
        self._longitude = longitude
        self._city_name = city_name

    def run(self) -> None:
        try:
            data = WeatherService.get_current_weather(
                latitude=self._latitude,
                longitude=self._longitude,
            )
            data["city_name"] = self._city_name
            self.weather_ready.emit(data)
        except WeatherServiceError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Unexpected error: {e}")


class WeatherAPIWorker(QThread):
    """Worker thread for fetching current weather from WeatherAPI.com."""

    weather_ready = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._api_key: str = ""
        self._query: str = ""
        self._city_name: str = ""

    def set_params(self, api_key: str, query: str, city_name: str = "") -> None:
        self._api_key = api_key
        self._query = query
        self._city_name = city_name

    def run(self) -> None:
        try:
            data = WeatherAPIService.get_current_weather(
                api_key=self._api_key,
                query=self._query,
            )
            data["city_name"] = self._city_name
            self.weather_ready.emit(data)
        except WeatherAPIError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Unexpected error: {e}")


class HourlyForecastWorker(QThread):
    """Worker thread for fetching hourly forecast from Open-Meteo API."""

    forecast_ready = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._latitude: float = 0.0
        self._longitude: float = 0.0
        self._hours: int = 24
        self._forecast_days: int = 1

    def set_params(
        self,
        latitude: float,
        longitude: float,
        hours: int = 24,
        forecast_days: int = 1,
    ) -> None:
        self._latitude = latitude
        self._longitude = longitude
        self._hours = hours
        self._forecast_days = forecast_days

    def run(self) -> None:
        try:
            data = WeatherService.get_hourly_forecast(
                latitude=self._latitude,
                longitude=self._longitude,
                hours=self._hours,
                forecast_days=self._forecast_days,
            )
            self.forecast_ready.emit(data)
        except WeatherServiceError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Unexpected error: {e}")


class DailyForecastWorker(QThread):
    """Worker thread for fetching daily forecast from Open-Meteo API."""

    forecast_ready = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._latitude: float = 0.0
        self._longitude: float = 0.0
        self._days: int = 5

    def set_params(self, latitude: float, longitude: float, days: int = 5) -> None:
        self._latitude = latitude
        self._longitude = longitude
        self._days = days

    def run(self) -> None:
        try:
            data = WeatherService.get_forecast(
                latitude=self._latitude,
                longitude=self._longitude,
                days=self._days,
            )
            self.forecast_ready.emit(data)
        except WeatherServiceError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Unexpected error: {e}")


class WeatherAPIDailyForecastWorker(QThread):
    """Worker thread for fetching daily forecast from WeatherAPI.com."""

    forecast_ready = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._api_key: str = ""
        self._query: str = ""
        self._days: int = 5

    def set_params(self, api_key: str, query: str, days: int = 5) -> None:
        self._api_key = api_key
        self._query = query
        self._days = days

    def run(self) -> None:
        try:
            data = WeatherAPIService.get_daily_forecast(
                api_key=self._api_key,
                query=self._query,
                days=self._days,
            )
            self.forecast_ready.emit(data)
        except WeatherAPIError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Unexpected error: {e}")


class WeatherAPIForecastWorker(QThread):
    """Worker thread for fetching hourly forecast from WeatherAPI.com."""

    forecast_ready = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._api_key: str = ""
        self._query: str = ""
        self._days: int = 2

    def set_params(self, api_key: str, query: str, days: int = 2) -> None:
        self._api_key = api_key
        self._query = query
        self._days = days

    def run(self) -> None:
        try:
            data = WeatherAPIService.get_hourly_forecast(
                api_key=self._api_key,
                query=self._query,
                days=self._days,
            )
            self.forecast_ready.emit(data)
        except WeatherAPIError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Unexpected error: {e}")
