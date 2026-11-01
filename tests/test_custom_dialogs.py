"""Frameless message/input dialog behaviour.

The application replaces native ``QMessageBox`` / ``QInputDialog`` windows
with the shared CivilQntify chrome.  These tests pin the parts call sites
depend on: the standard-button return values, the Escape/close mapping, the
fixed-size layout and the text-prompt API.
"""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QEvent, QTimer, Qt
from PyQt6.QtWidgets import QApplication, QLayout, QMessageBox, QWidget

from app.styles import STYLESHEET
from app.widgets.frameless_dialog import FramelessDialog, open_detached
from app.widgets.input_dialog import InputDialog
from app.widgets.message_dialog import MessageBox, MessageDialog
from app.widgets.title_bar import TitleBar


@pytest.fixture(scope="module")
def qt():
    app = QApplication.instance() or QApplication([])
    previous = app.styleSheet()
    app.setStyleSheet(STYLESHEET)
    yield app
    app.setStyleSheet(previous)


def _click_modal(standard: QMessageBox.StandardButton) -> None:
    """Click ``standard`` in the modal dialog once it is shown."""
    remaining = [200]

    def attempt() -> None:
        dialog = QApplication.activeModalWidget()
        if dialog is None or not hasattr(dialog, "_buttons"):
            remaining[0] -= 1
            assert remaining[0] > 0, "modal dialog never appeared"
            QTimer.singleShot(5, attempt)
            return
        for button, value in dialog._buttons.items():
            if value == standard:
                button.click()
                return
        raise AssertionError(f"button {standard!r} not present")

    QTimer.singleShot(5, attempt)


def _close_modal() -> None:
    """Close the modal dialog through its custom title bar."""
    remaining = [200]

    def attempt() -> None:
        dialog = QApplication.activeModalWidget()
        if dialog is None or not hasattr(dialog, "titlebar"):
            remaining[0] -= 1
            assert remaining[0] > 0, "modal dialog never appeared"
            QTimer.singleShot(5, attempt)
            return
        dialog.titlebar._btn_close.click()

    QTimer.singleShot(5, attempt)


def test_message_dialog_uses_frameless_chrome(qt):
    dialog = MessageDialog(
        None, kind="information", title="No Data", text="Nothing to show."
    )
    try:
        assert isinstance(dialog, FramelessDialog)
        assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
        assert dialog.windowTitle() == "No Data"
        assert (
            dialog.layout().sizeConstraint()
            == QLayout.SizeConstraint.SetFixedSize
        )
    finally:
        dialog.deleteLater()


def test_information_returns_ok(qt):
    _click_modal(QMessageBox.StandardButton.Ok)
    result = MessageBox.information(None, "No Data", "Nothing to show.")
    assert result == QMessageBox.StandardButton.Ok


