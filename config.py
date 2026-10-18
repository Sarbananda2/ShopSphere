"""Application configuration for the ShopSphere e-commerce project."""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration shared by every environment."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "mca-integrated-project-secret-key-2026")
    DATABASE = os.path.join(BASE_DIR, "instance", "shopsphere.db")

    # Store / business rules
    STORE_NAME = "ShopSphere"
    CURRENCY = "₹"
    GST_RATE = 0.18                 # 18% GST applied on the discounted subtotal
    SHIPPING_FEE = 49.0             # flat shipping charge
    FREE_SHIPPING_ABOVE = 999.0     # order value that unlocks free delivery
    LOW_STOCK_THRESHOLD = 10        # inventory alert level on the admin dashboard

    # Mock payment gateway
    GATEWAY_NAME = "PayNova"
    GATEWAY_OTP = "123456"          # OTP accepted by the simulated bank page

    SESSION_COOKIE_HTTPONLY = True
    TEMPLATES_AUTO_RELOAD = True


class TestConfig(Config):
    """Configuration used by the automated test-suite (isolated DB)."""

    TESTING = True
    DATABASE = os.path.join(BASE_DIR, "instance", "test_shopsphere.db")
    WTF_CSRF_ENABLED = False
