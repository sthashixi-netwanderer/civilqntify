"""Single-request weather workers with immutable inputs and explicit ownership."""
from __future__ import annotations

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from app.weather.weather_service import WeatherService
from app.weather.weatherapi_service import WeatherAPIService


class WeatherWorkerGroup(QObject):
    """Keep threads alive and join them before their Qt owner is destroyed.

    Network calls have service-level timeouts. Interruption is cooperative;
    never terminate a thread in the middle of an HTTP/Python operation.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.workers: set[QThread] = set()

    def add(self, worker: QThread) -> None:
        self.workers.add(worker)
        worker.finished.connect(self._retire)

    @pyqtSlot()
    def _retire(self) -> None:
        worker = self.sender()
        if worker in self.workers:
            self.workers.remove(worker)
            worker.deleteLater()

    @pyqtSlot()
    def shutdown(self) -> None:
        for worker in self.workers:
            worker.requestInterruption()
        for worker in self.workers:
            worker.wait()
            worker.deleteLater()
        self.workers.clear()


class _RequestWorker(QThread):
    weather_ready = pyqtSignal(dict)
    forecast_ready = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, parent=None, *, request_id: int = 0) -> None:
        super().__init__(parent)
        self.request_id = request_id
        self._params: tuple | None = None

    def _configure(self, **params) -> None:
        if self._params is not None:
            raise RuntimeError("Weather workers are single-request; create a new worker")
        self._params = tuple(params.items())

    def _fetch(self, params: dict) -> dict:
        raise NotImplementedError

    def run(self) -> None:
        try:
            if self._params is None:
                raise RuntimeError("Weather request has no parameters")
            params = dict(self._params)
            city = params.pop("city_name", None)
            if self.isInterruptionRequested():
                return
            data = dict(self._fetch(params))
            if city is not None:
                data["city_name"] = city
            if not self.isInterruptionRequested():
                self.weather_ready.emit(data)
                self.forecast_ready.emit(data)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.error.emit(str(exc))


class WeatherWorker(_RequestWorker):
    def set_params(self, latitude: float, longitude: float, city_name: str = "") -> None:
        self._configure(latitude=latitude, longitude=longitude, city_name=city_name)

    def _fetch(self, params: dict) -> dict:
        return WeatherService.get_current_weather(**params)


class WeatherAPIWorker(_RequestWorker):
    def set_params(self, api_key: str, query: str, city_name: str = "") -> None:
        self._configure(api_key=api_key, query=query, city_name=city_name)

    def _fetch(self, params: dict) -> dict:
        return WeatherAPIService.get_current_weather(**params)


class HourlyForecastWorker(_RequestWorker):
    def set_params(self, latitude: float, longitude: float, hours: int = 24,
                   forecast_days: int = 1) -> None:
        self._configure(latitude=latitude, longitude=longitude, hours=hours,
                        forecast_days=forecast_days)

    def _fetch(self, params: dict) -> dict:
        return WeatherService.get_hourly_forecast(**params)


class DailyForecastWorker(_RequestWorker):
    def set_params(self, latitude: float, longitude: float, days: int = 5) -> None:
        self._configure(latitude=latitude, longitude=longitude, days=days)

    def _fetch(self, params: dict) -> dict:
        return WeatherService.get_forecast(**params)


class WeatherAPIDailyForecastWorker(_RequestWorker):
    def set_params(self, api_key: str, query: str, days: int = 5) -> None:
        self._configure(api_key=api_key, query=query, days=days)

    def _fetch(self, params: dict) -> dict:
        return WeatherAPIService.get_daily_forecast(**params)


class WeatherAPIForecastWorker(_RequestWorker):
    def set_params(self, api_key: str, query: str, days: int = 2) -> None:
        self._configure(api_key=api_key, query=query, days=days)

    def _fetch(self, params: dict) -> dict:
        return WeatherAPIService.get_hourly_forecast(**params)
