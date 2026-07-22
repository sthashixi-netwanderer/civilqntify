"""Live supplier price feed backed by a shared Google Sheet.

Sellers maintain material prices in a single Google Sheet where **each row is
one shop/store** and the columns are the five material prices used by the Cost
Estimation tab::

    store_name | cement_per_bag | fine_agg_per_m3 | coarse_agg_per_m3 |
    water_per_1000l | admixture_per_kg   (+ optional ``city`` column)

The app reads this sheet (read-only) via the Google Sheets API using a
service-account ``credentials.json`` and exposes the shops + their prices to the
UI. The app never writes back to the sheet — prices are editable locally after
being populated.

Access is via ``gspread`` (no user OAuth for a service account). The import is
deferred so the application still launches when the optional dependency is not
installed; callers should check :meth:`PriceSheetService.is_available`.
"""

from __future__ import annotations

import re
import threading
from typing import Any

# Canonical price keys — must match the keys used by CostEstimationTab.
PRICE_KEYS = (
    "cement_per_bag",
    "fine_agg_per_m3",
    "coarse_agg_per_m3",
    "water_per_1000l",
    "admixture_per_kg",
)

# Header aliases accepted from the sheet. Keys are normalized (lowercased,
# stripped of spaces/underscores/hyphens) to match _normalize_header output.
_HEADER_ALIASES: dict[str, str] = {
    "storename": "store_name",
    "store": "store_name",
    "shop": "store_name",
    "shopname": "store_name",
    "name": "store_name",
    "city": "city",
    "location": "city",
    "comment": "comment",
    "notes": "comment",
    "cementperbag": "cement_per_bag",
    "cement": "cement_per_bag",
    "cementprice": "cement_per_bag",
    "fineaggperm3": "fine_agg_per_m3",
    "fineagg": "fine_agg_per_m3",
    "finesand": "fine_agg_per_m3",
    "sand": "fine_agg_per_m3",
    "coarseaggperm3": "coarse_agg_per_m3",
    "coarseagg": "coarse_agg_per_m3",
    "gravel": "coarse_agg_per_m3",
    "stone": "coarse_agg_per_m3",
    "waterper1000l": "water_per_1000l",
    "water": "water_per_1000l",
    "waterprice": "water_per_1000l",
    "admixtureperkg": "admixture_per_kg",
    "admixture": "admixture_per_kg",
    "admix": "admixture_per_kg",
}


def _normalize_header(raw: str) -> str | None:
    """Map a raw sheet header to a canonical key, or None if unknown."""
    key = raw.strip().lower().replace(" ", "").replace("_", "").replace("-", "")
    return _HEADER_ALIASES.get(key)


class PriceSheetError(Exception):
    """Raised when the price sheet cannot be read or is malformed."""


