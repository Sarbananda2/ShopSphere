# -*- coding: utf-8 -*-
"""Admin back-office: dashboard, product CRUD, inventory, orders and payments."""
from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, url_for)

from database import execute, log_stock, now, query
from services import ORDER_FLOW, admin_required, restock

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
@admin_required
def guard():
    """Every /admin/* route requires an admin session."""
    return None


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
@bp.route("/")
def dashboard():
    one = lambda sql, args=(): query(sql, args, one=True)

    stats = {
        "revenue": one("SELECT COALESCE(SUM(total), 0) AS v FROM orders"
                       " WHERE payment_status IN ('PAID', 'COD_PENDING')")["v"],
        "orders": one("SELECT COUNT(*) AS v FROM orders")["v"],
        "pending": one("SELECT COUNT(*) AS v FROM orders WHERE status = 'PENDING'")["v"],
        "customers": one("SELECT COUNT(*) AS v FROM users WHERE role = 'customer'")["v"],
        "products": one("SELECT COUNT(*) AS v FROM products WHERE is_active = 1")["v"],
        "stock_units": one("SELECT COALESCE(SUM(stock), 0) AS v FROM products")["v"],
        "stock_value": one("SELECT COALESCE(SUM(stock * price), 0) AS v FROM products")["v"],
        "failed_payments": one("SELECT COUNT(*) AS v FROM payments WHERE status = 'FAILED'")["v"],
    }

    low_stock = query(
        "SELECT p.*, c.name AS category_name FROM products p JOIN categories c ON c.id = p.category_id"
        " WHERE p.stock <= ? ORDER BY p.stock ASC LIMIT 8",
        (current_app.config["LOW_STOCK_THRESHOLD"],))
    recent_orders = query(
        "SELECT o.*, u.name AS customer FROM orders o JOIN users u ON u.id = o.user_id"
        " ORDER BY o.id DESC LIMIT 8")
    top_products = query(
        "SELECT i.product_name, i.icon, p.gradient, p.image_url,"
        "       SUM(i.quantity) AS sold, SUM(i.line_total) AS revenue"
        "  FROM order_items i JOIN orders o ON o.id = i.order_id"
        "  JOIN products p ON p.id = i.product_id"
        " WHERE o.payment_status IN ('PAID', 'COD_PENDING')"
        " GROUP BY i.product_id ORDER BY sold DESC LIMIT 6")
    by_category = query(
        "SELECT c.name, c.color, COUNT(p.id) AS products, COALESCE(SUM(p.stock), 0) AS units"
        "  FROM categories c LEFT JOIN products p ON p.category_id = c.id"
        " GROUP BY c.id ORDER BY units DESC")

    return render_template("admin/dashboard.html", stats=stats, low_stock=low_stock,
                           recent_orders=recent_orders, top_products=top_products,
                           by_category=by_category)


# --------------------------------------------------------------------------- #
# Products
# --------------------------------------------------------------------------- #
@bp.route("/products")
def products():
    search = (request.args.get("q") or "").strip()
    sql = ("SELECT p.*, c.name AS category_name, c.color AS category_color"
           "  FROM products p JOIN categories c ON c.id = p.category_id")
    args = ()
    if search:
        sql += " WHERE p.name LIKE ? OR p.sku LIKE ?"
        args = ("%{}%".format(search),) * 2
    sql += " ORDER BY p.id DESC"
    return render_template("admin/products.html", products=query(sql, args),
                           categories=query("SELECT * FROM categories ORDER BY name"),
                           search=search)


def _product_form(form):
    """Validate the product add/edit form. Returns (values, errors)."""
    errors = []
    values = {
        "name": (form.get("name") or "").strip(),
        "sku": (form.get("sku") or "").strip().upper(),
        "description": (form.get("description") or "").strip(),
        "icon": (form.get("icon") or "\U0001F4E6").strip(),
        "gradient": (form.get("gradient") or "#6366f1,#8b5cf6").strip(),
        "image_url": (form.get("image_url") or "").strip(),
        "is_active": 1 if form.get("is_active") else 0,
    }
    for field, label, caster, lo in (("price", "Price", float, 0),
                                     ("mrp", "MRP", float, 0),
                                     ("stock", "Stock", int, 0),
                                     ("category_id", "Category", int, 1)):
        try:
            value = caster(form.get(field))
            if value < lo:
                raise ValueError
            values[field] = value
        except (TypeError, ValueError):
            errors.append("{} must be a valid number.".format(label))
            values[field] = 0

    try:
        values["rating"] = min(5.0, max(0.0, float(form.get("rating") or 4.0)))
    except ValueError:
        values["rating"] = 4.0

    if len(values["name"]) < 3:
        errors.append("Product name must be at least 3 characters.")
    if not values["sku"]:
        errors.append("SKU is required.")
    if values.get("mrp") and values.get("price") and values["price"] > values["mrp"]:
        errors.append("Selling price cannot be higher than MRP.")
    if values["image_url"] and not values["image_url"].lower().startswith(("http://", "https://")):
        errors.append("Image URL must start with http:// or https://.")
    return values, errors


