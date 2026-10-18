# -*- coding: utf-8 -*-
"""Checkout payment pages driven by the simulated PayNova gateway.

Flow:  /payment/<id>  ->  choose method & enter details  ->  (OTP for cards)
       ->  capture  ->  success / failure page
"""
from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, session, url_for)

import payment_gateway as pg
from database import execute, query
from services import (current_user, deduct_stock, login_required,
                      order_with_items, record_payment)

bp = Blueprint("payment", __name__, url_prefix="/payment")


def _open_order(order_id, user_id):
    """Fetch an order that still needs paying, or (None, redirect)."""
    order, items = order_with_items(order_id, user_id)
    if order is None:
        return None, None
    if order["payment_status"] == "PAID":
        flash("This order has already been paid.", "info")
        return None, redirect(url_for("orders.order_detail", order_id=order_id))
    if order["status"] == "CANCELLED":
        flash("This order was cancelled.", "warning")
        return None, redirect(url_for("orders.order_detail", order_id=order_id))
    return (order, items), None


@bp.route("/<int:order_id>")
@login_required
def pay(order_id):
    user = current_user()
    result, redirection = _open_order(order_id, user["id"])
    if redirection is not None:
        return redirection
    if result is None:
        return render_template("404.html"), 404

    order, items = result
    session.pop("pending_payment", None)
    return render_template("payment.html", order=order, items=items,
                           banks=pg.BANKS, user=user)


@bp.post("/<int:order_id>/process")
@login_required
def process(order_id):
    """Validate the instrument and either capture or hand over to the OTP step."""
    user = current_user()
    result, redirection = _open_order(order_id, user["id"])
    if redirection is not None:
        return redirection
    if result is None:
        return render_template("404.html"), 404

    order, items = result
    method = (request.form.get("method") or "").upper()

    try:
        txn = pg.initiate(order["total"], method)
        detail, requires_otp = pg.authorize(method, order["total"], request.form)
    except pg.PaymentError as exc:
        txn = {"txn_id": pg.new_txn_id(), "gateway_ref": "-",
               "amount": order["total"], "method": method or "UNKNOWN"}
        record_payment(order_id, user["id"], txn, pg.FAILED, "-", str(exc))
        execute("UPDATE orders SET payment_status = 'FAILED' WHERE id = ?", (order_id,))
        return render_template("payment_result.html", success=False, order=order,
                               message=str(exc), txn=txn), 402

    if requires_otp:
        session["pending_payment"] = {
            "order_id": order_id, "txn": txn, "detail": detail, "method": method,
        }
        masked = "XXXXX" + (user["phone"] or "00000")[-5:]
        return render_template("payment_otp.html", order=order, txn=txn,
                               detail=detail, masked_phone=masked)

    return _finalise(order, user, txn, method, detail)


@bp.post("/<int:order_id>/otp")
@login_required
def otp(order_id):
    """Second factor for card payments."""
    user = current_user()
    pending = session.get("pending_payment")

    if not pending or pending.get("order_id") != order_id:
        flash("Your payment session expired. Please start again.", "warning")
        return redirect(url_for("payment.pay", order_id=order_id))

    order, _ = order_with_items(order_id, user["id"])
    if order is None:
        return render_template("404.html"), 404

    txn, detail, method = pending["txn"], pending["detail"], pending["method"]
    attempts = session.get("otp_attempts", 0) + 1
    session["otp_attempts"] = attempts

    try:
        pg.verify_otp(request.form.get("otp"), current_app.config["GATEWAY_OTP"])
    except pg.PaymentError as exc:
        if attempts >= 3:
            session.pop("pending_payment", None)
            session.pop("otp_attempts", None)
            record_payment(order_id, user["id"], txn, pg.FAILED, detail,
                           "Transaction cancelled after 3 incorrect OTP attempts")
            execute("UPDATE orders SET payment_status = 'FAILED' WHERE id = ?", (order_id,))
            return render_template("payment_result.html", success=False, order=order,
                                   message="Transaction cancelled after 3 incorrect OTP attempts.",
                                   txn=txn), 402
        masked = "XXXXX" + (user["phone"] or "00000")[-5:]
        return render_template("payment_otp.html", order=order, txn=txn, detail=detail,
                               masked_phone=masked, error=str(exc),
                               attempts_left=3 - attempts), 401

    session.pop("pending_payment", None)
    session.pop("otp_attempts", None)
    return _finalise(order, user, txn, method, detail)


def _finalise(order, user, txn, method, detail):
    """Capture the payment, move inventory and mark the order."""
    order_id = order["id"]
    ok, stock_message = deduct_stock(order_id)

    if not ok:
        record_payment(order_id, user["id"], txn, pg.FAILED, detail, stock_message)
        execute("UPDATE orders SET payment_status = 'FAILED' WHERE id = ?", (order_id,))
        return render_template("payment_result.html", success=False, order=order,
                               message=stock_message, txn=txn), 409

    status, message = pg.capture(method)
    record_payment(order_id, user["id"], txn, status, detail, message)

    if status == pg.SUCCESS:
        execute("UPDATE orders SET status = 'CONFIRMED', payment_status = 'PAID' WHERE id = ?",
                (order_id,))
    else:  # Cash on delivery
        execute("UPDATE orders SET status = 'CONFIRMED', payment_status = 'COD_PENDING'"
                " WHERE id = ?", (order_id,))

    order = query("SELECT * FROM orders WHERE id = ?", (order_id,), one=True)
    return render_template("payment_result.html", success=True, order=order,
                           message=message, txn=txn, detail=detail, method=method)


@bp.route("/<int:order_id>/retry")
@login_required
def retry(order_id):
    execute("UPDATE orders SET payment_status = 'UNPAID' WHERE id = ? AND user_id = ?"
            " AND payment_status = 'FAILED'", (order_id, session["user_id"]))
    return redirect(url_for("payment.pay", order_id=order_id))
