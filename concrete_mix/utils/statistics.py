"""Statistical helpers for concrete mix design.

Distribution functions come from scipy, the established scientific library
(see requirements.txt). No hand-rolled approximations are used here.
"""

from __future__ import annotations

from scipy.stats import norm


def defective_k_factor(defective_rate: float) -> float:
    """Return the statistical 'k' factor (Z-score) for a defective rate.

    k is the standard-normal quantile (percent-point / probit function) at
    cumulative probability ``(1 - p)``, where ``p`` is the defective
    proportion — i.e. the margin multiplier in ``M = k × s`` used by
    BRE 331:1997 §4.4 / BS 5328 target-strength calculations.

    Args:
        defective_rate: Allowed defectives, EITHER as a percentage in
            ``[1, 100)`` (e.g. ``5`` or ``2.5``) OR as a decimal proportion
            in ``(0, 1)`` (e.g. ``0.05`` or ``0.025``). Values in ``(0, 1)``
            are read as proportions and values in ``[1, 100)`` as
            percentages — so a sub-1% rate must be passed as a proportion
            (``0.005``, not ``0.5``, which reads as 50% defectives).

    Returns:
        Precise floating-point k, e.g. ≈ ``1.6448536270`` for 5% and
        ≈ ``1.8807936082`` for 3% defectives (last-ulp may vary by
        scipy/libm build). Callers that need the standard's quoted
        precision round afterwards (BRE 331 works to 2dp).

    Raises:
        ValueError: if the rate is not in ``(0, 1)`` ∪ ``[1, 100)``.
    """
    rate = float(defective_rate)
    if 0.0 < rate < 1.0:
        p = rate
    elif 1.0 <= rate < 100.0:
        p = rate / 100.0
    else:
        raise ValueError(
            f"Defective rate {defective_rate!r} is not usable — pass a "
            f"proportion in (0, 1) or a percentage in [1, 100)."
        )
    return float(norm.ppf(1.0 - p))
