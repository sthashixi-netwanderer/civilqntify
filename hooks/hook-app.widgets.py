"""PyInstaller hook for ``app.widgets`` subpackage."""

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("app.widgets")
hiddenimports += ["app.widgets.concrete_tab"]
