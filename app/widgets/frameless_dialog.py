"""Reusable frameless dialog shell with CivilQntify window chrome.

All application dialogs inherit from :class:`FramelessDialog` so they use
the same custom title bar as the main window instead of the operating
system decoration. The shell provides:

* a theme-matched :class:`~app.widgets.title_bar.TitleBar` (dialog title,
  app icon, close control, optional full min/max controls),
* a content area whose layout subclasses populate instead of adding a
  layout directly to the ``QDialog``,
* edge-resize support through :class:`FramelessResizeHelper`,
* window-title propagation, so the existing ``setWindowTitle`` calls in
  each dialog automatically update the custom bar.

Dialogs are single-instance on screen: opening an already-open dialog
through :func:`open_detached` focuses the existing window instead of
stacking a duplicate.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout, QWidget

from app.paths import resource_path
from app.widgets.frameless import FramelessResizeHelper
from app.widgets.title_bar import TitleBar
from app.widgets.window_switcher import add_window_switch_shortcuts


class FramelessDialog(QDialog):
    """QDialog with the CivilQntify custom title bar and frameless edges.

    Dialogs are independent top-level windows (``Qt.WindowType.Window``):
    each carries its own taskbar entry, can be dragged to any monitor and
    arranged beside or behind the main window. Open them through
    :func:`open_detached` so they run modeless with ``WA_DeleteOnClose``
    lifetime instead of blocking in :meth:`QDialog.exec`, and so only one
    window per dialog (same class and title) is kept on screen.
    """

    #: Modal Q&A shells (:class:`MessageDialog`, :class:`InputDialog`) opt
    #: out of the Ctrl+Tab window cycling — a transient confirmation has
    #: no other window to switch to (while it is open the rest of the app
    #: is blocked anyway).
    switcher_enabled: bool = True

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        title: str = "",
        subtitle: str = "CivilQntify",
        controls: str = "min-close",
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setSizeGripEnabled(False)
        self.setWindowTitle(title)

        self._titlebar = TitleBar(
            self,
            title=title or "CivilQntify",
            subtitle=subtitle,
            version="",
            icon_path=str(resource_path("icon.png")),
            controls=controls,
        )
        self.titlebar = self._titlebar

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._titlebar)

        content = QWidget(self)
        content.setObjectName("dialog-content")
        content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._content = content
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        root.addWidget(content, 1)

        self._frameless_helper = FramelessResizeHelper(self)

        if type(self).switcher_enabled:
            # Ctrl+Tab / Ctrl+Shift+Tab cycle between the main window and
            # the open detached dialogs.
            add_window_switch_shortcuts(self)

    # ── Public API ───────────────────────────────────────────────────────

    @property
    def content_layout(self) -> QVBoxLayout:
        """Layout that dialog subclasses populate with their own content."""
        return self._content_layout

    def setWindowTitle(self, title: str) -> None:  # noqa: N802 - Qt naming
        """Propagate title changes to the custom title bar."""
        super().setWindowTitle(title)
        titlebar = getattr(self, "_titlebar", None)
        if titlebar is not None and title:
            titlebar.set_title(title)


def _visible_singleton_match(dialog: QDialog) -> QDialog | None:
    """Return the already-visible detached window equivalent to *dialog*.

    Two detached dialogs count as the same window when they share a class
    and a window title. Fixed-title dialogs (settings, weather, the trial
    mix workbooks, the compliance checks) therefore collapse to a single
    instance, while parameterised dialogs whose title carries their
    content (the per-tab report previews, :class:`HistoryDetailDialog`
    per record) only collapse with their own content.
    """
    cls = type(dialog)
    title = dialog.windowTitle()
    for widget in QApplication.topLevelWidgets():
        if (
            widget is not dialog
            and type(widget) is cls
            and widget.isVisible()
            and widget.windowTitle() == title
        ):
            return widget
    return None


def open_detached(dialog: QDialog) -> None:
    """Show a dialog as an independent, modeless top-level window.

    The dialog keeps its parent for ownership and initial centering but is
    no longer application-modal: the main window stays usable while it is
    open. ``WA_DeleteOnClose`` frees the C++ object when the user closes
    the window, so call sites may drop their local reference immediately.
    Blocking Q&A helpers (``MessageBox.*``, ``InputDialog.getText``) do not
    go through here — a confirmation must wait for its answer.

    Only one window of the same dialog is kept on screen: when a dialog
    with the same class and window title is already visible, it is
    restored, raised and focused instead, and the freshly built *dialog*
    is discarded before it is ever shown (see
    :func:`_visible_singleton_match`). Call sites must therefore finish
    wiring the dialog (``set_html``, signal connections, …) *before*
    calling this function.
    """
    existing = _visible_singleton_match(dialog)
    if existing is not None:
        if existing.isMinimized():
            existing.showNormal()
        existing.raise_()
        existing.activateWindow()
        dialog.deleteLater()
        return
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    dialog.show()
