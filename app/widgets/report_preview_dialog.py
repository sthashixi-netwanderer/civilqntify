"""Report preview dialog with PDF export capability.

Displays an HTML report in a styled dialog with:
- QTextBrowser for HTML rendering (no QtWebEngine dependency)
- Print/Export button
- Close button
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


class ReportPreviewDialog(QDialog):
    """Modal dialog for previewing HTML reports before PDF export."""

    def __init__(self, parent=None, title: str = "Report Preview") -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(900, 700)
        self.resize(1000, 800)
        self.setModal(True)

        self._html_content: str = ""
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Action bar
        action_bar = QWidget()
        action_bar.setObjectName("dialog-action-bar")
        action_bar.setFixedHeight(50)
        action_bar_layout = QHBoxLayout(action_bar)
        action_bar_layout.setContentsMargins(16, 8, 16, 8)

        title_label = QLabel("Report Preview")
        title_label.setObjectName("dialog-title")
        action_bar_layout.addWidget(title_label)

        action_bar_layout.addStretch()

        # Export button
        self._btn_export = QPushButton("Export PDF")
        self._btn_export.setFixedHeight(32)
        self._btn_export.clicked.connect(self._on_export)
        action_bar_layout.addWidget(self._btn_export)

        # Close button
        self._btn_close = QPushButton("Close")
        self._btn_close.setObjectName("secondary")
        self._btn_close.setFixedHeight(32)
        self._btn_close.clicked.connect(self.close)
        action_bar_layout.addWidget(self._btn_close)

        layout.addWidget(action_bar)

        # Web view (using QTextBrowser as fallback when QWebEngine is unavailable)
        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(False)
        layout.addWidget(self._browser)

    def set_html(self, html: str) -> None:
        """Set the HTML content to display."""
        self._html_content = html
        self._browser.setHtml(html)

    def set_export_callback(self, callback) -> None:
        """Set a callback function to be called when export is clicked."""
        self._export_callback = callback

    def _on_export(self) -> None:
        """Handle export button click."""
        if hasattr(self, "_export_callback") and self._export_callback:
            self._export_callback()
        self.close()
