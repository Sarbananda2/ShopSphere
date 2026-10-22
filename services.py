# -*- coding: utf-8 -*-
"""Business logic shared by the view layer: cart maths, coupons, orders, stock."""
from functools import wraps

from flask import current_app, flash, redirect, session, url_for

from database import execute, log_stock, now, query

ORDER_FLOW = ["PENDING", "CONFIRMED", "PACKED", "SHIPPED", "DELIVERED"]


# --------------------------------------------------------------------------- #
# Access control
# --------------------------------------------------------------------------- #
def current_user():
    """Return the logged-in user row, or None."""
    uid = session.get("user_id")
    if not uid:
        return None
    return query("SELECT * FROM users WHERE id = ?", (uid,), one=True)


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Admin access only.", "danger")
            return redirect(url_for("main.index"))
        return view(*args, **kwargs)
    return wrapper


# --------------------------------------------------------------------------- #
# Cart
# --------------------------------------------------------------------------- #
def cart_rows(user_id):
    """Cart lines joined with live product data."""
    return query(
        "SELECT c.id AS cart_id, c.quantity, p.id, p.name, p.price, p.mrp, p.stock,"
        "       p.icon, p.gradient, p.image_url, p.sku,"
        "       (c.quantity * p.price) AS line_total"
        "  FROM cart_items c JOIN products p ON p.id = c.product_id"
        " WHERE c.user_id = ? ORDER BY c.id",
        (user_id,),
    )


def cart_count(user_id):
    row = query("SELECT COALESCE(SUM(quantity), 0) AS n FROM cart_items WHERE user_id = ?",
                (user_id,), one=True)
    return row["n"] if row else 0


def add_to_cart(user_id, product_id, qty=1):
    product = query("SELECT * FROM products WHERE id = ? AND is_active = 1",
                    (product_id,), one=True)
    if product is None:
        return False, "Product not found"
    if product["stock"] < 1:
        return False, "{} is out of stock".format(product["name"])

    existing = query("SELECT * FROM cart_items WHERE user_id = ? AND product_id = ?",
                     (user_id, product_id), one=True)
    wanted = (existing["quantity"] if existing else 0) + qty
    if wanted > product["stock"]:
        return False, "Only {} unit(s) of {} left in stock".format(product["stock"], product["name"])

    if existing:
        execute("UPDATE cart_items SET quantity = ? WHERE id = ?", (wanted, existing["id"]))
    else:
        execute("INSERT INTO cart_items (user_id, product_id, quantity) VALUES (?, ?, ?)",
                (user_id, product_id, qty))
    return True, "{} added to cart".format(product["name"])


def update_cart(user_id, product_id, qty):
    if qty <= 0:
        execute("DELETE FROM cart_items WHERE user_id = ? AND product_id = ?", (user_id, product_id))
        return True, "Item removed from cart"
    product = query("SELECT * FROM products WHERE id = ?", (product_id,), one=True)
    if product is None:
        return False, "Product not found"
    if qty > product["stock"]:
        return False, "Only {} unit(s) available".format(product["stock"])
    execute("UPDATE cart_items SET quantity = ? WHERE user_id = ? AND product_id = ?",
            (qty, user_id, product_id))
    return True, "Cart updated"


def clear_cart(user_id):
    execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))


# --------------------------------------------------------------------------- #
# Pricing
# --------------------------------------------------------------------------- #
def find_coupon(code):
    if not code:
        return None
    return query("SELECT * FROM coupons WHERE code = ? AND is_active = 1",
                 (code.strip().upper(),), one=True)


