# -*- coding: utf-8 -*-
"""Storefront: home page, catalogue filtering, search and product details."""
from flask import Blueprint, render_template, request

from database import query

bp = Blueprint("main", __name__)

SORT_OPTIONS = {
    "featured": "p.rating DESC, p.id",
    "price_low": "p.price ASC",
    "price_high": "p.price DESC",
    "rating": "p.rating DESC",
    "newest": "p.id DESC",
}


@bp.route("/")
def index():
    search = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "").strip()
    sort = request.args.get("sort", "featured")
    max_price = request.args.get("max_price", type=float)
    in_stock = request.args.get("in_stock") == "1"

    sql = ["SELECT p.*, c.name AS category_name, c.slug AS category_slug, c.color AS category_color",
           "  FROM products p JOIN categories c ON c.id = p.category_id",
           " WHERE p.is_active = 1"]
    args = []

    if search:
        sql.append(" AND (p.name LIKE ? OR p.description LIKE ? OR p.sku LIKE ?)")
        args += ["%{}%".format(search)] * 3
    if category:
        sql.append(" AND c.slug = ?")
        args.append(category)
    if max_price:
        sql.append(" AND p.price <= ?")
        args.append(max_price)
    if in_stock:
        sql.append(" AND p.stock > 0")

    sql.append(" ORDER BY " + SORT_OPTIONS.get(sort, SORT_OPTIONS["featured"]))

    products = query("".join(sql), tuple(args))
    categories = query(
        "SELECT c.*, COUNT(p.id) AS product_count"
        "  FROM categories c LEFT JOIN products p ON p.category_id = c.id AND p.is_active = 1"
        " GROUP BY c.id ORDER BY c.name"
    )
    deals = query(
        "SELECT p.*, c.color AS category_color FROM products p JOIN categories c ON c.id = p.category_id"
        " WHERE p.is_active = 1 AND p.mrp > p.price"
        " ORDER BY (p.mrp - p.price) * 1.0 / p.mrp DESC LIMIT 4"
    )

    return render_template(
        "index.html", products=products, categories=categories, deals=deals,
        search=search, active_category=category, sort=sort,
        max_price=max_price, in_stock=in_stock,
        price_ceiling=int((query("SELECT MAX(price) AS m FROM products", one=True)["m"] or 0) + 1),
    )


@bp.route("/product/<int:product_id>")
def product_detail(product_id):
    product = query(
        "SELECT p.*, c.name AS category_name, c.slug AS category_slug, c.color AS category_color"
        "  FROM products p JOIN categories c ON c.id = p.category_id"
        " WHERE p.id = ? AND p.is_active = 1",
        (product_id,), one=True,
    )
    if product is None:
        return render_template("404.html"), 404

    related = query(
        "SELECT p.*, c.color AS category_color FROM products p JOIN categories c ON c.id = p.category_id"
        " WHERE p.category_id = ? AND p.id != ? AND p.is_active = 1 LIMIT 4",
        (product["category_id"], product_id),
    )
    return render_template("product.html", product=product, related=related)


@bp.route("/about")
def about():
    stats = {
        "products": query("SELECT COUNT(*) AS c FROM products", one=True)["c"],
        "orders": query("SELECT COUNT(*) AS c FROM orders", one=True)["c"],
        "customers": query("SELECT COUNT(*) AS c FROM users WHERE role = 'customer'", one=True)["c"],
    }
    return render_template("about.html", stats=stats)
