"""Populate the database with a realistic dataset.

    python scripts/seed_data.py

Everything that has an endpoint is created *through the HTTP API*, so this
doubles as a volume test: 200+ real requests through routing, validation, auth,
and the ORM. Anything the API cannot reach yet is written directly with the ORM
and clearly reported as such.

Re-running is safe. Seeded accounts use the @vendora.seed email domain and are
removed at the start of every run; everything else hangs off them by foreign key,
so the cascades clear the rest. Your admin account is never touched.
"""

import asyncio
import random
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import delete, func, select, text

from app.config import settings
from app.database import AsyncSessionLocal, engine
from app.main import app, lifespan
from app.models import (
    Cart,
    CartItem,
    Category,
    Order,
    OrderItem,
    Payment,
    Product,
    Review,
    Seller,
    User,
)
from app.models.enums import OrderStatus, PaymentStatus

random.seed(20260827)

SEED_DOMAIN = "vendora.seed"
GREEN, RED, YELLOW, CYAN, DIM, BOLD, OFF = (
    "\033[32m", "\033[31m", "\033[33m", "\033[36m", "\033[2m", "\033[1m", "\033[0m"
)

# How many API calls each endpoint received, and how many were not 2xx.
calls: dict[str, list[int]] = {}
problems: list[str] = []


def record(endpoint: str, status: int, expected: tuple[int, ...] = (200, 201)) -> bool:
    ok = status in expected
    entry = calls.setdefault(endpoint, [0, 0])
    entry[0] += 1
    if not ok:
        entry[1] += 1
    return ok


def head(title: str) -> None:
    print(f"\n{BOLD}{title}{OFF}")


def line(label: str, detail: str = "") -> None:
    print(f"  {GREEN}·{OFF} {label}" + (f"{DIM}  {detail}{OFF}" if detail else ""))


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------

CATEGORIES = [
    ("Smartphones", "Handsets and accessories"),
    ("Laptops", "Notebooks and ultrabooks"),
    ("Tablets", "Tablets and e-readers"),
    ("Headphones", "Over-ear, on-ear and in-ear audio"),
    ("Cameras", "Mirrorless, DSLR and action cameras"),
    ("Televisions", "Smart TVs and displays"),
    ("Home Audio", "Speakers, soundbars and receivers"),
    ("Gaming", "Consoles, controllers and titles"),
    ("Wearables", "Smartwatches and fitness trackers"),
    ("Computer Parts", "Components and upgrades"),
    ("Networking", "Routers, switches and range extenders"),
    ("Storage", "Drives, cards and enclosures"),
    ("Printers", "Inkjet, laser and consumables"),
    ("Kitchen Appliances", "Blenders, kettles and cookers"),
    ("Home Cleaning", "Vacuums and steam cleaners"),
    ("Furniture", "Desks, chairs and shelving"),
    ("Lighting", "Lamps, bulbs and fixtures"),
    ("Bedding", "Sheets, duvets and pillows"),
    ("Cookware", "Pots, pans and bakeware"),
    ("Power & Solar", "Inverters, panels and batteries"),
    ("Tools", "Hand and power tools"),
    ("Garden", "Outdoor and horticulture"),
    ("Sports Equipment", "Training and field gear"),
    ("Cycling", "Bicycles, parts and safety"),
    ("Outdoor & Camping", "Tents, packs and stoves"),
    ("Beauty & Grooming", "Skincare and personal care"),
    ("Books", "Print and digital titles"),
    ("Toys & Games", "Play and learning"),
    ("Baby & Kids", "Nursery and childcare"),
    ("Automotive", "Car care, parts and electronics"),
]

BUSINESS_PREFIX = [
    "Savannah", "Rift Valley", "Kilimanjaro", "Lakeside", "Nairobi", "Coastal",
    "Highland", "Acacia", "Baobab", "Serengeti", "Amboseli", "Tsavo",
    "Meridian", "Northgate", "Copperline", "Blue Harbour", "Stonebridge",
    "Fair Trade", "Summit", "Halcyon", "Anvil", "Beacon", "Cedar", "Delta",
    "Everline", "Foundry", "Granite", "Harbour", "Ironwood", "Juniper",
]
BUSINESS_SUFFIX = [
    "Electronics", "Traders", "Supplies", "Distributors", "Retail", "Imports",
    "Merchants", "Outfitters", "Depot", "Emporium", "Works", "Collective",
]

