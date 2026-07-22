#!/usr/bin/env python3
"""Quick diagnostic for the live supplier pricing setup.

Run this to check if your Google Sheet + credentials are configured correctly:

    python check_pricing_setup.py /path/to/credentials.json SHEET_ID_OR_URL
"""

import re
import sys

from app.pricing.price_sheet_service import PriceSheetService


def _extract_sheet_id(raw: str) -> str:
    """Extract the Sheet ID from a URL or return it as-is if it's already an ID."""
    # Match /d/<id>/ or /d/<id>#
    m = re.search(r"/d/([A-Za-z0-9_-]+)", raw)
    if m:
        return m.group(1)
    # Already looks like a bare ID (alphanumeric + dashes/underscores, 20+ chars).
    if re.fullmatch(r"[A-Za-z0-9_-]{20,}", raw):
        return raw
    # Return as-is and let gspread report the error.
    return raw


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "Usage: python check_pricing_setup.py <credentials.json> <sheet_id_or_url>\n"
            "\n"
            "You can pass either the bare Sheet ID or the full Google Sheets URL:\n"
            "  python check_pricing_setup.py creds.json 1AbCdEfGhIjKlMnOpQrStUvWxYz\n"
            "  python check_pricing_setup.py creds.json https://docs.google.com/spreadsheets/d/1AbCd.../edit"
        )
        return 1

    creds_path, raw_id = sys.argv[1], sys.argv[2]
    sheet_id = _extract_sheet_id(raw_id)

    print(f"Credentials : {creds_path}")
    print(f"Sheet ID    : {sheet_id}")
    if raw_id != sheet_id:
        print(f"  (extracted from URL)")
    print()

    svc = PriceSheetService(credentials_path=creds_path, sheet_id=sheet_id)

    if not svc.is_available():
        print("ERROR: gspread is not installed. Run:  pip install gspread")
        return 1

    print("Fetching prices from Google Sheet...")
    try:
        stores = svc.fetch_all()
    except Exception as e:
        print(f"\nERROR: {e}")
        print(
            "\nCommon causes:\n"
            "  - Wrong Sheet ID (check the URL)\n"
            "  - Sheet not shared with service account (Share → Viewer)\n"
            "  - Invalid credentials.json file"
        )
        return 1

    print(f"\nSUCCESS: Found {len(stores)} shop(s)\n")
    for name, prices in stores.items():
        price_str = ", ".join(f"{k}={v}" for k, v in prices.items())
        print(f"  {name}: {price_str}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
