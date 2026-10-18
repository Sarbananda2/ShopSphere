# -*- coding: utf-8 -*-
"""Automated test-suite for the ShopSphere e-commerce application.

Run from the project root:

    python -m unittest discover -s tests -v
    or simply:  python run_tests.py

Covers: authentication, catalogue, cart API, coupons, pricing, checkout,
every payment method, OTP handling, inventory movement and admin access.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app                      # noqa: E402
from config import TestConfig                   # noqa: E402
from database import query, reset_db            # noqa: E402
import payment_gateway as pg                    # noqa: E402

GOOD_CARD = "4111 1111 1111 1111"
DECLINED_CARD = "4000000000000002"
NO_FUNDS_CARD = "4000000000009995"
BAD_CARD = "1234567812345678"


class BaseCase(unittest.TestCase):
    """Builds a throwaway database and a Flask test client for each test."""

    @classmethod
    def setUpClass(cls):
        if os.path.exists(TestConfig.DATABASE):
            os.remove(TestConfig.DATABASE)
        cls.app = create_app(TestConfig)

    def setUp(self):
        with self.app.app_context():
            reset_db()
        self.client = self.app.test_client()

    # ----------------------------------------------------------- helpers
    def login(self, email="user@shopsphere.com", password="User@123"):
        return self.client.post("/login", data={"email": email, "password": password},
                                follow_redirects=True)

    def login_admin(self):
        return self.login("admin@shopsphere.com", "Admin@123")

    def product(self, index=0):
        with self.app.app_context():
            return query("SELECT * FROM products WHERE stock > 0 ORDER BY id")[index]

    def add_to_cart(self, product_id, quantity=1):
        return self.client.post("/cart/api/add",
                                json={"product_id": product_id, "quantity": quantity})

    def place_order(self, product_id=None, quantity=1):
        """Login -> add to cart -> checkout. Returns the new order id."""
        pid = product_id or self.product()["id"]
        self.add_to_cart(pid, quantity)
        self.client.post("/checkout", data={
            "shipping_name": "Demo Customer",
            "shipping_phone": "9876500002",
            "shipping_address": "Flat 402, Green Residency, Kochi - 682016",
        })
        with self.app.app_context():
            return query("SELECT id FROM orders ORDER BY id DESC", one=True)["id"]

    def pay_by_card(self, order_id, card=GOOD_CARD, otp="123456"):
        res = self.client.post("/payment/{}/process".format(order_id), data={
            "method": "CARD", "card_number": card, "card_name": "DEMO CUSTOMER",
            "expiry_month": "12", "expiry_year": "2030", "cvv": "123",
        })
        if res.status_code != 200 or b"otp" not in res.data.lower():
            return res
        return self.client.post("/payment/{}/otp".format(order_id), data={"otp": otp})


# ===================================================================== #
# 1. Storefront
# ===================================================================== #
class TestStorefront(BaseCase):

    def test_home_page_loads_with_products(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"ShopSphere", res.data)
        self.assertIn(b"Add to cart", res.data)

    def test_seed_catalogue_is_present(self):
        with self.app.app_context():
            self.assertEqual(query("SELECT COUNT(*) AS c FROM categories", one=True)["c"], 6)
            self.assertGreaterEqual(query("SELECT COUNT(*) AS c FROM products", one=True)["c"], 20)

    def test_search_finds_a_known_product(self):
        res = self.client.get("/?q=Headphones")
        self.assertIn(b"Nova Pro Wireless Headphones", res.data)

    def test_search_with_no_match_shows_empty_state(self):
        res = self.client.get("/?q=zzzznotarealproduct")
        self.assertIn(b"No products matched", res.data)

    def test_category_filter(self):
        res = self.client.get("/?category=books")
        self.assertIn(b"Mastering Python Programming", res.data)
        self.assertNotIn(b"Nova Pro Wireless Headphones", res.data)

    def test_price_sorting_is_ascending(self):
        with self.app.app_context():
            rows = query("SELECT price FROM products WHERE is_active = 1 ORDER BY price ASC")
            prices = [r["price"] for r in rows]
        self.assertEqual(prices, sorted(prices))

    def test_product_detail_page(self):
        p = self.product()
        res = self.client.get("/product/{}".format(p["id"]))
        self.assertEqual(res.status_code, 200)
        self.assertIn(p["sku"].encode(), res.data)

    def test_unknown_product_returns_404(self):
        self.assertEqual(self.client.get("/product/999999").status_code, 404)


# ===================================================================== #
# 2. Authentication
# ===================================================================== #
class TestAuth(BaseCase):

    def test_register_creates_an_account(self):
        res = self.client.post("/register", data={
            "name": "Anita Rao", "email": "anita@example.com", "phone": "9123456780",
            "password": "Secret@123", "confirm_password": "Secret@123",
            "address": "12 Park Street, Pune 411001",
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        with self.app.app_context():
            self.assertIsNotNone(query("SELECT 1 FROM users WHERE email = 'anita@example.com'", one=True))

    def test_password_is_hashed_not_stored_in_plain_text(self):
        self.client.post("/register", data={
            "name": "Hash Test", "email": "hash@example.com", "phone": "9123456781",
            "password": "Secret@123", "confirm_password": "Secret@123",
        })
        with self.app.app_context():
            row = query("SELECT password_hash FROM users WHERE email = 'hash@example.com'", one=True)
        self.assertNotIn("Secret@123", row["password_hash"])
        self.assertGreater(len(row["password_hash"]), 40)

    def test_weak_password_is_rejected(self):
        res = self.client.post("/register", data={
            "name": "Weak User", "email": "weak@example.com",
            "password": "abc", "confirm_password": "abc",
        })
        self.assertEqual(res.status_code, 400)
        with self.app.app_context():
            self.assertIsNone(query("SELECT 1 FROM users WHERE email = 'weak@example.com'", one=True))

    def test_duplicate_email_is_rejected(self):
        res = self.client.post("/register", data={
            "name": "Copy Cat", "email": "user@shopsphere.com",
            "password": "Secret@123", "confirm_password": "Secret@123",
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn(b"already exists", res.data)

    def test_mismatched_passwords_rejected(self):
        res = self.client.post("/register", data={
            "name": "Mismatch", "email": "mm@example.com",
            "password": "Secret@123", "confirm_password": "Secret@999",
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn(b"do not match", res.data)

    def test_login_with_valid_credentials(self):
        res = self.login()
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Signed in as", res.data)

    def test_login_with_wrong_password_fails(self):
        res = self.client.post("/login", data={"email": "user@shopsphere.com",
                                               "password": "WrongPass@1"})
        self.assertEqual(res.status_code, 401)
        self.assertIn(b"Invalid email or password", res.data)

    def test_logout_clears_the_session(self):
        self.login()
        self.client.get("/logout")
        res = self.client.get("/account", follow_redirects=True)
        self.assertIn(b"Sign in", res.data)

    def test_protected_pages_redirect_anonymous_users(self):
        for url in ("/cart/", "/checkout", "/orders", "/account"):
            res = self.client.get(url)
            self.assertEqual(res.status_code, 302, url)
            self.assertIn("/login", res.headers["Location"])


# ===================================================================== #
# 3. Cart & pricing
# ===================================================================== #
class TestCart(BaseCase):

    def test_anonymous_add_to_cart_is_blocked(self):
        res = self.add_to_cart(self.product()["id"])
        self.assertEqual(res.status_code, 401)
        self.assertTrue(res.get_json()["login_required"])

    def test_add_to_cart_updates_count(self):
        self.login()
        res = self.add_to_cart(self.product()["id"], 2)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["count"], 2)

    def test_adding_same_product_twice_merges_quantity(self):
        self.login()
        pid = self.product()["id"]
        self.add_to_cart(pid, 1)
        res = self.add_to_cart(pid, 3)
        self.assertEqual(res.get_json()["count"], 4)

    def test_cannot_add_more_than_available_stock(self):
        self.login()
        p = self.product()
        res = self.add_to_cart(p["id"], p["stock"] + 5)
        self.assertEqual(res.status_code, 409)
        self.assertFalse(res.get_json()["ok"])

    def test_update_and_remove_cart_item(self):
        self.login()
        pid = self.product()["id"]
        self.add_to_cart(pid, 3)

        res = self.client.post("/cart/api/update", json={"product_id": pid, "quantity": 1})
        self.assertEqual(res.get_json()["count"], 1)

        res = self.client.post("/cart/api/remove", json={"product_id": pid})
        self.assertEqual(res.get_json()["count"], 0)

    def test_price_summary_adds_gst_and_shipping(self):
        self.login()
        with self.app.app_context():
            cheap = query("SELECT * FROM products WHERE price < 500 AND stock > 0", one=True)
        res = self.add_to_cart(cheap["id"], 1)
        summary = res.get_json()["summary"]

        expected_tax = round(summary["subtotal"] * 0.18, 2)
        self.assertAlmostEqual(summary["tax"], expected_tax, places=2)
        self.assertEqual(summary["shipping"], 49.0)          # below the free-shipping threshold
        self.assertAlmostEqual(summary["total"],
                               round(summary["subtotal"] + expected_tax + 49.0, 2), places=2)

    def test_free_shipping_above_threshold(self):
        self.login()
        with self.app.app_context():
            pricey = query("SELECT * FROM products WHERE price > 1000 AND stock > 0", one=True)
        res = self.add_to_cart(pricey["id"], 1)
        self.assertEqual(res.get_json()["summary"]["shipping"], 0.0)

    def test_valid_coupon_applies_discount(self):
        self.login()
        with self.app.app_context():
            pricey = query("SELECT * FROM products WHERE price > 2500 AND stock > 0", one=True)
        self.add_to_cart(pricey["id"], 1)

        res = self.client.post("/cart/api/coupon", json={"code": "MCA25"})
        summary = res.get_json()["summary"]
        self.assertEqual(summary["coupon"], "MCA25")
        self.assertGreater(summary["discount"], 0)
        self.assertLessEqual(summary["discount"], 2000)      # capped at max_discount

    def test_invalid_coupon_is_rejected(self):
        self.login()
        self.add_to_cart(self.product()["id"])
        res = self.client.post("/cart/api/coupon", json={"code": "NOTACOUPON"})
        self.assertEqual(res.status_code, 404)

    def test_coupon_below_minimum_order_is_rejected(self):
        self.login()
        with self.app.app_context():
            cheap = query("SELECT * FROM products WHERE price < 400 AND stock > 0", one=True)
        self.add_to_cart(cheap["id"], 1)
        res = self.client.post("/cart/api/coupon", json={"code": "FEST50"})
        self.assertEqual(res.status_code, 409)


# ===================================================================== #
# 4. Payment gateway unit tests (no HTTP involved)
# ===================================================================== #
class TestGatewayUnit(unittest.TestCase):

    def test_luhn_accepts_valid_numbers(self):
        for number in ("4111111111111111", "5555555555554444", "6011111111111117"):
            self.assertTrue(pg.luhn_check(number), number)

    def test_luhn_rejects_invalid_numbers(self):
        for number in ("1234567812345678", "4111111111111112", "123"):
            self.assertFalse(pg.luhn_check(number), number)

    def test_network_detection(self):
        self.assertEqual(pg.detect_network("4111111111111111"), "VISA")
        self.assertEqual(pg.detect_network("5555555555554444"), "MASTERCARD")
        self.assertEqual(pg.detect_network("378282246310005"), "AMEX")

    def test_expired_card_raises(self):
        with self.assertRaises(pg.PaymentError):
            pg.validate_expiry("01", "2020")

    def test_bad_cvv_raises(self):
        with self.assertRaises(pg.PaymentError):
            pg.validate_card("4111111111111111", "Demo", "12", "2030", "12")

    def test_upi_validation(self):
        self.assertEqual(pg.validate_upi("Student@OKAXIS"), "student@okaxis")
        with self.assertRaises(pg.PaymentError):
            pg.validate_upi("not-a-vpa")

    def test_unknown_bank_raises(self):
        with self.assertRaises(pg.PaymentError):
            pg.validate_bank("XXXX")

    def test_initiate_rejects_bad_method_and_amount(self):
        with self.assertRaises(pg.PaymentError):
            pg.initiate(100, "BITCOIN")
        with self.assertRaises(pg.PaymentError):
            pg.initiate(0, "CARD")

    def test_otp_verification(self):
        pg.verify_otp("123456", "123456")                     # no exception = pass
        with self.assertRaises(pg.PaymentError):
            pg.verify_otp("000000", "123456")

    def test_cod_blocked_for_large_orders(self):
        with self.assertRaises(pg.PaymentError):
            pg.authorize("COD", 25000, {})

    def test_capture_rules(self):
        self.assertEqual(pg.capture("CARD")[0], pg.SUCCESS)
        self.assertEqual(pg.capture("COD")[0], pg.PENDING)

    def test_order_number_and_txn_id_format(self):
        self.assertTrue(pg.new_order_number().startswith("ORD-"))
        self.assertTrue(pg.new_txn_id().startswith("PAY_"))


# ===================================================================== #
# 5. Checkout and payment flow (end to end)
# ===================================================================== #
class TestCheckoutAndPayment(BaseCase):

    def test_checkout_requires_a_non_empty_cart(self):
        self.login()
        res = self.client.get("/checkout", follow_redirects=True)
        self.assertIn(b"Your cart is empty", res.data)

    def test_checkout_rejects_an_invalid_phone_number(self):
        self.login()
        self.add_to_cart(self.product()["id"])
        res = self.client.post("/checkout", data={
            "shipping_name": "Demo Customer", "shipping_phone": "123",
            "shipping_address": "Flat 402, Green Residency, Kochi - 682016",
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn(b"10 digits", res.data)

    def test_checkout_creates_order_and_empties_cart(self):
        self.login()
        order_id = self.place_order()
        with self.app.app_context():
            order = query("SELECT * FROM orders WHERE id = ?", (order_id,), one=True)
            left = query("SELECT COUNT(*) AS c FROM cart_items", one=True)["c"]
        self.assertEqual(order["status"], "PENDING")
        self.assertEqual(order["payment_status"], "UNPAID")
        self.assertEqual(left, 0)

    def test_successful_card_payment_confirms_the_order(self):
        self.login()
        order_id = self.place_order()
        res = self.pay_by_card(order_id)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"successfully", res.data)

        with self.app.app_context():
            order = query("SELECT * FROM orders WHERE id = ?", (order_id,), one=True)
            payment = query("SELECT * FROM payments WHERE order_id = ?", (order_id,), one=True)
        self.assertEqual(order["payment_status"], "PAID")
        self.assertEqual(order["status"], "CONFIRMED")
        self.assertEqual(payment["status"], "SUCCESS")

    def test_card_payment_reduces_stock(self):
        self.login()
        p = self.product()
        before = p["stock"]
        order_id = self.place_order(p["id"], 2)
        self.pay_by_card(order_id)

        with self.app.app_context():
            after = query("SELECT stock FROM products WHERE id = ?", (p["id"],), one=True)["stock"]
            log = query("SELECT * FROM inventory_logs WHERE product_id = ? ORDER BY id DESC",
                        (p["id"],), one=True)
        self.assertEqual(after, before - 2)
        self.assertEqual(log["change"], -2)

    def test_invalid_card_number_is_declined(self):
        self.login()
        order_id = self.place_order()
        res = self.pay_by_card(order_id, card=BAD_CARD)
        self.assertEqual(res.status_code, 402)
        self.assertIn(b"Invalid card number", res.data)

    def test_declined_test_card_fails_and_keeps_stock(self):
        self.login()
        p = self.product()
        before = p["stock"]
        order_id = self.place_order(p["id"], 1)
        res = self.pay_by_card(order_id, card=DECLINED_CARD)

        self.assertEqual(res.status_code, 402)
        with self.app.app_context():
            order = query("SELECT * FROM orders WHERE id = ?", (order_id,), one=True)
            after = query("SELECT stock FROM products WHERE id = ?", (p["id"],), one=True)["stock"]
        self.assertEqual(order["payment_status"], "FAILED")
        self.assertEqual(after, before)                       # stock untouched on failure

    def test_insufficient_funds_card_fails(self):
        self.login()
        order_id = self.place_order()
        res = self.pay_by_card(order_id, card=NO_FUNDS_CARD)
        self.assertIn(b"Insufficient funds", res.data)

    def test_wrong_otp_is_rejected(self):
        self.login()
        order_id = self.place_order()
        res = self.pay_by_card(order_id, otp="999999")
        self.assertEqual(res.status_code, 401)
        self.assertIn(b"Incorrect OTP", res.data)

    def test_three_wrong_otps_cancel_the_transaction(self):
        self.login()
        order_id = self.place_order()
        self.client.post("/payment/{}/process".format(order_id), data={
            "method": "CARD", "card_number": GOOD_CARD, "card_name": "DEMO",
            "expiry_month": "12", "expiry_year": "2030", "cvv": "123"})
        for _ in range(2):
            self.client.post("/payment/{}/otp".format(order_id), data={"otp": "000000"})
        res = self.client.post("/payment/{}/otp".format(order_id), data={"otp": "000000"})
        self.assertEqual(res.status_code, 402)
        self.assertIn(b"3 incorrect OTP", res.data)

    def test_upi_payment_succeeds_without_otp(self):
        self.login()
        order_id = self.place_order()
        res = self.client.post("/payment/{}/process".format(order_id),
                               data={"method": "UPI", "upi_id": "student@okaxis"})
        self.assertEqual(res.status_code, 200)
        with self.app.app_context():
            order = query("SELECT * FROM orders WHERE id = ?", (order_id,), one=True)
        self.assertEqual(order["payment_status"], "PAID")

    def test_failing_upi_id_is_declined(self):
        self.login()
        order_id = self.place_order()
        res = self.client.post("/payment/{}/process".format(order_id),
                               data={"method": "UPI", "upi_id": "fail@upi"})
        self.assertEqual(res.status_code, 402)

    def test_netbanking_payment(self):
        self.login()
        order_id = self.place_order()
        res = self.client.post("/payment/{}/process".format(order_id),
                               data={"method": "NETBANKING", "bank_code": "HDFC"})
        self.assertEqual(res.status_code, 200)
        with self.app.app_context():
            payment = query("SELECT * FROM payments WHERE order_id = ?", (order_id,), one=True)
        self.assertEqual(payment["detail"], "HDFC Bank")

    def test_cod_stays_pending_until_delivery(self):
        self.login()
        order_id = self.place_order()
        self.client.post("/payment/{}/process".format(order_id), data={"method": "COD"})
        with self.app.app_context():
            order = query("SELECT * FROM orders WHERE id = ?", (order_id,), one=True)
        self.assertEqual(order["payment_status"], "COD_PENDING")
        self.assertEqual(order["status"], "CONFIRMED")

    def test_a_paid_order_cannot_be_paid_twice(self):
        self.login()
        order_id = self.place_order()
        self.pay_by_card(order_id)
        res = self.client.get("/payment/{}".format(order_id), follow_redirects=True)
        self.assertIn(b"already been paid", res.data)

    def test_user_cannot_open_another_users_order(self):
        self.login()
        order_id = self.place_order()
        self.client.get("/logout")

        self.client.post("/register", data={
            "name": "Other Person", "email": "other@example.com",
            "password": "Secret@123", "confirm_password": "Secret@123"})
        res = self.client.get("/orders/{}".format(order_id))
        self.assertEqual(res.status_code, 404)

    def test_cancelling_a_paid_order_refunds_and_restocks(self):
        self.login()
        p = self.product()
        before = p["stock"]
        order_id = self.place_order(p["id"], 2)
        self.pay_by_card(order_id)
        self.client.post("/orders/{}/cancel".format(order_id), follow_redirects=True)

        with self.app.app_context():
            order = query("SELECT * FROM orders WHERE id = ?", (order_id,), one=True)
            after = query("SELECT stock FROM products WHERE id = ?", (p["id"],), one=True)["stock"]
            refund = query("SELECT * FROM payments WHERE order_id = ? AND method = 'REFUND'",
                           (order_id,), one=True)
        self.assertEqual(order["status"], "CANCELLED")
        self.assertEqual(order["payment_status"], "REFUNDED")
        self.assertEqual(after, before)
        self.assertIsNotNone(refund)


# ===================================================================== #
# 6. Admin back-office
# ===================================================================== #
class TestAdmin(BaseCase):

    def test_customer_cannot_reach_the_admin_panel(self):
        self.login()
        res = self.client.get("/admin/", follow_redirects=True)
        self.assertIn(b"Admin access only", res.data)

    def test_anonymous_cannot_reach_the_admin_panel(self):
        res = self.client.get("/admin/products", follow_redirects=True)
        self.assertNotIn(b"Product management", res.data)

    def test_admin_dashboard_loads(self):
        self.login_admin()
        res = self.client.get("/admin/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Total revenue", res.data)

    def test_admin_can_create_a_product(self):
        self.login_admin()
        res = self.client.post("/admin/products/new", data={
            "name": "Test Gadget", "sku": "TST-001", "description": "Created by a test",
            "price": "999", "mrp": "1499", "category_id": "1", "stock": "25",
            "icon": "\U0001F9EA", "gradient": "#6366f1,#8b5cf6", "rating": "4.5",
            "is_active": "1",
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        with self.app.app_context():
            product = query("SELECT * FROM products WHERE sku = 'TST-001'", one=True)
        self.assertIsNotNone(product)
        self.assertEqual(product["stock"], 25)

    def test_duplicate_sku_is_rejected(self):
        self.login_admin()
        res = self.client.post("/admin/products/new", data={
            "name": "Clone", "sku": "ELE-001", "price": "100", "mrp": "200",
            "category_id": "1", "stock": "5",
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn(b"already in use", res.data)

    def test_price_above_mrp_is_rejected(self):
        self.login_admin()
        res = self.client.post("/admin/products/new", data={
            "name": "Overpriced", "sku": "OVR-001", "price": "500", "mrp": "100",
            "category_id": "1", "stock": "5",
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn(b"cannot be higher than MRP", res.data)

    def test_admin_can_edit_a_product(self):
        self.login_admin()
        p = self.product()
        self.client.post("/admin/products/{}/edit".format(p["id"]), data={
            "name": "Renamed Product", "sku": p["sku"], "description": p["description"],
            "price": "111", "mrp": "222", "category_id": str(p["category_id"]),
            "stock": "77", "icon": p["icon"], "gradient": p["gradient"],
            "rating": "4.0", "is_active": "1",
        }, follow_redirects=True)
        with self.app.app_context():
            updated = query("SELECT * FROM products WHERE id = ?", (p["id"],), one=True)
        self.assertEqual(updated["name"], "Renamed Product")
        self.assertEqual(updated["stock"], 77)

    def test_soft_delete_hides_product_from_storefront(self):
        self.login_admin()
        p = self.product()
        self.client.post("/admin/products/{}/delete".format(p["id"]), follow_redirects=True)
        self.client.get("/logout")

        res = self.client.get("/")
        self.assertNotIn(p["name"].encode(), res.data)
        self.assertEqual(self.client.get("/product/{}".format(p["id"])).status_code, 404)

    def test_inventory_adjustment_is_logged(self):
        self.login_admin()
        p = self.product()
        self.client.post("/admin/inventory/{}/adjust".format(p["id"]),
                         data={"change": "15", "reason": "New shipment"}, follow_redirects=True)
        with self.app.app_context():
            stock = query("SELECT stock FROM products WHERE id = ?", (p["id"],), one=True)["stock"]
            log = query("SELECT * FROM inventory_logs WHERE product_id = ? ORDER BY id DESC",
                        (p["id"],), one=True)
        self.assertEqual(stock, p["stock"] + 15)
        self.assertEqual(log["reason"], "New shipment")

    def test_cannot_remove_more_stock_than_available(self):
        self.login_admin()
        p = self.product()
        self.client.post("/admin/inventory/{}/adjust".format(p["id"]),
                         data={"change": str(-(p["stock"] + 10)), "reason": "Oops"},
                         follow_redirects=True)
        with self.app.app_context():
            stock = query("SELECT stock FROM products WHERE id = ?", (p["id"],), one=True)["stock"]
        self.assertEqual(stock, p["stock"])

    def test_admin_can_move_an_order_through_the_workflow(self):
        self.login()
        order_id = self.place_order()
        self.pay_by_card(order_id)
        self.client.get("/logout")

        self.login_admin()
        for status in ("PACKED", "SHIPPED", "DELIVERED"):
            self.client.post("/admin/orders/{}/status".format(order_id),
                             data={"status": status}, follow_redirects=True)
        with self.app.app_context():
            order = query("SELECT * FROM orders WHERE id = ?", (order_id,), one=True)
        self.assertEqual(order["status"], "DELIVERED")

    def test_delivering_a_cod_order_marks_it_paid(self):
        self.login()
        order_id = self.place_order()
        self.client.post("/payment/{}/process".format(order_id), data={"method": "COD"})
        self.client.get("/logout")

        self.login_admin()
        self.client.post("/admin/orders/{}/status".format(order_id),
                         data={"status": "DELIVERED"}, follow_redirects=True)
        with self.app.app_context():
            order = query("SELECT * FROM orders WHERE id = ?", (order_id,), one=True)
        self.assertEqual(order["payment_status"], "PAID")

    def test_payment_ledger_lists_transactions(self):
        self.login()
        order_id = self.place_order()
        self.pay_by_card(order_id)
        self.client.get("/logout")

        self.login_admin()
        res = self.client.get("/admin/payments")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"PAY_", res.data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