def test_question_close_maps_to_no(qt):
    _close_modal()
    result = MessageBox.question(
        None,
        "Confirm Delete",
        "Delete this record?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    assert result == QMessageBox.StandardButton.No


def test_warning_default_button_is_honoured(qt):
    dialog = MessageDialog(
        None,
        kind="warning",
        title="Clear All History",
        text="This permanently deletes every record.",
        buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        default_button=QMessageBox.StandardButton.No,
    )
    try:
        defaults = {
            standard: button.isDefault()
            for button, standard in dialog._buttons.items()
        }
        assert defaults[QMessageBox.StandardButton.No] is True
        assert defaults[QMessageBox.StandardButton.Yes] is False
    finally:
        dialog.deleteLater()


def test_input_dialog_accepts_text(qt):
    def accept() -> None:
        dialog = QApplication.activeModalWidget()
        if dialog is None:
            QTimer.singleShot(5, accept)
            return
        dialog._edit.setText("M25 Site Mix")
        dialog._on_accept()

    QTimer.singleShot(5, accept)
    text, ok = InputDialog.getText(
        None, "Rename History Entry", "Custom name:", "Old name"
    )
    assert (text, ok) == ("M25 Site Mix", True)


def test_input_dialog_cancel_reports_not_accepted(qt):
    _close_modal()
    _, ok = InputDialog.getText(
        None, "Rename History Entry", "Custom name:", "Old name"
    )
    assert ok is False


# ── Detached independent windows ─────────────────────────────────────────


def test_frameless_dialog_flags_allow_taskbar_and_behind_main(qt):
    """Detached dialogs are Qt.Window top-levels: own taskbar entry,
    draggable beside/behind the main window, minimizable via the title
    bar. (Qt.WindowType.Dialog *includes* the Window bit, so only the
    dialog-specific bit — Dialog & ~Window — must be absent.)"""
    dialog = FramelessDialog(None, title="Detached")
    try:
        flags = dialog.windowFlags()
        assert flags & Qt.WindowType.Window
        assert not flags & (Qt.WindowType.Dialog & ~Qt.WindowType.Window)
        assert flags & Qt.WindowType.FramelessWindowHint
        # "min-close" chrome: minimize without maximize.
        assert dialog.titlebar._btn_min is not None
        assert dialog.titlebar._btn_max is None
    finally:
        dialog.deleteLater()


def test_title_bar_controls_variants(qt):
    """full → min+max, min-close → min only, close → neither."""
    window = QWidget()
    full = TitleBar(window, controls="full")
    min_close = TitleBar(window, controls="min-close")
    close_only = TitleBar(window, controls="close")
    assert full._btn_min is not None and full._btn_max is not None
    assert min_close._btn_min is not None and min_close._btn_max is None
    assert close_only._btn_min is None and close_only._btn_max is None


def test_open_detached_is_modeless_and_deletes_on_close(qt):
    """open_detached shows the dialog without blocking the parent and
    frees it when closed (WA_DeleteOnClose)."""
    from PyQt6 import sip

    parent = QWidget()
    dialog = FramelessDialog(parent, title="Trial Workbook")
    open_detached(dialog)
    try:
        assert dialog.isVisible()
        assert QApplication.activeModalWidget() is None
        assert parent.isEnabled()
        assert dialog.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    finally:
        dialog.close()
        QApplication.processEvents()
    assert sip.isdeleted(dialog)
    parent.deleteLater()


def _visible_detached(title: str) -> list[FramelessDialog]:
    """Every currently visible detached window carrying *title*."""
    return [
        widget for widget in QApplication.topLevelWidgets()
        if isinstance(widget, FramelessDialog)
        and widget.isVisible()
        and widget.windowTitle() == title
    ]


def _flush_deferred_deletes() -> None:
    """Deliver pending ``deleteLater`` events.

    Deferred deletes posted outside a running event loop are not picked
    up by :meth:`QApplication.processEvents`, so flush them explicitly
    (inside the app the real event loop does this on its own).
    """
    QApplication.processEvents()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_open_detached_focuses_existing_same_dialog(qt):
    """Re-opening the same dialog (same class and title) raises the first
    window instead of stacking a duplicate; the freshly built instance is
    discarded before it is ever shown."""
    from PyQt6 import sip

    parent = QWidget()
    first = FramelessDialog(parent, title="Trial Workbook")
    open_detached(first)

    duplicate = FramelessDialog(parent, title="Trial Workbook")
    open_detached(duplicate)
    _flush_deferred_deletes()

    try:
        assert sip.isdeleted(duplicate)
        assert _visible_detached("Trial Workbook") == [first]
        assert not first.isMinimized()
        # A third click after the original closes must open a fresh one.
        first.close()
        _flush_deferred_deletes()
        third = FramelessDialog(parent, title="Trial Workbook")
        open_detached(third)
        QApplication.processEvents()
        try:
            assert third.isVisible()
            assert _visible_detached("Trial Workbook") == [third]
        finally:
            third.close()
            QApplication.processEvents()
    finally:
        parent.deleteLater()


def test_open_detached_keeps_parameterised_dialogs_separate(qt):
    """Same class but different window titles (e.g. a history detail per
    record) are distinct dialogs and may coexist on screen."""
    from PyQt6 import sip

    parent = QWidget()
    first = FramelessDialog(parent, title="History #1 — DOE Trial")
    second = FramelessDialog(parent, title="History #2 — DOE Trial")
    open_detached(first)
    open_detached(second)
    try:
        assert first.isVisible() and second.isVisible()
        # Re-clicking one record's button still focuses that record's
        # window rather than opening a duplicate of it.
        duplicate = FramelessDialog(parent, title="History #1 — DOE Trial")
        open_detached(duplicate)
        _flush_deferred_deletes()
        assert sip.isdeleted(duplicate)
        assert _visible_detached("History #1 — DOE Trial") == [first]
        assert second.isVisible()
    finally:
        first.close()
        second.close()
        _flush_deferred_deletes()
    parent.deleteLater()


def test_open_detached_restores_minimized_singleton(qt):
    """Triggering the opener of a minimized dialog un-minimizes and
    focuses it instead of opening a second window."""
    parent = QWidget()
    first = FramelessDialog(parent, title="Weather Data")
    open_detached(first)
    first.setWindowState(Qt.WindowState.WindowMinimized)
    assert first.isMinimized()

    duplicate = FramelessDialog(parent, title="Weather Data")
    open_detached(duplicate)
    _flush_deferred_deletes()

    try:
        assert first.isVisible()
        assert not first.isMinimized()
        assert _visible_detached("Weather Data") == [first]
    finally:
        first.close()
        _flush_deferred_deletes()
    parent.deleteLater()
