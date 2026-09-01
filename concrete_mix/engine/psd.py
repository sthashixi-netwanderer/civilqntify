"""Particle-size distribution (PSD) calculations from sieve-analysis data.

The user enters only the **mass retained on each sieve** (raw lab data). This
module derives every secondary quantity:

- percent retained on each sieve
- cumulative percent retained
- percent passing each sieve
- Fineness Modulus (FM) — ACI 211.1-22 §4.3.5 / ASTM C136
- characteristic sizes D10, D30, D60 (log-linear interpolation of the
  passing curve) and the uniformity/coefficient-of-curvature indices
  Cu = D60/D10, Cc = D30²/(D60·D10)

No Qt dependency — pure functions and a dataclass, fully unit-testable.

Reference standards (per AGENTS.md):
  - ACI 211.1-22 §4.3.5 — Fineness modulus definition and standard sieve
    series (halving openings).
  - IS 383:2016 — grading zones / coarse aggregate grading (Table 7).
  - ASTM D6913 / C136 — sieve analysis of soils/aggregates.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Standard-specific sieve sets (mm), coarsest → finest.
# ---------------------------------------------------------------------------
# IS 383 fine aggregate grading zones use the 10 mm top sieve.
IS_FINE_SIEVES: list[float] = [
    10.0, 4.75, 2.36, 1.18, 0.600, 0.300, 0.150
]

# ASTM C33/C33M Table 1 uses the 9.5 mm (3/8 in.) top sieve.
ASTM_FINE_SIEVES: list[float] = [
    9.5, 4.75, 2.36, 1.18, 0.600, 0.300, 0.150
]

# Every IS sieve designation shown in IS 383:2016 Table 7.
IS_COARSE_SIEVES: list[float] = [
    80.0, 63.0, 40.0, 20.0, 16.0, 12.5, 10.0, 4.75, 2.36
]

# Every SI laboratory-sieve column in ASTM C33/C33M Table 2. Unspecified
# cells remain available for laboratory input but are omitted from the
# corresponding grading-band mapping and conformance checks.
ASTM_COARSE_SIEVES: list[float] = [
    100.0,
    90.0,
    75.0,
    63.0,
    50.0,
    37.5,
    25.0,
    19.0,
    12.5,
    9.5,
    4.75,
    2.36,
    1.18,
    0.300,
]

STANDARD_SIEVES_BY_CODE: dict[str, dict[str, list[float]]] = {
    "is383": {
        "fine": IS_FINE_SIEVES,
        "coarse": IS_COARSE_SIEVES,
    },
    "astm_c33": {
        "fine": ASTM_FINE_SIEVES,
        "coarse": ASTM_COARSE_SIEVES,
    },
}

# Backward-compatible aliases for existing engine callers. The UI uses
# STANDARD_SIEVES_BY_CODE so it never combines one standard's sieve set with
# the other standard's grading limits.
FINE_SIEVES = IS_FINE_SIEVES
COARSE_SIEVES = ASTM_COARSE_SIEVES
STANDARD_SIEVES: dict[str, list[float]] = {
    "fine": FINE_SIEVES,
    "coarse": COARSE_SIEVES,
}

# Sieves used for the ACI 211.1-22 §4.3.5 fineness modulus sum. The sum of
# cumulative percentages retained on these six sieves divided by 100 yields
# the FM (ASTM C136 procedure). Public so the PSD display and the psd-link
# bridge cannot drift away from the computation.
FM_SIEVES: frozenset[float] = frozenset(
    {0.150, 0.300, 0.600, 1.18, 2.36, 4.75}
)

# Backward-compatible private alias used within this module.
_FM_SIEVES: set[float] = set(FM_SIEVES)


@dataclass
class PSDResult:
    """Computed particle-size distribution for one sieve analysis.

    All lists are aligned with ``sieve_sizes`` (coarsest → finest). The
    optional ``pan_mass`` is included in the total but has no sieve size.
    """

    sieve_sizes: list[float]
    mass_retained: list[float]
    pan_mass: float
    total_mass: float
    percent_retained: list[float]
    cumulative_percent_retained: list[float]
    percent_passing: list[float]
    fineness_modulus: float | None
    d10: float | None
    d30: float | None
    d60: float | None
    uniformity_coefficient: float | None
    coefficient_of_curvature: float | None
    # Per-sieve band conformance: True where %passing is inside the band.
    conforms: list[bool] = field(default_factory=list)

    @property
    def all_conform(self) -> bool:
        """True if every checked sieve is inside its band limit."""
        return bool(self.conforms) and all(self.conforms)

    @property
    def pct_passing_600um(self) -> float | None:
        """Percentage passing the 600 µm (0.600 mm) sieve for BRE 331 (DOE)."""
        for s, p in zip(self.sieve_sizes, self.percent_passing):
            if abs(s - 0.600) < 1e-4:
                return round(p, 1)
        # Only interpolate for fine-aggregate stacks (top sieve <= 10 mm spanning 0.600 mm)
        if self.sieve_sizes and max(self.sieve_sizes) <= 10.0 and min(self.sieve_sizes) <= 0.600 <= max(self.sieve_sizes):
            return _interpolate_percent_passing(self.sieve_sizes, self.percent_passing, 0.600)
        return None


def compute_psd(
    mass_retained: list[float],
    sieve_sizes: list[float],
    pan_mass: float = 0.0,
    compute_fineness_modulus: bool = True,
) -> PSDResult:
    """Compute the full particle-size distribution from raw sieve masses.

    Args:
        mass_retained: Mass (g) retained on each sieve, aligned with
            *sieve_sizes* (coarsest → finest). Zero/empty entries are treated
            as 0.0 g.
        sieve_sizes: Sieve opening sizes in mm (coarsest → finest), e.g.
            ``FINE_SIEVES`` or ``COARSE_SIEVES``.
        pan_mass: Mass (g) passing the finest sieve (the pan catch).
        compute_fineness_modulus: Whether the fineness modulus belongs to
            the result. The FM is a fine-aggregate quantity consumed by
            ACI 211.1-22 §4.3.5 and restricted by ASTM C33/C33M Clauses
            6.2/6.4; it is not a requirement of IS 383:2016 (grading
            zones) or of any coarse-aggregate analysis, so callers on
            those standards pass ``False`` and get ``fineness_modulus=None``.

    Returns:
        A :class:`PSDResult`. If the total mass is zero, all derived
        quantities are zero/``None``.

    Raises:
        ValueError: if ``len(mass_retained) != len(sieve_sizes)`` or if any
            mass is negative.
    """
    if len(mass_retained) != len(sieve_sizes):
        raise ValueError(
            f"mass_retained ({len(mass_retained)}) must match sieve_sizes "
            f"({len(sieve_sizes)})"
        )
    if any(m < 0 for m in mass_retained) or pan_mass < 0:
        raise ValueError("Mass values cannot be negative")

    masses = [float(m) for m in mass_retained]
    pan = float(pan_mass)
    total = sum(masses) + pan

    if total <= 0:
        return PSDResult(
            sieve_sizes=list(sieve_sizes),
            mass_retained=masses,
            pan_mass=pan,
            total_mass=0.0,
            percent_retained=[0.0] * len(masses),
            cumulative_percent_retained=[0.0] * len(masses),
            percent_passing=[0.0] * len(masses),
            fineness_modulus=None,
            d10=None,
            d30=None,
            d60=None,
            uniformity_coefficient=None,
            coefficient_of_curvature=None,
            conforms=[],
        )

    pct_retained = [m / total * 100.0 for m in masses]
    cum_retained: list[float] = []
    running = 0.0
    for p in pct_retained:
        running += p
        cum_retained.append(running)
    pct_passing = [100.0 - c for c in cum_retained]

    # Fineness modulus (ACI 211.1-22 §4.3.5):
    #   FM = Σ cumulative % retained on {0.150, 0.30, 0.60, 1.18, 2.36, 4.75}
    #         / 100
    # Only meaningful for fine aggregate; computed if those sieves are
    # present AND the caller's standard uses an FM (ASTM C33/C33M
    # Clauses 6.2/6.4 — IS 383:2016 grades by zone instead, and coarse
    # aggregates carry no FM requirement).
    fm: float | None = None
    if compute_fineness_modulus:
        fm_sieves_present = [s for s in sieve_sizes if s in _FM_SIEVES]
        if len(fm_sieves_present) == len(_FM_SIEVES):
            fm_sum = 0.0
            for s, cum in zip(sieve_sizes, cum_retained):
                if s in _FM_SIEVES:
                    fm_sum += cum
            fm = round(fm_sum / 100.0, 2)

    # Characteristic sizes D10, D30, D60 by log-linear interpolation of the
    # passing curve (sieve size vs % passing). The curve is monotonic
    # decreasing in size vs increasing in %passing, so we interpolate size as
    # a function of %passing between adjacent sieve points.
    d10 = _interpolate_size(sieve_sizes, pct_passing, 10.0)
    d30 = _interpolate_size(sieve_sizes, pct_passing, 30.0)
    d60 = _interpolate_size(sieve_sizes, pct_passing, 60.0)

    cu: float | None = None
    cc: float | None = None
    if d10 and d10 > 0 and d60 and d60 > 0:
        cu = round(d60 / d10, 2)
        if d30 and d30 > 0:
            cc = round(d30 * d30 / (d60 * d10), 2)

    return PSDResult(
        sieve_sizes=list(sieve_sizes),
        mass_retained=masses,
        pan_mass=pan,
        total_mass=total,
        percent_retained=pct_retained,
        cumulative_percent_retained=cum_retained,
        percent_passing=pct_passing,
        fineness_modulus=fm,
        d10=d10,
        d30=d30,
        d60=d60,
        uniformity_coefficient=cu,
        coefficient_of_curvature=cc,
        conforms=[],
    )


def check_conformance(
    result: PSDResult,
    band: dict[float, tuple[float, float]],
) -> list[bool]:
    """Check each sieve's %passing against a standard grading band.

    Args:
        result: A :class:`PSDResult` from :func:`compute_psd`.
        band: ``{sieve_mm: (lower_passing%, upper_passing%)}`` from
            :mod:`concrete_mix.codes.tables.grading_bands`.

    Returns:
        List of bools aligned with ``result.sieve_sizes``. ``True`` where the
        %passing lies inside (inclusive) the band, or where the sieve is not
        in the band (unchecked sieves are treated as conforming). The list is
        also written to ``result.conforms``.
    """
    conforms: list[bool] = []
    for s, p in zip(result.sieve_sizes, result.percent_passing):
        if s in band:
            lo, hi = band[s]
            conforms.append(lo <= p <= hi)
        else:
            conforms.append(True)
    result.conforms = conforms
    return conforms


def _interpolate_size(
    sieve_sizes: list[float],
    percent_passing: list[float],
    target_pct: float,
) -> float | None:
    """Log-linear interpolate the sieve size at a given %passing.

    The gradation curve is treated as size (log axis) vs %passing (linear).
    We walk the sieves coarsest→finest (size decreasing, %passing
    decreasing) and find the interval straddling *target_pct*, then
    interpolate in log-space.

    Returns ``None`` if *target_pct* is outside the measured range.
    """
    if not sieve_sizes:
        return None

    # Build points sorted by %passing ascending (finest → coarsest), which
    # gives an increasing size-vs-passing curve for interpolation.
    pts = sorted(zip(percent_passing, sieve_sizes))
    passes = [p for p, _ in pts]
    sizes = [s for _, s in pts]

    if target_pct < passes[0] or target_pct > passes[-1]:
        return None

    for i in range(1, len(pts)):
        p0, s0 = passes[i - 1], sizes[i - 1]
        p1, s1 = passes[i], sizes[i]
        if p0 == p1:
            continue
        if p0 <= target_pct <= p1:
            # Log-linear interpolation: log(size) vs %passing
            if s0 <= 0 or s1 <= 0:
                # Fall back to linear if a size is zero (shouldn't happen for
                # real sieve sizes, but guard anyway).
                frac = (target_pct - p0) / (p1 - p0)
                return s0 + frac * (s1 - s0)
            import math

            log_s0 = math.log(s0)
            log_s1 = math.log(s1)
            frac = (target_pct - p0) / (p1 - p0)
            return math.exp(log_s0 + frac * (log_s1 - log_s0))

    return None


def _interpolate_percent_passing(
    sieve_sizes: list[float],
    percent_passing: list[float],
    target_size_mm: float,
) -> float | None:
    """Log-linear interpolate the % passing at a given sieve size (mm)."""
    if not sieve_sizes or target_size_mm <= 0:
        return None

    import math

    # Direct match check (within tolerance)
    for s, p in zip(sieve_sizes, percent_passing):
        if abs(s - target_size_mm) < 1e-4:
            return round(p, 1)

    pts = sorted(zip(sieve_sizes, percent_passing))
    sizes = [s for s, _ in pts if s > 0]
    passes = [p for s, p in pts if s > 0]

    if not sizes or target_size_mm < sizes[0] or target_size_mm > sizes[-1]:
        return None

    for i in range(1, len(sizes)):
        s0, p0 = sizes[i - 1], passes[i - 1]
        s1, p1 = sizes[i], passes[i]
        if s0 == s1:
            continue
        if s0 <= target_size_mm <= s1:
            log_s0 = math.log(s0)
            log_s1 = math.log(s1)
            frac = (math.log(target_size_mm) - log_s0) / (log_s1 - log_s0)
            interpolated = p0 + frac * (p1 - p0)
            return round(interpolated, 1)

    return None

