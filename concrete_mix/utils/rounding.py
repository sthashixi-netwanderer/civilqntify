"""Shared rounding policies used across the design codes."""

from __future__ import annotations

import math


def ceil_to_one_decimal(value: float) -> float:
    """Round a value UP to the nearest 0.1 (app target-strength policy).

    The standards state no target-strength rounding rule (DOE C2 expresses
    its worked examples to two significant figures, which the app treats as
    a conservative upward rounding). Rounding up, never down, avoids
    under-designing while keeping the reported target to one decimal place.
    The epsilon absorbs float noise just above an exact tenth.
    """
    return math.ceil(value * 10.0 - 1e-9) / 10.0
