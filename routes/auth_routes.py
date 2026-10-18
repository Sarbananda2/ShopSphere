# -*- coding: utf-8 -*-
"""Registration, login, logout and the customer account page."""
import re

from flask import (Blueprint, flash, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from database import execute, now, query
from services import current_user, login_required

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")
PHONE_RE = re.compile(r"^[6-9]\d{9}$")


def password_problems(password):
    """Password policy: 8+ chars, at least one letter, one digit, one symbol."""
    issues = []
    if len(password) < 8:
        issues.append("at least 8 characters")
    if not re.search(r"[A-Za-z]", password):
        issues.append("one letter")
    if not re.search(r"\d", password):
        issues.append("one number")
    if not re.search(r"[^A-Za-z0-9]", password):
        issues.append("one special character")
    return issues


@bp.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("main.index"))

    form = {}
    if request.method == "POST":
        form = {k: (v or "").strip() for k, v in request.form.items()}
        name = form.get("name", "")
        email = form.get("email", "").lower()
        phone = form.get("phone", "")
        address = form.get("address", "")
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        errors = []
        if len(name) < 3:
            errors.append("Name must be at least 3 characters long.")
        if not EMAIL_RE.match(email):
            errors.append("Please enter a valid email address.")
        elif query("SELECT id FROM users WHERE email = ?", (email,), one=True):
            errors.append("An account with this email already exists.")
        if phone and not PHONE_RE.match(phone):
            errors.append("Phone number must be 10 digits starting with 6-9.")
        problems = password_problems(password)
        if problems:
            errors.append("Password needs " + ", ".join(problems) + ".")
        if password != confirm:
            errors.append("Passwords do not match.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("register.html", form=form), 400

        user_id = execute(
            "INSERT INTO users (name, email, password_hash, phone, address, role, created_at)"
            " VALUES (?, ?, ?, ?, ?, 'customer', ?)",
            (name, email, generate_password_hash(password), phone, address, now()),
        )
        session.clear()
        session["user_id"] = user_id
        session["name"] = name
        session["role"] = "customer"
        flash("Welcome aboard, {}! Your account is ready.".format(name.split()[0]), "success")
        return redirect(url_for("main.index"))

    return render_template("register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("main.index"))

    email = ""
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = query("SELECT * FROM users WHERE email = ?", (email,), one=True)

        if user is None or not check_password_hash(user["password_hash"], password):
            # Deliberately vague: never reveal which half of the pair was wrong.
            flash("Invalid email or password.", "danger")
            return render_template("login.html", email=email), 401

        session.clear()
        session["user_id"] = user["id"]
        session["name"] = user["name"]
        session["role"] = user["role"]
        flash("Signed in as {}.".format(user["name"]), "success")

        nxt = request.args.get("next")
        if nxt and nxt.startswith("/"):
            return redirect(nxt)
        return redirect(url_for("admin.dashboard" if user["role"] == "admin" else "main.index"))

    return render_template("login.html", email=email)


@bp.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("main.index"))


@bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    user = current_user()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        address = (request.form.get("address") or "").strip()
        if len(name) < 3:
            flash("Name must be at least 3 characters long.", "danger")
        elif phone and not PHONE_RE.match(phone):
            flash("Phone number must be 10 digits starting with 6-9.", "danger")
        else:
            execute("UPDATE users SET name = ?, phone = ?, address = ? WHERE id = ?",
                    (name, phone, address, user["id"]))
            session["name"] = name
            flash("Profile updated.", "success")
        return redirect(url_for("auth.account"))

    orders = query("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 5", (user["id"],))
    spent = query(
        "SELECT COALESCE(SUM(total), 0) AS t FROM orders"
        " WHERE user_id = ? AND payment_status = 'PAID'", (user["id"],), one=True)["t"]
    return render_template("account.html", user=user, orders=orders, spent=spent)


@bp.route("/account/password", methods=["POST"])
@login_required
def change_password():
    user = current_user()
    current = request.form.get("current_password") or ""
    new = request.form.get("new_password") or ""

    if not check_password_hash(user["password_hash"], current):
        flash("Your current password is incorrect.", "danger")
    elif password_problems(new):
        flash("New password needs " + ", ".join(password_problems(new)) + ".", "danger")
    else:
        execute("UPDATE users SET password_hash = ? WHERE id = ?",
                (generate_password_hash(new), user["id"]))
        flash("Password changed successfully.", "success")
    return redirect(url_for("auth.account"))
