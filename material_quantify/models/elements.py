"""Structural element models for material quantification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass
class StructuralElement:
    """A structural element with dimensions and quantity.

    All dimensions are in metres. Volume is computed as
    length × width × depth × quantity.

    Attributes:
        element_type: Type identifier (e.g. "footing", "column", "beam", "slab")
        length_m: Length in metres
        width_m: Width in metres
        depth_m: Depth / height / thickness in metres
        quantity: Number of identical elements (default 1)
    """

    element_type: str
    length_m: float
    width_m: float
    depth_m: float
    quantity: int = 1

    DIMENSION_LABELS: ClassVar[dict[str, tuple[str, str, str]]] = {
        "footing": ("Length", "Width", "Depth"),
        "column": ("Length", "Width", "Height"),
        "beam": ("Length", "Width", "Depth"),
        "slab": ("Length", "Width", "Thickness"),
        "wall": ("Length", "Height", "Thickness"),
        "custom": ("Dim 1", "Dim 2", "Dim 3"),
    }

    def __post_init__(self) -> None:
        if self.length_m <= 0 or self.width_m <= 0 or self.depth_m <= 0:
            raise ValueError(
                f"All dimensions must be positive: "
                f"L={self.length_m}, W={self.width_m}, D={self.depth_m}"
            )
        if self.quantity < 1:
            raise ValueError(f"Quantity must be >= 1, got {self.quantity}")
        self.element_type = self.element_type.lower().strip()

    @property
    def volume_per_element_m3(self) -> float:
        """Volume of a single element (m³)."""
        return self.length_m * self.width_m * self.depth_m

    @property
    def total_volume_m3(self) -> float:
        """Total volume for all identical elements (m³)."""
        return self.volume_per_element_m3 * self.quantity

    @property
    def dimension_labels(self) -> tuple[str, str, str]:
        """Human-readable dimension labels for this element type."""
        return self.DIMENSION_LABELS.get(
            self.element_type, self.DIMENSION_LABELS["custom"]
        )

    def summary_line(self) -> str:
        """One-line summary for display."""
        lbl = self.dimension_labels
        return (
            f"{self.element_type.title()} ({self.quantity}x): "
            f"{lbl[0]}={self.length_m:.3f}m, "
            f"{lbl[1]}={self.width_m:.3f}m, "
            f"{lbl[2]}={self.depth_m:.3f}m "
            f"= {self.total_volume_m3:.3f} m\u00b3"
        )
