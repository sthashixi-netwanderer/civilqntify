"""Weather data widget for CivilQntify.

Displays real-time weather data and 24-hour forecast from
Open-Meteo or WeatherAPI.com with Ghana cities dropdown and search.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.weather.ghana_cities import GHANA_CITIES, get_city_coordinates
from app.weather.weather_service import WeatherService
from app.weather.weatherapi_service import WeatherAPIService
from app.weather.weather_worker import (
    WeatherWorker,
    WeatherAPIWorker,
    HourlyForecastWorker,
    WeatherAPIForecastWorker,
    DailyForecastWorker,
    WeatherAPIDailyForecastWorker,
)


class StatCard(QFrame):
    """A card displaying a single weather statistic."""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("weather-stat-card")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(120)
        self.setStyleSheet("""
            QFrame#weather-stat-card {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 10px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        self._title = QLabel(title)
        self._title.setStyleSheet("font-size: 11px; color: #64748b; font-weight: 500;")
        layout.addWidget(self._title)

        self._value = QLabel("—")
        self._value.setStyleSheet("font-size: 20px; font-weight: 700; color: #1e293b;")
        self._value.setWordWrap(False)
        layout.addWidget(self._value)

        self._subtitle = QLabel("")
        self._subtitle.setStyleSheet("font-size: 11px; color: #64748b;")
        self._subtitle.setWordWrap(True)
        layout.addWidget(self._subtitle)

    def set_value(self, value: str, subtitle: str = "") -> None:
        """Set the card value and optional subtitle."""
        self._value.setText(value)
        self._subtitle.setText(subtitle)
        self._subtitle.setVisible(bool(subtitle))


class HourlyForecastCard(QFrame):
    """A card displaying a single hour's forecast."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("hourly-card")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFixedWidth(80)
        self.setStyleSheet("""
            QFrame#hourly-card {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 6px;
            }
            QFrame#hourly-card:selected {
                background-color: #e0f2fe;
                border-color: #0ea5e9;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Hour
        self._hour = QLabel("—")
        self._hour.setStyleSheet("font-size: 10px; color: #64748b; font-weight: 500;")
        self._hour.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._hour)

        # Temperature
        self._temp = QLabel("—")
        self._temp.setStyleSheet("font-size: 14px; font-weight: 700; color: #1e293b;")
        self._temp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._temp)

        # Weather icon/description (short)
        self._weather = QLabel("—")
        self._weather.setStyleSheet("font-size: 9px; color: #475569;")
        self._weather.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._weather.setWordWrap(True)
        layout.addWidget(self._weather)

        # Precipitation probability
        self._precip = QLabel("")
        self._precip.setStyleSheet("font-size: 9px; color: #0ea5e9;")
        self._precip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._precip)

    def set_data(self, data: dict) -> None:
        """Set the forecast data for this hour."""
        self._hour.setText(data.get("hour", "—"))

        temp = data.get("temperature", 0.0)
        self._temp.setText(f"{temp:.0f}°")

        # Short weather description
        desc = data.get("weather_description", "—")
        if len(desc) > 8:
            desc = desc[:8] + "."
        self._weather.setText(desc)

        precip_prob = data.get("precipitation_probability", 0)
        if precip_prob > 0:
            self._precip.setText(f"💧{precip_prob}%")
        else:
            self._precip.setText("")


