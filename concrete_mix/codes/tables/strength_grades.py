"""Selectable characteristic-strength grades, per mix design code.

The three codes the app implements do not agree on what a "grade" is, and
none of them agree on the units it is written in, so this module is the one
place that reconciles them:

- **IS 10262:2019** names its grades (M10…M80) and specifies them in N/mm².
- **ACI PRC-211.1-22** has no grade names at all — f'c is a number in psi on
  a fixed increment grid, so the "name" is just the psi value.
- **BRE 331:1997** names nothing and specifies nothing discrete; the grid
  here is app policy (see :data:`doe_tables.DOE_FC_GRADES_MPA`).

Everything is stored in **metric MPa** because that is what the engines and
:class:`~concrete_mix.models.mix_input.MixDesignInput` take. Display units are
a rendering concern handled by :func:`format_grade`, which keeps this module
free of any Qt or unit-preference import.
"""

from __future__ import annotations

from dataclasses import dataclass

from concrete_mix.codes.tables import aci_tables, doe_tables, is_tables

# 1 MPa = 145.038 psi.
_MPA_TO_PSI = 145.038


@dataclass(frozen=True)
class GradeOption:
    """One selectable characteristic strength for a code.

    Attributes:
        value_mpa: Characteristic strength in metric MPa — the value the
            engines and the input model consume.
        name: The code's own designation for the grade (e.g. ``"M30"``,
            ``"4000 psi"``). Empty when the code names nothing.
        native_unit: Unit the code itself specifies strengths in —
            ``"psi"`` for ACI, ``"MPa"`` for IS and DoE. Drives which number
            leads in :func:`format_grade`.
        clause: Where the value comes from, shown in the item tooltip.
        psi: The exact psi value when the code specifies in psi. Kept exact
            rather than round-tripped through MPa so a listed 3000 never
            renders as 2999.
        label_override: Rendered verbatim by :func:`format_grade`, bypassing
            the usual "designation · value" layout. For off-list values
            that need their own wording.
    """

    value_mpa: float
    name: str = ""
    native_unit: str = "MPa"
    clause: str = ""
    psi: int | None = None
    label_override: str = ""


def _aci_grades() -> tuple[GradeOption, ...]:
    return tuple(
        GradeOption(
            value_mpa=round(psi * aci_tables._PSI_TO_MPA, 4),
            name=f"{psi:,} psi",
            native_unit="psi",
            clause="ACI 318-19 §26.4.2.1(a)(1) increment grid",
            psi=psi,
        )
        for psi in aci_tables.ACI_FC_GRADES_PSI
    )


def _is_grades() -> tuple[GradeOption, ...]:
    return tuple(
        GradeOption(
            value_mpa=fck,
            name=f"M{int(fck)}",
            native_unit="MPa",
            clause="IS 10262:2019 Table 1 (grade set)",
        )
        for fck in is_tables.IS_FC_GRADES
    )


def _doe_grades() -> tuple[GradeOption, ...]:
    return tuple(
        GradeOption(
            value_mpa=fc,
            native_unit="MPa",
            clause="BRE 331:1997 §4.3 (app 5 N/mm² grid)",
        )
        for fc in doe_tables.DOE_FC_GRADES_MPA
    )


_GRADES: dict[str, tuple[GradeOption, ...]] = {
    "aci211": _aci_grades(),
    "is10262": _is_grades(),
    "doe": _doe_grades(),
}


def grades_for_code(code: str) -> tuple[GradeOption, ...]:
    """Characteristic strengths the given code allows, ascending.

    Args:
        code: "aci211", "is10262" or "doe".

    Returns:
        The selectable grades for that code. Empty tuple for an unknown
        code, so a caller wiring an unexpected standard degrades to "no
        choices offered" rather than crashing on import.
    """
    return _GRADES.get(code, ())


def min_fc_for_code(
    code: str,
    *,
    exposure: str | None = None,
    concrete_type: str = "reinforced",
    freezing_exposure_class: str = "F0",
    water_exposure_class: str = "W0",
    corrosion_exposure_class: str = "C0",
    sulfate_exposure_class: str = "S0",
) -> float | None:
    """Lowest characteristic strength (MPa) the code's exposure rules allow.

    The exposure vocabulary is code-specific, so only the arguments relevant
    to ``code`` are read; the rest are ignored.

    Args:
        code: "aci211", "is10262" or "doe".
        exposure: IS 456:2000 Table 5 exposure class.
        concrete_type: "plain" or "reinforced" (IS 456 Table 5 row).
        freezing_exposure_class: ACI F0–F3.
        water_exposure_class: ACI W0–W2.
        corrosion_exposure_class: ACI C0–C2.
        sulfate_exposure_class: ACI S0–S3.

    Returns:
        Minimum strength in MPa, or None when nothing imposes a floor.
    """
    if code == "is10262":
        return is_tables.is_min_fc_mpa(concrete_type, exposure)
    if code == "aci211":
        return aci_tables.aci_min_fc_mpa(
            freezing_exposure_class,
            water_exposure_class,
            corrosion_exposure_class,
            sulfate_exposure_class,
        )
    return None


def format_grade(option: GradeOption, imperial: bool = False) -> str:
    """Render one grade for a combo box.

    The code's native designation always leads — "M30 · 30 MPa" under IS,
    "4,000 psi · 27.6 MPa" under ACI — with the display-unit figure
    following. Both numbers are shown because an engineer reading an ACI
    report wants psi and the report writer wants MPa, and the combo is the
    only place the two meet.

    Args:
        option: The grade to render.
        imperial: True when the app is displaying imperial units.

    Returns:
        The combo item text.
    """
    if option.label_override:
        return option.label_override
    if option.name:
        # Native-psi codes lead with the psi value and append the MPa the
        # backend uses; native-MPa codes lead with the grade and append the
        # display unit, so IS shows psi once imperial is on.
        if option.psi is not None:
            return f"{option.name} · {option.value_mpa:.1f} MPa"
        alt = (
            f"{option.value_mpa * _MPA_TO_PSI:,.0f} psi"
            if imperial
            else f"{option.value_mpa:.0f} MPa"
        )
        return f"{option.name} · {alt}"
    if imperial:
        return f"{option.value_mpa * _MPA_TO_PSI:,.0f} psi"
    return f"{option.value_mpa:.0f} MPa"


def nearest_grade(code: str, value_mpa: float) -> GradeOption | None:
    """Closest offered grade to ``value_mpa``, for standard switches.

    Used when a value cannot be carried across a code change verbatim and we
    must land somewhere sensible rather than snapping to the first item.

    Args:
        code: "aci211", "is10262" or "doe".
        value_mpa: The strength to approximate.

    Returns:
        The nearest grade, or None when the code offers none.
    """
    grades = grades_for_code(code)
    if not grades:
        return None
    return min(grades, key=lambda g: (abs(g.value_mpa - value_mpa), g.value_mpa))