@bp.route("/products/new", methods=["GET", "POST"])
def product_new():
    categories = query("SELECT * FROM categories ORDER BY name")
    if request.method == "POST":
        values, errors = _product_form(request.form)
        if query("SELECT id FROM products WHERE sku = ?", (values["sku"],), one=True):
            errors.append("SKU {} is already in use.".format(values["sku"]))
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("admin/product_form.html", categories=categories,
                                   product=values, mode="new"), 400

        product_id = execute(
            "INSERT INTO products (name, sku, description, price, mrp, category_id, stock,"
            " icon, gradient, image_url, rating, is_active, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (values["name"], values["sku"], values["description"], values["price"],
             values["mrp"], values["category_id"], values["stock"], values["icon"],
             values["gradient"], values["image_url"], values["rating"], values["is_active"], now()))
        log_stock(product_id, values["stock"], values["stock"], "Initial stock (admin)")
        flash("Product \"{}\" created.".format(values["name"]), "success")
        return redirect(url_for("admin.products"))

    return render_template("admin/product_form.html", categories=categories,
                           product={"is_active": 1, "rating": 4.0,
                                    "gradient": "#6366f1,#8b5cf6", "icon": "\U0001F4E6"},
                           mode="new")


@bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
def product_edit(product_id):
    product = query("SELECT * FROM products WHERE id = ?", (product_id,), one=True)
    if product is None:
        return render_template("404.html"), 404
    categories = query("SELECT * FROM categories ORDER BY name")

    if request.method == "POST":
        values, errors = _product_form(request.form)
        clash = query("SELECT id FROM products WHERE sku = ? AND id != ?",
                      (values["sku"], product_id), one=True)
        if clash:
            errors.append("SKU {} is already in use.".format(values["sku"]))
        if errors:
            for e in errors:
                flash(e, "danger")
            values["id"] = product_id
            return render_template("admin/product_form.html", categories=categories,
                                   product=values, mode="edit"), 400

        if values["stock"] != product["stock"]:
            log_stock(product_id, values["stock"] - product["stock"], values["stock"],
                      "Stock corrected by admin")
        execute(
            "UPDATE products SET name = ?, sku = ?, description = ?, price = ?, mrp = ?,"
            " category_id = ?, stock = ?, icon = ?, gradient = ?, image_url = ?, rating = ?,"
            " is_active = ? WHERE id = ?",
            (values["name"], values["sku"], values["description"], values["price"],
             values["mrp"], values["category_id"], values["stock"], values["icon"],
             values["gradient"], values["image_url"], values["rating"], values["is_active"],
             product_id))
        flash("Product \"{}\" updated.".format(values["name"]), "success")
        return redirect(url_for("admin.products"))

    return render_template("admin/product_form.html", categories=categories,
                           product=product, mode="edit")


@bp.post("/products/<int:product_id>/delete")
def product_delete(product_id):
    product = query("SELECT * FROM products WHERE id = ?", (product_id,), one=True)
    if product is None:
        return render_template("404.html"), 404
    # Soft delete keeps historical order lines intact.
    execute("UPDATE products SET is_active = 0 WHERE id = ?", (product_id,))
    execute("DELETE FROM cart_items WHERE product_id = ?", (product_id,))
    flash("\"{}\" removed from the storefront.".format(product["name"]), "info")
    return redirect(url_for("admin.products"))


@bp.post("/products/<int:product_id>/restore")
def product_restore(product_id):
    execute("UPDATE products SET is_active = 1 WHERE id = ?", (product_id,))
    flash("Product restored to the storefront.", "success")
    return redirect(url_for("admin.products"))


