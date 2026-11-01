"""Frameless window resize support.

A window using ``Qt.WindowType.FramelessWindowHint`` loses the native
operating-system border, and with it the OS-provided resize grips.  This
helper restores that behaviour without bringing the native title bar back:

* an application event filter hit-tests the outer :data:`RESIZE_MARGIN`
  pixels of the window and sets the matching resize cursor,
* a left press in that margin asks the window manager for a native resize
  (``QWindow.startSystemResize``) so X11/Wayland/Windows keep their own
  snapping and constraints,
* when the platform cannot start a system resize, a manual geometry
  fallback keeps the feature working everywhere (including offscreen).

The helper is intentionally window-agnostic and only observes events that
belong to its own window; every other application event is ignored.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, QPoint, QRect, Qt
from PyQt6.QtWidgets import QApplication, QWidget

#: Width of the invisible resize band around the window, in pixels.
RESIZE_MARGIN = 6


class FramelessResizeHelper(QObject):
    """Enable edge resizing for a frameless top-level widget."""

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self._window = window
        self._manual_edges = Qt.Edge(0)
        self._manual_start_global = QPoint()
        self._manual_start_geometry = QRect()
        self._mouse_grabbed = False

        # Cursor currently forced on a child widget while hovering an edge.
        self._cursor_widget: QWidget | None = None
        self._saved_cursor = None
        self._cursor_edges = Qt.Edge(0)

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        # QWidget only emits hover mouse-move events when mouse tracking is
        # enabled. Edge hover feedback therefore needs tracking on every
        # descendant; new children are picked up via ChildAdded below.
        self.enable_hover_tracking()

    # ── Hover tracking ────────────────────────────────────────────────────

    def enable_hover_tracking(self) -> None:
        """Ensure the window and all descendants report unclicked moves."""
        self._enable_tracking(self._window)

    def _enable_tracking(self, widget: QWidget) -> None:
        try:
            widget.setMouseTracking(True)
        except RuntimeError:
            return
        for child in widget.findChildren(QWidget):
            try:
                child.setMouseTracking(True)
            except RuntimeError:
                continue

    # ── Edge detection & cursor feedback ──────────────────────────────────

    def _edges_at(self, global_pos: QPoint) -> Qt.Edge:
        """Return which window edges are under *global_pos*."""
        if self._window.isMaximized() or self._window.isFullScreen():
            return Qt.Edge(0)
        if self._window.minimumSize() == self._window.maximumSize():
            return Qt.Edge(0)
        pos = self._window.mapFromGlobal(global_pos)
        rect = self._window.rect()
        if not rect.contains(pos):
            return Qt.Edge(0)

        edges = Qt.Edge(0)
        # A fixed axis gets no cursor/edge: the window manager would refuse
        # the resize anyway, so do not advertise a grip that cannot move.
        if self._window.minimumWidth() != self._window.maximumWidth():
            if pos.x() < RESIZE_MARGIN:
                edges |= Qt.Edge.LeftEdge
            elif pos.x() >= rect.width() - RESIZE_MARGIN:
                edges |= Qt.Edge.RightEdge
        if self._window.minimumHeight() != self._window.maximumHeight():
            if pos.y() < RESIZE_MARGIN:
                edges |= Qt.Edge.TopEdge
            elif pos.y() >= rect.height() - RESIZE_MARGIN:
                edges |= Qt.Edge.BottomEdge
        return edges

    @staticmethod
    def _cursor_for_edges(edges: Qt.Edge) -> Qt.CursorShape:
        corner_diag = (
            Qt.Edge.LeftEdge | Qt.Edge.TopEdge,
            Qt.Edge.RightEdge | Qt.Edge.BottomEdge,
        )
        corner_anti = (
            Qt.Edge.RightEdge | Qt.Edge.TopEdge,
            Qt.Edge.LeftEdge | Qt.Edge.BottomEdge,
        )
        if edges in corner_diag:
            return Qt.CursorShape.SizeFDiagCursor
        if edges in corner_anti:
            return Qt.CursorShape.SizeBDiagCursor
        if edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge):
            return Qt.CursorShape.SizeHorCursor
        return Qt.CursorShape.SizeVerCursor

    def _restore_hover_cursor(self) -> None:
        if self._cursor_widget is None:
            return
        try:
            if self._saved_cursor is not None:
                self._cursor_widget.setCursor(self._saved_cursor)
            else:
                self._cursor_widget.unsetCursor()
        except RuntimeError:
            # The widget was destroyed while the cursor was forced.
            pass
        self._cursor_widget = None
        self._saved_cursor = None
        self._cursor_edges = Qt.Edge(0)

    def _update_hover_cursor(self, widget: QWidget, edges: Qt.Edge) -> None:
        if not edges:
            self._restore_hover_cursor()
            return
        if widget is self._cursor_widget and edges == self._cursor_edges:
            return
        self._restore_hover_cursor()
        self._cursor_widget = widget
        self._saved_cursor = widget.cursor()
        self._cursor_edges = edges
        try:
            widget.setCursor(self._cursor_for_edges(edges))
        except RuntimeError:
            self._cursor_widget = None
            self._saved_cursor = None

    # ── Manual resize fallback ────────────────────────────────────────────

    def _begin_manual_resize(self, edges: Qt.Edge, global_pos: QPoint) -> None:
        self._manual_edges = edges
        self._manual_start_global = global_pos
        self._manual_start_geometry = self._window.geometry()

    def _perform_manual_resize(self, global_pos: QPoint) -> None:
        delta = global_pos - self._manual_start_global
        geo = QRect(self._manual_start_geometry)
        min_w = max(self._window.minimumWidth(), 1)
        min_h = max(self._window.minimumHeight(), 1)

        if self._manual_edges & Qt.Edge.LeftEdge:
            geo.setLeft(min(geo.left() + delta.x(), geo.right() - min_w + 1))
        elif self._manual_edges & Qt.Edge.RightEdge:
            geo.setRight(max(geo.left() + min_w - 1, geo.right() + delta.x()))

        if self._manual_edges & Qt.Edge.TopEdge:
            geo.setTop(min(geo.top() + delta.y(), geo.bottom() - min_h + 1))
        elif self._manual_edges & Qt.Edge.BottomEdge:
            geo.setBottom(max(geo.top() + min_h - 1, geo.bottom() + delta.y()))

        self._window.setGeometry(geo)

    def _end_manual_resize(self) -> None:
        if not self._manual_edges:
            return
        self._manual_edges = Qt.Edge(0)
        if self._mouse_grabbed:
            self._mouse_grabbed = False
            try:
                self._window.releaseMouse()
            except RuntimeError:
                pass

    # ── Event filter ──────────────────────────────────────────────────────

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        window = getattr(self, "_window", None)
        if window is None or not isinstance(obj, QWidget):
            return False
        try:
            if obj.window() is not window:
                return False
        except RuntimeError:
            # The C++ side was already destroyed (application shutdown).
            return False

        event_type = event.type()

        if event_type == QEvent.Type.ChildAdded:
            child = event.child()
            if isinstance(child, QWidget) and obj.window() is self._window:
                self._enable_tracking(child)
            return False

        if event_type == QEvent.Type.Show and obj is self._window:
            self.enable_hover_tracking()
            return False

        if event_type == QEvent.Type.MouseButtonPress:
            if event.button() != Qt.MouseButton.LeftButton:
                return False
            global_pos = event.globalPosition().toPoint()
            edges = self._edges_at(global_pos)
            if not edges:
                return False

            self._restore_hover_cursor()
            native = False
            handle = self._window.windowHandle()
            if handle is not None:
                try:
                    native = handle.startSystemResize(edges)
                except (RuntimeError, TypeError):
                    native = False
            if not native:
                # No window-manager resize loop: track the drag ourselves.
                # Grab the mouse so moves keep arriving when the cursor
                # leaves the window bounds mid-drag.
                self._begin_manual_resize(edges, global_pos)
                try:
                    self._window.grabMouse()
                    self._mouse_grabbed = True
                except RuntimeError:
                    self._mouse_grabbed = False
            # Consume the press so the widget underneath never sees a click
            # in the resize band.
            return True

        if event_type == QEvent.Type.MouseMove:
            if self._manual_edges:
                if not (event.buttons() & Qt.MouseButton.LeftButton):
                    self._end_manual_resize()
                    return False
                self._perform_manual_resize(event.globalPosition().toPoint())
                return True
            if event.buttons() == Qt.MouseButton.NoButton:
                # Mouse-move events propagate from the deepest child up the
                # parent chain; always target the actual widget under the
                # cursor so the resize cursor is not repeatedly moved to an
                # ancestor (which the child would override with its own).
                local = self._window.mapFromGlobal(event.globalPosition().toPoint())
                target = self._window.childAt(local) or self._window
                self._update_hover_cursor(
                    target, self._edges_at(event.globalPosition().toPoint())
                )
            return False

        if event_type == QEvent.Type.MouseButtonRelease:
            if self._manual_edges:
                self._end_manual_resize()
                return True
            return False

        if event_type == QEvent.Type.UngrabMouse:
            # Another grab superseded ours; stop treating moves as a drag.
            self._end_manual_resize()
            return False

        if event_type in (QEvent.Type.Leave, QEvent.Type.WindowDeactivate):
            self._restore_hover_cursor()
            if event_type == QEvent.Type.WindowDeactivate:
                self._end_manual_resize()

        return False
