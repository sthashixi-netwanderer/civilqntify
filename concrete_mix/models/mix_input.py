"""Immutable input model for concrete mix design."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from concrete_mix.models.materials import (
    SCM,
    Admixture,
    Cement,
    CoarseAggregate,
    FineAggregate,
)


@dataclass(frozen=True)
class MixDesignInput:
    """All inputs required for a concrete mix design calculation.

    Args:
        code: Mix design code to use — "aci211" or "is10262"
        target_strength_mpa: Required characteristic/compressive strength (MPa)
        slump_mm: Required slump in mm
        cement: Cement material properties
        fine_aggregate: Fine aggregate (sand) properties
        coarse_aggregate: Coarse aggregate properties
        scms: Optional list of supplementary cementitious materials
        admixture: Optional chemical admixture
        exposure_class: IS 456 exposure class (for IS 10262 only)
            Valid: "mild", "moderate", "severe", "very_severe", "extreme"
        concrete_type: Plain or reinforced concrete (IS 456:2000 Table 5).
            "plain" or "reinforced" (default). Determines which row of
            Table 5 is used for min cement, max W/C, and min grade limits.
        air_entrained: Whether air-entrained concrete is required (ACI only)
        w_c_ratio: Optional manual override for W/C ratio
        volume_m3: Target concrete volume in cubic meters (default 1.0)
        has_production_data: Whether ≥30 test results exist (ACI only).
            False uses ACI 318 Table 26.4.3.1(b) overdesign.
        sulfate_exposure_class: ACI 318 sulfate exposure class (ACI only).
            Valid: "S0", "S1", "S2", "S3". Default "S0" (no sulfate).
    """

    code: Literal["aci211", "is10262", "doe"]
    target_strength_mpa: float
    characteristic_strength_mpa: float | None = (
        None  # User enters this; target is calculated
    )
    ca_volume_fraction_override: float | None = (
        None  # Direct CA volume fraction from Table 5
    )
    slump_mm: float = 75.0
    cement: Cement = field(default_factory=Cement)
    fine_aggregate: FineAggregate = field(default_factory=FineAggregate)
    coarse_aggregate: CoarseAggregate = field(default_factory=CoarseAggregate)
    scms: tuple[SCM, ...] = ()
    admixture: Optional[Admixture] = None
    exposure_class: Optional[str] = None
    concrete_type: Literal["plain", "reinforced"] = "reinforced"
    air_entrained: bool = False
    w_c_ratio: Optional[float] = None
    volume_m3: float = 1.0
    has_production_data: bool = True
    sulfate_exposure_class: str = "S0"
    freezing_exposure_class: str = "F0"
    """ACI 301 freezing-and-thawing exposure class (ACI only).

    Valid: "F0" (not exposed), "F1", "F2", "F3" (ACI 318 Chapter 19 /
    ACI 301 Table 4.2.2.6(c)). F1–F3 require air-entrained concrete and
    impose maximum w/cm, minimum specified strength, and (F3) SCM caps.
    """
    water_exposure_class: str = "W0"
    """ACI 301 water-contact exposure class (ACI only).

    Valid: "W0" (dry/protected), "W1" (in contact, permeability a concern),
    "W2" (water-barrier elements: w/c ≤ 0.50, min 4000 psi).
    """
    corrosion_exposure_class: str = "C0"
    """ACI 301 corrosion-protection class, non-prestressed scope (ACI only).

    Valid: "C0", "C1" (chloride guidance), "C2" (external chlorides:
    w/c ≤ 0.40, min 5000 psi, chloride guidance).
    """
    form_width_mm: float | None = None
    """Narrowest form dimension in mm (ACI only, optional).

    NMSA must not exceed 1/5 of this value (ACI 318 26.4.2.1(a)(5)).
    None (default) skips the check.
    """
    slab_depth_mm: float | None = None
    """Slab depth in mm (ACI only, optional).

    NMSA must not exceed 1/3 of this value (ACI 318 26.4.2.1(a)(5)).
    None (default) skips the check.
    """
    bar_spacing_mm: float | None = None
    """Minimum clear bar/bundle/strand spacing in mm (ACI only, optional).

    NMSA must not exceed 3/4 of this value (ACI 318 26.4.2.1(a)(5)).
    None (default) skips the check.
    """
    concrete_temp_c: float = 22.5
    """Fresh concrete temperature in °C (ACI only).

    Table 5.3.3.1 baseline is standard laboratory 68–77 °F (midpoint
    22.5 °C): ±2% water per 10 °F deviation. The default reproduces the
    unadjusted Table 5.3.3 estimate (legacy behavior).
    """
    manufactured_sand: bool = False
    """Fine aggregate is manufactured (crushed) sand (ACI only).

    Table 5.3.3.1: +5% mixing water vs natural sand baseline.
    """
    prestressed: bool = False
    """Concrete contains prestressed reinforcement (ACI only).

    Selects the prestressed chloride caps of ACI 301 Table 4.2.2.6(e)
    (0.06% water-soluble Cl⁻ for C0/C1/C2); C2 w/c and strength limits
    are identical for prestressed and non-prestressed concrete.
    """
    num_strength_tests: int | None = None
    """Number of strength tests behind the standard deviation (ACI only).

    15–29 tests apply the Table 4.7.4.3 k-modification (1.16/1.08/1.03) to
    the sample s in the Table 4.7.4.4 required-average formulas; ≥30 (or
    None) uses s unmodified. Fewer than 15 is not permitted with s — leave
    None and set has_production_data=False for the no-data table.
    """
    target_paste_volume_pct: float | None = None
    """Target paste volume as % of concrete volume (ACI only, optional).

    Triggers the Example 4 (§9.5) redesign: cementitious contents solved
    for the target PV at the design w/cm and SCM fraction, water = w/cm ×
    cementitious, aggregates rebalanced by volume. AASHTO PP 84 cites 25%
    for slab warping/cracking control. None (default) keeps the
    strength-designed proportions and only reports the PV.
    """
    trial_density_kg_m3: float | None = None
    """Measured fresh density of a trial batch in kg/m³ (ACI only, optional).

    Enables the §5.3.10 yield check (ASTM C138): relative yield
    Ry = design volume / (batch mass / measured density); 0.98–1.02
    is the working tolerance. None (default) skips trial adjustments.
    """
    trial_slump_mm: float | None = None
    """Measured slump of the trial batch in mm (ACI only, optional)."""
    trial_air_pct: float | None = None
    """Measured air content of the trial batch in % (ACI only, optional)."""
    trial_strength_mpa: float | None = None
    """Measured 28-day strength of the trial batch in MPa (ACI only, optional)."""
    air_pct: float = 0.0
    """Entrained air content in % of concrete volume (DOE only).

    BRE 331:1997 §8 air-entrained design (3–7% typical). 0.0 (default) is
    non-air-entrained concrete; above 0 the §8 modifications apply
    (inflated target strength, lower-class water, density reduction).
    """
    vebe_s: float | None = None
    """Vebe time in seconds as the workability basis (DOE only, optional).

    Alternative to slump per BRE 331 Table 3 (>12/6–12/3–6/0–3 s map to the
    same four classes as slump). When set, it governs water content and the
    Figure 6 class; None (default) uses slump.
    """
    ca_split: str | None = None
    """Split of total coarse aggregate into single sizes (DOE only, optional).

    "10+20" (1:2, requires 20 mm NMSA) or "10+20+40" (1:1.5:3, requires
    40 mm NMSA) per BRE 331:1997 §5.5. None (default) leaves CA undivided.
    """
    placing_method: str = "chute"
    """Concrete placing method (IS 10262 ordinary/mass grades).

    "chute" (default, non-pumpable) or "pump". Pumping — or congested
    reinforcement — reduces the Table 5 coarse-aggregate fraction by up to
    10% (IS 10262:2019 §5.5.2) or the Table 10 fraction by up to 5%
    (§6.2.7); see pump_ca_reduction_percent for the applied amount.
    """
    pump_ca_reduction_percent: float | None = None
    """Pumped-placing CA reduction in percent, 0–10 (IS 10262 only).

    Honoured only when placing_method is "pump". None (default) applies the
    standard maximum for the route — 10% ordinary (§5.5.2), 5%
    high-strength (§6.2.7) — as in the worked examples; mass sizes have no
    tabulated reduction and only warn unless an explicit value is given.
    An explicit value above the route maximum is rejected (§5.5.2 "up to").
    """
    site_control: str = "good"
    """Degree of site control (IS 10262 Table 2 Note 1).

    "good" (proper storage, weigh batching, controlled water, regular
    checks) uses the tabulated assumed deviation; "fair" adds 1 N/mm².
    """
    admixture_water_kg: float = 0.0
    """Mixing water contributed by liquid admixtures in kg/m³ (IS 10262).

    Counted in the water-cement ratio at durability upper limits
    (Cl. 5.1 note). 0.0 (default) means none or already included.
    """
    mass_concrete: bool = False
    """Design as mass concrete per IS 10262:2019 Section 9 (IS only).

    Uses Tables 11/12/13, the §9.2 wet-sieving target allowance for 80/150
    mm aggregate, and the §9.10 mortar check. Valid NMSA: 40/80/150 mm.
    """
    scc_class: str | None = None
    """Target slump-flow class for self-compacting concrete (IS only).

    "SF1" (550–650 mm), "SF2" (660–750 mm) or "SF3" (760–850 mm) per
    IS 10262:2019 §7.2.1. None (default) disables the SCC checks.
    """
    scc_slump_flow_mm: float | None = None
    """Measured slump-flow in mm for SCC acceptance (IS only, optional)."""
    scc_lbox_ratio: float | None = None
    """Measured L-box blocking ratio h2/h1 for SCC (IS only, ≥ 0.80 passes)."""
    scc_segregation_pct: float | None = None
    """Measured sieve-segregation ratio SR in % for SCC (IS only, optional)."""
    scc_vfunnel_s: float | None = None
    """Measured V-funnel flow time in seconds for SCC (IS only, optional)."""
    defective_percent: float = 5.0
    age_days: int = 28
    min_cement_kg: float | None = None
    max_cement_kg: float | None = None
    std_deviation: float | None = None  # DOE: user-provided standard deviation (MPa)
    margin_mpa: float | None = None  # DOE: user-specified margin (MPa), overrides k×s calculation
    num_test_cubes: int | None = None  # DOE: number of test cubes (n) for std-dev determination
    # BRE 331 Figure 3: n<20 → Line A (s = 0.4×fc for fc≤20, else 8 MPa);
    # n≥20 → Line B (s = 0.2×fc for fc≤20, else 4 MPa).

    def __post_init__(self) -> None:
        # No app-imposed structural floor: any grade in [5, 100] MPa is
        # accepted for every code (DOE Figure 3 spans the full axis; IS/ACI
        # proportion normally, with IS 456 Table 5 and ACI 318 Chapter 19
        # exposure minima enforced downstream as the real durability gates).
        # 5 MPa is a sanity floor (below that is soil-cement territory).
        fc_eff = (
            self.characteristic_strength_mpa
            if self.characteristic_strength_mpa is not None
            else self.target_strength_mpa
        )
        if not 5.0 <= fc_eff <= 100.0:
            raise ValueError(
                f"{self.code.upper()} characteristic strength fc outside valid "
                f"range [5, 100] MPa. Got {fc_eff:.1f} MPa."
            )
        if not 5.0 <= self.target_strength_mpa <= 100.0:
            raise ValueError(
                f"Characteristic strength {self.target_strength_mpa} MPa outside valid range [5, 100]."
            )

        if self.code == "doe":
            # DOE Table 3: NMSA must be 10, 20, or 40 mm
            valid_nmsa = (10, 20, 40)
            nmsa = self.coarse_aggregate.nominal_max_size_mm
            if nmsa not in valid_nmsa:
                raise ValueError(
                    f"NMSA {nmsa} mm not supported in DOE method. "
                    f"Use one of {valid_nmsa} mm (BRE 331:1997 Table 3)"
                )
            # DOE Table 3: Slump must be 0-180 mm
            if not 0.0 <= self.slump_mm <= 180.0:
                raise ValueError(
                    f"Slump {self.slump_mm} mm outside valid range [0, 180] for DOE method. "
                    f"See BRE 331:1997 Table 3"
                )
        min_slump = 0.0 if self.code == "doe" else 10.0
        if not min_slump <= self.slump_mm <= 250.0:
            raise ValueError(f"Slump {self.slump_mm} mm outside valid range [{min_slump}, 250]")
        if self.exposure_class is not None:
            valid_classes = ("mild", "moderate", "severe", "very_severe", "extreme")
            if self.exposure_class not in valid_classes:
                raise ValueError(
                    f"Exposure class '{self.exposure_class}' not valid. Use one of {valid_classes}"
                )
        if self.w_c_ratio is not None and not 0.25 <= self.w_c_ratio <= 0.80:
            raise ValueError(
                f"W/C ratio {self.w_c_ratio} outside valid range [0.25, 0.80]"
            )
        if self.volume_m3 <= 0:
            raise ValueError("Volume must be positive")
        if self.sulfate_exposure_class not in ("S0", "S1", "S2", "S3"):
            raise ValueError(
                f"Sulfate exposure class '{self.sulfate_exposure_class}' not valid. "
                "Use one of ('S0', 'S1', 'S2', 'S3')"
            )
        if self.freezing_exposure_class not in ("F0", "F1", "F2", "F3"):
            raise ValueError(
                f"Freezing exposure class '{self.freezing_exposure_class}' not valid. "
                "Use one of ('F0', 'F1', 'F2', 'F3')"
            )
        if self.water_exposure_class not in ("W0", "W1", "W2"):
            raise ValueError(
                f"Water exposure class '{self.water_exposure_class}' not valid. "
                "Use one of ('W0', 'W1', 'W2')"
            )
        if self.corrosion_exposure_class not in ("C0", "C1", "C2"):
            raise ValueError(
                f"Corrosion exposure class '{self.corrosion_exposure_class}' not valid. "
                "Use one of ('C0', 'C1', 'C2')"
            )
        for _name, _val in (
            ("form_width_mm", self.form_width_mm),
            ("slab_depth_mm", self.slab_depth_mm),
            ("bar_spacing_mm", self.bar_spacing_mm),
        ):
            if _val is not None and _val <= 0:
                raise ValueError(f"Structural dimension '{_name}' must be positive")
        if self.concrete_temp_c is not None and not -10.0 <= self.concrete_temp_c <= 60.0:
            raise ValueError(
                f"Concrete temperature {self.concrete_temp_c} °C outside valid range [-10, 60]"
            )
        if self.num_strength_tests is not None:
            if self.num_strength_tests < 15:
                raise ValueError(
                    f"Number of strength tests {self.num_strength_tests} cannot "
                    f"establish a sample standard deviation — ACI 301 Table "
                    f"4.2.3.3(a)2 needs at least 15 (PRC-211.1-22 Table "
                    f"4.7.4.3); use has_production_data=False for the no-data "
                    f"required-average table"
                )
            if self.num_strength_tests > 1000:
                raise ValueError(
                    f"Number of strength tests {self.num_strength_tests} outside "
                    f"valid range [15, 1000]"
                )
        if self.target_paste_volume_pct is not None and not (
            15.0 <= self.target_paste_volume_pct <= 45.0
        ):
            raise ValueError(
                f"Target paste volume {self.target_paste_volume_pct}% outside "
                f"valid range [15, 45] (PRC-211.1-22 Example 4 / AASHTO PP 84 "
                f"work with ~25–35%)"
            )
        for _name, _val in (
            ("trial_density_kg_m3", self.trial_density_kg_m3),
            ("trial_slump_mm", self.trial_slump_mm),
            ("trial_air_pct", self.trial_air_pct),
            ("trial_strength_mpa", self.trial_strength_mpa),
        ):
            if _val is not None and _val <= 0:
                raise ValueError(f"Trial observation '{_name}' must be positive")
        if not 0.0 <= self.air_pct <= 10.0:
            raise ValueError(
                f"Entrained air {self.air_pct}% outside valid range [0, 10]"
            )
        if self.vebe_s is not None and self.vebe_s <= 0:
            raise ValueError("Vebe time must be positive")
        if self.ca_split is not None and self.ca_split not in ("10+20", "10+20+40"):
            raise ValueError(
                f"CA split '{self.ca_split}' not valid. Use '10+20' or '10+20+40'"
            )
        if self.placing_method not in ("chute", "pump"):
            raise ValueError(
                f"Placing method '{self.placing_method}' not valid. Use 'chute' or 'pump'"
            )
        if self.pump_ca_reduction_percent is not None and not (
            0.0 <= self.pump_ca_reduction_percent <= 10.0
        ):
            raise ValueError(
                f"Pump CA reduction '{self.pump_ca_reduction_percent}' not valid. "
                "Use 0–10% (IS 10262:2019 §5.5.2 'up to 10%')"
            )
        if self.site_control not in ("good", "fair"):
            raise ValueError(
                f"Site control '{self.site_control}' not valid. Use 'good' or 'fair'"
            )
        if self.admixture_water_kg < 0:
            raise ValueError("Admixture water contribution cannot be negative")
        if self.scc_class is not None and self.scc_class not in ("SF1", "SF2", "SF3"):
            raise ValueError(
                f"SCC class '{self.scc_class}' not valid. Use 'SF1', 'SF2' or 'SF3'"
            )
        for _name, _val in (
            ("scc_slump_flow_mm", self.scc_slump_flow_mm),
            ("scc_lbox_ratio", self.scc_lbox_ratio),
            ("scc_segregation_pct", self.scc_segregation_pct),
            ("scc_vfunnel_s", self.scc_vfunnel_s),
        ):
            if _val is not None and _val <= 0:
                raise ValueError(f"SCC measurement '{_name}' must be positive")
        if self.min_cement_kg is not None and self.min_cement_kg <= 0:
            raise ValueError("Minimum cement content must be positive")
        if self.max_cement_kg is not None and self.max_cement_kg <= 0:
            raise ValueError("Maximum cement content must be positive")
        if self.num_test_cubes is not None and self.num_test_cubes <= 0:
            raise ValueError("Number of test cubes (n) must be positive")
        if self.std_deviation is not None and self.std_deviation < 0:
            raise ValueError("Standard deviation must be non-negative")
        if self.defective_percent is not None and not 0.5 <= self.defective_percent <= 15.0:
            raise ValueError("Defective percent must be between 0.5 and 15%")

    @property
    def nmsa(self) -> int | float:
        """Nominal Maximum Size of Aggregate (mm)."""
        return self.coarse_aggregate.nominal_max_size_mm

    @property
    def characteristic_strength(self) -> float:
        """Characteristic compressive strength (fck)."""
        return self.characteristic_strength_mpa or self.target_strength_mpa

    @property
    def total_scm_replacement_percent(self) -> float:
        """Total SCM replacement percentage."""
        return sum(s.replacement_percent for s in self.scms)
