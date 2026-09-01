"""Standards compliance dialog — clause-by-clause acceptance report.

Shown automatically after "Compute & Plot" whenever the sieve analysis or
any entered laboratory result fails a requirement of the selected grading
standard (ASTM C33 edition C 33 – 99ae1 per
``docs/ASTM-C33-99-Concrete-Aggregates.md``, or IS 383:2016 per
``docs/IS-383-2016-Coarse-and-Fine-Aggregate-for-Concrete.md``).
Each row cites the exact clause or table the limit comes from so the user
never has to open the standard to understand a failure.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from concrete_mix.validation.base import (
    FAIL,
    NOT_EVALUATED,
    PASS,
    ClauseCheck,
)

_STATUS_TEXT = {
    FAIL: "✗ NOT MET",
    PASS: "✓ Meets",
    NOT_EVALUATED: "— n/a",
}
_STATUS_COLOR = {
    FAIL: "#b91c1c",
    PASS: "#047857",
    NOT_EVALUATED: "#64748b",
}


class ASTM_C33ComplianceDialog(QDialog):
    """Modal report listing every evaluated requirement of the standard.

    The header states how many requirements are not met; the body lists the
    failing clauses with their measured values and the standard's wording,
    followed by a full table of every check (met / not met / not evaluated).

    *standard_name* only changes the title/header wording ("ASTM C33" or
    "IS 383") — the checks themselves come from the standard's evaluator.
    """

    def __init__(
        self,
        checks: list[ClauseCheck],
        aggregate_kind: str = "fine",
        parent: QWidget | None = None,
        standard_name: str = "ASTM C33",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{standard_name} Compliance — Non-Conformance")
        self.resize(820, 560)
        self.setMinimumSize(680, 420)

        failures = [c for c in checks if c.failed]
        kind_label = "fine aggregate" if aggregate_kind == "fine" else "coarse aggregate"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel(
            f"⚠ {len(failures)} requirement(s) NOT met — the {kind_label} "
            f"analysis does not conform to {standard_name}."
        )
        header.setWordWrap(True)
        header.setStyleSheet(
            "QLabel {"
            "  background-color: #fef2f2;"
            "  color: #7f1d1d;"
            "  border: 1px solid #dc2626;"
            "  border-radius: 6px;"
            "  padding: 10px 14px;"
            "  font-size: 13px;"
            "  font-weight: 700;"
            "}"
        )
        layout.addWidget(header)

        # Detailed failure paragraphs — one per unmet clause.
        details = QLabel(self._failure_html(failures))
        details.setWordWrap(True)
        details.setTextFormat(Qt.TextFormat.RichText)
        details.setStyleSheet("QLabel { color: #1f2937; font-size: 12px; }")
        layout.addWidget(details)

        # Full checklist table.
        table = QTableWidget(len(checks), 4)
        table.setHorizontalHeaderLabels(
            ["Status", "Clause", "Requirement", "Result / measured value"]
        )
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        for row, check in enumerate(checks):
            status_item = QTableWidgetItem(_STATUS_TEXT[check.status])
            status_item.setForeground(
                Qt.GlobalColor.red
                if check.status == FAIL
                else Qt.GlobalColor.darkGreen
                if check.status == PASS
                else Qt.GlobalColor.gray
            )
            status_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
            table.setItem(row, 0, status_item)
            table.setItem(row, 1, QTableWidgetItem(check.clause))
            table.setItem(row, 2, QTableWidgetItem(check.requirement))
            table.setItem(row, 3, QTableWidgetItem(check.measured))
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        layout.addWidget(table, 1)

        if standard_name == "IS 383":
            note_text = (
                "Clause and table numbers follow IS 383:2016 (Third "
                "Revision, incorporating Amendment No. 1), extracted in "
                "docs/IS-383-2016-Coarse-and-Fine-Aggregate-for-Concrete.md."
                " Requirements shown as “n/a” had no test result entered or "
                "carry no requirement (a dash cell of the standard's tables) "
                "and were not evaluated."
            )
        else:
            note_text = (
                "Clause and table numbers follow ASTM C 33 – 99ae1, the edition "
                "extracted in docs/ASTM-C33-99-Concrete-Aggregates.md (later "
                "C33/C33M editions renumber the Clause 6.1 grading table as "
                "“Table 1”). Requirements shown as “n/a” had no test result "
                "entered and were not evaluated."
            )
        note = QLabel(note_text)
        note.setWordWrap(True)
        note.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    @staticmethod
    def _failure_html(failures: list[ClauseCheck]) -> str:
        if not failures:
            return ""
        parts = ["<b>The analysis does not meet the following requirements:</b>"]
        for check in failures:
            text = (
                f"<br><b>Clause {check.clause} — {check.title}:</b> "
                f"{check.measured}."
            )
            if check.detail:
                text += f"<br>{check.detail}"
            parts.append(text)
        return "".join(parts)
