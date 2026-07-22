"""Reusable info button widget — shows a brief explanation on click.

The info is displayed as a frameless in-app overlay (not a separate window).
It dismisses automatically when the user clicks elsewhere.
Long content is wrapped in a scroll area.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QEvent, QObject, QPoint
from PyQt6.QtGui import QCursor, QMouseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class _InfoOverlay(QWidget):
    """In-app overlay that dismisses on outside click."""

    _active: _InfoOverlay | None = None
    _filter: QObject | None = None

    def __init__(self, text: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMinimumWidth(260)
        self.setMaximumWidth(400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        html = text.replace("\n", "<br>").replace("  ", "&nbsp;&nbsp;")

        label = QLabel()
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setText(html)
        label.setStyleSheet(
            "QLabel {"
            "  background-color: #1e293b;"
            "  color: #e2e8f0;"
            "  border: 2px solid #3b82f6;"
            "  border-radius: 10px;"
            "  padding: 14px 18px;"
            "  font-size: 13px;"
            "}"
        )

        scroll = QScrollArea()
        scroll.setWidget(label)
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(360)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background-color: transparent; border: none; }"
        )
        layout.addWidget(scroll)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(Qt.GlobalColor.black)
        self.setGraphicsEffect(shadow)

    def mousePressEvent(self, event) -> None:
        """Consume clicks inside the overlay so they don't propagate."""
        event.accept()

    # ── class-level singleton management ──

    @classmethod
    def _ensure_app_filter(cls) -> None:
        if cls._filter is not None:
            return
        app = QApplication.instance()
        if app is None:
            return

        class _Filter(QObject):
            def eventFilter(self, obj: QObject, event: QEvent) -> bool:
                if cls._active is None:
                    return False
                t = event.type()
                if t in (
                    QEvent.Type.MouseButtonPress,
                    QEvent.Type.MouseButtonDblClick,
                ):
                    # Check if the click is inside the overlay
                    global_pos = QCursor.pos()
                    local = cls._active.mapFromGlobal(global_pos)
                    if not cls._active.rect().contains(local):
                        cls._dismiss_active()
                elif t == QEvent.Type.KeyPress:
                    cls._dismiss_active()
                return False

        cls._filter = _Filter(app)
        app.installEventFilter(cls._filter)

    @classmethod
    def _dismiss_active(cls) -> None:
        if cls._active is not None:
            w = cls._active
            cls._active = None
            w.close()

    @classmethod
    def show_overlay(cls, text: str, parent: QWidget, pos: QPoint) -> None:
        cls._dismiss_active()
        cls._ensure_app_filter()

        overlay = _InfoOverlay(text, parent)
        overlay.adjustSize()
        ow, oh = overlay.width(), overlay.height()

        x, y = pos.x() + 16, pos.y() + 4
        screen = parent.screen()
        if screen:
            g = screen.availableGeometry()
            if x + ow > g.right() - 10:
                x = pos.x() - ow - 16
            if y + oh > g.bottom() - 10:
                y = g.bottom() - oh - 10
            x = max(x, g.left() + 10)
            y = max(y, g.top() + 10)

        overlay.move(QPoint(x, y))
        QWidget.show(overlay)
        overlay.raise_()
        cls._active = overlay


class InfoButton(QPushButton):
    """A small circular 'i' button that shows an in-app overlay on click.

    Usage::

        btn = InfoButton("Enter the 28-day characteristic strength in MPa.")
        form_layout.addRow(MyLabel("Target Strength"), btn)
    """

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__("i", parent)
        self._info_text = text
        self.setObjectName("info-btn")
        self.setFixedSize(18, 18)
        self.setCursor(Qt.CursorShape.WhatsThisCursor)
        self.clicked.connect(self._show_overlay)

    def set_text(self, text: str) -> None:
        self._info_text = text

    def _find_main_window(self) -> QWidget | None:
        widget = self.parentWidget()
        while widget is not None:
            if widget.windowFlags() & Qt.WindowType.Window:
                return widget
            widget = widget.parentWidget()
        return None

    def _show_overlay(self) -> None:
        main_window = self._find_main_window()
        parent = main_window if main_window else self
        _InfoOverlay.show_overlay(self._info_text, parent, self.mapToGlobal(QPoint(0, 0)))
