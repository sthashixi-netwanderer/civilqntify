"""PSD table-export: input already shows only band-required sieves.

App policy (user request): the mass-retained table lists only sieves with
a grading requirement in the selected band, so Export Table CSV matches
the on-screen rows. Pan/Total always kept and cover the shown stack.
The BS washed 75 µm measurement row is the one exception: it is kept for
BS 812 reconciliation but stripped from the export with a Note.

Standards: IS 383:2016 Table 7, ASTM C33/C33M Table 2, BS 882:1992 Tables 3/4
with BS 812-103.1 sections 7, 8 and 10.
"""
from __future__ import annotations

import csv
import io
import os
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_TMP = tempfile.mkdtemp(prefix="cq_psd_export_test_")
os.environ["XDG_CONFIG_HOME"] = _TMP
os.environ["HOME"] = _TMP

_qapp = None

@pytest.fixture()
def qt():
    global _qapp
    if _qapp is None:
        from PyQt6.QtWidgets import QApplication
        _qapp = QApplication.instance() or QApplication([])
    yield _qapp

def _make_tab():
    from app.widgets.psd_widget import ParticleSizeDistributionTab
    return ParticleSizeDistributionTab()

def _select(tab, standard, agg, needle):
    tab.standard_combo.setCurrentIndex(tab.standard_combo.findData(standard))
    tab.agg_combo.setCurrentIndex(tab.agg_combo.findData(agg))
    for i in range(tab.band_combo.count()):
        if needle.lower() in tab.band_combo.itemText(i).lower():
            tab.band_combo.setCurrentIndex(i)
            return
    raise AssertionError(f"band {needle!r} not found")

def _fill(tab, mass=10.0, pan=5.0, m1=None):
    sieves = tab._current_sieves()
    for i in range(len(sieves)):
        tab.table.item(i, 1).setText(str(mass))
    tab.table.item(len(sieves), 1).setText(str(pan))
    if m1 is not None:
        tab.bs_quality.m1_spin.setValue(m1)
    return sieves

def _export_rows(tab, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog
    captured = {}
    def fake_save(*a, **k):
        return ("/tmp/fake_psd_table.csv", "CSV (*.csv)")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(fake_save))
    written = {}
    import builtins
    real_open = open
    def fake_open(path, mode="r", *a, **k):
        if path == "/tmp/fake_psd_table.csv" and "w" in mode:
            buf = io.StringIO()
            written["buf"] = buf
            class W:
                def __enter__(self): return buf
                def __exit__(self, *e): return False
            return W()
        return real_open(path, mode, *a, **k)
    monkeypatch.setattr("builtins.open", fake_open)
    tab._on_export_table_csv()
    content = written["buf"].getvalue()
    return list(csv.reader(io.StringIO(content)))

def _sieve_rows(rows):
    # data rows excluding header/meta/pan/total/note (header match is
    # case-insensitive: the input-table header is "Sieve size" under the
    # sentence-case policy)
    out = []
    for r in rows:
        if not r: continue
        if r[0] in ("Standard", "Aggregate Type", "Reference Band", "Note"): continue
        if r[0].lower().startswith("sieve size"): continue
        if r[0].startswith("Pan") or r[0].startswith("Total"): continue
        out.append(r[0])
    return out

def test_astm_coarse_size67_strips_to_five(qt, monkeypatch):
    tab = _make_tab()
    _select(tab, "astm_c33", "coarse", "Size 67")
    sieves = _fill(tab)
    assert sieves == [25.0, 19.0, 9.5, 4.75, 2.36]
    rows = _export_rows(tab, monkeypatch)
    kept = _sieve_rows(rows)
    assert kept == ["25 mm", "19 mm", "9.5 mm", "4.75 mm", "2.36 mm"]
    assert any(r and r[0].startswith("Pan") for r in rows)
    assert any(r and r[0].startswith("Total") for r in rows)

def test_is_graded40_strips_to_five(qt, monkeypatch):
    tab = _make_tab()
    _select(tab, "is383", "coarse", "Graded")
    # ensure 40mm graded selected (first graded entry)
    sieves = _fill(tab)
    rows = _export_rows(tab, monkeypatch)
    kept = _sieve_rows(rows)
    assert kept == ["80 mm", "40 mm", "20 mm", "10 mm", "4.75 mm"]

def test_bs_fine_overall_no_strip_no_note(qt, monkeypatch):
    tab = _make_tab()
    _select(tab, "bs882", "fine", "Overall")
    sieves = _fill(tab, m1=len(tab._current_sieves()) * 10.0 + 5.0)
    rows = _export_rows(tab, monkeypatch)
    kept = _sieve_rows(rows)
    assert len(kept) == 7
    assert not any(r and r[0] == "Note" for r in rows)

def test_bs_coarse_single40_strips_dashes(qt, monkeypatch):
    tab = _make_tab()
    _select(tab, "bs882", "coarse", "single")
    # select single 40 explicitly
    for i in range(tab.band_combo.count()):
        if "single 40" in tab.band_combo.itemText(i).lower():
            tab.band_combo.setCurrentIndex(i)
            break
    sieves = tab._current_sieves()
    _fill(tab, m1=len(sieves) * 10.0 + 5.0)
    rows = _export_rows(tab, monkeypatch)
    kept = _sieve_rows(rows)
    assert kept == ["50 mm", "37.5 mm", "20 mm", "10 mm"]

def test_astm_fine_no_strip(qt, monkeypatch):
    tab = _make_tab()
    _select(tab, "astm_c33", "fine", "Table 1")
    sieves = _fill(tab)
    assert len(sieves) == 7
    rows = _export_rows(tab, monkeypatch)
    assert len(_sieve_rows(rows)) == 7
    assert not any(r and r[0] == "Note" for r in rows)
