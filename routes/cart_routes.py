# -*- coding: utf-8 -*-
"""Shopping cart page plus the small JSON API the front-end calls with fetch()."""
from flask import (Blueprint, flash, jsonify, redirect, render_template,
                   request, session, url_for)

from services import (add_to_cart, cart_count, cart_rows, clear_cart,
                      current_user, find_coupon, login_required,
                      price_summary, update_cart)

bp = Blueprint("cart", __name__, url_prefix="/cart")


@bp.route("/")
@login_required
def view_cart():
    user = current_user()
    rows = cart_rows(user["id"])
    summary = price_summary(rows, session.get("coupon"))
    if session.get("coupon") and not summary["coupon"]:
        session.pop("coupon", None)  # no longer valid for this cart value
    return render_template("cart.html", rows=rows, summary=summary)


# --------------------------------------------------------------------------- #
# JSON API
# --------------------------------------------------------------------------- #
def _payload(ok, message, status=200):
    """Standard JSON response: flags, cart badge count and a re-rendered summary."""
    user_id = session.get("user_id")
    rows = cart_rows(user_id) if user_id else []
    summary = price_summary(rows, session.get("coupon"))
    return jsonify({
        "ok": ok,
        "message": message,
        "count": cart_count(user_id) if user_id else 0,
        "summary": summary,
        "empty": not rows,
        # The server renders the price box so the markup lives in one place only.
        "summary_html": render_template("_summary.html", summary=summary),
        "lines": {str(r["id"]): r["line_total"] for r in rows},
    }), status


@bp.post("/api/add")
def api_add():
    if not session.get("user_id"):
        return jsonify({"ok": False, "login_required": True,
                        "message": "Please sign in to add items to your cart"}), 401
    data = request.get_json(silent=True) or request.form
    try:
        product_id = int(data.get("product_id"))
        qty = max(1, int(data.get("quantity", 1)))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "Invalid request"}), 400

    ok, message = add_to_cart(session["user_id"], product_id, qty)
    return _payload(ok, message, 200 if ok else 409)


@bp.post("/api/update")
@login_required
def api_update():
    data = request.get_json(silent=True) or request.form
    try:
        product_id = int(data.get("product_id"))
        qty = int(data.get("quantity"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "Invalid request"}), 400

    ok, message = update_cart(session["user_id"], product_id, qty)
    return _payload(ok, message, 200 if ok else 409)


@bp.post("/api/remove")
@login_required
def api_remove():
    data = request.get_json(silent=True) or request.form
    try:
        product_id = int(data.get("product_id"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "Invalid request"}), 400
    ok, message = update_cart(session["user_id"], product_id, 0)
    return _payload(ok, message)


@bp.get("/api/count")
def api_count():
    uid = session.get("user_id")
    return jsonify({"count": cart_count(uid) if uid else 0})


@bp.post("/api/coupon")
@login_required
def api_coupon():
    data = request.get_json(silent=True) or request.form
    code = (data.get("code") or "").strip().upper()

    if not code:
        session.pop("coupon", None)
        return _payload(True, "Coupon removed")

    coupon = find_coupon(code)
    if coupon is None:
        return _payload(False, "Invalid or expired coupon code", 404)

    rows = cart_rows(session["user_id"])
    subtotal = sum(r["line_total"] for r in rows)
    if subtotal < coupon["min_order"]:
        return _payload(False, "Add items worth {:.0f} more to use {}".format(
            coupon["min_order"] - subtotal, code), 409)

    session["coupon"] = code
    return _payload(True, "Coupon {} applied".format(code))


@bp.post("/clear")
@login_required
def clear():
    clear_cart(session["user_id"])
    session.pop("coupon", None)
    flash("Cart cleared.", "info")
    return redirect(url_for("cart.view_cart"))
