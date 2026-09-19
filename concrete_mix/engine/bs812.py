"""BS 812-103.1:1985 clauses 7, 8 and 10: dry or washed sieve analysis."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from math import fsum, isclose, isfinite

from concrete_mix.engine.psd import PSDResult


def report_whole_percent(value: float) -> int:
    """Report to a whole percent (clause 10); ties use app half-up policy."""
    if not isfinite(value):
        raise ValueError("Percentage must be finite")
    return int(Decimal(str(value)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def washed_fines_percent(original_dry_mass: float, washed_dry_mass: float) -> float:
    """Return 100(M1-M2)/M1, washing alone (§7.2.1, BS 882 Table 6)."""
    if not isfinite(original_dry_mass) or original_dry_mass <= 0:
        raise ValueError("Original dry mass M1 must be finite and positive")
    if (not isfinite(washed_dry_mass)
            or not 0 <= washed_dry_mass <= original_dry_mass):
        raise ValueError("Washed dry mass M2 must be finite and between zero and M1")
    return (original_dry_mass - washed_dry_mass) / original_dry_mass * 100


def compute_bs812_psd(
    mass_retained: list[float],
    sieve_sizes: list[float],
    pan_mass: float = 0.0,
    *,
    original_dry_mass: float,
    washed_dry_mass: float | None = None,
    method: str = "dry",
) -> PSDResult:
    """Calculate §8 PSD using original dry mass M1, never recovered mass.

    Args:
        mass_retained: Raw dry-sieved masses in grams, coarsest first.
        sieve_sizes: Corresponding BS apertures in mm, strictly descending.
        pan_mass: Raw dry pan mass, excluding washing loss.
        original_dry_mass: Original oven-dry mass M1 in grams.
        washed_dry_mass: Oven-dry washed residue M2, required for washed mode.
        method: ``dry`` (§7.3) or ``washed`` (§7.2).

    Returns:
        PSDResult with raw retained masses and corrected pan (raw pan +
        washing loss exactly once). FM and characteristic sizes are None.

    Raises:
        ValueError: Invalid measurements or unreconciled dry residue. As an
            app integrity policy (not a BS laboratory tolerance), sums must
            agree to numerical precision; no unexplained loss is allocated
            to fines. The washed stack must end at 75 µm (§7.2.2.1).
    """
    if method not in ("dry", "washed"):
        raise ValueError("method must be 'dry' or 'washed'")
    if len(mass_retained) != len(sieve_sizes):
        raise ValueError("mass_retained must match sieve_sizes")
    if not sieve_sizes or any(not isfinite(s) or s <= 0 for s in sieve_sizes):
        raise ValueError("Sieve apertures must be finite and positive")
    if any(a <= b for a, b in zip(sieve_sizes, sieve_sizes[1:])):
        raise ValueError("Sieve apertures must be unique and strictly descending")
    if any(not isfinite(m) or m < 0 for m in [*mass_retained, pan_mass]):
        raise ValueError("Mass values must be finite and nonnegative")
    if not isfinite(original_dry_mass) or original_dry_mass <= 0:
        raise ValueError("Original dry mass M1 must be finite and positive")
    lost = 0.0
    residue = original_dry_mass
    if method == "washed":
        if washed_dry_mass is None:
            raise ValueError("Washed method requires M2")
        washed_fines_percent(original_dry_mass, washed_dry_mass)
        if sieve_sizes[-1] != 0.075:
            raise ValueError("Washed stack must end at the 75 µm sieve")
        residue = washed_dry_mass
        lost = original_dry_mass - washed_dry_mass
    elif washed_dry_mass is not None:
        raise ValueError("M2 belongs to the washed method, not dry sieving")
    if not isclose(fsum([*mass_retained, pan_mass]), residue,
                   rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError("Dry sieve masses plus pan must reconcile with residue mass")
    masses = [float(m) for m in mass_retained]
    cumulative = [fsum(masses[:i + 1]) / original_dry_mass * 100
                  for i in range(len(masses))]
    return PSDResult(
        sieve_sizes=list(sieve_sizes), mass_retained=masses,
        pan_mass=pan_mass + lost, total_mass=original_dry_mass,
        percent_retained=[m / original_dry_mass * 100 for m in masses],
        cumulative_percent_retained=cumulative,
        percent_passing=[max(0.0, 100 - c) for c in cumulative],
        fineness_modulus=None, d10=None, d30=None, d60=None,
        uniformity_coefficient=None, coefficient_of_curvature=None,
    )
