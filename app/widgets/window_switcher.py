"""In-app switching between the main window and the detached dialogs.

Every CivilQntify window is frameless (``FramelessWindowHint``) and dialogs
are independent top-levels that can sit beside or behind the main window,
so a platform's Alt+Tab is the only built-in way to move between them —
and it is unreliable for frameless windows on some window managers. This
module is the in-app counterpart, available from both directions:

* :func:`app_windows` enumerates the main window plus every visible
  modeless detached dialog,
* :func:`switch_to_window` restores, raises and focuses one of them,
* :func:`cycle_app_windows` steps through the list — wired to
  Ctrl+Tab / Ctrl+Shift+Tab on the main window and every dialog by
  :func:`add_window_switch_shortcuts`.
"""

from __future__ import annotations

from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication, QWidget

#: ``MainWindow`` sets this object name; it marks the switch list's anchor.
MAIN_WINDOW_OBJECT_NAME = "main-window"


def app_windows() -> list[QWidget]:
    """All switchable windows: the main window first, then every visible
    modeless detached dialog.

    Modal shells (``MessageBox``/``InputDialog`` Q&A, any exec'd dialog)
    are excluded: while one is open the rest of the application is
    blocked, so listing it as a switch target would promise something
    that cannot happen.
    """
    app = QApplication.instance()
    if app is None:
        return []
    # Local import: frameless_dialog imports this module at module level.
    from app.widgets.frameless_dialog import FramelessDialog

    mains: list[QWidget] = []
    dialogs: list[QWidget] = []
    for widget in app.topLevelWidgets():
        if not widget.isWindow() or not widget.isVisible():
            continue
        if isinstance(widget, FramelessDialog):
            if not widget.isModal():
                dialogs.append(widget)
        elif widget.objectName() == MAIN_WINDOW_OBJECT_NAME:
            mains.append(widget)
    return mains + dialogs


def switch_to_window(window: QWidget) -> None:
    """Bring *window* to the front: un-minimize, raise, focus."""
    if window.isMinimized():
        window.showNormal()
    window.show()
    window.raise_()
    window.activateWindow()


def cycle_app_windows(
    step: int = 1, current: QWidget | None = None
) -> QWidget | None:
    """Move focus ``step`` entries through :func:`app_windows`.

    Positive steps move forward (main window → dialogs), negative ones
    backward. *current* defaults to the application's active window; the
    focused window is returned, or ``None`` when there is nothing to
    switch to (fewer than two windows).
    """
    windows = app_windows()
    if len(windows) < 2:
        return None
    if current is None:
        current = QApplication.activeWindow()
    try:
        index = windows.index(current)
    except ValueError:
        # The active window is not switchable (e.g. a modal shell on top):
        # enter the list from the edge the step direction points at.
        index = 0 if step > 0 else len(windows) - 1
    target = windows[(index + step) % len(windows)]
    switch_to_window(target)
    return target


def add_window_switch_shortcuts(window: QWidget) -> None:
    """Bind Ctrl+Tab / Ctrl+Shift+Tab (the Next/Previous Child standard
    keys) to app-wide window cycling while *window* is active."""
    for keys, step in (
        (QKeySequence.StandardKey.NextChild, 1),
        (QKeySequence.StandardKey.PreviousChild, -1),
    ):
        shortcut = QShortcut(QKeySequence(keys), window)
        shortcut.activated.connect(
            lambda step=step: cycle_app_windows(step)  # type: ignore[misc]
        )
