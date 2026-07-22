"""QThread worker for non-blocking supplier price fetching.

Mirrors the weather worker pattern: runs :meth:`PriceSheetService.fetch_all`
off the UI thread and emits the resulting store map or an error string.
"""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from app.pricing.price_sheet_service import (
    PriceSheetError,
    PriceSheetService,
)


class PriceSheetWorker(QThread):
    """Background worker that fetches the live supplier price sheet."""

    stores_ready = pyqtSignal(dict)  # store_name -> {price_key: value}
    error = pyqtSignal(str)

    def __init__(self, service: PriceSheetService | None = None, parent=None) -> None:
        super().__init__(parent)
        self._service = service

    def set_service(self, service: PriceSheetService) -> None:
        self._service = service

    def run(self) -> None:
        if self._service is None:
            self.error.emit("Price service is not configured.")
            return
        try:
            stores = self._service.fetch_all()
            self.stores_ready.emit(stores)
        except PriceSheetError as exc:
            self.error.emit(str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            self.error.emit(f"Unexpected error fetching prices: {exc}")
