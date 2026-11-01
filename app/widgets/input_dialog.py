"""Frameless single-line text prompt.

``QInputDialog`` is a native window with an operating-system title bar.  The
only prompt in the app (renaming a history entry) uses this dialog instead,
so it shares the CivilQntify chrome with every other popup.
"""

from __future__ import annotations

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QWidget,
)

from app.widgets.frameless_dialog import FramelessDialog


class InputDialog(FramelessDialog):
    """Modal prompt with one line-edit field and OK / Cancel buttons."""

    # Transient blocking prompt: no window switcher (see FramelessDialog).
    switcher_enabled = False

    def __init__(
        self,
        parent: QWidget | None,
        *,
        title: str,
        label: str,
        initial: str = "",
    ) -> None:
        super().__init__(parent, title=title, controls="close")
        self.setModal(True)
        self._accepted = False

        root = self.content_layout
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(12)

        prompt = QLabel(label, self)
        prompt.setWordWrap(True)
        root.addWidget(prompt)

        self._edit = QLineEdit(initial, self)
        self._edit.setMinimumWidth(360)
        self._edit.selectAll()
        root.addWidget(self._edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel is not None:
            cancel.setObjectName("secondary")
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setDefault(True)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons, 0, Qt.AlignmentFlag.AlignRight)

        self.resize(440, self.sizeHint().height())

    # ── Public API ───────────────────────────────────────────────────────

    @property
    def text(self) -> str:
        return self._edit.text()

    @property
    def accepted(self) -> bool:
        return self._accepted

    @staticmethod
    def getText(
        parent: QWidget | None,
        title: str,
        label: str,
        initial: str = "",
    ) -> tuple[str, bool]:
        """Prompt for text; returns ``(text, accepted)`` like QInputDialog."""
        dialog = InputDialog(
            parent, title=title, label=label, initial=initial
        )
        dialog._edit.setFocus()
        dialog.exec()
        return dialog.text, dialog.accepted

    # ── Internals ────────────────────────────────────────────────────────

    def showEvent(self, event) -> None:  # noqa: N802 - Qt naming
        super().showEvent(event)
        QTimer.singleShot(0, self._edit.setFocus)

    def _on_accept(self) -> None:
        self._accepted = True
        self.accept()


__all__ = ["InputDialog"]
