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
    icon      TEXT NOT NULL DEFAULT 'box',
    color     TEXT NOT NULL DEFAULT '#6366f1',
    image_url TEXT NOT NULL DEFAULT ''
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
    image_url   TEXT    NOT NULL DEFAULT '',
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

# Columns added after the first release. CREATE TABLE IF NOT EXISTS leaves an
# older database file untouched, so init_db() adds these in place; SQLite
# raises OperationalError ("duplicate column") when one is already there.
MIGRATIONS = (
    "ALTER TABLE products ADD COLUMN image_url TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE categories ADD COLUMN image_url TEXT NOT NULL DEFAULT ''",
)


class DictRow(dict):
    """Row wrapper allowing access by column name (row['col']) and numeric index (row[0])."""
    def __init__(self, cols, values):
        super().__init__(zip(cols, values))
        self._values = tuple(values)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


class LibSQLCursorWrapper:
    """Cursor wrapper that normalises libSQL tuple rows into DictRow objects."""
    def __init__(self, cursor):
        self._cursor = cursor

    def __iter__(self):
        return iter(self.fetchall())

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def description(self):
        return self._cursor.description

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        cols = [c[0] for c in self._cursor.description] if self._cursor.description else []
        return DictRow(cols, row)

    def fetchall(self):
        raw = self._cursor.fetchall()
        cols = [c[0] for c in self._cursor.description] if self._cursor.description else []
        return [DictRow(cols, r) for r in raw]

    def fetchmany(self, size=None):
        raw = self._cursor.fetchmany(size) if size else self._cursor.fetchmany()
        cols = [c[0] for c in self._cursor.description] if self._cursor.description else []
        return [DictRow(cols, r) for r in raw]

    def close(self):
        self._cursor.close()


class LibSQLConnectionWrapper:
    """Connection wrapper providing sqlite3-compatible interface for libSQL."""
    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, args=()):
        cur = self._conn.execute(sql, args)
        return LibSQLCursorWrapper(cur)

    def executescript(self, sql):
        return self._conn.executescript(sql)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def get_db():
    """Return a request-scoped database connection (local SQLite or Turso libSQL)."""
    if "db" not in g:
        # Automated tests always run against isolated local SQLite
        if current_app.config.get("TESTING"):
            path = current_app.config["DATABASE"]
            os.makedirs(os.path.dirname(path), exist_ok=True)
            g.db = sqlite3.connect(path)
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
            return g.db

        turso_url = os.environ.get(
            "TURSO_DATABASE_URL",
            "libsql://shopsphere-sarbanandataw.aws-ap-south-1.turso.io"
        )
        turso_token = os.environ.get(
            "TURSO_AUTH_TOKEN",
            "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3OTI2OTg4MjcsImlkIjoiMDFhMTY1MjktMTIwMS03MDZmLWJkYmUtMjc3Y2NjODY0OWRkIiwia2lkIjoiWDhyTVVLZG9DaEVFa21yQjdHa1RhaUhyZHJlejZSaFRXSnJ6Tk53b0lzRSIsInJpZCI6IjQ4MmY0MzJmLWU0ZWYtNDQwZS05MWU3LWM1NDBkMmRkZDBlYSJ9.ZYdQIPNClZpta5tNfHcKIOmbIItLxiWbYwk1RipkutRPwivuc7gvtBkf3Aey8SNRs_833j4wRT55ba5vvzMsBQ"
        )
        if turso_url and turso_token:
            import libsql_experimental as libsql
            raw_conn = libsql.connect(turso_url, auth_token=turso_token)
            g.db = LibSQLConnectionWrapper(raw_conn)
            g.db.execute("PRAGMA foreign_keys = ON")
        else:
            path = current_app.config["DATABASE"]
            # In Vercel serverless functions, root is read-only; fall back to /tmp if needed
            if os.environ.get("VERCEL") and not path.startswith("/tmp"):
                import shutil
                tmp_path = "/tmp/shopsphere.db"
                if not os.path.exists(tmp_path) and os.path.exists(path):
                    shutil.copy2(path, tmp_path)
                path = tmp_path
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
    for ddl in MIGRATIONS:
        try:
            db.execute(ddl)
        except (sqlite3.OperationalError, Exception):
            pass  # column already present
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
            "INSERT OR IGNORE INTO categories (name, slug, icon, color, image_url)"
            " VALUES (?, ?, ?, ?, ?)",
            (cat["name"], cat["slug"], cat["icon"], cat["color"], cat.get("image_url", "")),
        )

    slug_to_id = {r["slug"]: r["id"] for r in db.execute("SELECT id, slug FROM categories")}

    for p in PRODUCTS:
        db.execute(
            "INSERT OR IGNORE INTO products"
            " (name, sku, description, price, mrp, category_id, stock, icon, gradient,"
            "  image_url, rating, is_active, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
            (p["name"], p["sku"], p["description"], p["price"], p["mrp"],
             slug_to_id[p["category"]], p["stock"], p["icon"], p["gradient"],
             p.get("image_url", ""), p["rating"], now()),
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
