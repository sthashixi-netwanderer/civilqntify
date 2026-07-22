"""Tests for the live supplier price sheet service.

These tests exercise the pure parsing logic and the gspread-backed fetch path
without any network access, by monkeypatching the gspread client.
"""

import sys
import types

import pytest

from app.pricing.price_sheet_service import (
    PRICE_KEYS,
    PriceSheetError,
    PriceSheetService,
)


# A realistic shop-per-row sheet (header + two shops, a blank row, a bad cell).
SAMPLE_ROWS = [
    [
        "store_name",
        "cement_per_bag",
        "fine_agg_per_m3",
        "coarse_agg_per_m3",
        "water_per_1000l",
        "admixture_per_kg",
    ],
    ["Accra Cement Ltd", "95.0", "360", "410", "18", "13"],
    ["Kumasi Builders", "92.5", "340", "395", "16", "12.5"],
    ["", "", "", "", "", ""],  # blank row — skipped
    ["OddShop", "GH₵ 90", "350", "400", "15", "bad"],  # currency + bad cell
]


def test_parse_rows_basic() -> None:
    stores = PriceSheetService._parse_rows(SAMPLE_ROWS)
    assert set(stores.keys()) == {"Accra Cement Ltd", "Kumasi Builders", "OddShop"}
    assert stores["Accra Cement Ltd"]["cement_per_bag"] == 95.0
    assert stores["Accra Cement Ltd"]["fine_agg_per_m3"] == 360.0
    assert stores["Kumasi Builders"]["admixture_per_kg"] == 12.5


def test_parse_rows_strips_currency_and_skips_bad_cell() -> None:
    stores = PriceSheetService._parse_rows(SAMPLE_ROWS)
    # Currency symbol stripped.
    assert stores["OddShop"]["cement_per_bag"] == 90.0
    # Non-numeric admixture cell ignored — shop still registered with other prices.
    assert "admixture_per_kg" not in stores["OddShop"]
    assert stores["OddShop"]["fine_agg_per_m3"] == 350.0


def test_parse_rows_header_aliases() -> None:
    """Column headers may use common aliases (shop, sand, gravel, …)."""
    rows = [
        ["shop", "cement", "sand", "gravel", "water", "admix"],
        ["Shop A", "80", "300", "380", "14", "10"],
    ]
    stores = PriceSheetService._parse_rows(rows)
    assert "Shop A" in stores
    assert stores["Shop A"]["cement_per_bag"] == 80.0
    assert stores["Shop A"]["fine_agg_per_m3"] == 300.0
    assert stores["Shop A"]["coarse_agg_per_m3"] == 380.0
    assert stores["Shop A"]["water_per_1000l"] == 14.0
    assert stores["Shop A"]["admixture_per_kg"] == 10.0


def test_parse_rows_missing_store_column_raises() -> None:
    rows = [["city", "cement_per_bag"], ["Accra", "95"]]
    with pytest.raises(PriceSheetError):
        PriceSheetService._parse_rows(rows)


def test_parse_rows_missing_price_column_raises() -> None:
    rows = [["store_name", "cement_per_bag", "fine_agg_per_m3"], ["Shop A", "95", "360"]]
    with pytest.raises(PriceSheetError):
        PriceSheetService._parse_rows(rows)


def test_parse_rows_empty() -> None:
    assert PriceSheetService._parse_rows([]) == {}


def test_parse_rows_header_only_without_all_prices_raises() -> None:
    # Header declares only one price column → required columns missing.
    with pytest.raises(PriceSheetError):
        PriceSheetService._parse_rows([["store_name", "cement_per_bag"]])


def test_is_available_reflects_environment(monkeypatch) -> None:
    # Simulate gspread missing.
    real_modules = dict(sys.modules)

    def fake_import(name, *args, **kwargs):
        if name == "gspread" or name.startswith("gspread."):
            raise ImportError("no gspread")
        return real_modules.get(name) if name in real_modules else types.ModuleType(name)

    monkeypatch.setattr("builtins.__import__", fake_import)
    assert PriceSheetService.is_available() is False


def test_extract_sheet_id_from_url() -> None:
    url = "https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz/edit?gid=12345"
    assert PriceSheetService._extract_sheet_id(url) == "1AbCdEfGhIjKlMnOpQrStUvWxYz"


def test_extract_sheet_id_from_url_no_gid() -> None:
    url = "https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz/edit"
    assert PriceSheetService._extract_sheet_id(url) == "1AbCdEfGhIjKlMnOpQrStUvWxYz"


