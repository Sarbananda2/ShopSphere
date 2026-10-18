# -*- coding: utf-8 -*-
"""Wipe the database and reload the demo catalogue.

    python reset_db.py
"""
from app import create_app
from database import reset_db

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        reset_db()
    print("Database reset. Demo users, categories, products and coupons reloaded.")
    print("  admin@shopsphere.com / Admin@123")
    print("  user@shopsphere.com  / User@123")
