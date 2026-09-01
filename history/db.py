"""SQLite database manager for CivilQntify calculation history.

Stores all calculation results across the three application tabs
(Mix Design, Material Quantification, Cost Estimation) in a single
`calculations` table with JSON blobs for flexible schema.

Database location: ~/.civilqntify/history.db
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from history.serializers import (
    deserialize_bill,
    deserialize_mix_input,
    deserialize_mix_result,
    now_iso,
    serialize_bill,
    serialize_cost_data,
    serialize_mix_input,
    serialize_mix_result,
    serialize_psd_input,
    serialize_psd_result,
    serialize_transfer_data,
)

# Default database location
_DEFAULT_DB_DIR = Path.home() / ".civilqntify"
_DEFAULT_DB_PATH = _DEFAULT_DB_DIR / "history.db"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS calculations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tab_type      TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    name          TEXT DEFAULT '',
    tags          TEXT DEFAULT '',
    input_json    TEXT NOT NULL,
    result_json   TEXT NOT NULL,
    parent_id     INTEGER,
    FOREIGN KEY (parent_id) REFERENCES calculations(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_calculations_tab
    ON calculations(tab_type);
CREATE INDEX IF NOT EXISTS idx_calculations_created
    ON calculations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_calculations_parent
    ON calculations(parent_id);
"""


