"""Open-Meteo weather service for CivilQntify.

Fetches real-time weather data from Open-Meteo API.
Free for non-commercial use, no API key required.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any, Optional


# WMO Weather interpretation codes
# Source: https://open-meteo.com/en/docs
WMO_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


class WeatherService:
    """Open-Meteo weather API client.

    Provides methods to fetch current weather data and forecasts.
    Free for non-commercial use, no API key required.
    """

    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    @staticmethod
    def get_current_weather(
        latitude: float,
        longitude: float,
        timezone: str = "Africa/Accra",
    ) -> dict[str, Any]:
        """Fetch current weather conditions from Open-Meteo API."""
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join([
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "precipitation",
                "weather_code",
                "wind_speed_10m",
                "wind_direction_10m",
            ]),
            "timezone": timezone,
        }

        try:
            data = WeatherService._make_request(params)
            return WeatherService._parse_current_weather(data)
        except Exception as e:
            raise WeatherServiceError(f"Failed to fetch weather: {e}")

    @staticmethod
    def get_forecast(
        latitude: float,
        longitude: float,
        days: int = 7,
        timezone: str = "Africa/Accra",
    ) -> dict[str, Any]:
        """Fetch weather forecast from Open-Meteo API."""
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": ",".join([
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "weather_code",
            ]),
            "timezone": timezone,
            "forecast_days": min(max(days, 1), 16),
        }

        try:
            data = WeatherService._make_request(params)
            return WeatherService._parse_forecast(data)
        except Exception as e:
            raise WeatherServiceError(f"Failed to fetch forecast: {e}")

    @staticmethod
    def get_hourly_forecast(
        latitude: float,
        longitude: float,
        hours: int = 24,
        forecast_days: int = 1,
        timezone: str = "Africa/Accra",
    ) -> dict[str, Any]:
        """Fetch hourly weather forecast from Open-Meteo API.

        When forecast_days > 1, uses forecast_days parameter instead of
        forecast_hours to get hourly data across multiple days (up to 16).
        """
        params: dict[str, Any] = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": ",".join([
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "precipitation_probability",
                "precipitation",
                "weather_code",
                "wind_speed_10m",
                "wind_direction_10m",
            ]),
            "timezone": timezone,
        }

        if forecast_days > 1:
            params["forecast_days"] = min(max(forecast_days, 1), 16)
        else:
            params["forecast_hours"] = min(max(hours, 1), 48)

        try:
            data = WeatherService._make_request(params)
            return WeatherService._parse_hourly_forecast(data)
        except Exception as e:
            raise WeatherServiceError(f"Failed to fetch hourly forecast: {e}")

    @staticmethod
    def _make_request(params: dict[str, Any]) -> dict[str, Any]:
        """Make HTTP request to Open-Meteo API."""
        query_parts = []
        for key, value in params.items():
            query_parts.append(f"{key}={value}")
        url = f"{WeatherService.BASE_URL}?{'&'.join(query_parts)}"

        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data
        except urllib.error.URLError as e:
            raise WeatherServiceError(f"Network error: {e}")
        except json.JSONDecodeError as e:
            raise WeatherServiceError(f"Invalid JSON response: {e}")
        except Exception as e:
            raise WeatherServiceError(f"Request failed: {e}")

    @staticmethod
    def _parse_current_weather(data: dict[str, Any]) -> dict[str, Any]:
        """Parse current weather data from API response."""
        current = data.get("current", {})
        weather_code = current.get("weather_code", 0)

        return {
            "temperature": current.get("temperature_2m", 0.0),
            "feels_like": current.get("apparent_temperature", 0.0),
            "humidity": current.get("relative_humidity_2m", 0),
            "wind_speed": current.get("wind_speed_10m", 0.0),
            "wind_direction": current.get("wind_direction_10m", 0),
            "precipitation": current.get("precipitation", 0.0),
            "weather_code": weather_code,
            "weather_description": WMO_CODES.get(weather_code, "Unknown"),
            "time": current.get("time", ""),
        }

    @staticmethod
    def _parse_forecast(data: dict[str, Any]) -> dict[str, Any]:
        """Parse forecast data from API response."""
        daily = data.get("daily", {})

        forecasts = []
        dates = daily.get("time", [])
        max_temps = daily.get("temperature_2m_max", [])
        min_temps = daily.get("temperature_2m_min", [])
        precip = daily.get("precipitation_sum", [])
        codes = daily.get("weather_code", [])

        for i in range(len(dates)):
            weather_code = codes[i] if i < len(codes) else 0
            forecasts.append({
                "date": dates[i],
                "max_temp": max_temps[i] if i < len(max_temps) else 0.0,
                "min_temp": min_temps[i] if i < len(min_temps) else 0.0,
                "precipitation": precip[i] if i < len(precip) else 0.0,
                "weather_code": weather_code,
                "weather_description": WMO_CODES.get(weather_code, "Unknown"),
            })

        return {
            "forecasts": forecasts,
            "timezone": data.get("timezone", "Africa/Accra"),
        }

    @staticmethod
    def _parse_hourly_forecast(data: dict[str, Any]) -> dict[str, Any]:
        """Parse hourly forecast data from API response."""
        hourly = data.get("hourly", {})

        forecasts = []
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        humidity = hourly.get("relative_humidity_2m", [])
        feels_like = hourly.get("apparent_temperature", [])
        precip_prob = hourly.get("precipitation_probability", [])
        precip = hourly.get("precipitation", [])
        codes = hourly.get("weather_code", [])
        wind_speed = hourly.get("wind_speed_10m", [])
        wind_dir = hourly.get("wind_direction_10m", [])

        for i in range(len(times)):
            weather_code = codes[i] if i < len(codes) else 0
            # Parse time string to extract hour
            time_str = times[i] if i < len(times) else ""
            hour = ""
            if "T" in time_str:
                hour = time_str.split("T")[1][:5]  # Extract "HH:MM"

            forecasts.append({
                "time": time_str,
                "hour": hour,
                "temperature": temps[i] if i < len(temps) else 0.0,
                "feels_like": feels_like[i] if i < len(feels_like) else 0.0,
                "humidity": humidity[i] if i < len(humidity) else 0,
                "precipitation_probability": precip_prob[i] if i < len(precip_prob) else 0,
                "precipitation": precip[i] if i < len(precip) else 0.0,
                "weather_code": weather_code,
                "weather_description": WMO_CODES.get(weather_code, "Unknown"),
                "wind_speed": wind_speed[i] if i < len(wind_speed) else 0.0,
                "wind_direction": wind_dir[i] if i < len(wind_dir) else 0.0,
            })

        return {
            "hourly": forecasts,
            "timezone": data.get("timezone", "Africa/Accra"),
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


class WeatherServiceError(Exception):
    """Exception raised by WeatherService."""
    pass
