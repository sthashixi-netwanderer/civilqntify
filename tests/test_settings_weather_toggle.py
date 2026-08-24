"""Tests for the Weather toolbar-button visibility setting.

Verifies that:
- The preference defaults to hidden (preserves prior behaviour).
- Toggling persists across singleton resets and emits a signal.
- SettingsDialog round-trips the checkbox state through Apply.
"""

from __future__ import annotations

import os
import tempfile

# Isolate QSettings storage BEFORE any Qt/app import so tests never touch
# the developer's real CivilQntify settings.
_TMP_CONFIG = tempfile.mkdtemp(prefix="cq_weather_toggle_test_")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["XDG_CONFIG_HOME"] = _TMP_CONFIG
os.environ["HOME"] = _TMP_CONFIG

import pytest  # noqa: E402

qapp = None  # set in fixture


@pytest.fixture()
def qt():
    global qapp
    if qapp is None:
        from PyQt6.QtWidgets import QApplication

        qapp = QApplication.instance() or QApplication([])
    yield qapp


@pytest.fixture()
def fresh_prefs(qt):
    """Reset the UnitPreferences singleton against a clean QSettings store."""
    import app.unit_preferences as up_mod

    settings = up_mod.get_unit_prefs()._settings
    settings.clear()
    up_mod._instance = None
    yield up_mod.get_unit_prefs()
    up_mod._instance = None


def test_weather_button_hidden_by_default(fresh_prefs):
    assert fresh_prefs.weather_button_visible() is False


def test_set_visibility_persists_and_emits(fresh_prefs):
    events: list[bool] = []
    fresh_prefs.weather_button_changed.connect(events.append)

    fresh_prefs.set_weather_button_visible(True)
    assert events == [True]

    # Simulate an app restart: rebuild the singleton from QSettings.
    import app.unit_preferences as up_mod

    up_mod._instance = None
    assert up_mod.get_unit_prefs().weather_button_visible() is True

    # No duplicate signal when value is unchanged.
    fresh_prefs.set_weather_button_visible(True)
    assert events == [True]


def test_settings_dialog_round_trip(fresh_prefs, qt):
    from app.widgets.settings_dialog import SettingsDialog

    fresh_prefs.set_weather_button_visible(False)
    dialog = SettingsDialog(fresh_prefs)
    assert dialog._show_weather_check.isChecked() is False

    dialog._show_weather_check.setChecked(True)
    dialog._apply()

    assert fresh_prefs.weather_button_visible() is True

    reopened = SettingsDialog(fresh_prefs)
    assert reopened._show_weather_check.isChecked() is True


def _click_apply(qt, dlg):
    """Click the real Apply button so production wiring is exercised."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    dlg.show()
    QTest.mouseClick(
        dlg._btn_apply, Qt.MouseButton.LeftButton
    )
    qt.processEvents()


def test_toolbar_button_updates_instantly_when_shown(fresh_prefs, qt):
    """Toggling ON must show the button live — no restart required."""
    from app.main import MainWindow
    from app.widgets.settings_dialog import SettingsDialog

    fresh_prefs.set_weather_button_visible(False)
    win = MainWindow()
    win.show()
    qt.processEvents()
    try:
        assert win._btn_weather.isVisibleTo(win) is False

        dlg = SettingsDialog(win.unit_prefs, parent=win)
        dlg._show_weather_check.setChecked(True)
        _click_apply(qt, dlg)

        assert win.unit_prefs.weather_button_visible() is True
        assert win._btn_weather.isVisible() is True
        assert win._action_weather.isVisible() is True
    finally:
        win.close()


def test_toolbar_button_updates_instantly_when_hidden(fresh_prefs, qt):
    """Toggling OFF must hide the button live — no restart required."""
    from app.main import MainWindow
    from app.widgets.settings_dialog import SettingsDialog

    fresh_prefs.set_weather_button_visible(True)
    win = MainWindow()
    win.show()
    qt.processEvents()
    try:
        assert win._btn_weather.isVisible() is True

        dlg = SettingsDialog(win.unit_prefs, parent=win)
        dlg._show_weather_check.setChecked(False)
        _click_apply(qt, dlg)

        assert win.unit_prefs.weather_button_visible() is False
        assert win._btn_weather.isVisible() is False
        assert win._action_weather.isVisible() is False
    finally:
        win.close()
