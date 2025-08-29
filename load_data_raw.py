#!/usr/bin/env python3
"""
CSV → Neon Postgres (raw mirror)
- Creates raw.* tables that mirror CSVs exactly (all TEXT, headers preserved)
- TRUNCATEs and loads via COPY (fast, streamy, robust)
- Verifies row counts after load
"""

import os
from pathlib import Path
import psycopg2
from psycopg2 import sql

# Database connection string
DB_URL = "postgresql://neondb_owner:npg_HNBZ6c8dUnuC@ep-fragrant-snow-a1gvjf6b-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

BASE = Path(__file__).resolve().parent

FILES = {
    "raw.store_status": (["store_id", "status", "timestamp_utc"], BASE / "store_status.csv"),
    "raw.menu_hours":   (["store_id", "dayOfWeek", "start_time_local", "end_time_local"], BASE / "menu_hours.csv"),
    "raw.timezones":    (["store_id", "timezone_str"], BASE / "timezones.csv"),
}

DDL = """
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.store_status (
  store_id TEXT,
  status TEXT,
  timestamp_utc TEXT
);

CREATE TABLE IF NOT EXISTS raw.menu_hours (
  store_id TEXT,
  "dayOfWeek" TEXT,
  start_time_local TEXT,
  end_time_local TEXT
);

CREATE TABLE IF NOT EXISTS raw.timezones (
  store_id TEXT,
  timezone_str TEXT
);
"""

def q_ident(ident: str) -> sql.Identifier:
    # Support schema.table notation
    parts = ident.split(".")
    return sql.Identifier(*parts) if len(parts) > 1 else sql.Identifier(ident)

def copy_csv(cur, table: str, cols: list[str], path: Path):
    if not path.exists():
        raise FileNotFoundError(path)
    # Quote weird headers like "dayOfWeek"
    collist = sql.SQL(", ").join(sql.Identifier(c) for c in cols)
    stmt = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)").format(
        q_ident(table), collist
    )
    with path.open("r", encoding="utf-8") as f:
        cur.copy_expert(stmt.as_string(cur), f)

def count_csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8") as f:
        # subtract header
        return sum(1 for _ in f) - 1

def main():
    with psycopg2.connect(DB_URL) as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            print("Creating schema/tables…")
            cur.execute(DDL)

            for table, (cols, path) in FILES.items():
                print(f"\nLoading {path.name} → {table}")
                cur.execute(sql.SQL("TRUNCATE {}").format(q_ident(table)))
                copy_csv(cur, table, cols, path)
                conn.commit()

                # verify counts
                cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(q_ident(table)))
                db_count = cur.fetchone()[0]
                csv_count = count_csv_rows(path)
                ok = "OK" if db_count == csv_count else "MISMATCH"
                print(f"Rows: CSV={csv_count} DB={db_count} [{ok}]")
                if db_count != csv_count:
                    raise RuntimeError(f"Row count mismatch for {table}")

    print("\n✅ All CSVs loaded into raw.* with exact headers and counts.")

if __name__ == "__main__":
    main()
