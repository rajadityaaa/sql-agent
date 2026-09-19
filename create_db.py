"""
create_db.py
------------
One-time (re-runnable) script that builds sales.db from scratch with realistic
sample data across three tables: customers, products, orders.

Run with:  python create_db.py
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "sales.db")


def create_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ── Drop existing tables (makes script re-runnable) ──────────────────────
    cursor.executescript("""
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS customers;
    """)

    # ── Create tables ─────────────────────────────────────────────────────────
    cursor.executescript("""
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            region      TEXT NOT NULL
        );

        CREATE TABLE products (
            product_id   INTEGER PRIMARY KEY,
            product_name TEXT NOT NULL,
            category     TEXT NOT NULL,
            price        REAL NOT NULL
        );

        CREATE TABLE orders (
            order_id    INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            product_id  INTEGER NOT NULL,
            quantity    INTEGER NOT NULL,
            order_date  TEXT NOT NULL,   -- ISO format: YYYY-MM-DD
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
            FOREIGN KEY (product_id)  REFERENCES products(product_id)
        );
    """)

    # ── Customers: 10 customers across 4 regions ──────────────────────────────
    customers = [
        (1,  "Alice Johnson",   "North"),
        (2,  "Bob Smith",       "South"),
        (3,  "Carol White",     "East"),
        (4,  "David Brown",     "West"),
        (5,  "Eva Martinez",    "North"),
        (6,  "Frank Lee",       "South"),
        (7,  "Grace Kim",       "East"),
        (8,  "Henry Wilson",    "West"),
        (9,  "Isabella Davis",  "North"),
        (10, "James Garcia",    "South"),
    ]
    cursor.executemany(
        "INSERT INTO customers VALUES (?, ?, ?)", customers
    )

    # ── Products: 10 products across 4 categories with varied prices ──────────
    products = [
        (1,  "Laptop Pro",        "Electronics",  1299.99),
        (2,  "Wireless Mouse",    "Electronics",    29.99),
        (3,  "USB-C Hub",         "Electronics",    49.99),
        (4,  "Mechanical Keyboard","Electronics",   89.99),
        (5,  "Office Chair",      "Furniture",     349.99),
        (6,  "Standing Desk",     "Furniture",     599.99),
        (7,  "Python Cookbook",   "Books",          39.99),
        (8,  "Data Science Guide","Books",          44.99),
        (9,  "Notebook Set",      "Stationery",     12.99),
        (10, "Ballpoint Pens 10pk","Stationery",     8.99),
    ]
    cursor.executemany(
        "INSERT INTO products VALUES (?, ?, ?, ?)", products
    )

    # ── Orders: 50 orders spread across Jan 2024 – Apr 2025 ──────────────────
    # Varied customers, products, quantities, and dates for rich aggregation.
    orders = [
        # order_id, customer_id, product_id, quantity, order_date
        ( 1,  1,  1, 1, "2024-01-05"),
        ( 2,  2,  2, 3, "2024-01-12"),
        ( 3,  3,  5, 2, "2024-01-20"),
        ( 4,  4,  7, 4, "2024-01-28"),
        ( 5,  5,  3, 2, "2024-02-03"),
        ( 6,  6,  4, 1, "2024-02-10"),
        ( 7,  7,  6, 1, "2024-02-14"),
        ( 8,  8,  9, 5, "2024-02-22"),
        ( 9,  9, 10, 8, "2024-02-27"),
        (10, 10,  1, 1, "2024-03-01"),
        (11,  1,  8, 2, "2024-03-08"),
        (12,  2,  3, 3, "2024-03-15"),
        (13,  3,  2, 5, "2024-03-19"),
        (14,  4,  4, 2, "2024-03-25"),
        (15,  5,  7, 3, "2024-04-02"),
        (16,  6,  1, 2, "2024-04-09"),
        (17,  7,  5, 1, "2024-04-16"),
        (18,  8,  6, 1, "2024-04-23"),
        (19,  9,  9, 6, "2024-04-30"),
        (20, 10,  2, 4, "2024-05-05"),
        (21,  1,  4, 1, "2024-05-12"),
        (22,  2,  8, 3, "2024-05-18"),
        (23,  3,  1, 1, "2024-05-25"),
        (24,  4, 10, 10,"2024-06-01"),
        (25,  5,  3, 4, "2024-06-08"),
        (26,  6,  7, 2, "2024-06-15"),
        (27,  7,  2, 6, "2024-06-22"),
        (28,  8,  4, 3, "2024-06-29"),
        (29,  9,  5, 2, "2024-07-05"),
        (30, 10,  6, 1, "2024-07-12"),
        (31,  1,  9, 4, "2024-07-19"),
        (32,  2,  1, 1, "2024-07-26"),
        (33,  3,  8, 2, "2024-08-02"),
        (34,  4,  3, 2, "2024-08-09"),
        (35,  5,  7, 5, "2024-08-16"),
        (36,  6, 10, 7, "2024-08-23"),
        (37,  7,  4, 2, "2024-09-03"),
        (38,  8,  2, 8, "2024-09-10"),
        (39,  9,  1, 2, "2024-09-17"),
        (40, 10,  5, 1, "2024-09-24"),
        (41,  1,  6, 1, "2024-10-01"),
        (42,  2,  9, 3, "2024-10-08"),
        (43,  3,  4, 4, "2024-11-05"),
        (44,  4,  7, 6, "2024-11-12"),
        (45,  5,  1, 1, "2024-12-03"),
        (46,  6,  8, 2, "2024-12-10"),
        (47,  7,  3, 3, "2025-01-07"),
        (48,  8, 10, 5, "2025-02-14"),
        (49,  9,  2, 4, "2025-03-21"),
        (50, 10,  6, 1, "2025-04-15"),
    ]
    cursor.executemany(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?)", orders
    )

    conn.commit()
    conn.close()

    print(f"[OK] sales.db created at: {DB_PATH}")
    _spot_check()


def _spot_check():
    """Print row counts as a quick sanity check."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for table in ("customers", "products", "orders"):
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"   {table}: {count} rows")
    conn.close()


if __name__ == "__main__":
    create_database()