class PriceSheetService:
    """Read-only client for the shared supplier price Google Sheet.

    Thread-safe: a single :class:`threading.Lock` guards the cached store map
    so the UI thread can read :meth:`get_store_prices` while a background
    worker refreshes :meth:`fetch_all`.
    """

    def __init__(self, credentials_path: str, sheet_id: str) -> None:
        self._credentials_path = credentials_path
        self._sheet_id = self._extract_sheet_id(sheet_id)
        self._stores: dict[str, dict[str, float]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _extract_sheet_id(raw: str) -> str:
        """Extract the Sheet ID from a Google Sheets URL, or return as-is.

        Accepts:
            https://docs.google.com/spreadsheets/d/<ID>/edit?gid=...
            https://docs.google.com/spreadsheets/d/<ID>/edit
            <bare-ID-string>
        """
        if not raw:
            return raw
        m = re.search(r"/d/([A-Za-z0-9_-]+)", raw)
        if m:
            return m.group(1)
        return raw.strip()

    # ── Availability ──────────────────────────────────────────────────

    @staticmethod
    def is_available() -> bool:
        """Return True if the optional ``gspread`` dependency is installed."""
        try:
            import gspread  # noqa: F401
        except Exception:
            return False
        return True

    # ── Public API ────────────────────────────────────────────────────

    def list_stores(self) -> list[str]:
        """Return cached shop names (empty before the first successful fetch)."""
        with self._lock:
            return list(self._stores.keys())

    def get_store_prices(self, store_name: str) -> dict[str, float] | None:
        """Return the price map for a shop, or None if not cached."""
        with self._lock:
            return dict(self._stores.get(store_name, {}))

    def fetch_all(self) -> dict[str, dict[str, float]]:
        """Fetch every shop and its prices from the sheet.

        Returns a mapping of ``store_name -> {price_key: value}``.
        On success the result is also cached for :meth:`list_stores` /
        :meth:`get_store_prices`.

        Raises:
            PriceSheetError: if gspread is missing, credentials/sheet are
                invalid, or the sheet lacks the required columns.
        """
        if not self._credentials_path or not self._sheet_id:
            raise PriceSheetError(
                "Live pricing is not configured. Set the Google Sheet ID and "
                "service-account credentials in Settings."
            )

        gspread = self._import_gspread()
        gspread_exc = getattr(gspread, "exceptions", None)

        try:
            gc = gspread.service_account(filename=self._credentials_path)
        except FileNotFoundError:
            raise PriceSheetError(
                f"Credentials file not found: {self._credentials_path}\n"
                "Re-select the correct file in Settings."
            )
        except Exception as exc:
            raise PriceSheetError(f"Failed to authenticate with Google: {exc}")

        try:
            sheet = gc.open_by_key(self._sheet_id)
        except Exception as exc:
            # gspread wraps errors in PermissionError/APIError. Extract the
            # underlying cause to get status code and human-readable message.
            real_exc = getattr(exc, "__cause__", exc) or exc
            status = getattr(getattr(real_exc, "response", None), "status_code", None)
            detail = str(real_exc) or str(exc)

            if status == 404:
                raise PriceSheetError(
                    "Sheet not found (HTTP 404). Check that:\n"
                    "  1. The Sheet ID is correct (from the sheet URL).\n"
                    "  2. The sheet exists and hasn't been deleted.\n"
                    "  3. The sheet is shared with your service-account email"
                    " as Viewer."
                )
            if status == 403:
                # The 403 may be "API not enabled" or "not shared". Show the
                # actual Google error so the user knows which one it is.
                if "API has not been used" in detail or "disabled" in detail:
                    raise PriceSheetError(
                        "Google Sheets API is not enabled for this project.\n\n"
                        "Go to:\n"
                        "  https://console.developers.google.com/apis/api/"
                        "sheets.googleapis.com/overview\n\n"
                        "Select your project and click ENABLE, then retry."
                    )
                raise PriceSheetError(
                    "Access denied (HTTP 403).\n\n"
                    "If the sheet is not shared with your service account, "
                    "open it in Google Sheets → Share → paste the service-account"
                    " email → set to Viewer.\n\n"
                    f"Details: {detail}"
                )
            raise PriceSheetError(f"Failed to open sheet: {detail}")

        try:
            worksheet = sheet.sheet1  # first/left-most tab
            rows = worksheet.get_all_values()
        except Exception as exc:
            raise PriceSheetError(f"Failed to read sheet data: {exc}")

        stores = self._parse_rows(rows)

        with self._lock:
            self._stores = stores
        return stores

    # ── Internals ─────────────────────────────────────────────────────

    @staticmethod
    def _import_gspread():
        try:
            import gspread
        except Exception as exc:  # pragma: no cover - environment dependent
            raise PriceSheetError(
                "The 'gspread' package is required for live pricing. "
                "Install it with: pip install gspread"
            ) from exc
        return gspread

    @staticmethod
    def _parse_rows(rows: list[list[str]]) -> dict[str, dict[str, float]]:
        """Parse raw sheet rows into a store → prices mapping.

        Pure function (no I/O) so it is unit-testable with a fake worksheet.
        """
        if not rows:
            return {}
        header = rows[0]
        canonical = [_normalize_header(h) for h in header]

        store_idx = None
        price_idx: dict[int, str] = {}
        for i, key in enumerate(canonical):
            if key == "store_name":
                store_idx = i
            elif key in PRICE_KEYS:
                price_idx[i] = key

        if store_idx is None:
            raise PriceSheetError(
                "Price sheet is missing a shop/store name column "
                "(expected a header like 'store_name', 'shop', or 'name')."
            )
        missing = [k for k in PRICE_KEYS if k not in price_idx.values()]
        if missing:
            raise PriceSheetError(
                "Price sheet is missing required price column(s): "
                + ", ".join(missing)
                + ". Expected headers: " + ", ".join(PRICE_KEYS) + "."
            )

        stores: dict[str, dict[str, float]] = {}
        for row in rows[1:]:
            if not row or all((c or "").strip() == "" for c in row):
                continue  # skip blank rows
            name = (row[store_idx] if store_idx < len(row) else "").strip()
            if not name:
                continue  # unnamed shop — skip

            prices: dict[str, float] = {}
            for idx, key in price_idx.items():
                raw = row[idx] if idx < len(row) else ""
                value = PriceSheetService._coerce_float(raw, name, key)
                if value is not None:
                    prices[key] = value

            # Only register shops that have at least one price. A shop with a
            # blank/malformed cell for some material is kept with the prices it
            # does have (the UI lets the user fill the rest manually).
            if prices:
                stores[name] = prices

        return stores

    @staticmethod
    def _coerce_float(raw: str, store: str, key: str) -> float | None:
        """Coerce a cell to float, tolerating currency symbols/commas/spaces."""
        if raw is None:
            return None
        cleaned = str(raw).strip()
        if cleaned == "":
            return None
        # Drop currency symbols, thousands separators, spaces, and any letters
        # (e.g. "GH₵ 90", "₦1,200", "USD 12.5") so only the numeric value remains.
        allowed = set("0123456789.-")
        cleaned = "".join(ch for ch in cleaned if ch in allowed)
        if cleaned in ("", "-", ".", "-."):
            return None
        try:
            return float(cleaned)
        except ValueError:
            # Non-numeric price cell — ignore this field for the shop.
            return None
