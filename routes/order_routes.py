# -*- coding: utf-8 -*-
"""Checkout, order history and order cancellation."""
from flask import (Blueprint, flash, redirect, render_template, request,
                   session, url_for)

from database import execute, query
from payment_gateway import refund
from services import (cart_rows, clear_cart, create_order, current_user,
                      login_required, order_with_items, price_summary,
                      record_payment, restock, stock_problems)

bp = Blueprint("orders", __name__)


@bp.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    user = current_user()
    rows = cart_rows(user["id"])

    if not rows:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("main.index"))

    issues = stock_problems(rows)
    summary = price_summary(rows, session.get("coupon"))

    if request.method == "POST":
        name = (request.form.get("shipping_name") or "").strip()
        phone = (request.form.get("shipping_phone") or "").strip()
        address = (request.form.get("shipping_address") or "").strip()

        errors = []
        if len(name) < 3:
            errors.append("Full name is required.")
        if not phone.isdigit() or len(phone) != 10:
            errors.append("Delivery phone number must be exactly 10 digits.")
        if len(address) < 10:
            errors.append("Please enter a complete delivery address.")
        errors += issues

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("checkout.html", user=user, rows=rows,
                                   summary=summary, issues=issues, form=request.form), 400

        order_id = create_order(user, rows, summary, name, phone, address)
        clear_cart(user["id"])
        session.pop("coupon", None)
        return redirect(url_for("payment.pay", order_id=order_id))

    return render_template("checkout.html", user=user, rows=rows, summary=summary,
                           issues=issues, form={})


@bp.route("/orders")
@login_required
def my_orders():
    user = current_user()
    orders = query(
        "SELECT o.*, (SELECT COUNT(*) FROM order_items i WHERE i.order_id = o.id) AS item_count"
        "  FROM orders o WHERE o.user_id = ? ORDER BY o.id DESC", (user["id"],))
    return render_template("orders.html", orders=orders)


@bp.route("/orders/<int:order_id>")
@login_required
def order_detail(order_id):
    user = current_user()
    scope = None if user["role"] == "admin" else user["id"]
    order, items = order_with_items(order_id, scope)
    if order is None:
        return render_template("404.html"), 404
    payments = query("SELECT * FROM payments WHERE order_id = ? ORDER BY id DESC", (order_id,))
    return render_template("order_detail.html", order=order, items=items, payments=payments)


@bp.post("/orders/<int:order_id>/cancel")
@login_required
def cancel_order(order_id):
    user = current_user()
    order, _ = order_with_items(order_id, user["id"])

    if order is None:
        return render_template("404.html"), 404
    if order["status"] in ("SHIPPED", "DELIVERED", "CANCELLED"):
        flash("Order {} can no longer be cancelled.".format(order["order_number"]), "warning")
        return redirect(url_for("orders.order_detail", order_id=order_id))

    if order["payment_status"] == "PAID":
        restock(order_id, "Cancelled & refunded")
        result = refund(order["total"])
        record_payment(order_id, user["id"],
                       {"txn_id": result["gateway_ref"], "gateway_ref": result["gateway_ref"],
                        "amount": result["amount"], "method": "REFUND"},
                       result["status"], "Refund to original payment method", result["message"])
        execute("UPDATE orders SET status = 'CANCELLED', payment_status = 'REFUNDED' WHERE id = ?",
                (order_id,))
        flash("Order cancelled. " + result["message"], "success")
    else:
        execute("UPDATE orders SET status = 'CANCELLED' WHERE id = ?", (order_id,))
        flash("Order cancelled.", "info")

    return redirect(url_for("orders.order_detail", order_id=order_id))