class HistoryDB:
    """SQLite-backed history storage for CivilQntify calculations.

    Usage::

        db = HistoryDB()  # uses default ~/.civilqntify/history.db
        calc_id = db.save_mix_design(inp, result, name="My Project")
        record = db.get_calculation(calc_id)
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------
    # Save methods
    # ------------------------------------------------------------------

    def save_mix_design(
        self,
        inp: Any,
        result: Any,
        *,
        name: str = "",
        parent_id: int | None = None,
    ) -> int:
        """Save a mix design calculation. Returns the new record ID."""
        now = now_iso()
        cur = self._conn.execute(
            """INSERT INTO calculations
               (tab_type, created_at, updated_at, name, input_json, result_json, parent_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("mix_design", now, now, name,
             serialize_mix_input(inp), serialize_mix_result(result), parent_id),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def save_quantification(
        self,
        inp: Any,
        bill: Any,
        *,
        name: str = "",
        parent_id: int | None = None,
        extra_input: dict | None = None,
    ) -> int:
        """Save a material quantification record. Returns the new record ID.

        *extra_input* is merged into the stored input JSON so the tab can
        record UI state the transfer data does not carry (mix-ratio parts,
        element rows, subtab and mode selection).
        """
        now = now_iso()
        input_json = serialize_transfer_data(inp)
        if extra_input:
            merged = json.loads(input_json)
            merged.update(extra_input)
            input_json = json.dumps(merged, default=str)
        cur = self._conn.execute(
            """INSERT INTO calculations
               (tab_type, created_at, updated_at, name, input_json, result_json, parent_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("quantification", now, now, name,
             input_json, serialize_bill(bill), parent_id),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def save_cost_estimation(
        self,
        cost_data: dict,
        *,
        name: str = "",
        parent_id: int | None = None,
        input: dict | None = None,
    ) -> int:
        """Save a cost estimation record. Returns the new record ID.

        *input* stores the form entries the result was computed from
        (additional-cost options, project info) so the tab can be refilled.
        """
        now = now_iso()
        cur = self._conn.execute(
            """INSERT INTO calculations
               (tab_type, created_at, updated_at, name, input_json, result_json, parent_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("cost_estimation", now, now, name,
             serialize_cost_data(input or {}), serialize_cost_data(cost_data),
             parent_id),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def save_psd(
        self,
        inp: dict,
        result: Any,
        *,
        name: str = "",
        parent_id: int | None = None,
    ) -> int:
        """Save a sieve-analysis (PSD) record. Returns the new record ID."""
        now = now_iso()
        cur = self._conn.execute(
            """INSERT INTO calculations
               (tab_type, created_at, updated_at, name, input_json, result_json, parent_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("psd", now, now, name,
             serialize_psd_input(inp), serialize_psd_result(result), parent_id),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Read methods
    # ------------------------------------------------------------------

    def get_calculation(self, calc_id: int) -> dict | None:
        """Get a single calculation by ID."""
        row = self._conn.execute(
            "SELECT * FROM calculations WHERE id = ?", (calc_id,)
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def get_calculation_parsed(self, calc_id: int) -> dict | None:
        """Get a calculation with parsed JSON blobs."""
        rec = self.get_calculation(calc_id)
        if rec is None:
            return None
        rec["input"] = json.loads(rec["input_json"])
        rec["result"] = json.loads(rec["result_json"])
        return rec

    def list_calculations(
        self,
        tab_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
    ) -> list[dict]:
        """List calculations with optional filtering."""
        query = "SELECT * FROM calculations WHERE 1=1"
        params: list[Any] = []

        if tab_type:
            query += " AND tab_type = ?"
            params.append(tab_type)

        if search:
            query += " AND (name LIKE ? OR tags LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self._conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def count_calculations(self, tab_type: str | None = None) -> int:
        """Count total calculations, optionally filtered by tab_type."""
        if tab_type:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM calculations WHERE tab_type = ?",
                (tab_type,),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM calculations"
            ).fetchone()
        return row[0]

    # ------------------------------------------------------------------
    # Update methods
    # ------------------------------------------------------------------

    def update_calculation(self, calc_id: int, **fields: Any) -> bool:
        """Update fields on an existing calculation. Returns True if updated."""
        allowed = {"name", "tags", "input_json", "result_json"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return False
        updates["updated_at"] = now_iso()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [calc_id]
        cur = self._conn.execute(
            f"UPDATE calculations SET {set_clause} WHERE id = ?", values
        )
        self._conn.commit()
        return cur.rowcount > 0

    def rename_calculation(self, calc_id: int, new_name: str) -> bool:
        return self.update_calculation(calc_id, name=new_name)

    def tag_calculation(self, calc_id: int, tags: str) -> bool:
        return self.update_calculation(calc_id, tags=tags)

    # ------------------------------------------------------------------
    # Delete methods
    # ------------------------------------------------------------------

    def delete_calculation(self, calc_id: int) -> bool:
        cur = self._conn.execute(
            "DELETE FROM calculations WHERE id = ?", (calc_id,)
        )
        self._conn.commit()
        return cur.rowcount > 0

    def delete_calculations(self, ids: list[int]) -> int:
        """Delete multiple calculations. Returns count deleted."""
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        cur = self._conn.execute(
            f"DELETE FROM calculations WHERE id IN ({placeholders})", ids
        )
        self._conn.commit()
        return cur.rowcount

    def clear_all(self) -> int:
        """Delete all calculations. Returns count deleted."""
        cur = self._conn.execute("DELETE FROM calculations")
        self._conn.commit()
        return cur.rowcount

    # ------------------------------------------------------------------
    # Chain methods
    # ------------------------------------------------------------------

    def get_chain(self, root_id: int) -> dict:
        """Follow parent_id links to build a full calculation chain.

        Returns::

            {
                "mix_design": {...} | None,
                "quantification": {...} | None,
                "cost_estimation": {...} | None,
            }
        """
        chain: dict[str, dict | None] = {
            "mix_design": None,
            "quantification": None,
            "cost_estimation": None,
        }
        rec = self.get_calculation_parsed(root_id)
        if rec is None:
            return chain
        chain[rec["tab_type"]] = rec

        # Walk children
        children = self._conn.execute(
            "SELECT id FROM calculations WHERE parent_id = ?", (root_id,)
        ).fetchall()
        for child_row in children:
            child = self.get_calculation_parsed(child_row["id"])
            if child and child["tab_type"] in chain:
                chain[child["tab_type"]] = child

        return chain

    # ------------------------------------------------------------------
    # Import / Export
    # ------------------------------------------------------------------

    def export_all(self, tab_type: str | None = None) -> str:
        """Export calculations to JSON string."""
        rows = self.list_calculations(tab_type=tab_type, limit=10000)
        return json.dumps(rows, indent=2, default=str)

    def import_records(self, json_str: str) -> int:
        """Import calculations from a JSON string. Returns count imported."""
        records = json.loads(json_str)
        if not isinstance(records, list):
            records = [records]
        count = 0
        for rec in records:
            self._conn.execute(
                """INSERT INTO calculations
                   (tab_type, created_at, updated_at, name, tags,
                    input_json, result_json, parent_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rec.get("tab_type", "unknown"),
                    rec.get("created_at", now_iso()),
                    rec.get("updated_at", now_iso()),
                    rec.get("name", ""),
                    rec.get("tags", ""),
                    rec.get("input_json", "{}"),
                    rec.get("result_json", "{}"),
                    rec.get("parent_id"),
                ),
            )
            count += 1
        self._conn.commit()
        return count

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_calculations(
        self, query: str, tab_type: str | None = None
    ) -> list[dict]:
        """Search by name, tags, or result content."""
        sql = """
            SELECT * FROM calculations
            WHERE (name LIKE ? OR tags LIKE ? OR result_json LIKE ?)
        """
        params: list[Any] = [f"%{query}%", f"%{query}%", f"%{query}%"]

        if tab_type:
            sql += " AND tab_type = ?"
            params.append(tab_type)

        sql += " ORDER BY created_at DESC"
        rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Get summary statistics."""
        total = self.count_calculations()
        by_type = {}
        for tt in ("mix_design", "quantification", "cost_estimation", "psd"):
            by_type[tt] = self.count_calculations(tt)

        row = self._conn.execute(
            "SELECT MIN(created_at) as earliest, MAX(created_at) as latest "
            "FROM calculations"
        ).fetchone()

        return {
            "total": total,
            "by_type": by_type,
            "earliest": row["earliest"] if row else None,
            "latest": row["latest"] if row else None,
        }


# Module-level singleton (lazy init)
_db: HistoryDB | None = None


def get_db() -> HistoryDB:
    """Get or create the global HistoryDB instance."""
    global _db
    if _db is None:
        _db = HistoryDB()
    return _db
