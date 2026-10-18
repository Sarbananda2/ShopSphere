# ShopSphere — E-Commerce Web Application

**MCA Integrated Project** · Flask · SQLite · HTML5 / CSS3 / Vanilla JavaScript

A complete, colourful and fully responsive online store with customer accounts, a product
catalogue, inventory control, a shopping cart, a simulated payment gateway (card / UPI /
net-banking / cash-on-delivery) and an admin back-office — plus an automated test suite of
**69 tests**.

---

## 1. Quick start

```bat
cd "D:\Integrated project MCA"
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000**

On Windows you can simply double-click **`run.bat`**, which installs Flask if needed,
opens the browser and starts the server.

### Demo accounts (created automatically on first run)

| Role     | Email                    | Password    |
|----------|--------------------------|-------------|
| Customer | `user@shopsphere.com`    | `User@123`  |
| Admin    | `admin@shopsphere.com`   | `Admin@123` |

The login page has **Fill customer** / **Fill admin** buttons so you don't have to type them
during a demo.

---

## 2. Modules implemented

### 2.1 User management
* Registration with server-side validation — email format, duplicate check, 10-digit Indian
  mobile number, password policy (8+ characters, a letter, a number, a symbol) and
  confirm-password match.
* Passwords stored as **salted PBKDF2-SHA256 hashes** (`werkzeug.security`), never in plain text.
* Session-based login/logout, a deliberately vague "Invalid email or password" message so the
  form cannot be used to discover which emails are registered.
* `@login_required` and `@admin_required` decorators protect customer and admin pages.
* Profile page: edit name / phone / address, change password, view spend and recent orders.

### 2.2 Product catalogue
* 6 categories, 23 seeded products, each with price, MRP, discount %, rating, SKU and stock.
* Keyword search over name, description and SKU.
* Filters: category, maximum price (slider), in-stock-only.
* 5 sort orders: featured, price low→high, price high→low, rating, newest.
* Product detail page with quantity stepper, stock badge and related products.

### 2.3 Inventory management
* Live stock count on every product card ("Only 4 left", "Out of stock").
* Admin inventory screen with stock value per product and one-click adjustments
  (positive = restock, negative = damage/return).
* **Every stock movement is written to an audit log** (`inventory_logs`) with the change, the
  resulting balance and a reason — opening stock, sale, cancellation, manual correction.
* Stock is deducted **only when a payment is captured**, and automatically **restored** when an
  order is cancelled or refunded. A failed payment never touches stock.
* Low-stock alerts on the admin dashboard (threshold configurable in `config.py`).

### 2.4 Shopping cart & pricing
* Per-user cart persisted in the database (survives logout).
* Quantity +/− and remove work over a **JSON API with `fetch()`** — no page reloads.
* Stock is re-validated on every cart change, so the cart can never exceed available units.
* Coupon engine with percentage discount, maximum-discount cap and minimum-order value:
  `WELCOME10` (10%, max ₹500), `MCA25` (25%, max ₹2000), `FEST50` (50%, max ₹1000).
* Price breakdown: MRP → product discount → coupon → **18% GST** → delivery
  (free above ₹999, otherwise ₹49) → total payable.

### 2.5 Payment gateway (simulated — `payment_gateway.py`)
A self-contained module named **PayNova** that mimics how Razorpay / Stripe / PayU behave:

| Stage | Function | What it does |
|-------|----------|--------------|
| 1 | `initiate()`  | Creates a transaction ID and holds the payment in `PENDING` |
| 2 | `authorize()` | Validates the instrument and asks the "issuer" for authorisation |
| 3 | `verify_otp()`| Second factor (3-D Secure) for card payments |
| 4 | `capture()`   | Settles the payment → `SUCCESS` / `FAILED` |
| – | `refund()`    | Reverses a captured payment when an order is cancelled |

Supported methods:
* **Card** — Luhn mod-10 checksum, IIN/BIN network detection (Visa / Mastercard / Amex /
  RuPay), expiry validation, CVV format check, then a 6-digit OTP page. Three wrong OTPs
  cancel the transaction.
* **UPI** — VPA format validation (`name@bank`).
* **Net banking** — six banks, simulated bank selection.
* **Cash on delivery** — blocked above ₹20,000; stays `COD_PENDING` until the admin marks the
  order *Delivered*, at which point it becomes `PAID`.

Every attempt — successful or not — is recorded in the `payments` ledger with a transaction ID,
gateway reference, masked instrument and a human-readable message.

#### Test instruments

| Instrument | Result |
|------------|--------|
| `4111 1111 1111 1111` | Payment succeeds (OTP **123456**) |
| `5555 5555 5555 4444` | Succeeds, detected as Mastercard |
| `4000 0000 0000 0002` | Declined by issuing bank |
| `4000 0000 0000 0069` | Card has expired |
| `4000 0000 0000 0127` | Incorrect CVV |
| `4000 0000 0000 9995` | Insufficient funds |
| `1234 5678 1234 5678` | Invalid card number (fails Luhn) |
| UPI `student@okaxis`  | Payment succeeds |
| UPI `fail@upi`        | Declined by the UPI app |

> **This gateway never contacts a bank and no money ever moves.** It exists so the complete
> checkout flow can be demonstrated and tested offline.

### 2.6 Orders
* 4-step checkout: Cart → Address → Payment → Confirmation, with a visible progress tracker.
* Order lifecycle: `PENDING → CONFIRMED → PACKED → SHIPPED → DELIVERED` (or `CANCELLED`),
  shown to the customer as a timeline.
* Payment status: `UNPAID` / `PAID` / `FAILED` / `COD_PENDING` / `REFUNDED`.
* Order history, order detail with a printable invoice (`window.print()`), payment history,
  retry-payment for failed transactions, and customer-initiated cancellation with automatic
  refund and restock.
* Users can only open their **own** orders (admins can open any) — verified by a test.

### 2.7 Admin back-office (`/admin`)
* **Dashboard** — revenue, order count, customers, active products, inventory value, failed
  payments, low-stock alerts, stock-by-category bars and best sellers.
* **Products** — full CRUD with a live preview card, SKU-uniqueness check and a
  *price ≤ MRP* rule. Deletion is a **soft delete** so historical order lines stay intact.
* **Inventory** — stock adjustments plus the complete movement log.
* **Orders** — filter by status and move orders through the workflow.
* **Payments** — the full transaction ledger with totals per status.
* **Customers** — accounts with order count and lifetime value.

---

## 3. Technology stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3, Flask 3 (application factory + blueprints) |
| Templating | Jinja2 with template inheritance and macros |
| Database | SQLite 3 (`sqlite3` module, parameterised queries) |
| Security | `werkzeug.security` PBKDF2 password hashing, server-side sessions |
| Frontend | HTML5, CSS3 (Grid, Flexbox, custom properties), vanilla JavaScript (Fetch API) |
| Testing | `unittest` + Flask test client (69 tests) |

No front-end framework, no CDN and no image files — the app runs **completely offline**.
Product artwork is drawn with CSS gradients and emoji.

---

## 4. Project structure

```
Integrated project MCA/
├── app.py                     Application factory, filters, error handlers, entry point
├── config.py                  Settings: secret key, DB path, GST, shipping, OTP
├── database.py                Schema, connection handling, query helpers, seeding
├── seed_data.py               Demo users, categories, 23 products, coupons
├── payment_gateway.py         PayNova simulated gateway (Luhn, OTP, UPI, COD, refunds)
├── services.py                Business logic: cart, pricing, orders, stock, decorators
├── reset_db.py                Wipe and reseed the database
├── run_tests.py               Test runner
├── run.bat                    One-click launcher for Windows
├── requirements.txt
│
├── routes/
│   ├── main_routes.py         Home, catalogue, search, product detail, about
│   ├── auth_routes.py         Register, login, logout, account, change password
│   ├── cart_routes.py         Cart page + JSON API (add/update/remove/coupon)
│   ├── order_routes.py        Checkout, order history, order detail, cancel
│   ├── payment_routes.py      Payment page, process, OTP, result, retry
│   └── admin_routes.py        Dashboard, products, inventory, orders, payments, customers
│
├── templates/
│   ├── base.html              Header, search, cart badge, theme switch, footer
│   ├── _macros.html           Product card, rating, status-tag macros
│   ├── _summary.html          Price breakdown (re-rendered by the cart API)
│   ├── index.html  product.html  login.html  register.html  account.html
│   ├── cart.html   checkout.html  orders.html  order_detail.html
│   ├── payment.html  payment_otp.html  payment_result.html
│   ├── about.html  404.html  500.html
│   └── admin/  _layout.html  dashboard.html  products.html  product_form.html
│                inventory.html  orders.html  payments.html  customers.html
│
├── static/
│   ├── css/style.css          Full design system, light + dark themes, responsive rules
│   └── js/  main.js (theme, toasts, add-to-cart)
│             cart.js (live cart + coupons)
│             payment.js (card preview, Luhn, OTP boxes)
│
├── tests/test_shopsphere.py   69 automated tests
└── instance/shopsphere.db     SQLite database (created automatically)
```

---

## 5. Database design

Nine tables, all created automatically on first run.

| Table | Purpose | Key columns |
|-------|---------|-------------|
| `users` | Accounts | `id`, `email` (unique), `password_hash`, `role` |
| `categories` | Product groups | `id`, `name`, `slug`, `icon`, `color` |
| `products` | Catalogue + stock | `id`, `sku` (unique), `price`, `mrp`, `stock`, `category_id` → categories |
| `cart_items` | Per-user cart | `user_id` → users, `product_id` → products, unique together |
| `coupons` | Discount codes | `code`, `percent`, `max_discount`, `min_order` |
| `orders` | Order header | `order_number` (unique), `user_id`, totals, `status`, `payment_status`, address |
| `order_items` | Order lines | `order_id` → orders, product snapshot, `unit_price`, `quantity` |
| `payments` | Transaction ledger | `txn_id` (unique), `order_id`, `method`, `amount`, `status` |
| `inventory_logs` | Stock audit trail | `product_id`, `change`, `balance`, `reason` |

**Relationships:** one category → many products · one user → many cart items / orders ·
one order → many order items and many payment attempts · one product → many inventory log rows.

Order totals are *snapshotted* onto the order and `order_items` store the product name and
price at the time of purchase, so later price or name changes never rewrite history.

---

## 6. Route reference

| Method | URL | Purpose |
|--------|-----|---------|
| GET | `/` | Storefront with search, filters, sorting |
| GET | `/product/<id>` | Product detail |
| GET | `/about` | Project information page |
| GET POST | `/register`, `/login` | Account creation and sign-in |
| GET | `/logout` | End the session |
| GET POST | `/account`, `/account/password` | Profile and password |
| GET | `/cart/` | Cart page |
| POST | `/cart/api/add`, `/api/update`, `/api/remove`, `/api/coupon` | Cart JSON API |
| GET | `/cart/api/count` | Cart badge count |
| GET POST | `/checkout` | Delivery address and order creation |
| GET | `/orders`, `/orders/<id>` | Order history and detail |
| POST | `/orders/<id>/cancel` | Cancel (with refund + restock) |
| GET | `/payment/<id>` | Choose a payment method |
| POST | `/payment/<id>/process`, `/payment/<id>/otp` | Authorise / verify / capture |
| GET | `/payment/<id>/retry` | Retry a failed payment |
| GET | `/admin/` | Dashboard |
| GET POST | `/admin/products`, `/products/new`, `/products/<id>/edit` | Product CRUD |
| POST | `/admin/products/<id>/delete`, `/restore` | Hide / restore a product |
| GET POST | `/admin/inventory`, `/inventory/<id>/adjust` | Stock control |
| GET POST | `/admin/orders`, `/orders/<id>/status` | Order workflow |
| GET | `/admin/payments`, `/admin/customers` | Ledger and user list |

---

## 7. Testing

```bat
python run_tests.py
```
or
```bat
python -m unittest discover -s tests -v
```

The suite uses a **separate database** (`instance/test_shopsphere.db`) that is rebuilt before
every single test, so tests never touch your demo data and can run in any order.

| Test class | Tests | What it covers |
|------------|-------|----------------|
| `TestStorefront` | 8 | Page loads, seed data, search, category filter, sorting, 404 |
| `TestAuth` | 9 | Registration validation, password hashing, duplicate email, login, logout, route protection |
| `TestCart` | 10 | Add/update/remove, quantity merge, stock limits, GST, free shipping, coupons |
| `TestGatewayUnit` | 12 | Luhn, network detection, expiry, CVV, UPI, bank, OTP, capture rules |
| `TestCheckoutAndPayment` | 17 | Order creation, card/UPI/net-banking/COD, declines, OTP lockout, stock movement, refunds, access control |
| `TestAdmin` | 13 | Admin authorisation, product CRUD, SKU and price rules, soft delete, inventory log, order workflow |
| **Total** | **69** | all passing |

Last run: `Ran 69 tests — OK`.

---

## 8. Configuration

Everything tunable lives in `config.py`:

| Setting | Default | Meaning |
|---------|---------|---------|
| `GST_RATE` | `0.18` | Tax applied to the discounted subtotal |
| `SHIPPING_FEE` | `49.0` | Flat delivery charge |
| `FREE_SHIPPING_ABOVE` | `999.0` | Order value that makes delivery free |
| `LOW_STOCK_THRESHOLD` | `10` | Low-stock alert level on the dashboard |
| `GATEWAY_OTP` | `"123456"` | OTP accepted by the simulated bank page |
| `SECRET_KEY` | dev key | **Change this before any real deployment** |

To start over with fresh demo data: `python reset_db.py`

---

## 9. Responsive & accessible design

* Mobile-first CSS with breakpoints at **1024px** and **760px**.
* Sidebars, cart summary and admin navigation collapse to a single column; the admin menu
  becomes a horizontal scroller; product grids reflow from 5 columns down to 2.
* A full-width search bar and a hamburger drawer menu appear on phones.
* **Light and dark themes** via a `data-theme` attribute, remembered in `localStorage`.
* Semantic HTML, `aria-label`s on icon buttons, visible focus rings, and a print stylesheet
  so order invoices print cleanly.

---

## 10. Known limitations (honest scope notes)

These are deliberate, appropriate for an academic project, and worth stating in the viva:

* **The payment gateway is simulated.** A real integration would use a provider SDK, server-side
  order creation, a webhook endpoint and signature verification. `payment_gateway.py` is
  deliberately shaped like that flow (initiate → authorize → capture → refund) so swapping in
  Razorpay would mainly mean replacing that one module.
* **No CSRF tokens.** A production app would add `Flask-WTF`. The forms here are plain HTML.
* **SQLite single-file database** — perfect for a demo, not for concurrent production traffic.
* **No email/SMS** — the OTP is fixed at `123456` and order confirmations are not sent.
* Run with `debug=True` only on your own machine; never expose it on a public network.

---

## 11. Possible extensions

Product reviews and ratings by real users · wishlist · order tracking by courier ·
PDF invoice generation · sales charts over time · product image uploads ·
REST API with JWT for a mobile client · Docker deployment.

---

*Built as an MCA Integrated Project. ShopSphere is a demonstration store — no real products
are sold and no real payments are processed.*