class DailyForecastDayWidget(QWidget):
    """Content widget for a single day in the 5-day forecast.

    Shows a daily summary row (high/low temp, weather, precipitation)
    and a horizontally scrollable row of hourly forecast cards for that day.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Daily summary stats
        summary_grid = QGridLayout()
        summary_grid.setSpacing(8)

        self._high_card = StatCard("High")
        self._low_card = StatCard("Low")
        self._weather_card = StatCard("Conditions")
        self._rain_card = StatCard("Rain")

        summary_grid.addWidget(self._high_card, 0, 0)
        summary_grid.addWidget(self._low_card, 0, 1)
        summary_grid.addWidget(self._weather_card, 0, 2)
        summary_grid.addWidget(self._rain_card, 0, 3)

        layout.addLayout(summary_grid)

        # Hourly forecast label
        hourly_label = QLabel("Hourly")
        hourly_label.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #64748b; margin-top: 4px;"
        )
        layout.addWidget(hourly_label)

        # Scrollable hourly cards
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll_area.setFixedHeight(140)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                background: white;
            }
            QScrollBar:horizontal {
                height: 8px;
                background: #f1f5f9;
            }
            QScrollBar::handle:horizontal {
                background: #94a3b8;
                border-radius: 4px;
                min-width: 40px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0;
            }
        """)

        self._hourly_container = QWidget()
        self._hourly_layout = QHBoxLayout(self._hourly_container)
        self._hourly_layout.setSpacing(8)
        self._hourly_layout.setContentsMargins(8, 8, 8, 8)
        self._hourly_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Pre-create 24 hourly cards
        self._hourly_cards: list[HourlyForecastCard] = []
        for _ in range(24):
            card = HourlyForecastCard()
            self._hourly_cards.append(card)
            self._hourly_layout.addWidget(card)

        scroll_area.setWidget(self._hourly_container)
        layout.addWidget(scroll_area)

    def set_day_data(
        self, forecast: dict, hourly_data: list[dict]
    ) -> None:
        """Populate this day's summary and hourly cards.

        Args:
            forecast: Daily forecast dict with max_temp, min_temp,
                      precipitation, weather_description.
            hourly_data: List of hourly dicts filtered to this day.
        """
        max_temp = forecast.get("max_temp", 0.0)
        self._high_card.set_value(f"{max_temp:.0f}°C")

        min_temp = forecast.get("min_temp", 0.0)
        self._low_card.set_value(f"{min_temp:.0f}°C")

        desc = forecast.get("weather_description", "—")
        self._weather_card.set_value(desc)

        precip = forecast.get("precipitation", 0.0)
        self._rain_card.set_value(f"{precip:.1f} mm")

        # Populate hourly cards
        for i, card in enumerate(self._hourly_cards):
            if i < len(hourly_data):
                card.set_data(hourly_data[i])
                card.setVisible(True)
            else:
                card.setVisible(False)

    def clear(self) -> None:
        """Reset all cards to placeholder state."""
        self._high_card.set_value("—")
        self._low_card.set_value("—")
        self._weather_card.set_value("—")
        self._rain_card.set_value("—")
        for card in self._hourly_cards:
            card.setVisible(False)


