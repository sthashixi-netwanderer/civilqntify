"""Bridge between sieve-analysis (PSD) results and mix-design inputs.

Every supported design standard makes a sieve analysis of the aggregates a
mandatory pre-design test, and each consumes a **different** parameter
derived from it (per AGENTS.md ground-truth extracts):

* ACI PRC-211.1-22 §4.3.5 + Appendix test list item (d) ("Sieve analysis
  and fineness modulus ... ASTM C136"): the fineness modulus "results from
  an ASTM C136/C136M sieve analysis" and is used with NMSA in Table 5.3.6
  (bulk volume of coarse aggregate per unit volume of concrete).
* IS 10262:2019 Clause 5.4/6.2.7 + IS 383:2016 Table 9: the grading zone
  of the fine aggregate, determined by sieve analysis, keys Table 5
  (volume of coarse aggregate per unit volume of total aggregate).
* BRE 331:1997 §1.2.5: combined grading curves are not used; the grading is
  characterised by the percentage passing the 600 µm test sieve, which
  feeds Figure 6 (recommended proportion of fine aggregate).

This module turns one :class:`PSDResult` into exactly those parameters so
the UI can hand them to the mix-design form without retyping.
"""

from __future__ import annotations

from dataclasses import dataclass

from concrete_mix.engine.grading import determine_grading_zone
from concrete_mix.engine.psd import (
    FM_SIEVES,
    IS_FINE_SIEVES,
    PSDResult,
)

# Same series as compute_psd uses internally — imported (not duplicated) so
# FM availability rules can never drift from the FM computation itself.
_FM_SIEVES_REQUIRED: set[float] = set(FM_SIEVES)

# All seven IS 383 fine-aggregate zone sieves (10 mm top sieve). A partial
# stack cannot determine a zone reliably, so we require the full set.
_ZONE_SIEVES_REQUIRED: set[float] = set(IS_FINE_SIEVES)

_P600_MM: float = 0.600


@dataclass(frozen=True)
class PSDLinkage:
    """PSD-derived parameters that feed each standard's mix-design engine.

    Attributes:
        fineness_modulus: FM of this analysis (ACI 211.1-22 uses it with
            NMSA via Table 5.3.6). ``None`` when the 0.150–4.75 mm series is
            absent.
        grading_zone: IS 383:2016 Table 9 zone determined by sieve analysis —
            "I"–"IV" or ``None`` when the full zone sieve set is missing.
            Consumed by IS 10262:2019 Table 5 (CA volume fraction).
        pct_passing_600um: % passing the 600 µm test sieve, one decimal
            (BRE 331:1997 Figure 6 / fitted proportion equation).
            ``None`` when that sieve was not included.
        warnings: Human-readable notes for every parameter a standard needs
            but this analysis cannot supply.
    """

    fineness_modulus: float | None
    grading_zone: str | None
    pct_passing_600um: float | None
    warnings: tuple[str, ...] = ()

    @property
    def aci211_ready(self) -> bool:
        """True when ACI 211.1 Table 5.3.6 can consume this result (FM)."""
        return self.fineness_modulus is not None

    @property
    def is10262_ready(self) -> bool:
        """True when IS 10262 Table 5 can consume this result (zone)."""
        return self.grading_zone is not None

    @property
    def doe_ready(self) -> bool:
        """True when BRE 331 Figure 6 can consume this result (%p600)."""
        return self.pct_passing_600um is not None


def derive_mix_design_params(result: PSDResult) -> PSDLinkage:
    """Derive every mix-design-relevant parameter from one sieve analysis.

    Args:
        result: A :class:`PSDResult` from :func:`compute_psd`. It may come
            from either the fine-aggregate or coarse-aggregate sieve stack;
            parameters whose required sieves are missing stay ``None`` with
            an explanatory warning.

    Returns:
        A :class:`PSDLinkage` holding the ACI fineness modulus, the IS 383
        grading zone and the DOE/BRE %passing 600 µm value, plus warnings.
    """
    warnings: list[str] = []
    fm = result.fineness_modulus
    sizes = set(result.sieve_sizes)

    # ---- Grading zone (IS 383 Table 9 → IS 10262:2019 Table 5) ------------
    zone: str | None = None
    if _ZONE_SIEVES_REQUIRED <= sizes:
        passing = dict(zip(result.sieve_sizes, result.percent_passing))
        zone = determine_grading_zone(passing)
    else:
        missing = sorted(_ZONE_SIEVES_REQUIRED - sizes)
        warnings.append(
            "IS 10262:2019 Table 5 needs the fine-aggregate grading zone "
            "(IS 383 Table 9); add sieves "
            f"{', '.join(f'{s:g} mm' for s in missing)} to determine it."
        )

    # ---- Fineness modulus availability (ACI 211.1-22 §4.3.5) --------------
    if fm is None:
        missing_fm = sorted(_FM_SIEVES_REQUIRED - sizes)
        warnings.append(
            "Fineness modulus could not be computed — ACI 211.1-22 uses it "
            "with NMSA in Table 5.3.6. Add sieves "
            f"{', '.join(f'{s:g} mm' for s in missing_fm)} "
            "(ACI 211.1-22 §4.3.5, ASTM C136)."
        )

    # ---- DOE / BRE 331 percentage passing 600 µm ---------------------------
    p600 = result.pct_passing_600um
    if p600 is None:
        warnings.append(
            "BRE 331:1997 Figure 6 needs the percentage passing the 600 µm "
            "test sieve; include the 600 µm (0.600 mm) sieve or a sieve stack spanning it (DOE §1.2.5)."
        )

    return PSDLinkage(
        fineness_modulus=fm,
        grading_zone=zone,
        pct_passing_600um=p600,
        warnings=tuple(warnings),
    )

