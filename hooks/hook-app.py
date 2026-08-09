"""PyInstaller hook for the local ``app`` package.

Ensures all app submodules are bundled even when PyInstaller's static
analysis misses them (e.g., imports inside functions or Windows path quirks).
This hook is referenced via ``hookspath=['hooks']`` in civilqntify.spec.
"""

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("app")
# Explicitly add the critical widget that has been reported missing in frozen
# builds even when hiddenimports is populated via spec. This guarantees the
# module is in the TOC regardless of collection timing.
hiddenimports += [
    "app.widgets.concrete_tab",
    "app.widgets.material_quantify_tab",
    "app.widgets.cost_estimation_tab",
    "app.widgets.history_tab",
    "app.widgets.psd_widget",
    "app.widgets.weather_widget",
    "app.pricing.price_sheet_service",
    "app.pricing.price_sheet_worker",
]
