# -*- coding: utf-8 -*-
"""Demo master data loaded into the database on first run.

Every product and category carries a studio photo hot-linked from Unsplash
(free to use under the Unsplash License). The CSS gradient + emoji artwork is
kept as the fallback, so the store still renders offline with no image files
to ship.
"""


def photo(photo_id, width=600):
    """Unsplash CDN URL for a photo id, resized and re-encoded on the fly."""
    return ("https://images.unsplash.com/photo-{}?w={}&q=80&auto=format&fit=crop"
            .format(photo_id, width))


USERS = [
    {
        "name": "Store Admin",
        "email": "admin@shopsphere.com",
        "password": "Admin@123",
        "phone": "9876500001",
        "address": "ShopSphere HQ, MG Road, Bengaluru - 560001",
        "role": "admin",
    },
    {
        "name": "Demo Customer",
        "email": "user@shopsphere.com",
        "password": "User@123",
        "phone": "9876500002",
        "address": "Flat 402, Green Residency, Kochi - 682016",
        "role": "customer",
    },
]

CATEGORIES = [
    {"name": "Electronics",    "slug": "electronics", "icon": "\U0001F4F1", "color": "#6366f1",
     "image_url": photo("1468495244123-6c6c332eeece", 900)},
    {"name": "Fashion",        "slug": "fashion",     "icon": "\U0001F455", "color": "#ec4899",
     "image_url": photo("1445205170230-053b83016050", 900)},
    {"name": "Home & Kitchen", "slug": "home",        "icon": "\U0001F3E1", "color": "#f59e0b",
     "image_url": photo("1556911220-bff31c812dba", 900)},
    {"name": "Books",          "slug": "books",       "icon": "\U0001F4DA", "color": "#10b981",
     "image_url": photo("1507842217343-583bb7270b66", 900)},
    {"name": "Sports",         "slug": "sports",      "icon": "\U000026BD", "color": "#06b6d4",
     "image_url": photo("1461896836934-ffe607ba8211", 900)},
    {"name": "Beauty",         "slug": "beauty",      "icon": "\U0001F484", "color": "#a855f7",
     "image_url": photo("1596462502278-27bfdc403348", 900)},
]

