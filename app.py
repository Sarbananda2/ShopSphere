# -*- coding: utf-8 -*-
"""ShopSphere - E-Commerce Web Application
MCA Integrated Project | Flask + SQLite

Run with:  python app.py       then open  http://127.0.0.1:5000
"""
from flask import Flask, render_template, session

from config import Config
from database import close_db, init_db, query
from routes.admin_routes import bp as admin_bp
from routes.auth_routes import bp as auth_bp
from routes.cart_routes import bp as cart_bp
from routes.main_routes import bp as main_bp
from routes.order_routes import bp as orders_bp
from routes.payment_routes import bp as payment_bp
from services import cart_count


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    app.teardown_appcontext(close_db)

    for bp in (main_bp, auth_bp, cart_bp, orders_bp, payment_bp, admin_bp):
        app.register_blueprint(bp)

    # ----------------------------------------------------------------- Jinja
    @app.template_filter("money")
    def money(value):
        """Format a number as Indian currency: 12345.5 -> 12,345.50"""
        try:
            value = float(value)
        except (TypeError, ValueError):
            return value
        whole, dec = "{:.2f}".format(abs(value)).split(".")
        if len(whole) > 3:                      # Indian digit grouping (lakh / crore)
            head, tail = whole[:-3], whole[-3:]
            parts = []
            while len(head) > 2:
                parts.insert(0, head[-2:])
                head = head[:-2]
            if head:
                parts.insert(0, head)
            whole = ",".join(parts + [tail])
        return "{}{}.{}".format("-" if value < 0 else "", whole, dec)

    @app.context_processor
    def inject_globals():
        """Values every template can use (navbar, footer, badges)."""
        uid = session.get("user_id")
        return {
            "STORE_NAME": app.config["STORE_NAME"],
            "CURRENCY": app.config["CURRENCY"],
            "GATEWAY_NAME": app.config["GATEWAY_NAME"],
            "cart_badge": cart_count(uid) if uid else 0,
            "nav_categories": query("SELECT * FROM categories ORDER BY name"),
            "current_user_name": session.get("name"),
            "current_role": session.get("role"),
        }

    # ------------------------------------------------------------ Error pages
    @app.errorhandler(404)
    def not_found(_):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(_):
        return render_template("500.html"), 500

    # -------------------------------------------------------- First-run setup
    with app.app_context():
        init_db(seed=True)

    return app


app = create_app()


if __name__ == "__main__":
    print("=" * 62)
    print("  ShopSphere  |  MCA Integrated Project  |  Flask + SQLite")
    print("  Storefront :  http://127.0.0.1:5000")
    print("  Admin panel:  http://127.0.0.1:5000/admin")
    print("  Admin login:  admin@shopsphere.com / Admin@123")
    print("  User  login:  user@shopsphere.com  / User@123")
    print("=" * 62)
    app.run(debug=True, host="127.0.0.1", port=5000)
