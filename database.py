"""
database.py
-----------
Database access layer for the SQL Data Analyst Agent.

Exposes:
  - DB_PATH          : absolute path to the single allowed database file
  - get_connection()  : opens a read-only SQLite connection to DB_PATH only
  - get_schema()      : returns a clean, LLM-readable schema string
  - execute_query()   : runs pre-validated SQL and returns structured results
"""

import os
import sqlite3

# ── Fixed database path — the only file this module ever touches ──────────────
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sales.db")

# Tables the agent is allowed to inspect (explicit allowlist)
_TABLES = ("customers", "products", "orders")


# ── Connection ────────────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    """
    Open and return a SQLite connection to DB_PATH in read-only mode.

    The path is fixed at the module level — callers cannot override it.
    Uses the sqlite3 URI interface with mode=ro for defense-in-depth.

    Raises:
        FileNotFoundError: if sales.db does not exist at DB_PATH.
        sqlite3.Error:     if the connection cannot be established.
    """
    if not os.path.isfile(DB_PATH):
        raise FileNotFoundError(
            f"Database not found at '{DB_PATH}'. "
            "Please run 'python create_db.py' to generate it."
        )

    # Open in read-only mode via URI — prevents any accidental writes
    uri = f"file:{DB_PATH}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row  # rows accessible by column name
    return conn


# ── Schema inspection ─────────────────────────────────────────────────────────

def get_schema() -> str:
    """
    Return a concise, LLM-readable description of the database schema.

    Queries PRAGMA table_info for each table in _TABLES and formats the
    result as one line per table, e.g.:

        customers(customer_id INTEGER, name TEXT, region TEXT)
        products(product_id INTEGER, product_name TEXT, category TEXT, price REAL)
        orders(order_id INTEGER, customer_id INTEGER, product_id INTEGER,
               quantity INTEGER, order_date TEXT)

    Raises:
        FileNotFoundError: if sales.db is missing (propagated from get_connection).
        RuntimeError:      if a table is missing or PRAGMA returns no rows.
    """
    conn = get_connection()
    lines = []

    try:
        cursor = conn.cursor()
        for table in _TABLES:
            cursor.execute(f"PRAGMA table_info({table})")
            rows = cursor.fetchall()

            if not rows:
                raise RuntimeError(
                    f"Table '{table}' not found in the database. "
                    "Has sales.db been created with create_db.py?"
                )

            # Build "col_name TYPE" pairs
            col_defs = ", ".join(f"{row['name']} {row['type']}" for row in rows)
            lines.append(f"{table}({col_defs})")
    finally:
        conn.close()

    return "\n".join(lines)


# ── Query execution ──────────────────────────────────────────────────────────

_MAX_ROWS = 100  # Hard cap — never return more than this many rows


def execute_query(sql: str) -> dict:
    """
    Execute a pre-validated SQL query against the database and return results.

    IMPORTANT: Callers MUST call sql_validator.validate_sql() before this
    function. This function assumes the SQL is already validated, but still
    opens the connection in read-only mode as defense-in-depth.

    Args:
        sql: A validated SELECT statement (or WITH … SELECT).

    Returns:
        On success: {"columns": [str, ...], "rows": [list, ...], "error": None}
        On failure: {"columns": [],          "rows": [],           "error": str}

    Rows are capped at _MAX_ROWS (100) regardless of any LIMIT in the query.
    """
    try:
        conn = get_connection()  # read-only URI, raises FileNotFoundError if missing
    except FileNotFoundError as e:
        return {"columns": [], "rows": [], "error": str(e)}

    try:
        cursor = conn.cursor()
        cursor.execute(sql)

        # Extract column names from cursor description
        columns = [desc[0] for desc in cursor.description] if cursor.description else []

        # Hard row cap — fetchmany enforces _MAX_ROWS regardless of LIMIT
        raw_rows = cursor.fetchmany(_MAX_ROWS)

        # Convert sqlite3.Row (or plain tuples) to plain lists for JSON-safety
        rows = [list(row) for row in raw_rows]

        return {"columns": columns, "rows": rows, "error": None}

    except sqlite3.Error as e:
        return {
            "columns": [],
            "rows": [],
            "error": f"Query execution failed: {e}",
        }
    finally:
        conn.close()


# ── Manual verification entry point ──────────────────────────────────────────

if __name__ == "__main__":
    try:
        schema = get_schema()
        print("Database schema:")
        print("-" * 60)
        print(schema)
        print("-" * 60)
        print("Schema loaded successfully.")
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
    except RuntimeError as e:
        print(f"[ERROR] {e}")
