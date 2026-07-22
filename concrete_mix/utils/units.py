"""Unit conversion utilities for concrete mix design.

Internal representation is always metric (kg, m³, MPa, mm).
US customary conversions provided for ACI compatibility.
"""


def kg_to_lbs(kg: float) -> float:
    return kg * 2.20462


def lbs_to_kg(lbs: float) -> float:
    return lbs / 2.20462


def mpa_to_psi(mpa: float) -> float:
    return mpa * 145.038


def psi_to_mpa(psi: float) -> float:
    return psi / 145.038


def mm_to_inches(mm: float) -> float:
    return mm / 25.4


def inches_to_mm(inches: float) -> float:
    return inches * 25.4


def m3_to_yd3(m3: float) -> float:
    return m3 * 1.30795


def yd3_to_m3(yd3: float) -> float:
    return yd3 / 1.30795


def kg_per_m3_to_lbs_per_yd3(kg_m3: float) -> float:
    return kg_m3 * 1.68555


def lbs_per_yd3_to_kg_per_m3(lbs_yd3: float) -> float:
    return lbs_yd3 / 1.68555