class WeatherWidget(QWidget):
    """Main weather display widget with API source tabs, city search, and forecast."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # Open-Meteo workers
        self._openmeteo_worker = WeatherWorker(self)
        self._openmeteo_worker.weather_ready.connect(self._on_weather_ready)
        self._openmeteo_worker.error.connect(self._on_error)

        self._openmeteo_forecast_worker = HourlyForecastWorker(self)
        self._openmeteo_forecast_worker.forecast_ready.connect(self._on_forecast_ready)
        self._openmeteo_forecast_worker.error.connect(self._on_forecast_error)

        # WeatherAPI workers
        self._weatherapi_worker = WeatherAPIWorker(self)
        self._weatherapi_worker.weather_ready.connect(self._on_weather_ready)
        self._weatherapi_worker.error.connect(self._on_error)

        self._weatherapi_forecast_worker = WeatherAPIForecastWorker(self)
        self._weatherapi_forecast_worker.forecast_ready.connect(self._on_forecast_ready)
        self._weatherapi_forecast_worker.forecast_ready.connect(self._on_5day_hourly_ready)
        self._weatherapi_forecast_worker.error.connect(self._on_forecast_error)

        # Daily forecast workers (both APIs)
        self._daily_forecast_worker = DailyForecastWorker(self)
        self._daily_forecast_worker.forecast_ready.connect(self._on_daily_forecast_ready)
        self._daily_forecast_worker.error.connect(self._on_daily_forecast_error)

        self._weatherapi_daily_worker = WeatherAPIDailyForecastWorker(self)
        self._weatherapi_daily_worker.forecast_ready.connect(self._on_daily_forecast_ready)
        self._weatherapi_daily_worker.error.connect(self._on_daily_forecast_error)

        self._current_api: str = "openmeteo"
        self._api_key: str = ""
        self._current_coords: Optional[dict] = None

        self._setup_ui()

    def set_api_key(self, api_key: str) -> None:
        """Set the WeatherAPI.com API key."""
        self._api_key = api_key
        if hasattr(self, '_api_key_label'):
            if api_key:
                self._api_key_label.setText("API Key: ✓ Set")
                self._api_key_label.setStyleSheet("font-size: 10px; color: #16a34a;")
            else:
                self._api_key_label.setText("API Key: Not set (get free key at weatherapi.com)")
                self._api_key_label.setStyleSheet("font-size: 10px; color: #94a3b8;")

    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # API Source tabs
        self._api_tabs = QTabWidget()
        self._api_tabs.setTabPosition(QTabWidget.TabPosition.North)
        self._api_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                background: white;
            }
            QTabBar::tab {
                padding: 6px 16px;
                margin-right: 2px;
                border: 1px solid #e2e8f0;
                border-bottom: none;
                border-radius: 6px 6px 0 0;
                background: #f8fafc;
                font-size: 11px;
                font-weight: 500;
                color: #64748b;
            }
            QTabBar::tab:selected {
                background: white;
                color: #1e293b;
                border-bottom: 1px solid white;
            }
            QTabBar::tab:hover { background: #e2e8f0; }
        """)

        openmeteo_tab = self._create_openmeteo_tab()
        self._api_tabs.addTab(openmeteo_tab, "Open-Meteo (Free)")

        weatherapi_tab = self._create_weatherapi_tab()
        self._api_tabs.addTab(weatherapi_tab, "WeatherAPI.com")

        self._api_tabs.currentChanged.connect(self._on_api_tab_changed)
        layout.addWidget(self._api_tabs)

        # Current weather stats
        stats_grid = QGridLayout()
        stats_grid.setSpacing(12)

        self._temp_card = StatCard("Temperature")
        self._feels_card = StatCard("Feels Like")
        self._humidity_card = StatCard("Humidity")
        self._wind_card = StatCard("Wind Speed")

        stats_grid.addWidget(self._temp_card, 0, 0)
        stats_grid.addWidget(self._feels_card, 0, 1)
        stats_grid.addWidget(self._humidity_card, 1, 0)
        stats_grid.addWidget(self._wind_card, 1, 1)

        layout.addLayout(stats_grid)

        # Weather conditions
        conditions_frame = QFrame()
        conditions_frame.setStyleSheet("""
            QFrame {
                background-color: #f0f9ff;
                border: 1px solid #bae6fd;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        conditions_layout = QVBoxLayout(conditions_frame)
        conditions_layout.setSpacing(4)

        conditions_title = QLabel("Current Conditions")
        conditions_title.setStyleSheet("font-size: 12px; font-weight: 600; color: #0369a1;")
        conditions_layout.addWidget(conditions_title)

        self._conditions_label = QLabel("—")
        self._conditions_label.setStyleSheet("font-size: 16px; font-weight: 500; color: #1e293b;")
        conditions_layout.addWidget(self._conditions_label)

        self._precipitation_label = QLabel("Precipitation: —")
        self._precipitation_label.setStyleSheet("font-size: 13px; color: #475569;")
        conditions_layout.addWidget(self._precipitation_label)

        layout.addWidget(conditions_frame)

        # 5-Day Forecast section
        daily_header = QLabel("5-Day Forecast")
        daily_header.setStyleSheet("font-size: 14px; font-weight: 600; color: #1e293b;")
        layout.addWidget(daily_header)

        self._day_tabs = QTabWidget()
        self._day_tabs.setTabPosition(QTabWidget.TabPosition.North)
        self._day_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                background: white;
            }
            QTabBar::tab {
                padding: 6px 14px;
                margin-right: 2px;
                border: 1px solid #e2e8f0;
                border-bottom: none;
                border-radius: 6px 6px 0 0;
                background: #f8fafc;
                font-size: 11px;
                font-weight: 500;
                color: #64748b;
            }
            QTabBar::tab:selected {
                background: white;
                color: #1e293b;
                border-bottom: 1px solid white;
            }
            QTabBar::tab:hover { background: #e2e8f0; }
        """)

        # Pre-create 5 day tabs
        self._day_tab_widgets: list[DailyForecastDayWidget] = []
        for _ in range(5):
            day_widget = DailyForecastDayWidget()
            self._day_tab_widgets.append(day_widget)
            self._day_tabs.addTab(day_widget, "—")

        layout.addWidget(self._day_tabs)

        # 24-Hour Forecast section
        forecast_header = QLabel("24-Hour Forecast")
        forecast_header.setStyleSheet("font-size: 14px; font-weight: 600; color: #1e293b;")
        layout.addWidget(forecast_header)

        # Scrollable forecast area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFixedHeight(160)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                background: white;
            }
            QScrollBar:horizontal {
                height: 8px;
                background: #f1f5f9;
            }
            QScrollBar::handle:horizontal {
                background: #94a3b8;
                border-radius: 4px;
                min-width: 40px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0;
            }
        """)

        self._forecast_container = QWidget()
        self._forecast_layout = QHBoxLayout(self._forecast_container)
        self._forecast_layout.setSpacing(8)
        self._forecast_layout.setContentsMargins(8, 8, 8, 8)
        self._forecast_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Add placeholder cards
        self._forecast_cards = []
        for i in range(24):
            card = HourlyForecastCard()
            self._forecast_cards.append(card)
            self._forecast_layout.addWidget(card)

        scroll_area.setWidget(self._forecast_container)
        layout.addWidget(scroll_area)

        # Status row
        status_row = QHBoxLayout()
        self._status_label = QLabel("Select a city to view weather")
        self._status_label.setStyleSheet("font-size: 12px; color: #64748b;")
        status_row.addWidget(self._status_label)
        status_row.addStretch()
        self._update_label = QLabel("")
        self._update_label.setStyleSheet("font-size: 12px; color: #64748b;")
        status_row.addWidget(self._update_label)
        layout.addLayout(status_row)

        # Trigger initial load
        self._on_city_changed()

    def _create_openmeteo_tab(self) -> QWidget:
        """Create the Open-Meteo tab with search and city selection."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Search row
        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        search_label = QLabel("Search:")
        search_label.setStyleSheet("font-size: 12px; font-weight: 500; color: #475569;")
        search_row.addWidget(search_label)

        self._openmeteo_search_input = QLineEdit()
        self._openmeteo_search_input.setPlaceholderText("Type city name...")
        # Uses global QLineEdit style — no inline override to keep dropdown palette consistent
        self._openmeteo_search_input.textChanged.connect(self._on_openmeteo_search_changed)
        search_row.addWidget(self._openmeteo_search_input, stretch=1)

        layout.addLayout(search_row)

        # City dropdown
        city_row = QHBoxLayout()
        city_row.setSpacing(8)

        city_label = QLabel("City:")
        city_label.setStyleSheet("font-size: 12px; font-weight: 500; color: #475569;")
        city_row.addWidget(city_label)

        self._openmeteo_city_combo = QComboBox()
        self._openmeteo_city_combo.setMinimumWidth(180)
        # Global QComboBox style — ensures dropdown colors match design system (#e2e8f0→#1e40af)

        self._populate_city_combo(self._openmeteo_city_combo, None)

        self._openmeteo_city_combo.currentIndexChanged.connect(self._on_city_changed)
        city_row.addWidget(self._openmeteo_city_combo, stretch=1)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                background-color: #1e40af;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #1e3a8a; }
            QPushButton:pressed { background-color: #172554; }
        """)
        refresh_btn.clicked.connect(self._on_refresh)
        city_row.addWidget(refresh_btn)

        layout.addLayout(city_row)

        return widget

    def _create_weatherapi_tab(self) -> QWidget:
        """Create the WeatherAPI tab with search functionality."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Search row
        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        search_label = QLabel("Search:")
        search_label.setStyleSheet("font-size: 12px; font-weight: 500; color: #475569;")
        search_row.addWidget(search_label)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Type city name...")
        # Uses global style
        self._search_input.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self._search_input, stretch=1)

        layout.addLayout(search_row)

        # City dropdown
        city_row = QHBoxLayout()
        city_row.setSpacing(8)

        city_label = QLabel("City:")
        city_label.setStyleSheet("font-size: 12px; font-weight: 500; color: #475569;")
        city_row.addWidget(city_label)

        self._weatherapi_city_combo = QComboBox()
        self._weatherapi_city_combo.setMinimumWidth(180)
        # Global style — no inline override

        self._populate_city_combo(self._weatherapi_city_combo, None)

        self._weatherapi_city_combo.currentIndexChanged.connect(self._on_city_changed)
        city_row.addWidget(self._weatherapi_city_combo, stretch=1)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                background-color: #1e40af;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #1e3a8a; }
            QPushButton:pressed { background-color: #172554; }
        """)
        refresh_btn.clicked.connect(self._on_refresh)
        city_row.addWidget(refresh_btn)

        layout.addLayout(city_row)

        # API key status
        self._api_key_label = QLabel("API Key: Not set (get free key at weatherapi.com)")
        self._api_key_label.setStyleSheet("font-size: 10px; color: #94a3b8;")
        layout.addWidget(self._api_key_label)

        return widget

    def _populate_city_combo(self, combo: QComboBox, filter_text: Optional[str]) -> None:
        """Populate city combo, optionally filtering by search text."""
        combo.blockSignals(True)
        combo.clear()

        cities = sorted(GHANA_CITIES.keys())
        if filter_text:
            filter_lower = filter_text.lower()
            cities = [c for c in cities if filter_lower in c.lower()]

        for city_name in cities:
            info = GHANA_CITIES[city_name]
            combo.addItem(f"{city_name} ({info['region']})", city_name)

        combo.blockSignals(False)

    def _on_api_tab_changed(self, index: int) -> None:
        """Handle API source tab change."""
        self._current_api = "openmeteo" if index == 0 else "weatherapi"
        self._on_city_changed()

    def _on_search_changed(self, text: str) -> None:
        """Handle WeatherAPI search input change."""
        self._populate_city_combo(self._weatherapi_city_combo, text if text else None)

    def _on_openmeteo_search_changed(self, text: str) -> None:
        """Handle Open-Meteo search input change."""
        self._populate_city_combo(self._openmeteo_city_combo, text if text else None)

    def _on_city_changed(self) -> None:
        """Handle city selection change."""
        if self._current_api == "openmeteo":
            city_name = self._openmeteo_city_combo.currentData()
        else:
            city_name = self._weatherapi_city_combo.currentData()

        if not city_name:
            return

        coords = get_city_coordinates(city_name)
        if not coords:
            return

        self._current_coords = coords

        # Fetch current weather
        if self._current_api == "openmeteo":
            self._status_label.setText(f"Fetching weather for {city_name}...")
            self._openmeteo_worker.set_params(
                latitude=coords["lat"],
                longitude=coords["lon"],
                city_name=city_name,
            )
            self._openmeteo_worker.start()

            # Fetch hourly forecast
            self._openmeteo_forecast_worker.set_params(
                latitude=coords["lat"],
                longitude=coords["lon"],
                hours=24,
            )
            self._openmeteo_forecast_worker.start()

            # Fetch 5-day daily forecast
            self._daily_forecast_worker.set_params(
                latitude=coords["lat"],
                longitude=coords["lon"],
                days=5,
            )
            self._daily_forecast_worker.start()

            # Fetch 5-day hourly forecast (for per-day hourly breakdown)
            self._openmeteo_5day_hourly_worker = HourlyForecastWorker(self)
            self._openmeteo_5day_hourly_worker.forecast_ready.connect(
                self._on_5day_hourly_ready
            )
            self._openmeteo_5day_hourly_worker.error.connect(
                self._on_daily_forecast_error
            )
            self._openmeteo_5day_hourly_worker.set_params(
                latitude=coords["lat"],
                longitude=coords["lon"],
                forecast_days=5,
            )
            self._openmeteo_5day_hourly_worker.start()
        else:
            if not self._api_key:
                self._status_label.setText("API key required. Set in Settings.")
                return
            self._status_label.setText(f"Fetching weather for {city_name}...")
            query = f"{coords['lat']},{coords['lon']}"
            self._weatherapi_worker.set_params(
                api_key=self._api_key,
                query=query,
                city_name=city_name,
            )
            self._weatherapi_worker.start()

            # Fetch 5-day daily forecast
            self._weatherapi_daily_worker.set_params(
                api_key=self._api_key,
                query=query,
                days=5,
            )
            self._weatherapi_daily_worker.start()

            # Fetch 5-day hourly forecast
            self._weatherapi_forecast_worker.set_params(
                api_key=self._api_key,
                query=query,
                days=5,
            )
            self._weatherapi_forecast_worker.start()

    def _on_refresh(self) -> None:
        """Handle refresh button click."""
        self._on_city_changed()

    def _on_weather_ready(self, data: dict) -> None:
        """Handle successful weather data fetch."""
        temp = data.get("temperature", 0.0)
        self._temp_card.set_value(f"{temp:.1f}°C")

        feels = data.get("feels_like", 0.0)
        self._feels_card.set_value(f"{feels:.1f}°C")

        humidity = data.get("humidity", 0)
        self._humidity_card.set_value(f"{humidity}%")

        wind_speed = data.get("wind_speed", 0.0)
        wind_dir_deg = data.get("wind_direction", 0.0)
        wind_dir = WeatherService.get_wind_direction_name(wind_dir_deg)
        self._wind_card.set_value(f"{wind_speed:.1f} km/h", f"Direction: {wind_dir}")

        weather_desc = data.get("weather_description", "Unknown")
        self._conditions_label.setText(weather_desc)

        precip = data.get("precipitation", 0.0)
        self._precipitation_label.setText(f"Precipitation: {precip:.1f} mm")

        self._status_label.setText("Weather data loaded")
        self._update_label.setText(datetime.now().strftime("%H:%M:%S"))

    def _on_forecast_ready(self, data: dict) -> None:
        """Handle successful forecast data fetch."""
        hourly = data.get("hourly", [])

        # Update forecast cards
        for i, card in enumerate(self._forecast_cards):
            if i < len(hourly):
                card.set_data(hourly[i])
                card.setVisible(True)
            else:
                card.setVisible(False)

    def _on_error(self, message: str) -> None:
        """Handle weather fetch error."""
        self._status_label.setText(f"Error: {message}")
        self._status_label.setStyleSheet("font-size: 12px; color: #dc2626;")
        self._temp_card.set_value("—")
        self._feels_card.set_value("—")
        self._humidity_card.set_value("—")
        self._wind_card.set_value("—")
        self._conditions_label.setText("Unable to load weather data")
        self._precipitation_label.setText("Precipitation: —")

    def _on_forecast_error(self, message: str) -> None:
        """Handle forecast fetch error."""
        # Silently fail for forecast - current weather is more important
        for card in self._forecast_cards:
            card.setVisible(False)

    def _on_daily_forecast_ready(self, data: dict) -> None:
        """Handle successful daily forecast data fetch."""
        from datetime import datetime

        self._daily_forecasts = data.get("forecasts", [])

        today = datetime.now().date()

        for i, tab in enumerate(self._day_tab_widgets):
            if i < len(self._daily_forecasts):
                fc = self._daily_forecasts[i]
                date_str = fc.get("date", "")
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    if dt.date() == today:
                        label = "Today"
                    else:
                        label = dt.strftime("%b %d")
                except ValueError:
                    label = date_str

                self._day_tabs.setTabText(i, label)
                self._day_tabs.setTabVisible(i, True)
            else:
                self._day_tabs.setTabVisible(i, False)

        # If we already have hourly data, populate the day tabs
        if hasattr(self, "_daily_hourly_data"):
            self._populate_day_tabs()

    def _on_5day_hourly_ready(self, data: dict) -> None:
        """Handle successful 5-day hourly forecast fetch."""
        self._daily_hourly_data = data.get("hourly", [])

        # If we already have daily forecasts, populate the day tabs
        if hasattr(self, "_daily_forecasts") and self._daily_forecasts:
            self._populate_day_tabs()

    def _populate_day_tabs(self) -> None:
        """Populate each day tab with its summary and hourly data."""
        from datetime import datetime

        today = datetime.now().date()

        for i, day_widget in enumerate(self._day_tab_widgets):
            if i < len(self._daily_forecasts):
                fc = self._daily_forecasts[i]
                date_str = fc.get("date", "")

                # Filter hourly data to this day
                day_hourly = [
                    h for h in self._daily_hourly_data
                    if h.get("time", "").startswith(date_str)
                ]

                day_widget.set_day_data(fc, day_hourly)
            else:
                day_widget.clear()

    def _on_daily_forecast_error(self, message: str) -> None:
        """Handle daily forecast fetch error."""
        for tab in self._day_tab_widgets:
            tab.clear()
