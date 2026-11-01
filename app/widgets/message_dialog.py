"""Frameless drop-in replacement for ``QMessageBox``.

The application uses the theme-matched :class:`FramelessDialog` chrome for
every window it owns.  ``QMessageBox`` is a native top-level window, so its
operating-system title bar looks out of place next to the main window and the
custom dialogs.  :class:`MessageBox` mirrors the static ``QMessageBox`` API
(``information`` / ``warning`` / ``critical`` / ``question``) while rendering
the same message content inside the CivilQntify title bar.

Call sites can keep their existing code by importing the class under the
familiar name::

    from app.widgets.message_dialog import MessageBox as QMessageBox

``MessageBox.StandardButton`` is the real ``QMessageBox.StandardButton``
enum, so button masks and return-value comparisons work unchanged.
"""

from __future__ import annotations

from collections.abc import Iterable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractButton,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMessageBox,
    QStyle,
    QWidget,
)

from app.widgets.frameless_dialog import FramelessDialog

_StandardButton = QMessageBox.StandardButton

_ICONS = {
    "information": QStyle.StandardPixmap.SP_MessageBoxInformation,
    "warning": QStyle.StandardPixmap.SP_MessageBoxWarning,
    "critical": QStyle.StandardPixmap.SP_MessageBoxCritical,
    "question": QStyle.StandardPixmap.SP_MessageBoxQuestion,
}

#: Order in which combined button masks are rendered.  Qt's platform style
#: still decides the final left-to-right order inside the button box.
_BUTTON_ORDER: tuple[_StandardButton, ...] = (
    _StandardButton.Ok,
    _StandardButton.Yes,
    _StandardButton.No,
    _StandardButton.Cancel,
    _StandardButton.Close,
)

_ROLES = {
    _StandardButton.Ok: QDialogButtonBox.ButtonRole.AcceptRole,
    _StandardButton.Yes: QDialogButtonBox.ButtonRole.YesRole,
    _StandardButton.No: QDialogButtonBox.ButtonRole.NoRole,
    _StandardButton.Cancel: QDialogButtonBox.ButtonRole.RejectRole,
    _StandardButton.Close: QDialogButtonBox.ButtonRole.RejectRole,
}

_LABELS = {
    _StandardButton.Ok: "OK",
    _StandardButton.Yes: "Yes",
    _StandardButton.No: "No",
    _StandardButton.Cancel: "Cancel",
    _StandardButton.Close: "Close",
}

_SECONDARY = frozenset(
    {_StandardButton.No, _StandardButton.Cancel, _StandardButton.Close}
)


def _button_mask(
    buttons: _StandardButton | int,
) -> list[_StandardButton]:
    """Expand a ``StandardButton`` bit mask into ordered buttons."""
    mask = _StandardButton(buttons)
    selected = [button for button in _BUTTON_ORDER if mask & button]
    return selected or [_StandardButton.Ok]


def _escape_button(
    buttons: Iterable[_StandardButton],
    default: _StandardButton,
) -> _StandardButton:
    """Button returned when the dialog is dismissed (Esc / title-bar close)."""
    if default != _StandardButton.NoButton:
        return default
    for candidate in (
        _StandardButton.Cancel,
        _StandardButton.No,
        _StandardButton.Close,
    ):
        if candidate in buttons:
            return candidate
    return next(iter(buttons))


