"""History browser tab for CivilQntify.

Displays a searchable, filterable table of past calculations
across all three tabs (Mix Design, Material Quantification,
Cost Estimation). Supports loading records back into the
appropriate tab for editing.
"""

from __future__ import annotations

import json

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from history.db import get_db
from app.widgets.history_detail_dialog import HistoryDetailDialog


_TAB_TYPE_LABELS = {
    "mix_design": "Mix Design",
    "quantification": "Quantification",
    "cost_estimation": "Cost Estimation",
    "psd": "PSD Analysis",
    "doe_trial": "DOE Trial Mix",
    "aci_trial": "ACI Trial Mix",
}

_TAB_TYPE_ICONS = {
    "mix_design": "\U0001f3d7",
    "quantification": "\U0001f4cf",
    "cost_estimation": "\U0001f4b0",
    "psd": "\U0001f52c",
    "doe_trial": "\U0001f9ea",
    "aci_trial": "\U0001f9ea",
}


class HistoryTab(QWidget):
    """Tab for browsing and managing calculation history."""

    load_mix_design = pyqtSignal(int)       # calc_id
    load_quantification = pyqtSignal(int)   # calc_id
    load_cost_estimation = pyqtSignal(int)  # calc_id
    load_psd = pyqtSignal(int)              # calc_id

    def __init__(self, db=None, parent=None) -> None:
        super().__init__(parent)
        self._db = db or get_db()
        self._current_filter: str | None = None
        self._page_size = 50
        self._offset = 0
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # -- Filter bar --
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        lbl = QLabel("Filter:")
        lbl.setObjectName("result-label")
        filter_row.addWidget(lbl)

        self._type_combo = QComboBox()
        self._type_combo.addItem("All Types", None)
        self._type_combo.addItem("\U0001f3d7 Mix Design", "mix_design")
        self._type_combo.addItem("\U0001f4cf Quantification", "quantification")
        self._type_combo.addItem("\U0001f4b0 Cost Estimation", "cost_estimation")
        self._type_combo.addItem("\U0001f52c PSD Analysis", "psd")
        self._type_combo.addItem("\U0001f9ea DOE Trial Mix", "doe_trial")
        self._type_combo.addItem("\U0001f9ea ACI Trial Mix", "aci_trial")
        self._type_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._type_combo)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search by name or tag...")
        self._search_input.returnPressed.connect(self._on_search)
        filter_row.addWidget(self._search_input, 1)

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._on_search)
        filter_row.addWidget(search_btn)

        filter_row.addStretch()

        # -- Stats label --
        self._stats_label = QLabel("")
        self._stats_label.setObjectName("result-unit")
        filter_row.addWidget(self._stats_label)

        root.addLayout(filter_row)

        # -- Table --
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["", "ID", "Name", "Type", "Date", "Key Result"]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed
        )
        self._table.setColumnWidth(0, 36)
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.Stretch
        )
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        self._table.doubleClicked.connect(self._on_double_click)

        root.addWidget(self._table, 1)

        # -- Pagination --
        page_row = QHBoxLayout()
        page_row.setSpacing(8)
        self._btn_prev = QPushButton("\u2190 Prev")
        self._btn_prev.clicked.connect(self._on_prev_page)
        page_row.addWidget(self._btn_prev)
        self._page_label = QLabel("")
        self._page_label.setObjectName("result-unit")
        page_row.addWidget(self._page_label)
        page_row.addStretch()
        self._btn_next = QPushButton("Next \u2192")
        self._btn_next.clicked.connect(self._on_next_page)
        page_row.addWidget(self._btn_next)
        root.addLayout(page_row)

        # -- Bottom action bar --
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        # Select-all lives outside the table: a cell-widget checkbox would
        # be overwritten by the first data row on every refresh.
        self._select_all_cb = QCheckBox("Select All")
        self._select_all_cb.stateChanged.connect(self._on_select_all_changed)
        action_row.addWidget(self._select_all_cb)

        btn_load = QPushButton("Load Selected")
        btn_load.clicked.connect(self._on_load)
        action_row.addWidget(btn_load)

        btn_delete = QPushButton("Delete Selected")
        btn_delete.clicked.connect(self._on_delete)
        action_row.addWidget(btn_delete)

        btn_export_selected = QPushButton("Export Selected")
        btn_export_selected.clicked.connect(self._on_export_selected)
        action_row.addWidget(btn_export_selected)

        action_row.addStretch()

        btn_import = QPushButton("Import JSON")
        btn_import.clicked.connect(self._on_import)
        action_row.addWidget(btn_import)

        btn_export_all = QPushButton("Export All")
        btn_export_all.clicked.connect(self._on_export)
        action_row.addWidget(btn_export_all)

        btn_clear_all = QPushButton("Clear All History")
        btn_clear_all.setObjectName("danger-btn")
        btn_clear_all.clicked.connect(self._on_clear_all)
        action_row.addWidget(btn_clear_all)

        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.refresh)
        action_row.addWidget(btn_refresh)

        root.addLayout(action_row)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Reload the table from the database."""
        tab_type = self._type_combo.currentData()
        search = self._search_input.text().strip() or None

        if search:
            found = self._db.search_calculations(search, tab_type)
            total = len(found)
            records = found[self._offset : self._offset + self._page_size]
        else:
            records = self._db.list_calculations(
                tab_type=tab_type,
                limit=self._page_size,
                offset=self._offset,
            )
            total = self._db.count_calculations(tab_type)

        # A filter change may leave the offset past the last page.
        if self._offset > 0 and self._offset >= total:
            self._offset = max(0, ((total - 1) // self._page_size) * self._page_size)
            return self.refresh()

        self._populate_table(records)
        self._stats_label.setText(f"{total} records")
        self._update_nav(total)

    def _populate_table(self, records: list[dict]) -> None:
        self._table.setRowCount(len(records))
        # Reset select-all checkbox
        self._select_all_cb.blockSignals(True)
        self._select_all_cb.setChecked(False)
        self._select_all_cb.blockSignals(False)

        pinned_bg = QBrush(QColor("#fef3c7"))
        pinned_fg = QBrush(QColor("#92400e"))

        for i, rec in enumerate(records):
            pinned = bool(rec.get("pinned"))

            # Checkbox column
            cb = QCheckBox()
            cb.setProperty("calc_id", rec["id"])
            self._table.setCellWidget(i, 0, cb)

            id_item = QTableWidgetItem(str(rec["id"]))
            if pinned:
                f = QFont(id_item.font())
                f.setBold(True)
                id_item.setFont(f)
                id_item.setBackground(pinned_bg)
                id_item.setToolTip("Pinned — stays at top. Right-click to unpin.")
            self._table.setItem(i, 1, id_item)

            raw_name = rec.get("name", "") or ""
            display_name = f"\U0001f4cc {raw_name}" if pinned else raw_name
            # Use pushpin 📌 U+1F4CC
            if pinned and not raw_name:
                display_name = "\U0001f4cc"
            name_item = QTableWidgetItem(display_name)
            if pinned:
                f = QFont(name_item.font())
                f.setBold(True)
                name_item.setFont(f)
                name_item.setBackground(pinned_bg)
                name_item.setForeground(pinned_fg)
                name_item.setToolTip("Pinned — stays at top. Right-click to unpin or rename.")
            else:
                name_item.setToolTip("Right-click to pin to top or rename.")
            self._table.setItem(i, 2, name_item)

            tab_label = _TAB_TYPE_LABELS.get(rec["tab_type"], rec["tab_type"])
            type_item = QTableWidgetItem(tab_label)
            if pinned:
                f = QFont(type_item.font())
                f.setBold(True)
                type_item.setFont(f)
                type_item.setBackground(pinned_bg)
            self._table.setItem(i, 3, type_item)

            date_str = rec.get("created_at", "")[:10]
            date_item = QTableWidgetItem(date_str)
            if pinned:
                date_item.setBackground(pinned_bg)
            self._table.setItem(i, 4, date_item)

            key_result = self._extract_key_result(rec)
            key_item = QTableWidgetItem(key_result)
            if pinned:
                key_item.setBackground(pinned_bg)
            self._table.setItem(i, 5, key_item)

    def _extract_key_result(self, rec: dict) -> str:
        """Extract a human-readable key result from the record."""
        try:
            result = json.loads(rec.get("result_json", "{}"))
        except (json.JSONDecodeError, TypeError):
            return ""

        tt = rec["tab_type"]
        if tt == "mix_design":
            wc = result.get("w_c_ratio", "")
            cement = result.get("cement_kg", "")
            code = result.get("code_used", "")
            return f"W/C={wc}, C={cement} kg [{code}]"
        elif tt == "quantification":
            vol = result.get("gross_concrete_volume_m3", "")
            cement = result.get("total_cement_kg", "")
            return f"Vol={vol} m\u00b3, C={cement} kg"
        elif tt == "cost_estimation":
            total = result.get("total_project_cost", "")
            return f"Total: {total}"
        elif tt == "psd":
            key = f"Total={result.get('total_mass', '')} g"
            fm = result.get("fineness_modulus")
            if fm is not None:
                key += f", FM={fm}"
            return key
        elif tt == "doe_trial":
            fig7 = result.get("figure7") or {}
            verdict = (result.get("verdict") or {}).get("decision", "")
            if fig7.get("D") is not None:
                return f"w/c {fig7.get('B')}\u2192{fig7.get('D')}, C={fig7.get('C')} MPa [{verdict or 'n/a'}]"
            return "DOE trial record"
        elif tt == "aci_trial":
            nt = result.get("next_trial_per_m3") or {}
            y = result.get("yield") or {}
            ry = y.get("relative_yield")
            if nt.get("water"):
                ry_txt = f", Ry={ry}" if ry is not None else ""
                return (f"next water {nt.get('water')} kg/m\u00b3{ry_txt}, "
                        f"w/cm {result.get('next_trial_w_cm') or '\u2014'}")
            return "ACI trial record"
        return ""

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _selected_ids(self) -> list[int]:
        """Return calc_ids of all checked rows."""
        ids = []
        for row in range(self._table.rowCount()):
            cb = self._table.cellWidget(row, 0)
            if cb and cb.isChecked():
                calc_id = cb.property("calc_id")
                if calc_id is not None:
                    ids.append(calc_id)
        return ids

    def _on_load(self) -> None:
        ids = self._selected_ids()
        if not ids:
            QMessageBox.information(
                self,
                "No Selection",
                "No records selected. Check the boxes next to the records "
                "to load them.",
            )
            return
        # Load every checked record into its tab. Emission runs in reverse
        # so the topmost (newest) checked record is loaded last — the main
        # window navigates to that record's tab.
        for calc_id in reversed(ids):
            self._load_record(calc_id)

    def _on_double_click(self, index) -> None:
        cb = self._table.cellWidget(index.row(), 0)
        calc_id = cb.property("calc_id") if cb else None
        if calc_id is not None:
            self._load_record(calc_id)

    def _load_record(self, calc_id: int) -> None:
        rec = self._db.get_calculation(calc_id)
        if rec is None:
            return
        tt = rec["tab_type"]
        if tt == "mix_design":
            self.load_mix_design.emit(calc_id)
        elif tt == "quantification":
            self.load_quantification.emit(calc_id)
        elif tt == "cost_estimation":
            self.load_cost_estimation.emit(calc_id)
        elif tt == "psd":
            self.load_psd.emit(calc_id)
        elif tt == "doe_trial":
            # Trial records are view-only: show the structured detail.
            dlg = HistoryDetailDialog(rec, parent=self)
            dlg.exec()
        elif tt == "aci_trial":
            dlg = HistoryDetailDialog(rec, parent=self)
            dlg.exec()
        else:
            QMessageBox.information(
                self, "Info", f"Cannot load record of type '{tt}'"
            )

    def _delete_records(self, ids: list[int]) -> None:
        """Delete the given records after confirmation, then refresh."""
        if not ids:
            return
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete {len(ids)} record(s)? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._db.delete_calculations(ids)
            self.refresh()

    def _on_delete(self) -> None:
        self._delete_records(self._selected_ids())

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import History", "", "JSON Files (*.json)"
        )
        if not path:
            return
        with open(path, "r") as f:
            data = f.read()
        try:
            count = self._db.import_records(data)
        except (json.JSONDecodeError, OSError, ValueError) as e:
            QMessageBox.critical(
                self, "Import Failed", f"Could not import '{path}': {e}"
            )
            return
        QMessageBox.information(
            self, "Import Complete", f"Imported {count} record(s)."
        )
        self.refresh()

    def _on_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export History", "civilqntify_history.json",
            "JSON Files (*.json)"
        )
        if not path:
            return
        data = self._db.export_all()
        with open(path, "w") as f:
            f.write(data)
        QMessageBox.information(self, "Export Complete", f"Exported to {path}")

    def _on_export_selected(self) -> None:
        """Export only the checked records."""
        ids = self._selected_ids()
        if not ids:
            QMessageBox.information(
                self, "No Selection",
                "No records selected. Check the boxes next to records to export them."
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Selected", "civilqntify_selected.json",
            "JSON Files (*.json)"
        )
        if not path:
            return
        # Export the raw records (input_json/result_json as stored) so the
        # file imports back through Import JSON without losing data.
        records = []
        for cid in ids:
            rec = self._db.get_calculation(cid)
            if rec:
                records.append(rec)
        with open(path, "w") as f:
            json.dump(records, f, indent=2, default=str)
        QMessageBox.information(
            self, "Export Complete",
            f"Exported {len(records)} record(s) to {path}"
        )

    def _on_select_all_changed(self, state: int) -> None:
        """Toggle all row checkboxes to match the header checkbox."""
        checked = state == Qt.CheckState.Checked.value
        for row in range(self._table.rowCount()):
            cb = self._table.cellWidget(row, 0)
            if cb:
                cb.blockSignals(True)
                cb.setChecked(checked)
                cb.blockSignals(False)

    def _on_clear_all(self) -> None:
        """Delete all history records after confirmation."""
        total = self._db.count_calculations()
        if total == 0:
            QMessageBox.information(self, "No History", "There are no records to clear.")
            return
        reply = QMessageBox.warning(
            self, "Clear All History",
            f"This will permanently delete all {total} record(s).\n\n"
            "This action cannot be undone. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._db.clear_all()
            self.refresh()
            QMessageBox.information(
                self, "History Cleared", "All history records have been deleted."
            )

    def _on_filter_changed(self, _index: int) -> None:
        self._offset = 0
        self.refresh()

    def _on_search(self) -> None:
        self._offset = 0
        self.refresh()

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def _update_nav(self, total: int) -> None:
        """Enable/disable page buttons and show the page position."""
        pages = max(1, (total + self._page_size - 1) // self._page_size)
        page = self._offset // self._page_size + 1
        self._page_label.setText(f"Page {page} / {pages}")
        self._btn_prev.setEnabled(self._offset > 0)
        self._btn_next.setEnabled(self._offset + self._page_size < total)

    def _on_prev_page(self) -> None:
        self._offset = max(0, self._offset - self._page_size)
        self.refresh()

    def _on_next_page(self) -> None:
        self._offset += self._page_size
        self.refresh()

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _on_context_menu(self, pos) -> None:
        # Get the row under the cursor
        row = self._table.rowAt(pos.y())
        if row < 0:
            return

        cb = self._table.cellWidget(row, 0)
        calc_id = cb.property("calc_id") if cb else None
        if calc_id is None:
            return

        rec = self._db.get_calculation(calc_id)
        is_pinned = bool(rec.get("pinned")) if rec else False

        menu = QMenu(self)
        menu.addAction("View Details", lambda: self._view_details(calc_id))
        menu.addAction("Load into Tab", lambda: self._load_record(calc_id))
        menu.addSeparator()
        pin_label = "\U0001f4cc Unpin from Top" if is_pinned else "\U0001f4cc Pin to Top"
        menu.addAction(pin_label, lambda checked=False, cid=calc_id: self._toggle_pin(cid))
        menu.addAction("\u270f\ufe0f Rename\u2026", lambda: self._rename(calc_id))
        menu.addSeparator()
        menu.addAction("Delete", lambda: self._delete_records([calc_id]))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _view_details(self, calc_id: int) -> None:
        rec = self._db.get_calculation_parsed(calc_id)
        if rec is None:
            return
        dlg = HistoryDetailDialog(rec, self)
        dlg.load_requested.connect(self._load_record)
        dlg.exec()

    def _toggle_pin(self, calc_id: int) -> None:
        """Pin or unpin the record and refresh so pinned stays at top."""
        rec = self._db.get_calculation(calc_id)
        if rec is None:
            return
        is_pinned = bool(rec.get("pinned"))
        self._db.set_pinned(calc_id, not is_pinned)
        # Pinned items sort first globally — reset to page 1 so the
        # user immediately sees the pinned row at the top instead of
        # staying on a stale page 2 offset where it is hidden.
        self._offset = 0
        self.refresh()

    def _rename(self, calc_id: int) -> None:
        from PyQt6.QtWidgets import QInputDialog, QLineEdit

        rec = self._db.get_calculation(calc_id)
        if rec is None:
            return
        old_name = rec.get("name", "") or ""
        name, ok = QInputDialog.getText(
            self,
            "Rename History Entry",
            "Custom name:",
            QLineEdit.EchoMode.Normal,
            old_name,
        )
        if not ok:
            return
        new_name = name.strip()
        if not new_name:
            # Ignore empty — keep existing name. Allow clearing via explicit
            # empty handling if desired: uncomment the next two lines.
            # self._db.rename_calculation(calc_id, "")
            # self.refresh()
            return
        if new_name == old_name:
            return
        self._db.rename_calculation(calc_id, new_name)
        self.refresh()