FIRST_NAMES = [
    "Amina", "Brian", "Chege", "Daniela", "Elias", "Faith", "Gitau", "Halima",
    "Ian", "Joyce", "Kamau", "Lydia", "Mwangi", "Nadia", "Omar", "Pauline",
    "Quentin", "Rehema", "Samuel", "Tabitha", "Umar", "Violet", "Wanjiru",
    "Xavier", "Yusuf", "Zawadi", "Aiden", "Bianca", "Collins", "Dorothy",
    "Erick", "Fatuma", "George", "Hannah", "Isaac", "Janet", "Kevin", "Linet",
    "Martin", "Nancy", "Oscar", "Purity", "Ruth", "Simon", "Teresa", "Victor",
    "Winnie", "Yvonne", "Zachary", "Abigail", "Bernard", "Cynthia", "Dennis",
    "Emily", "Felix", "Grace", "Henry", "Irene", "James", "Kelvin",
]
LAST_NAMES = [
    "Achieng", "Barasa", "Cheruiyot", "Dube", "Ekiru", "Fernandes", "Gathoni",
    "Hassan", "Irungu", "Juma", "Kiptoo", "Lumumba", "Muthoni", "Njoroge",
    "Ochieng", "Peters", "Quaye", "Ruto", "Simiyu", "Tembo", "Ugwu", "Vincent",
    "Wekesa", "Yusuf", "Zulu", "Adeyemi", "Bosire", "Chirchir", "Dlamini",
    "Egbo",
]

PRODUCT_NOUNS = {
    "Smartphones": ["Aurora X1 Smartphone", "Pulse 5G Handset", "Nimbus Lite Phone"],
    "Laptops": ["Vertex 14 Ultrabook", "Forge 15 Laptop", "Slate Pro Notebook"],
    "Tablets": ["Canvas 11 Tablet", "Slate Mini Tablet", "Scribe E-Reader"],
    "Headphones": ["Echo ANC Headphones", "Drift Wireless Earbuds", "Studio Monitor Headset"],
    "Cameras": ["Lumen M50 Mirrorless", "Trail Action Camera", "Vista DSLR Kit"],
    "Televisions": ["Horizon 55in 4K TV", "Panorama 43in Smart TV", "Vivid 65in QLED"],
    "Home Audio": ["Resonance Soundbar", "Atlas Bookshelf Speakers", "Cadence AV Receiver"],
    "Gaming": ["Volt Wireless Controller", "Arcade Fight Stick", "Nexus Gaming Headset"],
    "Wearables": ["Stride Fitness Band", "Meridian Smartwatch", "Pulse Heart Monitor"],
    "Computer Parts": ["Torque 750W PSU", "Cryo CPU Cooler", "Spectra RGB Fan Kit"],
    "Networking": ["Mesh Wi-Fi 6 Router", "Gigabit 8-Port Switch", "Range Extender Pro"],
    "Storage": ["Vault 2TB NVMe SSD", "Cache 64GB Memory Card", "Portable 4TB Drive"],
    "Printers": ["Inkline All-in-One Printer", "Laserjet Mono Printer", "Photo Print Studio"],
    "Kitchen Appliances": ["Whirl Pro Blender", "Rapid Boil Kettle", "Multi Pressure Cooker"],
    "Home Cleaning": ["Cyclone Cordless Vacuum", "Steam Floor Cleaner", "Robot Vacuum Mini"],
    "Furniture": ["Standing Desk Frame", "Ergo Mesh Office Chair", "Modular Shelf Unit"],
    "Lighting": ["Warm LED Bulb 4-Pack", "Architect Desk Lamp", "Smart Ceiling Light"],
    "Bedding": ["Cotton Percale Sheet Set", "Duvet 200GSM", "Memory Foam Pillow"],
    "Cookware": ["Cast Iron Skillet 12in", "Nonstick Pan Set", "Stainless Stock Pot"],
    "Power & Solar": ["1kW Pure Sine Inverter", "150W Solar Panel", "Deep Cycle Battery"],
    "Tools": ["20V Cordless Drill", "Precision Driver Set", "Laser Distance Meter"],
    "Garden": ["Drip Irrigation Kit", "Pruning Shear Set", "Raised Planter Box"],
    "Sports Equipment": ["Adjustable Dumbbell Pair", "Match Football Size 5", "Yoga Mat 6mm"],
    "Cycling": ["Trail Hardtail Bicycle", "Vented Cycling Helmet", "Bike Repair Toolkit"],
    "Outdoor & Camping": ["Two-Person Trail Tent", "45L Hiking Backpack", "Compact Camp Stove"],
    "Beauty & Grooming": ["Beard Trimmer Kit", "Vitamin C Serum", "Hair Dryer 1800W"],
    "Books": ["Practical Python Handbook", "Modern Web Architecture", "Data Systems Primer"],
    "Toys & Games": ["Wooden Building Blocks", "Strategy Board Game", "Remote Control Rover"],
    "Baby & Kids": ["Convertible Car Seat", "Compact Stroller", "Nursery Night Light"],
    "Automotive": ["Dash Camera 1080p", "Tyre Inflator 12V", "Ceramic Wax Kit"],
}