def test_extract_sheet_id_bare_id() -> None:
    assert PriceSheetService._extract_sheet_id("1AbCdEfGhIjKlMnOpQrStUvWxYz") == "1AbCdEfGhIjKlMnOpQrStUvWxYz"


def test_extract_sheet_id_empty() -> None:
    assert PriceSheetService._extract_sheet_id("") == ""


def test_extract_sheet_id_strips_whitespace() -> None:
    assert PriceSheetService._extract_sheet_id("  1AbCdEf  ") == "1AbCdEf"


# ── fetch_all with a fake gspread client ─────────────────────────────────


class _FakeWorksheet:
    def get_all_values(self):
        return SAMPLE_ROWS


class _FakeSheet:
    sheet1 = _FakeWorksheet()


class _FakeGC:
    def open_by_key(self, sheet_id):
        return _FakeSheet()


def _install_fake_gspread(monkeypatch, *, gc_class=None, service_account_raises=None) -> None:
    """Inject a fake 'gspread' module so fetch_all runs without network."""
    fake = types.ModuleType("gspread")

    def _make_service_account(filename):
        if service_account_raises is not None:
            raise service_account_raises
        return (gc_class or _FakeGC)()

    fake.service_account = _make_service_account
    # Provide a stub for gspread.exceptions used by the service.
    exc_mod = types.ModuleType("gspread.exceptions")
    exc_mod.SpreadsheetNotFound = type("SpreadsheetNotFound", (Exception,), {})
    exc_mod.APIError = type("APIError", (Exception,), {"response": None})
    fake.exceptions = exc_mod
    monkeypatch.setitem(sys.modules, "gspread", fake)
    monkeypatch.setitem(sys.modules, "gspread.exceptions", exc_mod)


def test_fetch_all_populates_cache(monkeypatch) -> None:
    _install_fake_gspread(monkeypatch)
    svc = PriceSheetService(credentials_path="/tmp/fake.json", sheet_id="SHEET123")
    stores = svc.fetch_all()
    assert "Accra Cement Ltd" in stores
    # Cache is populated for list_stores / get_store_prices.
    assert "Accra Cement Ltd" in svc.list_stores()
    assert svc.get_store_prices("Accra Cement Ltd")["cement_per_bag"] == 95.0


def test_fetch_all_not_configured_raises() -> None:
    svc = PriceSheetService(credentials_path="", sheet_id="")
    with pytest.raises(PriceSheetError):
        svc.fetch_all()


def test_fetch_all_missing_dependency_raises(monkeypatch) -> None:
    real_modules = dict(sys.modules)

    def fake_import(name, *args, **kwargs):
        if name == "gspread" or name.startswith("gspread."):
            raise ImportError("no gspread")
        return real_modules.get(name) if name in real_modules else types.ModuleType(name)

    monkeypatch.setattr("builtins.__import__", fake_import)
    svc = PriceSheetService(credentials_path="/tmp/fake.json", sheet_id="SHEET123")
    with pytest.raises(PriceSheetError):
        svc.fetch_all()


def test_fetch_all_missing_credentials_file_raises(monkeypatch) -> None:
    _install_fake_gspread(
        monkeypatch,
        service_account_raises=FileNotFoundError("no such file"),
    )
    svc = PriceSheetService(
        credentials_path="/nonexistent/path/creds.json", sheet_id="SHEET123"
    )
    with pytest.raises(PriceSheetError) as exc_info:
        svc.fetch_all()
    assert "Credentials file not found" in str(exc_info.value)


def test_fetch_all_404_sheet_not_found_raises(monkeypatch) -> None:
    class _FakeGC_404:
        def open_by_key(self, sheet_id):
            exc = Exception("Spreadsheet not found")
            exc.response = type("R", (), {"status_code": 404})()
            raise exc

    _install_fake_gspread(monkeypatch, gc_class=_FakeGC_404)
    svc = PriceSheetService(credentials_path="/tmp/fake.json", sheet_id="BAD_ID")
    with pytest.raises(PriceSheetError) as exc_info:
        svc.fetch_all()
    assert "Sheet not found" in str(exc_info.value)


def test_fetch_all_403_access_denied_raises(monkeypatch) -> None:
    class _FakeGC_403:
        def open_by_key(self, sheet_id):
            exc = Exception("Access denied")
            exc.response = type("R", (), {"status_code": 403})()
            raise exc

    _install_fake_gspread(monkeypatch, gc_class=_FakeGC_403)
    svc = PriceSheetService(credentials_path="/tmp/fake.json", sheet_id="SHEET123")
    with pytest.raises(PriceSheetError) as exc_info:
        svc.fetch_all()
    assert "Access denied" in str(exc_info.value)
