"""In-app switching between the main window and the detached dialogs.

Pins the window-switcher contract: the switch list is main window first,
then every visible modeless dialog; modal Q&A shells never appear;
Ctrl+Tab / Ctrl+Shift+Tab (or an explicit call) raises and focuses the
next/previous window; and the settings / report-preview dialogs are
genuinely modeless so switching to them and back is possible at all.
"""

from __future__ import annotations

import os
import tempfile

# Isolate QSettings storage BEFORE any Qt/app import so tests never touch
# the developer's real CivilQntify settings.
_TMP_CONFIG = tempfile.mkdtemp(prefix="cq_window_switcher_test_")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["XDG_CONFIG_HOME"] = _TMP_CONFIG
os.environ["HOME"] = _TMP_CONFIG

import pytest  # noqa: E402
from PyQt6.QtCore import QEvent, Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from app.widgets.frameless_dialog import FramelessDialog, open_detached  # noqa: E402
from app.widgets.message_dialog import MessageDialog  # noqa: E402
from app.widgets.report_preview_dialog import (  # noqa: E402
    ReportPreviewDialog,
)
from app.widgets.settings_dialog import SettingsDialog  # noqa: E402
from app.widgets.window_switcher import (  # noqa: E402
    app_windows,
    cycle_app_windows,
    switch_to_window,
)


@pytest.fixture(scope="module")
def qt():
    app = QApplication.instance() or QApplication([])
    yield app


def _flush_deferred_deletes() -> None:
    """Deliver pending ``deleteLater`` events (no-op in a live app loop)."""
    QApplication.processEvents()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _close_and_delete(*widgets) -> None:
    for widget in widgets:
        widget.close()
        widget.deleteLater()
    _flush_deferred_deletes()


def test_app_windows_orders_main_first_then_dialogs(qt):
    """The switch list anchors on the main window; only visible, modeless
    detached dialogs follow it."""
    from app.main import MainWindow

    win = MainWindow()
    win.show()
    first = FramelessDialog(None, title="Switch A")
    second = FramelessDialog(None, title="Switch B")
    open_detached(first)
    open_detached(second)
    hidden = FramelessDialog(None, title="Switch Hidden")  # never opened

    try:
        windows = app_windows()
        assert win in windows and first in windows and second in windows
        # Main window anchors the list; Qt does not guarantee the order
        # of the dialogs among themselves, only that they follow it.
        assert windows.index(win) < windows.index(first)
        assert windows.index(win) < windows.index(second)
        assert hidden not in windows
    finally:
        _close_and_delete(win, first, second, hidden)


def test_switch_to_window_unminimizes_and_raises(qt):
    win = FramelessDialog(None, title="Switch Target")
    open_detached(win)
    try:
        win.setWindowState(Qt.WindowState.WindowMinimized)
        assert win.isMinimized()
        switch_to_window(win)
        assert win.isVisible()
        assert not win.isMinimized()
    finally:
        _close_and_delete(win)


def test_cycle_steps_forward_and_backward(qt):
    from app.main import MainWindow

    win = MainWindow()
    win.show()
    first = FramelessDialog(None, title="Cycle A")
    second = FramelessDialog(None, title="Cycle B")
    open_detached(first)
    open_detached(second)

    try:
        windows = app_windows()
        i = windows.index(win)
        # Forward from the main window; wraps around at the end.
        assert cycle_app_windows(1, current=win) is windows[(i + 1) % len(windows)]
        assert cycle_app_windows(1, current=windows[-1]) is windows[0]
        # Backward from the main window; wraps to the last dialog.
        assert cycle_app_windows(-1, current=win) is windows[i - 1]
    finally:
        _close_and_delete(win, first, second)


def test_cycle_is_noop_with_single_window(qt, monkeypatch):
    import app.widgets.window_switcher as ws

    win = FramelessDialog(None, title="Only Window")
    open_detached(win)
    try:
        monkeypatch.setattr(ws, "app_windows", lambda: [win])
        assert ws.cycle_app_windows(1, current=win) is None
        assert ws.cycle_app_windows(-1, current=win) is None
    finally:
        _close_and_delete(win)


def test_modal_qa_shells_are_not_listed(qt):
    """Transient blocking Q&A: no title-bar switcher, and never a switch
    target (the rest of the app is blocked while one is open)."""
    dialog = MessageDialog(
        None, kind="information", title="QA Shell", text="Nothing to show."
    )
    try:
        assert not hasattr(dialog, "_btn_windows")
        dialog.show()
        QApplication.processEvents()
        assert dialog not in app_windows()
    finally:
        _close_and_delete(dialog)


def test_settings_and_report_preview_are_modeless(qt):
    """Regression: both once called setModal(True), which blocked the main
    window entirely and made switching impossible. open_detached's
    contract is an independent, modeless window."""
    import app.unit_preferences as up_mod

    settings = SettingsDialog(up_mod.get_unit_prefs())
    preview = ReportPreviewDialog()
    try:
        assert not settings.isModal()
        assert not preview.isModal()
    finally:
        _close_and_delete(settings, preview)
