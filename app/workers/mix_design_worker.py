"""QThread worker for non-blocking concrete mix design calculations."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from concrete_mix import design_mix_simple, MixDesignResult


class MixDesignWorker(QThread):
    """Run mix design calculation in a background thread."""

    result_ready = pyqtSignal(object)  # MixDesignResult
    error = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._kwargs: dict = {}

    def set_params(self, kwargs: dict) -> None:
        """Store calculation parameters for next run."""
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = design_mix_simple(**self._kwargs)
            self.result_ready.emit(result)
        except Exception as e:
            self.error.emit(str(e))