ADJECTIVES = ["Compact", "Premium", "Everyday", "Heavy Duty", "Essential",
              "Professional", "Value", "Signature", "Traveller", "Studio"]

REVIEW_TEXT = [
    "Exactly as described, and it shipped faster than I expected.",
    "Good value for the price. Packaging could be sturdier.",
    "Works well so far. Setup took about ten minutes.",
    "Solid build quality. Would order from this seller again.",
    "Does the job, though the manual is thin.",
    "Better than the one it replaced. No complaints.",
    "Arrived on time and well packed.",
    "Decent, but I expected slightly better battery life.",
    "Very happy with this purchase.",
    "Reliable and straightforward. Recommended.",
]

TOWNS = ["Nairobi", "Mombasa", "Kisumu", "Nakuru", "Eldoret", "Thika", "Nyeri",
         "Machakos", "Kericho", "Malindi", "Garissa", "Kitale"]
STREETS = ["Moi Avenue", "Kenyatta Road", "Ngong Road", "Waiyaki Way", "Argwings Kodhek",
           "Langata Road", "Mama Ngina Street", "Biashara Street", "Oginga Odinga Street"]


def person(index: int) -> tuple[str, str]:
    first = FIRST_NAMES[index % len(FIRST_NAMES)]
    last = LAST_NAMES[(index * 7) % len(LAST_NAMES)]
    return first, last


def address() -> str:
    return (f"{random.randint(1, 400)} {random.choice(STREETS)}, "
            f"{random.choice(TOWNS)}, Kenya")


# ---------------------------------------------------------------------------