class MessageDialog(FramelessDialog):
    """Message window using the CivilQntify title bar."""

    # Transient blocking Q&A: no window switcher (see FramelessDialog).
    switcher_enabled = False

    def __init__(
        self,
        parent: QWidget | None,
        *,
        kind: str,
        title: str,
        text: str,
        buttons: _StandardButton | int = _StandardButton.Ok,
        default_button: _StandardButton = _StandardButton.NoButton,
    ) -> None:
        super().__init__(parent, title=title, controls="close")
        self.setModal(True)
        self._selected = _StandardButton.NoButton

        selected_buttons = _button_mask(buttons)
        self._escape = _escape_button(selected_buttons, default_button)

        root = self.content_layout
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(18)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(16)

        icon = QLabel(self)
        pixmap = self.style().standardIcon(
            _ICONS.get(kind, _ICONS["information"])
        ).pixmap(48, 48)
        icon.setPixmap(pixmap)
        icon.setFixedSize(48, 48)
        icon.setAlignment(Qt.AlignmentFlag.AlignTop)
        body.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)

        message = QLabel(text, self)
        message.setObjectName("message-dialog-text")
        message.setWordWrap(True)
        message.setTextFormat(Qt.TextFormat.PlainText)
        message.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        message.setMinimumWidth(360)
        message.setMaximumWidth(520)
        body.addWidget(message, 1, Qt.AlignmentFlag.AlignTop)

        root.addLayout(body)

        button_box = QDialogButtonBox(self)
        button_box.setCenterButtons(False)
        self._buttons: dict[QAbstractButton, _StandardButton] = {}

        for standard in selected_buttons:
            button = button_box.addButton(
                _LABELS[standard], _ROLES[standard]
            )
            if standard in _SECONDARY:
                button.setObjectName("secondary")
            button.setAutoDefault(False)
            self._buttons[button] = standard

        default = default_button
        if default == _StandardButton.NoButton:
            default = next(
                (
                    standard
                    for standard in selected_buttons
                    if standard not in _SECONDARY
                ),
                selected_buttons[0],
            )
        for button, standard in self._buttons.items():
            if standard == default:
                button.setDefault(True)
                button.setAutoDefault(True)
                break

        button_box.clicked.connect(self._on_button_clicked)
        root.addWidget(
            button_box, 0, Qt.AlignmentFlag.AlignRight
        )

        self.layout().setSizeConstraint(
            QLayout.SizeConstraint.SetFixedSize
        )

    # ── Result handling ──────────────────────────────────────────────────

    @property
    def selected_button(self) -> _StandardButton:
        """The button chosen by the user (or the dismiss button)."""
        return self._selected

    def _on_button_clicked(self, button: QAbstractButton) -> None:
        self._selected = self._buttons.get(
            button, _StandardButton.NoButton
        )
        if self._selected in _SECONDARY:
            self.reject()
        else:
            self.accept()

    def reject(self) -> None:  # noqa: N802 - Qt naming
        """Return the escape button when dismissed without a click."""
        if self._selected == _StandardButton.NoButton:
            self._selected = self._escape
        super().reject()


def _show(
    parent: QWidget | None,
    *,
    kind: str,
    title: str,
    text: str,
    buttons: _StandardButton | int,
    default_button: _StandardButton,
) -> _StandardButton:
    dialog = MessageDialog(
        parent,
        kind=kind,
        title=title,
        text=text,
        buttons=buttons,
        default_button=default_button,
    )
    dialog.exec()
    return dialog.selected_button


class MessageBox:
    """Static API compatible with the ``QMessageBox`` calls in the app."""

    StandardButton = _StandardButton

    @staticmethod
    def information(
        parent: QWidget | None,
        title: str,
        text: str,
        buttons: _StandardButton = _StandardButton.Ok,
        defaultButton: _StandardButton = _StandardButton.NoButton,
    ) -> _StandardButton:
        return _show(
            parent,
            kind="information",
            title=title,
            text=text,
            buttons=buttons,
            default_button=defaultButton,
        )

    @staticmethod
    def warning(
        parent: QWidget | None,
        title: str,
        text: str,
        buttons: _StandardButton = _StandardButton.Ok,
        defaultButton: _StandardButton = _StandardButton.NoButton,
    ) -> _StandardButton:
        return _show(
            parent,
            kind="warning",
            title=title,
            text=text,
            buttons=buttons,
            default_button=defaultButton,
        )

    @staticmethod
    def critical(
        parent: QWidget | None,
        title: str,
        text: str,
        buttons: _StandardButton = _StandardButton.Ok,
        defaultButton: _StandardButton = _StandardButton.NoButton,
    ) -> _StandardButton:
        return _show(
            parent,
            kind="critical",
            title=title,
            text=text,
            buttons=buttons,
            default_button=defaultButton,
        )

    @staticmethod
    def question(
        parent: QWidget | None,
        title: str,
        text: str,
        buttons: _StandardButton = (
            _StandardButton.Yes | _StandardButton.No
        ),
        defaultButton: _StandardButton = _StandardButton.NoButton,
    ) -> _StandardButton:
        return _show(
            parent,
            kind="question",
            title=title,
            text=text,
            buttons=buttons,
            default_button=defaultButton,
        )
