# -*- coding: utf-8 -*-
"""PayNova - a self-contained *simulated* payment gateway.

Nothing here talks to a real bank; the module mimics how a live gateway
(Razorpay / Stripe / PayU) behaves so the checkout flow can be demonstrated
and tested offline:

    initiate()  ->  create a transaction id and hold the payment in PENDING
    authorize() ->  validate the instrument (Luhn, UPI VPA, bank code)
    verify_otp()->  second factor for card payments
    capture()   ->  mark the payment SUCCESS / FAILED

Deterministic test instruments (documented in README.md) let the automated
test-suite assert both the happy path and every failure path.
"""
import random
import re
import string
from datetime import datetime

# --------------------------------------------------------------------------- #
# Status constants
# --------------------------------------------------------------------------- #
PENDING = "PENDING"
SUCCESS = "SUCCESS"
FAILED = "FAILED"
REFUNDED = "REFUNDED"

METHODS = ("CARD", "UPI", "NETBANKING", "COD")

BANKS = {
    "SBIN": "State Bank of India",
    "HDFC": "HDFC Bank",
    "ICIC": "ICICI Bank",
    "UTIB": "Axis Bank",
    "KKBK": "Kotak Mahindra Bank",
    "PUNB": "Punjab National Bank",
}

# Instruments that always fail, so failure handling can be demonstrated.
DECLINED_CARDS = {"4000000000000002": "Card declined by issuing bank",
                  "4000000000000069": "Card has expired",
                  "4000000000000127": "Incorrect CVV"}
INSUFFICIENT_FUNDS_CARD = "4000000000009995"
DECLINED_UPI_PREFIX = "fail@"


class PaymentError(Exception):
    """Raised when the gateway rejects a payment request."""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _ref(prefix, size=12):
    body = "".join(random.choices(string.ascii_uppercase + string.digits, k=size))
    return f"{prefix}_{body}"


def new_txn_id():
    """Public transaction id shown to the customer, e.g. PAY_7K2M9QX4LZ01."""
    return _ref("PAY")


def new_order_number():
    """Human friendly order number, e.g. ORD-20261018-4821."""
    return "ORD-{}-{}".format(datetime.now().strftime("%Y%m%d"), random.randint(1000, 9999))


def luhn_check(number: str) -> bool:
    """Standard Luhn mod-10 checksum used by every real card network."""
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 12:
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, digit in enumerate(digits):
        if i % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def detect_network(number: str) -> str:
    """Identify the card network from its IIN / BIN range."""
    number = re.sub(r"\D", "", number)
    if number.startswith("4"):
        return "VISA"
    if number[:2] in {"51", "52", "53", "54", "55"} or number[:4].isdigit() and "2221" <= number[:4] <= "2720":
        return "MASTERCARD"
    if number[:2] in {"34", "37"}:
        return "AMEX"
    if number[:4] in {"6011", "6521", "6522"} or number.startswith("65"):
        return "RUPAY"
    return "UNKNOWN"


def validate_expiry(month: str, year: str, today=None) -> None:
    """Reject malformed or already-expired cards."""
    today = today or datetime.now()
    try:
        month_i, year_i = int(month), int(year)
    except (TypeError, ValueError):
        raise PaymentError("Expiry date must be numeric (MM / YY)")
    if not 1 <= month_i <= 12:
        raise PaymentError("Expiry month must be between 01 and 12")
    if year_i < 100:
        year_i += 2000
    if (year_i, month_i) < (today.year, today.month):
        raise PaymentError("This card has expired")


def validate_card(number, name, month, year, cvv):
    """Full card validation. Returns the masked card detail string."""
    number = re.sub(r"\s|-", "", number or "")
    if not number.isdigit():
        raise PaymentError("Card number may contain digits only")
    if not 12 <= len(number) <= 19:
        raise PaymentError("Card number must be 12 to 19 digits long")
    if not luhn_check(number):
        raise PaymentError("Invalid card number (failed Luhn checksum)")
    if not (name or "").strip():
        raise PaymentError("Name on card is required")
    validate_expiry(month, year)
    if not re.fullmatch(r"\d{3,4}", cvv or ""):
        raise PaymentError("CVV must be 3 or 4 digits")
    return number, "{} **** {}".format(detect_network(number), number[-4:])


def validate_upi(vpa: str) -> str:
    """UPI Virtual Payment Address check, e.g. student@okaxis."""
    vpa = (vpa or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9.\-_]{3,}@[a-z]{3,}", vpa):
        raise PaymentError("Enter a valid UPI ID, for example name@okhdfcbank")
    return vpa


def validate_bank(code: str) -> str:
    if code not in BANKS:
        raise PaymentError("Please choose a bank to continue")
    return BANKS[code]


# --------------------------------------------------------------------------- #
# Gateway API
# --------------------------------------------------------------------------- #
def initiate(amount: float, method: str):
    """Step 1 - open a transaction with the gateway."""
    if method not in METHODS:
        raise PaymentError("Unsupported payment method: {}".format(method))
    if amount <= 0:
        raise PaymentError("Payment amount must be greater than zero")
    return {
        "txn_id": new_txn_id(),
        "gateway_ref": _ref("REF", 10),
        "amount": round(amount, 2),
        "method": method,
        "status": PENDING,
        "requires_otp": method == "CARD",
    }


def authorize(method: str, amount: float, form: dict):
    """Step 2 - validate the instrument and ask the issuer for authorisation.

    Returns (detail, requires_otp). Raises PaymentError when declined.
    """
    if method == "CARD":
        number, detail = validate_card(
            form.get("card_number"), form.get("card_name"),
            form.get("expiry_month"), form.get("expiry_year"), form.get("cvv"),
        )
        if number in DECLINED_CARDS:
            raise PaymentError(DECLINED_CARDS[number])
        if number == INSUFFICIENT_FUNDS_CARD:
            raise PaymentError("Insufficient funds in the linked account")
        return detail, True

    if method == "UPI":
        vpa = validate_upi(form.get("upi_id"))
        if vpa.startswith(DECLINED_UPI_PREFIX):
            raise PaymentError("Payment declined by the UPI app")
        return vpa, False

    if method == "NETBANKING":
        bank = validate_bank(form.get("bank_code"))
        return bank, False

    # Cash on delivery - collected by the courier, nothing to authorise now.
    if amount > 20000:
        raise PaymentError("Cash on delivery is not available above " + "₹20,000")
    return "Cash on delivery", False


def verify_otp(entered: str, expected: str) -> None:
    """Step 3 (cards only) - second-factor authentication."""
    if not (entered or "").strip():
        raise PaymentError("Please enter the OTP sent to your registered mobile number")
    if entered.strip() != expected:
        raise PaymentError("Incorrect OTP. Please try again.")


def capture(method: str):
    """Step 4 - settle the authorised payment.

    COD stays PENDING until the courier collects the cash; everything else is
    captured immediately.
    """
    if method == "COD":
        return PENDING, "Amount will be collected at the time of delivery"
    return SUCCESS, "Payment captured successfully"


def refund(amount: float):
    """Reverse a captured payment (used when an order is cancelled)."""
    return {
        "status": REFUNDED,
        "gateway_ref": _ref("RFND", 10),
        "amount": round(amount, 2),
        "message": "Refund initiated - credited in 5 to 7 working days",
    }
