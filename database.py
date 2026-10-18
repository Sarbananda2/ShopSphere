"""SQLite data-access layer: connection handling, schema creation and seeding."""
import os
import sqlite3
from datetime import datetime

from flask import current_app, g
from werkzeug.security import generate_password_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    phone         TEXT,
    address       TEXT,
    role          TEXT    NOT NULL DEFAULT 'customer',
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS categories (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT NOT NULL UNIQUE,
    slug  TEXT NOT NULL UNIQUE,
    icon  TEXT NOT NULL DEFAULT 'box',
    color TEXT NOT NULL DEFAULT '#6366f1'
);

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    sku         TEXT    NOT NULL UNIQUE,
    description TEXT    NOT NULL DEFAULT '',
    price       REAL    NOT NULL CHECK (price >= 0),
    mrp         REAL    NOT NULL DEFAULT 0,
    category_id INTEGER NOT NULL REFERENCES categories (id),
    stock       INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    icon        TEXT    NOT NULL DEFAULT 'box',
    gradient    TEXT    NOT NULL DEFAULT '#6366f1,#8b5cf6',
    rating      REAL    NOT NULL DEFAULT 4.0,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS cart_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    quantity   INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    UNIQUE (user_id, product_id)
);

CREATE TABLE IF NOT EXISTS coupons (
    code         TEXT PRIMARY KEY,
    percent      REAL    NOT NULL,
    max_discount REAL    NOT NULL,
    min_order    REAL    NOT NULL DEFAULT 0,
    is_active    INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS orders (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    order_number     TEXT    NOT NULL UNIQUE,
    user_id          INTEGER NOT NULL REFERENCES users (id),
    subtotal         REAL    NOT NULL,
    discount         REAL    NOT NULL DEFAULT 0,
    coupon_code      TEXT,
    shipping         REAL    NOT NULL DEFAULT 0,
    tax              REAL    NOT NULL DEFAULT 0,
    total            REAL    NOT NULL,
    status           TEXT    NOT NULL DEFAULT 'PENDING',
    payment_status   TEXT    NOT NULL DEFAULT 'UNPAID',
    shipping_name    TEXT    NOT NULL,
    shipping_phone   TEXT    NOT NULL,
    shipping_address TEXT    NOT NULL,
    placed_at        TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id     INTEGER NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
    product_id   INTEGER NOT NULL REFERENCES products (id),
    product_name TEXT    NOT NULL,
    icon         TEXT    NOT NULL DEFAULT 'box',
    unit_price   REAL    NOT NULL,
    quantity     INTEGER NOT NULL,
    line_total   REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_id      TEXT    NOT NULL UNIQUE,
    order_id    INTEGER NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL REFERENCES users (id),
    method      TEXT    NOT NULL,
    amount      REAL    NOT NULL,
    status      TEXT    NOT NULL,
    gateway_ref TEXT,
    detail      TEXT,
    message     TEXT,
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    change     INTEGER NOT NULL,
    balance    INTEGER NOT NULL,
    reason     TEXT    NOT NULL,
    created_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_products_category ON products (category_id);
CREATE INDEX IF NOT EXISTS idx_orders_user       ON orders (user_id);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items (order_id);
CREATE INDEX IF NOT EXISTS idx_payments_order    ON payments (order_id);
"""


def get_db():
    """Return a request-scoped SQLite connection with row access by column name."""
    if "db" not in g:
        path = current_app.config["DATABASE"]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        g.db = sqlite3.connect(path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, args=(), one=False):
    """Run a SELECT and return a list of rows, or a single row when one=True."""
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute(sql, args=()):
    """Run an INSERT/UPDATE/DELETE, commit, and return the new row id."""
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db(seed=True):
    """Create every table and (optionally) load the demo catalogue."""
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()
    if seed:
        seed_db()


def reset_db():
    """Drop all data and rebuild from scratch. Used by tests and by reset_db.py."""
    db = get_db()
    for table in ("inventory_logs", "payments", "order_items", "orders",
                  "cart_items", "coupons", "products", "categories", "users"):
        db.execute("DROP TABLE IF EXISTS " + table)
    db.commit()
    init_db(seed=True)


def log_stock(product_id, change, balance, reason):
    """Write an audit row every time inventory moves."""
    execute(
        "INSERT INTO inventory_logs (product_id, change, balance, reason, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (product_id, change, balance, reason, now()),
    )


def seed_db():
    """Insert demo users, categories, products and coupons exactly once."""
    from seed_data import CATEGORIES, COUPONS, PRODUCTS, USERS

    db = get_db()
    if db.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"]:
        return  # database already carries the demo data

    for user in USERS:
        db.execute(
            "INSERT OR IGNORE INTO users (name, email, password_hash, phone, address, role, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user["name"], user["email"], generate_password_hash(user["password"]),
             user["phone"], user["address"], user["role"], now()),
        )

    for cat in CATEGORIES:
        db.execute(
            "INSERT OR IGNORE INTO categories (name, slug, icon, color) VALUES (?, ?, ?, ?)",
            (cat["name"], cat["slug"], cat["icon"], cat["color"]),
        )

    slug_to_id = {r["slug"]: r["id"] for r in db.execute("SELECT id, slug FROM categories")}

    for p in PRODUCTS:
        db.execute(
            "INSERT OR IGNORE INTO products"
            " (name, sku, description, price, mrp, category_id, stock, icon, gradient,"
            "  rating, is_active, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
            (p["name"], p["sku"], p["description"], p["price"], p["mrp"],
             slug_to_id[p["category"]], p["stock"], p["icon"], p["gradient"],
             p["rating"], now()),
        )

    for c in COUPONS:
        db.execute(
            "INSERT OR IGNORE INTO coupons (code, percent, max_discount, min_order, is_active)"
            " VALUES (?, ?, ?, ?, 1)",
            (c["code"], c["percent"], c["max_discount"], c["min_order"]),
        )

    db.commit()

    for row in db.execute("SELECT id, stock FROM products").fetchall():
        log_stock(row["id"], row["stock"], row["stock"], "Opening stock (seed)")
