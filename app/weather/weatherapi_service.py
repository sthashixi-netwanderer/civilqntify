"""WeatherAPI.com service for CivilQntify.

Fetches real-time weather data from WeatherAPI.com.
Requires a free API key from https://www.weatherapi.com/
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
import urllib.parse
from typing import Any, Optional


class WeatherAPIService:
    """WeatherAPI.com API client.

    Provides methods to fetch current weather data and forecasts.
    Free tier available at https://www.weatherapi.com/
    """

    BASE_URL = "https://api.weatherapi.com/v1"

    @staticmethod
    def get_current_weather(
        api_key: str,
        query: str,
    ) -> dict[str, Any]:
        """Fetch current weather conditions from WeatherAPI."""
        if not api_key:
            raise WeatherAPIError("API key required. Get one free at https://www.weatherapi.com/")

        params = {
            "key": api_key,
            "q": query,
            "aqi": "no",
        }

        try:
            data = WeatherAPIService._make_request("current.json", params)
            return WeatherAPIService._parse_current_weather(data)
        except Exception as e:
            raise WeatherAPIError(f"Failed to fetch weather: {e}")

    @staticmethod
    def get_hourly_forecast(
        api_key: str,
        query: str,
        days: int = 2,
    ) -> dict[str, Any]:
        """Fetch hourly weather forecast from WeatherAPI.

        Args:
            api_key: WeatherAPI.com API key
            query: City name or coordinates
            days: Number of forecast days (1-14)

        Returns:
            Dictionary with hourly forecast data

        Raises:
            WeatherAPIError: If API request fails
        """
        if not api_key:
            raise WeatherAPIError("API key required. Get one free at https://www.weatherapi.com/")

        params = {
            "key": api_key,
            "q": query,
            "days": min(max(days, 1), 14),
            "aqi": "no",
            "alerts": "no",
        }

        try:
            data = WeatherAPIService._make_request("forecast.json", params)
            return WeatherAPIService._parse_hourly_forecast(data)
        except Exception as e:
            raise WeatherAPIError(f"Failed to fetch forecast: {e}")

    @staticmethod
    def get_daily_forecast(
        api_key: str,
        query: str,
        days: int = 5,
    ) -> dict[str, Any]:
        """Fetch daily weather forecast from WeatherAPI.

        Args:
            api_key: WeatherAPI.com API key
            query: City name or coordinates
            days: Number of forecast days (1-14)

        Returns:
            Dictionary with daily forecast data

        Raises:
            WeatherAPIError: If API request fails
        """
        if not api_key:
            raise WeatherAPIError("API key required. Get one free at https://www.weatherapi.com/")

        params = {
            "key": api_key,
            "q": query,
            "days": min(max(days, 1), 14),
            "aqi": "no",
            "alerts": "no",
        }

        try:
            data = WeatherAPIService._make_request("forecast.json", params)
            return WeatherAPIService._parse_daily_forecast(data)
        except Exception as e:
            raise WeatherAPIError(f"Failed to fetch daily forecast: {e}")

    @staticmethod
    def _make_request(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        """Make HTTP request to WeatherAPI."""
        query_parts = []
        for key, value in params.items():
            query_parts.append(f"{key}={urllib.parse.quote(str(value))}")
        url = f"{WeatherAPIService.BASE_URL}/{endpoint}?{'&'.join(query_parts)}"

        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))

                if "error" in data:
                    error = data["error"]
                    raise WeatherAPIError(error.get("message", "Unknown API error"))

                return data
        except urllib.error.URLError as e:
            raise WeatherAPIError(f"Network error: {e}")
        except json.JSONDecodeError as e:
            raise WeatherAPIError(f"Invalid JSON response: {e}")
        except WeatherAPIError:
            raise
        except Exception as e:
            raise WeatherAPIError(f"Request failed: {e}")

    @staticmethod
    def _parse_current_weather(data: dict[str, Any]) -> dict[str, Any]:
        """Parse current weather data from API response."""
        current = data.get("current", {})
        condition = current.get("condition", {})

        return {
            "temperature": current.get("temp_c", 0.0),
            "feels_like": current.get("feelslike_c", 0.0),
            "humidity": current.get("humidity", 0),
            "wind_speed": current.get("wind_kph", 0.0),
            "wind_direction": current.get("wind_degree", 0),
            "precipitation": current.get("precip_mm", 0.0),
            "weather_code": condition.get("code", 0),
            "weather_description": condition.get("text", "Unknown"),
            "time": current.get("last_updated", ""),
            "location": data.get("location", {}).get("name", ""),
        }

    @staticmethod
    def _parse_hourly_forecast(data: dict[str, Any]) -> dict[str, Any]:
        """Parse hourly forecast data from API response."""
        forecasts = []

        forecast_data = data.get("forecast", {})
        forecast_days = forecast_data.get("forecastday", [])

        for day in forecast_days:
            date = day.get("date", "")
            hours = day.get("hour", [])

            for hour_data in hours:
                time_epoch = hour_data.get("time_epoch", 0)
                time_str = hour_data.get("time", "")
                hour = ""
                if " " in time_str:
                    hour = time_str.split(" ")[1][:5]  # Extract "HH:MM"

                condition = hour_data.get("condition", {})
                weather_code = condition.get("code", 0)

                forecasts.append({
                    "time": time_str,
                    "hour": hour,
                    "date": date,
                    "temperature": hour_data.get("temp_c", 0.0),
                    "feels_like": hour_data.get("feelslike_c", 0.0),
                    "humidity": hour_data.get("humidity", 0),
                    "precipitation_probability": hour_data.get("chance_of_rain", 0),
                    "precipitation": hour_data.get("precip_mm", 0.0),
                    "weather_code": weather_code,
                    "weather_description": condition.get("text", "Unknown"),
                    "wind_speed": hour_data.get("wind_kph", 0.0),
                    "wind_direction": hour_data.get("wind_degree", 0),
                })

        return {
            "hourly": forecasts,
            "timezone": data.get("location", {}).get("tz_id", "Africa/Accra"),
        }

    @staticmethod
    def _parse_daily_forecast(data: dict[str, Any]) -> dict[str, Any]:
        """Parse daily forecast data from WeatherAPI response."""
        forecasts = []

        forecast_data = data.get("forecast", {})
        forecast_days = forecast_data.get("forecastday", [])

        for day in forecast_days:
            date = day.get("date", "")
            day_info = day.get("day", {})
            condition = day_info.get("condition", {})

            forecasts.append({
                "date": date,
                "max_temp": day_info.get("maxtemp_c", 0.0),
                "min_temp": day_info.get("mintemp_c", 0.0),
                "precipitation": day_info.get("totalprecip_mm", 0.0),
                "weather_code": condition.get("code", 0),
                "weather_description": condition.get("text", "Unknown"),
            })

        return {
            "forecasts": forecasts,
            "timezone": data.get("location", {}).get("tz_id", "Africa/Accra"),
        }

    @staticmethod
    def get_wind_direction_name(direction_degrees: float) -> str:
        """Convert wind direction in degrees to cardinal direction."""
        directions = [
            "N", "NNE", "NE", "ENE",
            "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW",
            "W", "WNW", "NW", "NNW",
        ]
        index = round(direction_degrees / 22.5) % 16
        return directions[index]


class WeatherAPIError(Exception):
    """Exception raised by WeatherAPIService."""
    pass
