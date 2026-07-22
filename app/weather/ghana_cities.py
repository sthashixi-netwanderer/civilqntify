"""Ghana cities and towns database with coordinates.

Contains major cities and towns in Ghana with their latitude,
longitude, and region information for weather data lookup.
"""

from __future__ import annotations

from typing import Optional


# Ghana cities and towns with coordinates
# Source: Open-Meteo Geocoding API and standard geographic data
GHANA_CITIES: dict[str, dict[str, float | str]] = {
    # Greater Accra Region
    "Accra": {"lat": 5.6037, "lon": -0.1870, "region": "Greater Accra"},
    "Tema": {"lat": 5.6698, "lon": -0.0166, "region": "Greater Accra"},
    "Ashaiman": {"lat": 5.6500, "lon": -0.0333, "region": "Greater Accra"},
    "Madina": {"lat": 5.6500, "lon": -0.1700, "region": "Greater Accra"},
    "East Legon": {"lat": 5.6400, "lon": -0.1500, "region": "Greater Accra"},
    "Teshie": {"lat": 5.5833, "lon": -0.1000, "region": "Greater Accra"},
    "Nungua": {"lat": 5.5833, "lon": -0.0833, "region": "Greater Accra"},
    "Dansoman": {"lat": 5.5333, "lon": -0.2333, "region": "Greater Accra"},
    "Kaneshie": {"lat": 5.5500, "lon": -0.2167, "region": "Greater Accra"},
    "Osu": {"lat": 5.5500, "lon": -0.1667, "region": "Greater Accra"},

    # Ashanti Region
    "Kumasi": {"lat": 6.6885, "lon": -1.6244, "region": "Ashanti"},
    "Obuasi": {"lat": 6.2030, "lon": -1.6609, "region": "Ashanti"},
    "Ejisu": {"lat": 6.7333, "lon": -1.3500, "region": "Ashanti"},
    "Mampong": {"lat": 7.0500, "lon": -1.4000, "region": "Ashanti"},
    "Konongo": {"lat": 6.6167, "lon": -1.2167, "region": "Ashanti"},
    "Offinso": {"lat": 6.9833, "lon": -1.5500, "region": "Ashanti"},
    "Bekwai": {"lat": 6.4500, "lon": -1.5833, "region": "Ashanti"},
    "Agona": {"lat": 6.8000, "lon": -1.4667, "region": "Ashanti"},

    # Northern Region
    "Tamale": {"lat": 9.4034, "lon": -0.8393, "region": "Northern"},
    "Yendi": {"lat": 9.4428, "lon": -0.0089, "region": "Northern"},
    "Salaga": {"lat": 8.6833, "lon": -0.5167, "region": "Northern"},
    "Savelugu": {"lat": 9.6167, "lon": -0.8333, "region": "Northern"},
        "Damongo": {"lat": 9.0833, "lon": -1.8167, "region": "Northern"},

    # Western Region
    "Takoradi": {"lat": 4.8986, "lon": -1.7600, "region": "Western"},
    "Sekondi": {"lat": 4.9340, "lon": -1.7960, "region": "Western"},
    "Tarkwa": {"lat": 5.3000, "lon": -1.9833, "region": "Western"},
    "Axim": {"lat": 4.8667, "lon": -2.2333, "region": "Western"},
    "Prestea": {"lat": 5.4333, "lon": -2.1500, "region": "Western"},

    # Central Region
    "Cape Coast": {"lat": 5.1315, "lon": -1.2795, "region": "Central"},
    "Winneba": {"lat": 5.3500, "lon": -0.6000, "region": "Central"},
    "Kasoa": {"lat": 5.2000, "lon": -0.4167, "region": "Central"},
    "Swedru": {"lat": 5.3333, "lon": -0.7000, "region": "Central"},
    "Mankessim": {"lat": 5.1333, "lon": -1.0333, "region": "Central"},

    # Eastern Region
    "Koforidua": {"lat": 6.0941, "lon": -0.2591, "region": "Eastern"},
    "Nkawkaw": {"lat": 6.5500, "lon": -0.7833, "region": "Eastern"},
    "Mampong Akuapem": {"lat": 5.9000, "lon": -0.0833, "region": "Eastern"},
    "Suhum": {"lat": 6.0333, "lon": -0.4500, "region": "Eastern"},
    "Bunso": {"lat": 6.2833, "lon": -0.5000, "region": "Eastern"},

    # Volta Region
    "Ho": {"lat": 6.6000, "lon": 0.4700, "region": "Volta"},
    "Hohoe": {"lat": 6.7833, "lon": 0.4667, "region": "Volta"},
    "Kpando": {"lat": 6.9833, "lon": 0.3000, "region": "Volta"},
    "Jasikan": {"lat": 7.4167, "lon": 0.4667, "region": "Volta"},
    "Kete Krachi": {"lat": 7.5500, "lon": -0.0500, "region": "Volta"},

    # Bono Region
    "Sunyani": {"lat": 7.3349, "lon": -2.3266, "region": "Bono"},
    "Berekum": {"lat": 7.4500, "lon": -2.5833, "region": "Bono"},
        "Dormaa Ahenkuro": {"lat": 7.2667, "lon": -2.7833, "region": "Bono"},
    "Wenchi": {"lat": 7.7333, "lon": -2.1000, "region": "Bono"},

    # Bono East Region
    "Techiman": {"lat": 7.5908, "lon": -1.9402, "region": "Bono East"},
    "Nkoranza": {"lat": 7.5500, "lon": -1.7000, "region": "Bono East"},
    "Kintampo": {"lat": 8.0500, "lon": -1.7333, "region": "Bono East"},

    # Ahafo Region
    "Goaso": {"lat": 6.8000, "lon": -2.5167, "region": "Ahafo"},
    "Duayaw Nkwanta": {"lat": 7.1667, "lon": -2.2833, "region": "Ahafo"},

    # Upper East Region
    "Bolgatanga": {"lat": 10.7855, "lon": -0.8514, "region": "Upper East"},
    "Bawku": {"lat": 11.0500, "lon": -0.2333, "region": "Upper East"},
    "Navrongo": {"lat": 10.9667, "lon": -0.7667, "region": "Upper East"},
    "Zebilla": {"lat": 10.7500, "lon": -0.5167, "region": "Upper East"},

    # Upper West Region
    "Wa": {"lat": 10.0601, "lon": -2.5099, "region": "Upper West"},
    "Lawra": {"lat": 10.5833, "lon": -2.9000, "region": "Upper West"},
    "Jirapa": {"lat": 10.5167, "lon": -2.7500, "region": "Upper West"},
    "Nandom": {"lat": 10.5167, "lon": -2.7500, "region": "Upper West"},

    # Oti Region
    "Dambai": {"lat": 8.0667, "lon": -0.1833, "region": "Oti"},
    "Krachi": {"lat": 7.5500, "lon": -0.0500, "region": "Oti"},

    # North East Region
    "Nalerigu": {"lat": 10.5167, "lon": -0.3667, "region": "North East"},
    "Gushegu": {"lat": 9.9333, "lon": -0.2333, "region": "North East"},

    # Savannah Region
    "Damongo": {"lat": 9.0833, "lon": -1.8167, "region": "Savannah"},
    "Bole": {"lat": 9.0333, "lon": -2.4833, "region": "Savannah"},
    "Salaga": {"lat": 8.6833, "lon": -0.5167, "region": "Savannah"},
}


def get_city_coordinates(city_name: str) -> Optional[dict[str, float]]:
    """Get coordinates for a Ghana city.

    Args:
        city_name: Name of the city

    Returns:
        Dictionary with 'lat' and 'lon' keys, or None if city not found
    """
    city = GHANA_CITIES.get(city_name)
    if city:
        return {"lat": float(city["lat"]), "lon": float(city["lon"])}
    return None


def get_cities_by_region(region: str) -> list[str]:
    """Get all cities in a specific region.

    Args:
        region: Name of the region

    Returns:
        List of city names in the region
    """
    return [
        city for city, info in GHANA_CITIES.items()
        if info["region"] == region
    ]


def get_all_regions() -> list[str]:
    """Get all unique regions in Ghana.

    Returns:
        Sorted list of region names
    """
    regions = set(info["region"] for info in GHANA_CITIES.values())
    return sorted(regions)