PRODUCTS = [
    # ---------------------------------------------------------------- Electronics
    {"name": "Nova Pro Wireless Headphones", "sku": "ELE-001", "category": "electronics",
     "price": 2499, "mrp": 4999, "stock": 42, "rating": 4.6, "icon": "\U0001F3A7",
     "gradient": "#6366f1,#8b5cf6", "image_url": photo("1505740420928-5e560c06d30e"),
     "description": "Active noise cancellation, 40 hour battery life and plush memory-foam ear cups for all-day listening."},
    {"name": "PixelView 24\" 4K Monitor", "sku": "ELE-002", "category": "electronics",
     "price": 14999, "mrp": 19999, "stock": 15, "rating": 4.4, "icon": "\U0001F5A5",
     "gradient": "#0ea5e9,#6366f1", "image_url": photo("1527443224154-c4a3942d3acf"),
     "description": "Ultra-sharp 4K IPS panel with 99% sRGB coverage, built-in speakers and a fully adjustable stand."},
    {"name": "SwiftType Mechanical Keyboard", "sku": "ELE-003", "category": "electronics",
     "price": 3299, "mrp": 4499, "stock": 60, "rating": 4.7, "icon": "\U00002328",
     "gradient": "#8b5cf6,#ec4899", "image_url": photo("1587829741301-dc798b83add3"),
     "description": "Hot-swappable brown switches, per-key RGB lighting and a solid aluminium top plate."},
    {"name": "PowerCell 20000mAh Power Bank", "sku": "ELE-004", "category": "electronics",
     "price": 1799, "mrp": 2999, "stock": 8, "rating": 4.3, "icon": "\U0001F50B",
     "gradient": "#22c55e,#0ea5e9", "image_url": photo("1619489646924-b4fce76b1db5"),
     "description": "65W fast charging, triple output ports and an LED display that shows the exact charge left."},
    {"name": "AeroBuds Lite Earphones", "sku": "ELE-005", "category": "electronics",
     "price": 1299, "mrp": 2499, "stock": 95, "rating": 4.2, "icon": "\U0001F3B5",
     "gradient": "#f43f5e,#f59e0b", "image_url": photo("1590658268037-6bf12165a8df"),
     "description": "Feather-light true-wireless buds with low-latency gaming mode and a pocket-size charging case."},
    {"name": "TrackFit Smart Watch", "sku": "ELE-006", "category": "electronics",
     "price": 3999, "mrp": 6999, "stock": 25, "rating": 4.5, "icon": "\U0000231A",
     "gradient": "#14b8a6,#6366f1", "image_url": photo("1523275335684-37898b6baf30"),
     "description": "AMOLED display, SpO2 and heart-rate tracking, 100+ sport modes and 10 day battery life."},

    # -------------------------------------------------------------------- Fashion
    {"name": "Urban Denim Jacket", "sku": "FAS-001", "category": "fashion",
     "price": 1999, "mrp": 3499, "stock": 30, "rating": 4.3, "icon": "\U0001F9E5",
     "gradient": "#ec4899,#a855f7", "image_url": photo("1576995853123-5a10305d93c0"),
     "description": "Washed indigo denim with a relaxed fit, metal buttons and two chest utility pockets."},
    {"name": "Classic White Sneakers", "sku": "FAS-002", "category": "fashion",
     "price": 2299, "mrp": 3999, "stock": 48, "rating": 4.6, "icon": "\U0001F45F",
     "gradient": "#f472b6,#fb7185", "image_url": photo("1608231387042-66d1773070a5"),
     "description": "Everyday leather-finish sneakers with cushioned memory insoles and a non-slip rubber outsole."},
    {"name": "Heritage Cotton Kurta", "sku": "FAS-003", "category": "fashion",
     "price": 1199, "mrp": 1899, "stock": 55, "rating": 4.4, "icon": "\U0001F454",
     "gradient": "#f59e0b,#ec4899", "image_url": photo("1597983073493-88cd35cf93b0"),
     "description": "Hand-block printed pure cotton kurta, breathable and perfect for festive occasions."},
    {"name": "Trailblazer Backpack 30L", "sku": "FAS-004", "category": "fashion",
     "price": 1599, "mrp": 2799, "stock": 6, "rating": 4.5, "icon": "\U0001F392",
     "gradient": "#a855f7,#6366f1", "image_url": photo("1553062407-98eeb64c6a62"),
     "description": "Water-resistant 30 litre backpack with a padded laptop sleeve and anti-theft rear pocket."},

    # ------------------------------------------------------------- Home & Kitchen
    {"name": "BrewMaster Coffee Machine", "sku": "HOM-001", "category": "home",
     "price": 5499, "mrp": 8999, "stock": 18, "rating": 4.5, "icon": "\U00002615",
     "gradient": "#f59e0b,#f43f5e", "image_url": photo("1497935586351-b67a49e012bf"),
     "description": "15-bar espresso machine with a steam wand for cafe-style cappuccino right at home."},
    {"name": "AirCrisp Digital Air Fryer", "sku": "HOM-002", "category": "home",
     "price": 4299, "mrp": 7499, "stock": 22, "rating": 4.6, "icon": "\U0001F373",
     "gradient": "#fb923c,#ef4444", "image_url": photo("1630384060421-cb20d0e0649d"),
     "description": "4.5L basket, eight presets and rapid air technology that cuts oil use by up to 90%."},
    {"name": "Aurora LED Table Lamp", "sku": "HOM-003", "category": "home",
     "price": 899, "mrp": 1599, "stock": 70, "rating": 4.1, "icon": "\U0001F4A1",
     "gradient": "#fbbf24,#f97316", "image_url": photo("1507473885765-e6ed057f782c"),
     "description": "Touch-dimmable desk lamp with three colour temperatures and a USB charging port in the base."},
    {"name": "StaySteel Vacuum Flask 1L", "sku": "HOM-004", "category": "home",
     "price": 749, "mrp": 1299, "stock": 110, "rating": 4.4, "icon": "\U0001F376",
     "gradient": "#f59e0b,#84cc16", "image_url": photo("1602143407151-7111542de6e8"),
     "description": "Double-wall stainless steel flask that keeps drinks hot for 18 hours and cold for 24."},

    # ---------------------------------------------------------------------- Books
    {"name": "Mastering Python Programming", "sku": "BOK-001", "category": "books",
     "price": 649, "mrp": 999, "stock": 80, "rating": 4.8, "icon": "\U0001F4D7",
     "gradient": "#10b981,#0ea5e9", "image_url": photo("1526379095098-d400fd0bf935"),
     "description": "From core syntax to decorators, async IO and testing - with 200+ worked examples."},
    {"name": "Database Systems Handbook", "sku": "BOK-002", "category": "books",
     "price": 799, "mrp": 1250, "stock": 45, "rating": 4.5, "icon": "\U0001F4D8",
     "gradient": "#059669,#14b8a6", "image_url": photo("1544383835-bda2bc66a55d"),
     "description": "Normalization, indexing, transactions and query tuning explained with real SQL case studies."},
    {"name": "The Startup Playbook", "sku": "BOK-003", "category": "books",
     "price": 499, "mrp": 799, "stock": 9, "rating": 4.2, "icon": "\U0001F4D9",
     "gradient": "#22c55e,#eab308", "image_url": photo("1512820790803-83ca734da794"),
     "description": "Practical lessons on validating ideas, finding product-market fit and raising a first round."},
    {"name": "Clean Code Essentials", "sku": "BOK-004", "category": "books",
     "price": 899, "mrp": 1399, "stock": 33, "rating": 4.7, "icon": "\U0001F4D5",
     "gradient": "#16a34a,#06b6d4", "image_url": photo("1544716278-ca5e3f4abd8c"),
     "description": "Naming, functions, error handling and refactoring patterns every developer should know."},

    # --------------------------------------------------------------------- Sports
    {"name": "ProGrip Yoga Mat 6mm", "sku": "SPO-001", "category": "sports",
     "price": 999, "mrp": 1799, "stock": 65, "rating": 4.4, "icon": "\U0001F9D8",
     "gradient": "#06b6d4,#8b5cf6", "image_url": photo("1601925260368-ae2f83cf8b7f"),
     "description": "Extra-thick anti-skid TPE mat with alignment lines and a free carry strap."},
    {"name": "IronCore Adjustable Dumbbell", "sku": "SPO-002", "category": "sports",
     "price": 3499, "mrp": 5499, "stock": 12, "rating": 4.5, "icon": "\U0001F3CB",
     "gradient": "#0891b2,#4f46e5", "image_url": photo("1638536532686-d610adfc8e5c"),
     "description": "2.5kg to 24kg in a single dial-adjustable unit - replaces an entire dumbbell rack."},
    {"name": "StrikeForce Badminton Racket", "sku": "SPO-003", "category": "sports",
     "price": 1299, "mrp": 2199, "stock": 40, "rating": 4.3, "icon": "\U0001F3F8",
     "gradient": "#22d3ee,#3b82f6", "image_url": photo("1708312604109-16c0be9326cd"),
     "description": "Graphite shaft, head-light balance and a pre-strung frame ready for match play."},
    {"name": "Velocity Football Size 5", "sku": "SPO-004", "category": "sports",
     "price": 849, "mrp": 1499, "stock": 4, "rating": 4.2, "icon": "\U000026BD",
     "gradient": "#0ea5e9,#10b981", "image_url": photo("1575361204480-aadea25e6e68"),
     "description": "Hand-stitched match football with a butyl bladder that holds air for weeks."},

    # --------------------------------------------------------------------- Beauty
    {"name": "GlowVita Vitamin C Serum", "sku": "BEA-001", "category": "beauty",
     "price": 599, "mrp": 1099, "stock": 90, "rating": 4.4, "icon": "\U0001F9F4",
     "gradient": "#a855f7,#ec4899", "image_url": photo("1620916566398-39f1143ab7be"),
     "description": "20% Vitamin C with hyaluronic acid for brighter, visibly even-toned skin in four weeks."},
    {"name": "Silk & Shine Hair Dryer", "sku": "BEA-002", "category": "beauty",
     "price": 1899, "mrp": 2999, "stock": 26, "rating": 4.3, "icon": "\U0001F487",
     "gradient": "#c026d3,#f43f5e", "image_url": photo("1522338140262-f46f5913618a"),
     "description": "1800W ionic dryer with a cool-shot button and two concentrator nozzles."},
    {"name": "PureHerb Aloe Face Wash", "sku": "BEA-003", "category": "beauty",
     "price": 299, "mrp": 499, "stock": 150, "rating": 4.1, "icon": "\U0001F33F",
     "gradient": "#8b5cf6,#14b8a6", "image_url": photo("1612817288484-6f916006741a"),
     "description": "Sulphate-free gel cleanser with aloe vera and neem for daily oil control."},
]

COUPONS = [
    {"code": "WELCOME10", "percent": 10, "max_discount": 500,  "min_order": 500},
    {"code": "MCA25",     "percent": 25, "max_discount": 2000, "min_order": 2000},
    {"code": "FEST50",    "percent": 50, "max_discount": 1000, "min_order": 5000},
]