# --------------------------------------------------------------------------- #
# Inventory
# --------------------------------------------------------------------------- #
@bp.route("/inventory")
def inventory():
    products = query(
        "SELECT p.*, c.name AS category_name, c.color AS category_color"
        "  FROM products p JOIN categories c ON c.id = p.category_id"
        " ORDER BY p.stock ASC")
    logs = query(
        "SELECT l.*, p.name AS product_name, p.icon FROM inventory_logs l"
        "  JOIN products p ON p.id = l.product_id ORDER BY l.id DESC LIMIT 40")
    return render_template("admin/inventory.html", products=products, logs=logs)


@bp.post("/inventory/<int:product_id>/adjust")
def inventory_adjust(product_id):
    product = query("SELECT * FROM products WHERE id = ?", (product_id,), one=True)
    if product is None:
        return render_template("404.html"), 404

    try:
        change = int(request.form.get("change"))
    except (TypeError, ValueError):
        flash("Enter a whole number to adjust stock by.", "danger")
        return redirect(url_for("admin.inventory"))

    balance = product["stock"] + change
    if balance < 0:
        flash("Cannot remove {} units - only {} in stock.".format(abs(change), product["stock"]),
              "danger")
        return redirect(url_for("admin.inventory"))

    reason = (request.form.get("reason") or "Manual adjustment").strip()
    execute("UPDATE products SET stock = ? WHERE id = ?", (balance, product_id))
    log_stock(product_id, change, balance, reason)
    flash("{}: stock {} {} -> {}".format(product["name"], "+" if change >= 0 else "",
                                         change, balance), "success")
    return redirect(url_for("admin.inventory"))


# --------------------------------------------------------------------------- #
# Orders, payments, customers
# --------------------------------------------------------------------------- #
@bp.route("/orders")
def orders():
    status = (request.args.get("status") or "").upper()
    sql = ("SELECT o.*, u.name AS customer, u.email,"
           " (SELECT COUNT(*) FROM order_items i WHERE i.order_id = o.id) AS item_count"
           "  FROM orders o JOIN users u ON u.id = o.user_id")
    args = ()
    if status:
        sql += " WHERE o.status = ?"
        args = (status,)
    sql += " ORDER BY o.id DESC"
    return render_template("admin/orders.html", orders=query(sql, args),
                           flow=ORDER_FLOW, status=status)


@bp.post("/orders/<int:order_id>/status")
def order_status(order_id):
    order = query("SELECT * FROM orders WHERE id = ?", (order_id,), one=True)
    if order is None:
        return render_template("404.html"), 404

    new_status = (request.form.get("status") or "").upper()
    if new_status not in ORDER_FLOW + ["CANCELLED"]:
        flash("Unknown order status.", "danger")
        return redirect(url_for("admin.orders"))

    if new_status == "CANCELLED" and order["status"] != "CANCELLED":
        if order["payment_status"] in ("PAID", "COD_PENDING"):
            restock(order_id, "Cancelled by admin")
        execute("UPDATE orders SET status = 'CANCELLED' WHERE id = ?", (order_id,))
    elif new_status == "DELIVERED" and order["payment_status"] == "COD_PENDING":
        execute("UPDATE orders SET status = ?, payment_status = 'PAID' WHERE id = ?",
                (new_status, order_id))
    else:
        execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))

    flash("Order {} marked as {}.".format(order["order_number"], new_status), "success")
    return redirect(request.referrer or url_for("admin.orders"))


@bp.route("/payments")
def payments():
    rows = query(
        "SELECT p.*, o.order_number, u.name AS customer FROM payments p"
        "  JOIN orders o ON o.id = p.order_id JOIN users u ON u.id = p.user_id"
        " ORDER BY p.id DESC")
    totals = query(
        "SELECT status, COUNT(*) AS n, COALESCE(SUM(amount), 0) AS amount"
        "  FROM payments GROUP BY status")
    return render_template("admin/payments.html", payments=rows, totals=totals)


@bp.route("/customers")
def customers():
    rows = query(
        "SELECT u.*, COUNT(o.id) AS order_count,"
        "       COALESCE(SUM(CASE WHEN o.payment_status IN ('PAID','COD_PENDING')"
        "                         THEN o.total ELSE 0 END), 0) AS spent"
        "  FROM users u LEFT JOIN orders o ON o.user_id = u.id"
        " GROUP BY u.id ORDER BY u.id")
    return render_template("admin/customers.html", customers=rows)
