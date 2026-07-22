# Live Supplier Pricing (Google Sheets)

CivilQntify can pull live material prices from a shared Google Sheet that
**sellers maintain**. In the **Cost Estimation** tab, pick a shop/store from the
dropdown to auto-fill its prices. Prices are locked after auto-fill but can be
edited locally via the **Edit / Override** button. The app never writes back
to the sheet.

> **Optional dependency:** `pip install gspread`. The app runs without it — the
> live-pricing controls simply stay disabled and you enter prices manually.

## 1. Sheet format (one row per shop)

The first tab of the sheet must have a header row. Each subsequent row is one
shop. Required columns:

| Column (header)      | Meaning                     | Example |
|----------------------|-----------------------------|---------|
| `store_name`         | Shop / store name (unique)  | Accra Cement Ltd |
| `cement_per_bag`     | Price per 50 kg bag (GH₵)   | 95.0    |
| `fine_agg_per_m3`    | Price per m³ sand (GH₵)     | 360     |
| `coarse_agg_per_m3`  | Price per m³ gravel (GH₵)   | 410     |
| `water_per_1000l`    | Price per 1000 L water (GH₵)| 18      |
| `admixture_per_kg`   | Price per kg admixture (GH₵)| 13      |

- Optional extra columns (e.g. `city`, `comment`) are ignored.
- Header names are matched flexibly: `shop`/`name` → store name; `sand` →
  fine aggregate; `gravel`/`stone` → coarse aggregate; `admix` → admixture, etc.
- Currency symbols, commas, and spaces in price cells are tolerated
  (`GH₵ 95`, `1,200`, `USD 12.5`).
- Blank rows and unnamed shops are skipped. A shop missing one material's price
  is still listed with the prices it does have.

## 2. Service-account credentials

1. In Google Cloud Console create a **Service Account** and download its
   `credentials.json`.
2. In the Google Sheet, share the file with the service account's email address
   as **Viewer** (read-only).
3. Copy the **Sheet ID** from the sheet URL:
   `https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit`.

## 3. Configure in CivilQntify

Open **Settings** (toolbar gear) → **Live Supplier Pricing (Google Sheet)**:

- **Sheet ID** — paste the value from step 2.3.
- **Credentials** — browse to the `credentials.json` from step 2.1.

Click **Apply**. The Cost Estimation tab fetches the shop list immediately and
refreshes whenever you press **Refresh**.

## 4. Usage

- Select a shop in **Supplier Prices (Live)** → its 5 prices load and lock
  (highlighted). The estimate uses them as-is.
- Press **Edit / Override** to unlock and adjust any price for the current
  estimate (e.g. to reflect a negotiated rate). Edits are local and saved with
  the estimate in History; the sheet is never modified.
- **Reset to Default Prices** or switching to **(manual entry)** returns to
  editable manual entry.

## Troubleshooting

| Error | Likely cause | Fix |
|-------|-------------|-----|
| **HTTP 404** — "Sheet not found" | Wrong Sheet ID, or sheet was deleted/moved | Verify the Sheet ID in the URL (`/d/<ID>/edit`). Ensure the sheet still exists. |
| **HTTP 403** — "Access denied" | Sheet not shared with service account | In Google Sheets → Share → paste the service account email → set to **Viewer**. |
| **"Credentials file not found"** | Path to `credentials.json` is wrong | Re-browse to the correct file in Settings. |
| **"Sheet not found" with 404** | Service account has no access | Share the sheet with the service account email as Viewer (see step 2 above). |
| **"Failed to authenticate"** | `credentials.json` is invalid/corrupted | Re-download from Google Cloud Console. Ensure the service account has "Service Account Token Creator" role. |
| **Header error** | Missing required columns | Ensure your sheet has these exact headers (row 1): `store_name`, `cement_per_bag`, `fine_agg_per_m3`, `coarse_agg_per_m3`, `water_per_1000l`, `admixture_per_kg`. |

### Quick diagnostic (run from terminal)

```bash
cd /home/defy/Documents/projects/civilqntify
QT_QPA_PLATFORM=offscreen python -c "
from app.pricing.price_sheet_service import PriceSheetService

# Replace these with your values
CREDENTIALS = '/path/to/credentials.json'
SHEET_ID = 'your_sheet_id_here'

svc = PriceSheetService(CREDENTIALS, SHEET_ID)
try:
    stores = svc.fetch_all()
    print(f'OK: {len(stores)} shop(s) found')
    for name, prices in stores.items():
        print(f'  {name}: {prices}')
except Exception as e:
    print(f'ERROR: {e}')
"
```

## Notes / deviations

- Read-only by design — the app does not publish prices back to the sheet.
- Requires network at fetch time (manual Refresh, plus one fetch on first open).
- If the sheet is unreachable, the dropdown keeps the last fetched shops and the
  app continues to work with manual entry.
