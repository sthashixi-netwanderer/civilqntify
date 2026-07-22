"""History browser tab for CivilQntify.

Displays a searchable, filterable table of past calculations
across all three tabs (Mix Design, Material Quantification,
Cost Estimation). Supports loading records back into the
appropriate tab for editing.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
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
}

_TAB_TYPE_ICONS = {
    "mix_design": "\U0001f3d7",
    "quantification": "\U0001f4cf",
    "cost_estimation": "\U0001f4b0",
}


class HistoryTab(QWidget):
    """Tab for browsing and managing calculation history."""

    load_mix_design = pyqtSignal(int)       # calc_id
    load_quantification = pyqtSignal(int)   # calc_id
    load_cost_estimation = pyqtSignal(int)  # calc_id

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

        # Header select-all checkbox
        self._select_all_cb = QCheckBox()
        self._select_all_cb.stateChanged.connect(self._on_select_all_changed)
        self._table.setCellWidget(0, 0, self._select_all_cb)

        root.addWidget(self._table, 1)

        # -- Bottom action bar --
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

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
            records = self._db.search_calculations(search, tab_type)
        else:
            records = self._db.list_calculations(
                tab_type=tab_type,
                limit=self._page_size,
                offset=self._offset,
            )

        self._populate_table(records)
        total = self._db.count_calculations(tab_type)
        self._stats_label.setText(f"{total} records")

    def _populate_table(self, records: list[dict]) -> None:
        self._table.setRowCount(len(records))
        # Reset select-all checkbox
        self._select_all_cb.blockSignals(True)
        self._select_all_cb.setChecked(False)
        self._select_all_cb.blockSignals(False)

        for i, rec in enumerate(records):
            # Checkbox column
            cb = QCheckBox()
            cb.setProperty("calc_id", rec["id"])
            self._table.setCellWidget(i, 0, cb)

            self._table.setItem(i, 1, QTableWidgetItem(str(rec["id"])))
            name_item = QTableWidgetItem(rec.get("name", ""))
            self._table.setItem(i, 2, name_item)

            tab_label = _TAB_TYPE_LABELS.get(rec["tab_type"], rec["tab_type"])
            self._table.setItem(i, 3, QTableWidgetItem(tab_label))

            date_str = rec.get("created_at", "")[:10]
            self._table.setItem(i, 4, QTableWidgetItem(date_str))

            key_result = self._extract_key_result(rec)
            self._table.setItem(i, 5, QTableWidgetItem(key_result))

    def _extract_key_result(self, rec: dict) -> str:
        """Extract a human-readable key result from the record."""
        import json
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
            return
        self._load_record(ids[0])

    def _on_double_click(self, index) -> None:
        item = self._table.item(index.row(), 0)
        if item:
            self._load_record(item.data(Qt.ItemDataRole.UserRole))

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
        else:
            QMessageBox.information(
                self, "Info", f"Cannot load record of type '{tt}'"
            )

    def _on_delete(self) -> None:
        ids = self._selected_ids()
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

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import History", "", "JSON Files (*.json)"
        )
        if not path:
            return
        with open(path, "r") as f:
            data = f.read()
        count = self._db.import_records(data)
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
        import json as _json
        records = []
        for cid in ids:
            rec = self._db.get_calculation_parsed(cid)
            if rec:
                records.append(rec)
        with open(path, "w") as f:
            _json.dump(records, f, indent=2)
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

        menu = QMenu(self)
        menu.addAction("View Details", lambda: self._view_details(calc_id))
        menu.addAction("Load into Tab", lambda: self._load_record(calc_id))
        menu.addSeparator()
        menu.addAction("Rename", lambda: self._rename(calc_id))
        menu.addAction("Delete", lambda: self._on_delete())
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _view_details(self, calc_id: int) -> None:
        rec = self._db.get_calculation_parsed(calc_id)
        if rec is None:
            return
        dlg = HistoryDetailDialog(rec, self)
        dlg.exec()

    def _rename(self, calc_id: int) -> None:
        from PyQt6.QtWidgets import QInputDialog
        rec = self._db.get_calculation(calc_id)
        if rec is None:
            return
        name, ok = QInputDialog.getText(
            self, "Rename", "Name:", text=rec.get("name", "")
        )
        if ok and name:
            self._db.rename_calculation(calc_id, name)
            self.refresh()