async def preflight() -> bool:
    head("Configuration")
    if "<YOUR_POSTGRES_PASSWORD>" in settings.DATABASE_URL:
        print(f"  {RED}FAIL{OFF}  DATABASE_URL still holds the placeholder password.")
        return False
    try:
        async with engine.connect() as conn:
            db = (await conn.execute(text("SELECT current_database()"))).scalar_one()
            tables = (await conn.execute(text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema='public'"))).scalar_one()
    except Exception as exc:  # noqa: BLE001
        print(f"  {RED}FAIL{OFF}  Cannot connect: {exc}")
        return False
    line("connected", db)
    if tables < 11:
        print(f"  {RED}FAIL{OFF}  Schema not migrated. Run: alembic upgrade head")
        return False
    line("schema migrated", f"{tables} tables")
    return True


async def clear_previous_seed() -> None:
    head("Clearing previous seed data")
    async with AsyncSessionLocal() as db:
        users = (await db.execute(
            select(User).where(User.email.like(f"%@{SEED_DOMAIN}"))
        )).scalars().all()
        user_ids = [u.id for u in users]

        if user_ids:
            sellers = (await db.execute(
                select(Seller.id).where(Seller.user_id.in_(user_ids))
            )).scalars().all()
            if sellers:
                products = (await db.execute(
                    select(Product.id).where(Product.seller_id.in_(sellers))
                )).scalars().all()
                if products:
                    await db.execute(
                        delete(Review).where(Review.product_id.in_(products)))
                    await db.execute(
                        delete(CartItem).where(CartItem.product_id.in_(products)))
                    await db.execute(
                        delete(OrderItem).where(OrderItem.product_id.in_(products)))
            orders = (await db.execute(
                select(Order.id).where(Order.user_id.in_(user_ids))
            )).scalars().all()
            if orders:
                await db.execute(delete(Payment).where(Payment.order_id.in_(orders)))
                await db.execute(delete(OrderItem).where(OrderItem.order_id.in_(orders)))
                await db.execute(delete(Order).where(Order.id.in_(orders)))
            await db.execute(delete(Review).where(Review.user_id.in_(user_ids)))
            carts = (await db.execute(
                select(Cart.id).where(Cart.user_id.in_(user_ids)))).scalars().all()
            if carts:
                await db.execute(delete(CartItem).where(CartItem.cart_id.in_(carts)))
                await db.execute(delete(Cart).where(Cart.id.in_(carts)))
            if sellers:
                await db.execute(delete(Product).where(Product.seller_id.in_(sellers)))
                await db.execute(delete(Seller).where(Seller.id.in_(sellers)))
            await db.execute(delete(User).where(User.id.in_(user_ids)))

        await db.execute(
            delete(Category).where(Category.name.in_([n for n, _ in CATEGORIES])))
        await db.commit()
    line("removed", f"{len(user_ids)} seeded accounts and everything hanging off them")


async def main() -> int:  # noqa: C901
    print(f"{BOLD}Vendora database seeding{OFF}")

    if not await preflight():
        return 1

    await clear_previous_seed()

    async with lifespan(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://seed.local", timeout=60
        ) as c:

            # ---------------------------------------------------------------
            head("Admin")
            r = await c.post("/auth/login", data={
                "username": settings.FIRST_ADMIN_USERNAME,
                "password": settings.FIRST_ADMIN_PASSWORD})
            record("POST /auth/login", r.status_code)
            if r.status_code != 200:
                print(f"  {RED}FAIL{OFF}  Admin login failed ({r.status_code}). "
                      f"Check FIRST_ADMIN_* in .env.")
                return 1
            AH = {"Authorization": f"Bearer {r.json()['access_token']}"}
            line("logged in", settings.FIRST_ADMIN_USERNAME)

            # ---------------------------------------------------------------
            head("Categories  ·  POST /categories")
            category_ids: dict[str, int] = {}
            for name, description in CATEGORIES:
                r = await c.post("/categories", headers=AH,
                                 json={"name": name, "description": description})
                if record("POST /categories", r.status_code, (201,)):
                    category_ids[name] = r.json()["id"]
                else:
                    problems.append(f"category {name!r} -> {r.status_code} {r.text[:90]}")
            line("created", f"{len(category_ids)} categories")

            # ---------------------------------------------------------------
            head("Users  ·  POST /auth/register")
            seller_accounts: list[dict] = []
            customer_accounts: list[dict] = []

            for i in range(30):                       # seller-owners
                first, last = person(i)
                seller_accounts.append({
                    "full_name": f"{first} {last}",
                    "username": f"seller_{first.lower()}{i:02d}",
                    "email": f"seller{i:02d}@{SEED_DOMAIN}",
                    "phone_number": f"+2547{100000 + i:06d}",
                    "password": "SeedPassword123",
                })
            for i in range(30):                       # customers
                first, last = person(i + 31)
                customer_accounts.append({
                    "full_name": f"{first} {last}",
                    "username": f"buyer_{first.lower()}{i:02d}",
                    "email": f"buyer{i:02d}@{SEED_DOMAIN}",
                    "phone_number": f"+2547{200000 + i:06d}",
                    "password": "SeedPassword123",
                })

            for account in seller_accounts + customer_accounts:
                r = await c.post("/auth/register", json=account)
                if record("POST /auth/register", r.status_code, (201,)):
                    account["id"] = r.json()["id"]
                else:
                    problems.append(
                        f"register {account['username']!r} -> {r.status_code} {r.text[:90]}")
            line("registered", f"{len(seller_accounts)} future sellers, "
                               f"{len(customer_accounts)} customers")

            async def token(account: dict) -> dict[str, str] | None:
                r = await c.post("/auth/login", data={
                    "username": account["username"], "password": account["password"]})
                if not record("POST /auth/login", r.status_code):
                    problems.append(
                        f"login {account['username']!r} -> {r.status_code}")
                    return None
                return {"Authorization": f"Bearer {r.json()['access_token']}"}

            # ---------------------------------------------------------------
            head("Sellers  ·  POST /sellers/register  +  PATCH /sellers/{id}/approve")
            approved: list[dict] = []
            pending = 0

            for index, account in enumerate(seller_accounts):
                headers = await token(account)
                if headers is None:
                    continue
                prefix = BUSINESS_PREFIX[index % len(BUSINESS_PREFIX)]
                suffix = BUSINESS_SUFFIX[index % len(BUSINESS_SUFFIX)]
                r = await c.post("/sellers/register", headers=headers, json={
                    "business_name": f"{prefix} {suffix}",
                    "business_description": (
                        f"{prefix} {suffix} has supplied the East African market "
                        f"since {2005 + (index % 18)}."),
                })
                if not record("POST /sellers/register", r.status_code, (201,)):
                    problems.append(
                        f"seller for {account['username']!r} -> {r.status_code}")
                    continue
                account["seller_id"] = r.json()["id"]

                # leave the last 4 unapproved, so the pending queue is not empty
                if index < len(seller_accounts) - 4:
                    r = await c.patch(f"/sellers/{account['seller_id']}/approve",
                                      headers=AH)
                    if record("PATCH /sellers/{id}/approve", r.status_code, (200,)):
                        account["headers"] = await token(account)   # role changed
                        approved.append(account)
                    else:
                        problems.append(
                            f"approve seller {account['seller_id']} -> {r.status_code}")
                else:
                    pending += 1
            line("sellers", f"{len(approved)} approved, {pending} awaiting approval")

            # ---------------------------------------------------------------
            head("Products  ·  POST /products")
            product_ids: list[int] = []
            category_names = list(category_ids)

            for n in range(60):
                account = approved[n % len(approved)]
                category_name = category_names[n % len(category_names)]
                base = PRODUCT_NOUNS[category_name][n % len(PRODUCT_NOUNS[category_name])]
                name = f"{random.choice(ADJECTIVES)} {base}"
                inventory = random.choice([0, 0, 3, 5, 8, 12, 25, 40, 60, 120])
                price = Decimal(random.choice([
                    "1299.00", "2450.50", "3999.99", "5750.00", "8999.00",
                    "12500.00", "18999.95", "24750.00", "31200.00", "47999.00",
                    "64500.00", "89999.99", "450.00", "899.50", "1750.25",
                ]))
                r = await c.post("/products", headers=account["headers"], json={
                    "name": name,
                    "description": (
                        f"{base} supplied by {account['full_name']}. "
                        f"Manufacturer warranty included. "
                        f"Ships from {random.choice(TOWNS)}."),
                    "price": str(price),
                    "inventory": inventory,
                    "category_id": category_ids[category_name],
                })
                if record("POST /products", r.status_code, (201,)):
                    product_ids.append(r.json()["id"])
                    account.setdefault("products", []).append(r.json()["id"])
                else:
                    problems.append(f"product {name!r} -> {r.status_code} {r.text[:90]}")
            line("created", f"{len(product_ids)} products across "
                            f"{len(category_ids)} categories")

            # ---------------------------------------------------------------
            head("Product images  ·  POST /products/{id}/images")
            image_count = 0
            for account in approved:
                for product_id in account.get("products", []):
                    for position in range(random.randint(2, 4)):
                        r = await c.post(
                            f"/products/{product_id}/images",
                            headers=account["headers"],
                            json={
                                "image_url":
                                    f"https://cdn.vendora.example/products/"
                                    f"{product_id}/{position}.jpg",
                                "is_primary": position == 0,
                                "sort_order": position,
                            })
                        if record("POST /products/{id}/images", r.status_code, (201,)):
                            image_count += 1
                        else:
                            problems.append(
                                f"image for product {product_id} -> {r.status_code}")
            line("created", f"{image_count} images")

    # -------------------------------------------------------------------
    # Tables with no endpoints yet -- written directly with the ORM.
    # -------------------------------------------------------------------
    head("Tables the API cannot reach  ·  written with the ORM")
    print(f"  {YELLOW}note{OFF}  {DIM}Cart, CartItem, Order, OrderItem, Payment and "
          f"Review have no routers,{OFF}")
    print(f"        {DIM}so these rows cannot be created through any endpoint.{OFF}")

    async with AsyncSessionLocal() as db:
        buyers = (await db.execute(
            select(User).where(User.email.like(f"buyer%@{SEED_DOMAIN}"))
        )).scalars().all()
        products = (await db.execute(
            select(Product).where(Product.inventory > 0))).scalars().all()

        if not buyers or not products:
            print(f"  {RED}FAIL{OFF}  No buyers or products to work with.")
            return 1

        # -- carts + items -------------------------------------------------
        cart_items = 0
        for buyer in buyers:
            cart = Cart(user_id=buyer.id)
            db.add(cart)
            await db.flush()
            for product in random.sample(products, random.randint(1, 4)):
                db.add(CartItem(cart_id=cart.id, product_id=product.id,
                                quantity=random.randint(1, 3)))
                cart_items += 1
        await db.commit()
        line("carts", f"{len(buyers)} carts holding {cart_items} items")

        # -- orders + items + payments ------------------------------------
        order_items = 0
        payments = 0
        now = datetime.now(UTC)
        for index, buyer in enumerate(buyers):
            for _ in range(random.randint(1, 2)):
                order = Order(
                    user_id=buyer.id,
                    total_amount=Decimal("0.00"),
                    status=random.choice(list(OrderStatus)).value,
                    shipping_address=address(),
                    created_at=now - timedelta(days=random.randint(0, 120)),
                )
                db.add(order)
                await db.flush()

                total = Decimal("0.00")
                for product in random.sample(products, random.randint(1, 4)):
                    quantity = random.randint(1, 3)
                    subtotal = product.price * quantity
                    db.add(OrderItem(order_id=order.id, product_id=product.id,
                                     quantity=quantity, unit_price=product.price,
                                     subtotal=subtotal))
                    total += subtotal
                    order_items += 1

                order.total_amount = total

                paid = order.status in (
                    OrderStatus.PAID.value, OrderStatus.SHIPPED.value,
                    OrderStatus.DELIVERED.value)
                db.add(Payment(
                    order_id=order.id,
                    amount=total,
                    status=(PaymentStatus.SUCCEEDED.value if paid
                            else PaymentStatus.PENDING.value),
                    payment_method=random.choice(["card", "mpesa", "bank_transfer"]),
                    transaction_reference=f"TXN-{order.id:06d}-{index:03d}",
                ))
                payments += 1
        await db.commit()
        orders_total = (await db.scalar(select(func.count()).select_from(Order))) or 0
        line("orders", f"{orders_total} orders, {order_items} line items, "
                       f"{payments} payments")

        # -- reviews (unique per user+product) -----------------------------
        reviews = 0
        used: set[tuple[int, int]] = set()
        for buyer in buyers:
            for product in random.sample(products, random.randint(1, 2)):
                key = (buyer.id, product.id)
                if key in used:
                    continue
                used.add(key)
                db.add(Review(
                    user_id=buyer.id, product_id=product.id,
                    rating=random.choices([5, 4, 3, 2, 1],
                                          weights=[45, 30, 15, 7, 3])[0],
                    comment=random.choice(REVIEW_TEXT),
                ))
                reviews += 1
        await db.commit()
        line("reviews", f"{reviews} reviews")

    # -------------------------------------------------------------------
    head("Row counts")
    async with engine.connect() as conn:
        for table in ("users", "sellers", "categories", "products", "product_images",
                      "carts", "cart_items", "orders", "order_items", "payments",
                      "reviews"):
            n = (await conn.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one()
            mark = f"{GREEN}✓{OFF}" if n >= 30 else f"{YELLOW}·{OFF}"
            print(f"  {mark} {table:16} {n:>5}")

    # -------------------------------------------------------------------
    head("Endpoint call summary")
    print(f"  {'endpoint':38} {'calls':>7} {'failed':>7}")
    total_calls = total_failed = 0
    for endpoint, (count, failed) in sorted(calls.items()):
        total_calls += count
        total_failed += failed
        colour = RED if failed else GREEN
        print(f"  {endpoint:38} {count:>7} {colour}{failed:>7}{OFF}")
    print(f"  {DIM}{'-' * 54}{OFF}")
    print(f"  {'TOTAL':38} {total_calls:>7} "
          f"{RED if total_failed else GREEN}{total_failed:>7}{OFF}")

    print(f"\n{BOLD}{'─' * 62}{OFF}")
    if problems:
        print(f"{RED}{BOLD}  {len(problems)} problems{OFF}")
        for problem in problems[:15]:
            print(f"    {RED}·{OFF} {problem}")
        if len(problems) > 15:
            print(f"    {DIM}… and {len(problems) - 15} more{OFF}")
    else:
        print(f"{GREEN}{BOLD}  {total_calls} API calls, 0 failures. "
              f"Database populated.{OFF}")
    print(f"{BOLD}{'─' * 62}{OFF}")

    await engine.dispose()
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
