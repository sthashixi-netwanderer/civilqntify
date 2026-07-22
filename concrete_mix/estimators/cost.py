"""Material cost estimation for concrete mix design."""

from __future__ import annotations

from dataclasses import dataclass

from concrete_mix.models.mix_result import MixDesignResult
from concrete_mix.utils.constants import (
    DEFAULT_PRICE_ADMIXTURE,
    DEFAULT_PRICE_CEMENT,
    DEFAULT_PRICE_COARSE_AGG,
    DEFAULT_PRICE_FINE_AGG,
    DEFAULT_PRICE_FLY_ASH,
    DEFAULT_PRICE_GGBFS,
    DEFAULT_PRICE_SILICA_FUME,
    DEFAULT_PRICE_WATER,
)


@dataclass(frozen=True)
class MaterialPrices:
    """Material prices in USD per kg."""
    cement: float = DEFAULT_PRICE_CEMENT
    fine_aggregate: float = DEFAULT_PRICE_FINE_AGG
    coarse_aggregate: float = DEFAULT_PRICE_COARSE_AGG
    fly_ash: float = DEFAULT_PRICE_FLY_ASH
    ggbfs: float = DEFAULT_PRICE_GGBFS
    silica_fume: float = DEFAULT_PRICE_SILICA_FUME
    admixture: float = DEFAULT_PRICE_ADMIXTURE
    water: float = DEFAULT_PRICE_WATER


def estimate_cost(
    result: MixDesignResult,
    prices: MaterialPrices | None = None,
    scm_type: str = "fly_ash",
) -> float:
    """Estimate material cost per m³ of concrete.

    Args:
        result: Mix design result
        prices: Material prices (defaults if None)
        scm_type: Type of SCM for pricing ("fly_ash", "ggbfs", "silica_fume")

    Returns:
        Cost per m³ in USD
    """
    if prices is None:
        prices = MaterialPrices()

    cost = 0.0
    cost += result.cement_kg * prices.cement
    cost += result.water_kg * prices.water
    cost += result.fine_aggregate_kg * prices.fine_aggregate
    cost += result.coarse_aggregate_kg * prices.coarse_aggregate

    if result.scm_kg > 0:
        scm_price = getattr(prices, scm_type, prices.fly_ash)
        cost += result.scm_kg * scm_price

    return round(cost, 2)