def price_summary(rows, coupon_code=None):
    """Compute subtotal, coupon discount, GST, shipping and the payable total."""
    cfg = current_app.config
    subtotal = round(sum(r["line_total"] for r in rows), 2)

    discount, applied = 0.0, None
    coupon = find_coupon(coupon_code)
    if coupon and subtotal >= coupon["min_order"]:
        discount = round(min(subtotal * coupon["percent"] / 100.0, coupon["max_discount"]), 2)
        applied = coupon["code"]

    taxable = max(subtotal - discount, 0)
    tax = round(taxable * cfg["GST_RATE"], 2)
    shipping = 0.0 if (taxable >= cfg["FREE_SHIPPING_ABOVE"] or taxable == 0) else cfg["SHIPPING_FEE"]
    total = round(taxable + tax + shipping, 2)

    return {
        "items": sum(r["quantity"] for r in rows),
        "subtotal": subtotal,
        "mrp_total": round(sum(r["mrp"] * r["quantity"] for r in rows), 2),
        "discount": discount,
        "coupon": applied,
        "tax": tax,
        "shipping": shipping,
        "total": total,
        "free_shipping_gap": max(cfg["FREE_SHIPPING_ABOVE"] - taxable, 0),
    }


# --------------------------------------------------------------------------- #
# Orders & stock
# --------------------------------------------------------------------------- #
def stock_problems(rows):
    """Return a list of human-readable stock issues for the given cart rows."""
    issues = []
    for r in rows:
        if r["quantity"] > r["stock"]:
            issues.append("{}: only {} left (you have {})".format(r["name"], r["stock"], r["quantity"]))
    return issues


def create_order(user, rows, summary, shipping_name, shipping_phone, shipping_address):
    """Persist an order plus its line items. Stock is reserved only on payment."""
    from payment_gateway import new_order_number

    order_id = execute(
        "INSERT INTO orders (order_number, user_id, subtotal, discount, coupon_code, shipping,"
        " tax, total, status, payment_status, shipping_name, shipping_phone, shipping_address, placed_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', 'UNPAID', ?, ?, ?, ?)",
        (new_order_number(), user["id"], summary["subtotal"], summary["discount"],
         summary["coupon"], summary["shipping"], summary["tax"], summary["total"],
         shipping_name, shipping_phone, shipping_address, now()),
    )
    for r in rows:
        execute(
            "INSERT INTO order_items (order_id, product_id, product_name, icon, unit_price,"
            " quantity, line_total) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (order_id, r["id"], r["name"], r["icon"], r["price"], r["quantity"], r["line_total"]),
        )
    return order_id


def order_with_items(order_id, user_id=None):
    sql = "SELECT * FROM orders WHERE id = ?"
    args = [order_id]
    if user_id is not None:
        sql += " AND user_id = ?"
        args.append(user_id)
    order = query(sql, tuple(args), one=True)
    if order is None:
        return None, []
    items = query("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
    return order, items


def deduct_stock(order_id):
    """Move inventory once a payment is confirmed. Returns (ok, message)."""
    items = query("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
    for item in items:
        product = query("SELECT * FROM products WHERE id = ?", (item["product_id"],), one=True)
        if product is None or product["stock"] < item["quantity"]:
            name = item["product_name"]
            return False, "{} went out of stock before payment completed".format(name)

    for item in items:
        product = query("SELECT * FROM products WHERE id = ?", (item["product_id"],), one=True)
        balance = product["stock"] - item["quantity"]
        execute("UPDATE products SET stock = ? WHERE id = ?", (balance, product["id"]))
        log_stock(product["id"], -item["quantity"], balance, "Sold - order #{}".format(order_id))
    return True, "Stock updated"


def restock(order_id, reason="Order cancelled"):
    for item in query("SELECT * FROM order_items WHERE order_id = ?", (order_id,)):
        product = query("SELECT * FROM products WHERE id = ?", (item["product_id"],), one=True)
        if product is None:
            continue
        balance = product["stock"] + item["quantity"]
        execute("UPDATE products SET stock = ? WHERE id = ?", (balance, product["id"]))
        log_stock(product["id"], item["quantity"], balance,
                  "{} - order #{}".format(reason, order_id))


def record_payment(order_id, user_id, txn, status, detail, message):
    execute(
        "INSERT INTO payments (txn_id, order_id, user_id, method, amount, status,"
        " gateway_ref, detail, message, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (txn["txn_id"], order_id, user_id, txn["method"], txn["amount"], status,
         txn["gateway_ref"], detail, message, now()),
    )
