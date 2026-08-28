"""QThread worker for non-blocking material quantification."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from material_quantify import (
    MaterialQuantifier,
    MixRatioQuantifier,
    StructuralElement,
)
from material_quantify.models.bill import MaterialBill
from material_quantify.models.transfer_data import MixDesignTransferData


class QuantificationWorker(QThread):
    """Run material quantification in a background thread."""

    result_ready = pyqtSignal(object)  # MaterialBill
    error = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._method: str = "design_mix"  # "design_mix" or "mix_ratio"
        self._transfer_data: MixDesignTransferData | None = None
        self._overrides: dict[str, float] = {}
        self._ratio_quantifier: MixRatioQuantifier | None = None
        self._elements: list[StructuralElement] = []
        self._total_volume: float = 0.0
        self._wastage: float = 5.0
        self._mode: str = "volume"  # "volume" or "elements"

    def set_transfer_data(self, data: MixDesignTransferData) -> None:
        """Set the mix design transfer data."""
        self._method = "design_mix"
        self._transfer_data = data

    def set_overrides(self, overrides: dict[str, float]) -> None:
        """Set field overrides."""
        self._overrides = overrides

    def set_volume_mode(self, volume_m3: float, wastage: float) -> None:
        """Configure for total-volume quantification."""
        self._mode = "volume"
        self._total_volume = volume_m3
        self._wastage = wastage

    def set_elements_mode(
        self, elements: list[StructuralElement], wastage: float
    ) -> None:
        """Configure for element-based quantification."""
        self._mode = "elements"
        self._elements = elements
        self._wastage = wastage

    def set_ratio_volume_mode(
        self, quantifier: MixRatioQuantifier, volume_m3: float, wastage: float
    ) -> None:
        """Configure for mix-ratio total-volume quantification."""
        self._method = "mix_ratio"
        self._ratio_quantifier = quantifier
        self._mode = "volume"
        self._total_volume = volume_m3
        self._wastage = wastage

    def set_ratio_elements_mode(
        self,
        quantifier: MixRatioQuantifier,
        elements: list[StructuralElement],
        wastage: float,
    ) -> None:
        """Configure for mix-ratio element-based quantification."""
        self._method = "mix_ratio"
        self._ratio_quantifier = quantifier
        self._mode = "elements"
        self._elements = elements
        self._wastage = wastage

    def run(self) -> None:
        try:
            if self._method == "mix_ratio":
                if self._ratio_quantifier is None:
                    self.error.emit("No mix ratio quantifier configured.")
                    return
                if self._mode == "volume":
                    bill = self._ratio_quantifier.quantify_by_volume(
                        self._total_volume, self._wastage
                    )
                else:
                    bill = self._ratio_quantifier.quantify_by_elements(
                        self._elements, self._wastage
                    )
                self.result_ready.emit(bill)
                return

            if self._transfer_data is None:
                self.error.emit("No mix design data available.")
                return

            quantifier = MaterialQuantifier(self._transfer_data)

            if self._overrides:
                quantifier.override(**self._overrides)

            if self._mode == "volume":
                bill = quantifier.quantify_by_volume(
                    self._total_volume, self._wastage
                )
            else:
                bill = quantifier.quantify_by_elements(
                    self._elements, self._wastage
                )

            self.result_ready.emit(bill)
        except Exception as e:
            self.error.emit(str(e))
