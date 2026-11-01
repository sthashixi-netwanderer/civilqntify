"""Theme-matched custom title bar for frameless CivilQntify windows.

The native OS title bar is removed by ``FramelessWindowHint``; this widget
replaces it with the same clean-studio-light surface used by the rest of
the application (white bar, 1px rule, cobalt accent, 4px control radii).

It provides:

* the app identity lockup (icon, wordmark, tagline, version badge),
* a host area on the right for the Weather / Settings actions,
* minimise / maximise-restore / close controls drawn with QPainter so
  they stay crisp at any DPI and follow the theme tokens,
* native window dragging (``startSystemMove``) plus double-click
  maximise/restore and a graceful manual fallback.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QPoint, QRectF, QSize, Qt
from PyQt6.QtGui import (
    QColor,
    QIcon,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.version import BUILD_TAG

#: Height of the custom title bar (keeps the app compact but clickable).
TITLEBAR_HEIGHT = 46


class _TitleBarButton(QAbstractButton):
    """Flat painted window control (minimise / maximise / close)."""

    def __init__(self, kind: str, tooltip: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("titlebar-control")
        self.setFixedSize(QSize(40, 32))
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._kind = kind
        self._hovered = False

    def set_kind(self, kind: str) -> None:
        if kind != self._kind:
            self._kind = kind
            self.update()

    def enterEvent(self, event) -> None:  # noqa: N802 - Qt naming
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt naming
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    # ── Painting ─────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        active = self._hovered or self.isDown()
        close = self._kind == "close"
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        if close and active:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#991b1b" if self.isDown() else "#b91c1c"))
            painter.drawRoundedRect(rect, 4, 4)
            icon_color = QColor("#ffffff")
        elif active:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#d1d5db" if self.isDown() else "#e5e7eb"))
            painter.drawRoundedRect(rect, 4, 4)
            icon_color = QColor("#111827")
        else:
            icon_color = QColor("#4b5563")

        self._paint_glyph(painter, icon_color)

    def _paint_glyph(self, painter: QPainter, color: QColor) -> None:
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        pen = QPen(color, 1.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if self._kind == "minimize":
            painter.drawLine(
                QPoint(int(cx - 5), int(cy)), QPoint(int(cx + 5), int(cy))
            )
        elif self._kind == "maximize":
            painter.drawRect(QRectF(cx - 5.0, cy - 5.0, 10.0, 10.0))
        elif self._kind == "restore":
            # Front square plus the exposed top/right edges of the back one.
            painter.drawRect(QRectF(cx - 5.0, cy - 3.0, 8.0, 8.0))
            path = QPainterPath()
            path.moveTo(cx - 3.0, cy - 5.0)
            path.lineTo(cx + 5.0, cy - 5.0)
            path.lineTo(cx + 5.0, cy + 3.0)
            painter.drawPath(path)
        else:  # close
            painter.drawLine(
                QPoint(int(cx - 5), int(cy - 5)), QPoint(int(cx + 5), int(cy + 5))
            )
            painter.drawLine(
                QPoint(int(cx - 5), int(cy + 5)), QPoint(int(cx + 5), int(cy - 5))
            )


class TitleBar(QWidget):
    """Custom top bar that replaces the OS window decoration."""

    def __init__(
        self,
        window: QWidget,
        *,
        title: str = "CivilQntify",
        subtitle: str = "Concrete Mix Design",
        version: str = BUILD_TAG,
        icon_path: str | None = None,
        controls: str = "full",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._window = window
        self._drag_ready = False
        self._drag_press_global = QPoint()
        self._drag_window_pos = QPoint()
        self._manual_drag = False

        self.setObjectName("titlebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(TITLEBAR_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 0, 6, 0)
        root.setSpacing(10)

        # ── Brand lockup ─────────────────────────────────────────────────
        brand = QWidget(self)
        brand.setObjectName("titlebar-brand")
        brand.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        brand_layout = QVBoxLayout(brand)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(0)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)

        if icon_path:
            logo = QLabel(brand)
            logo.setObjectName("titlebar-logo")
            logo.setFixedSize(22, 22)
            logo.setPixmap(
                QIcon(icon_path).pixmap(
                    QSize(22, 22), self.devicePixelRatioF() or 1.0
                )
            )
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_row.addWidget(logo, 0, Qt.AlignmentFlag.AlignVCenter)
            title_row.addSpacing(2)

        name = QLabel(title, brand)
        name.setObjectName("titlebar-title")
        self._title_label = name
        title_row.addWidget(name, 0, Qt.AlignmentFlag.AlignVCenter)

        if version:
            version_label = QLabel(version, brand)
            version_label.setObjectName("titlebar-version")
            version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_row.addWidget(version_label, 0, Qt.AlignmentFlag.AlignVCenter)

        title_row.addStretch(1)
        brand_layout.addLayout(title_row)

        if subtitle:
            tagline = QLabel(subtitle.upper(), brand)
            tagline.setObjectName("titlebar-subtitle")
            brand_layout.addWidget(tagline)

        root.addWidget(brand, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addStretch(1)

        # ── Right-side action area (Weather / Settings added by caller) ──
        self._actions_layout = QHBoxLayout()
        self._actions_layout.setContentsMargins(0, 0, 0, 0)
        self._actions_layout.setSpacing(6)
        root.addLayout(self._actions_layout)

        divider = QFrame(self)
        divider.setObjectName("titlebar-divider")
        divider.setFixedSize(1, 20)
        divider.setVisible(False)
        self._divider = divider
        root.addSpacing(3)
        root.addWidget(divider)
        root.addSpacing(3)

        # ── Window controls ──────────────────────────────────────────────
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(2)

        self._btn_close = _TitleBarButton("close", "Close", self)
        self._btn_close.clicked.connect(self._window.close)
        controls_layout.addWidget(self._btn_close)

        if controls == "full":
            self._btn_min = _TitleBarButton("minimize", "Minimize", self)
            self._btn_max = _TitleBarButton("maximize", "Maximize", self)
            self._btn_min.clicked.connect(self._window.showMinimized)
            self._btn_max.clicked.connect(self._toggle_maximize)
            # Insert min/max before the close button.
            controls_layout.insertWidget(0, self._btn_min)
            controls_layout.insertWidget(1, self._btn_max)
        elif controls == "min-close":
            # Detached dialogs: minimize without maximize — dialogs are
            # resized via FramelessResizeHelper, never maximized.
            self._btn_min = _TitleBarButton("minimize", "Minimize", self)
            self._btn_min.clicked.connect(self._window.showMinimized)
            self._btn_max = None
            controls_layout.insertWidget(0, self._btn_min)
        else:
            self._btn_min = None
            self._btn_max = None

        root.addLayout(controls_layout)

        self.sync_window_state()

    # ── Public API ───────────────────────────────────────────────────────

    def add_action_widget(self, widget: QWidget) -> None:
        """Insert a theme-styled action button before the window controls."""
        self._actions_layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
        self._divider.setVisible(True)

    def set_title(self, title: str) -> None:
        """Update the title lockup (used when a dialog's window title changes)."""
        self._title_label.setText(title)

    def sync_window_state(self) -> None:
        """Refresh the maximise/restore glyph from the window state."""
        if self._btn_max is None:
            return
        maximized = self._window.isMaximized() or self._window.isFullScreen()
        self._btn_max.set_kind("restore" if maximized else "maximize")
        self._btn_max.setToolTip("Restore Down" if maximized else "Maximize")

    # ── Dragging ─────────────────────────────────────────────────────────

    def event(self, event: QEvent) -> bool:  # noqa: N802 - Qt naming
        """Cancel a manual drag when the platform steals the mouse grab."""
        if event.type() in (
            QEvent.Type.UngrabMouse,
            QEvent.Type.WindowDeactivate,
        ):
            if self._manual_drag:
                self._manual_drag = False
                try:
                    self.releaseMouse()
                except RuntimeError:
                    pass
        return super().event(event)

    def _toggle_maximize(self) -> None:
        if self._btn_max is None:
            return
        if self._window.isMaximized() or self._window.isFullScreen():
            self._window.showNormal()
        else:
            self._window.showMaximized()
        self.sync_window_state()

    def _restore_under_cursor(self, global_pos: QPoint) -> None:
        """Un-maximise and keep the cursor at the same relative x position."""
        width = max(self._window.width(), 1)
        ratio = (global_pos.x() - self._window.x()) / width
        self._window.showNormal()
        self.sync_window_state()
        new_width = self._window.width()
        self._window.move(
            global_pos.x() - int(new_width * ratio),
            global_pos.y() - self.height() // 2,
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_ready = True
            self._drag_press_global = event.globalPosition().toPoint()
            self._drag_window_pos = self._window.pos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._manual_drag:
            if not (event.buttons() & Qt.MouseButton.LeftButton):
                # The release was lost (e.g. the grab was rejected by the
                # platform); stop dragging instead of following plain hover.
                self._manual_drag = False
                self.releaseMouse()
                return
            delta = event.globalPosition().toPoint() - self._drag_press_global
            self._window.move(self._drag_window_pos + delta)
            event.accept()
            return

        if not self._drag_ready or not (event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return

        global_pos = event.globalPosition().toPoint()
        if (global_pos - self._drag_press_global).manhattanLength() < (
            QApplication.startDragDistance()
        ):
            return

        self._drag_ready = False
        if self._window.isMaximized() or self._window.isFullScreen():
            self._restore_under_cursor(global_pos)
            self._drag_press_global = global_pos
            self._drag_window_pos = self._window.pos()

        handle = self._window.windowHandle()
        if handle is not None:
            try:
                if handle.startSystemMove():
                    return
            except (RuntimeError, TypeError):
                pass

        # Manual fallback for platforms without system move support.
        self._manual_drag = True
        self.grabMouse()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag_ready = False
        if self._manual_drag:
            self._manual_drag = False
            self.releaseMouse()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_maximize()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
