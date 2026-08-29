<div align="center">

<br>

# 🛒 &nbsp;V E N D O R A

### A multi-vendor marketplace API

*Customers browse and buy · Sellers run their own storefront · Admins curate the catalogue*

<br>

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![JWT](https://img.shields.io/badge/JWT-000000?style=for-the-badge&logo=jsonwebtokens&logoColor=white)

**[What it is](#-what-it-is)** &nbsp;·&nbsp; **[Endpoints](#-endpoints)** &nbsp;·&nbsp; **[Configuration](#-configuration)**

<br>

</div>

---

## 📖 What it is

Vendora is the backend for an online marketplace where independent sellers list products under their own storefront, customers browse and buy, and admins keep the catalogue in order.

It is a **JSON API** — no HTML, no templates. Authentication is **JWT bearer tokens**, passwords are hashed with **Argon2**, and the whole stack is async: FastAPI on top of SQLAlchemy 2.0 and PostgreSQL.

### Three roles

| Role | Can do |
|:--|:--|
| 🛍️ &nbsp;**Customer** | Browse the catalogue, manage their profile, apply to become a seller |
| 🏪 &nbsp;**Seller** | Everything a customer can, plus create and manage their own products and images |
| 👑 &nbsp;**Admin** | Everything above, plus create categories, approve sellers, and change anyone's role |

Everyone who registers starts as a **customer**. Roles change in exactly two ways:

```mermaid
graph LR
    A["register<br/>· customer ·"] --> B["apply<br/>POST /sellers/register"]
    B --> C["admin approves<br/>PATCH /sellers/id/approve"]
    C --> D["· seller ·"]
    A -.->|"seeded from .env"| E["· admin ·"]
    E -.->|"PATCH /users/id/role"| D
```

> [!IMPORTANT]
> After approval the seller must **log in again**. Their old token still carries the previous role until it expires.

### Interactive docs

Once the server is running, every endpoint is browsable and testable in your browser:

| | |
|:--|:--|
| 🧪 &nbsp;**Swagger UI** | `http://localhost:8000/docs` |
| 📗 &nbsp;**ReDoc** | `http://localhost:8000/redoc` |
| ⚙️ &nbsp;**OpenAPI spec** | `http://localhost:8000/openapi.json` |

---

## 🔌 Endpoints

**23 endpoints.** Anything marked *owner* only works on resources you created.

### 🌍 &nbsp;Public — no token needed

| Method | Endpoint | What it does |
|:--|:--|:--|
| ![GET](https://img.shields.io/badge/GET-0E7490?style=flat-square) | `/` | Welcome message |
| ![GET](https://img.shields.io/badge/GET-0E7490?style=flat-square) | `/health` | Health check |
| ![POST](https://img.shields.io/badge/POST-2B7D55?style=flat-square) | `/auth/register` | Create a customer account |
| ![POST](https://img.shields.io/badge/POST-2B7D55?style=flat-square) | `/auth/login` | Exchange credentials for tokens |
| ![POST](https://img.shields.io/badge/POST-2B7D55?style=flat-square) | `/auth/refresh` | Trade a refresh token for a fresh pair |
| ![GET](https://img.shields.io/badge/GET-0E7490?style=flat-square) | `/categories` | List categories |
| ![GET](https://img.shields.io/badge/GET-0E7490?style=flat-square) | `/categories/{id}` | One category |
| ![GET](https://img.shields.io/badge/GET-0E7490?style=flat-square) | `/products` | Browse the catalogue |
| ![GET](https://img.shields.io/badge/GET-0E7490?style=flat-square) | `/products/{id}` | One product |
| ![GET](https://img.shields.io/badge/GET-0E7490?style=flat-square) | `/products/{id}/images` | A product's images, sorted |

> [!WARNING]
> **`/auth/login` is the one endpoint that is not JSON.** It follows the OAuth2 spec and expects `application/x-www-form-urlencoded`. Send JSON and you get `422 Field required`.
>
> ```bash
> curl -X POST http://localhost:8000/auth/login -d "username=ada&password=supersecret123"
> ```

### 🔑 &nbsp;Authenticated — any logged-in user

| Method | Endpoint | What it does |
|:--|:--|:--|
| ![GET](https://img.shields.io/badge/GET-0E7490?style=flat-square) | `/users/me` | Your own profile |
| ![POST](https://img.shields.io/badge/POST-2B7D55?style=flat-square) | `/sellers/register` | Apply to become a seller |
| ![GET](https://img.shields.io/badge/GET-0E7490?style=flat-square) | `/sellers/me` | Your seller profile and approval status |

### 🏪 &nbsp;Seller — role `seller` **and** approved

| Method | Endpoint | What it does |
|:--|:--|:--|
| ![POST](https://img.shields.io/badge/POST-2B7D55?style=flat-square) | `/products` | Create a product |
| ![PATCH](https://img.shields.io/badge/PATCH-9A6410?style=flat-square) | `/products/{id}` | Update your product · *owner* |
| ![DELETE](https://img.shields.io/badge/DELETE-A63A31?style=flat-square) | `/products/{id}` | Delete your product · *owner* |
| ![POST](https://img.shields.io/badge/POST-2B7D55?style=flat-square) | `/products/{id}/images` | Attach an image · *owner* |
| ![DELETE](https://img.shields.io/badge/DELETE-A63A31?style=flat-square) | `/products/{id}/images/{image_id}` | Remove an image · *owner* |

### 👑 &nbsp;Admin only

| Method | Endpoint | What it does |
|:--|:--|:--|
| ![GET](https://img.shields.io/badge/GET-0E7490?style=flat-square) | `/users` | List every account · `?role=seller` |
| ![PATCH](https://img.shields.io/badge/PATCH-9A6410?style=flat-square) | `/users/{id}/role` | Promote or demote an account |
| ![GET](https://img.shields.io/badge/GET-0E7490?style=flat-square) | `/sellers` | Seller applications · `?pending_only=true` |
| ![PATCH](https://img.shields.io/badge/PATCH-9A6410?style=flat-square) | `/sellers/{id}/approve` | Approve a seller — **grants the seller role** |
| ![POST](https://img.shields.io/badge/POST-2B7D55?style=flat-square) | `/categories` | Create a category |

<br>

### 🔎 Filtering the catalogue

`GET /products` takes any combination of these. They all combine with **AND**.

| Parameter | Type | Default | |
|:--|:--|:--|:--|
| `limit` | `1–100` | `20` | Page size |
| `offset` | `≥ 0` | `0` | How many to skip |
| `category_id` | `int` | — | Restrict to one category |
| `search` | `string` | — | Case-insensitive match on the name |
| `min_price` `max_price` | `decimal` | — | Price band |
| `in_stock_only` | `bool` | `false` | Hide sold-out products |
| `sort_by` | `created_at` `price` `name` | `created_at` | |
| `sort_dir` | `asc` `desc` | `desc` | |

```
GET /products?search=laptop&in_stock_only=true&max_price=50000&sort_by=price&sort_dir=asc
```

### 📦 Response shapes

List endpoints — `/products`, `/categories`, `/users`, `/sellers` — return a **page**, not a bare array:

```jsonc
{
  "items":  [ /* … */ ],
  "total":  60,   // matches your filters, ignores limit/offset
  "limit":  20,
  "offset": 0
}
```

> [!NOTE]
> **`price` is a JSON string**, not a number — `"1999.99"`. That keeps cents exact. Convert it before doing arithmetic: `Number(product.price)`.

### 📋 Status codes

| | |
|:--|:--|
| `200` `201` `204` | Success |
| `401` | Missing, malformed, or expired token |
| `403` | Wrong role, seller not approved, or not your resource |
| `404` | Not found, or the category is inactive |
| `409` | Duplicate — username, email, phone, category, seller |
| `422` | Validation failed — read `detail[]` for the offending fields |

---

## ⚙️ Configuration

Everything is read from a `.env` file in the project root. Start from the template:

```bash
cp .env.example .env
```

### The two required values

**`DATABASE_URL`** — your PostgreSQL connection string.

```ini
DATABASE_URL=postgresql+asyncpg://postgres:yourpassword@localhost:5432/market_place_project
```

> [!CAUTION]
> The **`+asyncpg`** driver is required. A plain `postgresql://` URL fails at startup.
> If your password contains `@ : / ? # %` it must be percent-encoded:
> ```bash
> python -c "import urllib.parse,getpass; print(urllib.parse.quote(getpass.getpass()))"
> ```

**`SECRET_KEY`** — signs your JWTs. Must be **32+ characters**; the app refuses to start otherwise.

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

### Every setting

| Variable | Default | What it does |
|:--|:--|:--|
| **`DATABASE_URL`** | *required* | PostgreSQL DSN, `+asyncpg` driver |
| **`SECRET_KEY`** | *required* | JWT signing key, 32 chars minimum |
| `ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access-token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh-token lifetime |
| `DEBUG` | `false` | Logs every SQL statement — **local only**, it includes user data |
| `CORS_ORIGINS` | `localhost:3000,5173` | Comma-separated origins allowed to call the API |
| `FIRST_ADMIN_USERNAME` | *(unset)* | Seeds the first admin on startup — blank skips it |
| `FIRST_ADMIN_PASSWORD` | *(unset)* | That admin's password, 8 chars minimum |
| `FIRST_ADMIN_EMAIL` | `admin@example.com` | Must be a valid address |
| `FIRST_ADMIN_FULL_NAME` | `Site Admin` | |
| `FIRST_ADMIN_PHONE` | `+254700000000` | |

### About `CORS_ORIGINS`

These are the **frontend's** origins — the address the browser page is served from — *not* this API's URL. Get this wrong and every request from the browser is blocked before it reaches your code.

```ini
CORS_ORIGINS=http://localhost:5173,https://your-frontend.vercel.app
```

### About the first admin

Everyone who registers through the API is a customer, and only an admin can change roles — so the first admin has to come from configuration. Set these and it is created on the next startup:

```ini
FIRST_ADMIN_USERNAME=admin
FIRST_ADMIN_PASSWORD=pick-a-real-password
```

It runs on every boot but only ever creates the account once. **Log in, then clear `FIRST_ADMIN_PASSWORD` from the file.**

<br>

<details>
<summary><b>📄 A complete .env, ready to paste</b></summary>

<br>

```ini
# ── Database ─────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://postgres:yourpassword@localhost:5432/market_place_project

# ── Security ─────────────────────────────────────────────
# python -c "import secrets; print(secrets.token_urlsafe(64))"
SECRET_KEY=paste-a-64-character-random-string-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# ── Behaviour ────────────────────────────────────────────
DEBUG=false
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# ── First admin ──────────────────────────────────────────
FIRST_ADMIN_USERNAME=admin
FIRST_ADMIN_PASSWORD=change-this-password
FIRST_ADMIN_EMAIL=admin@example.com
FIRST_ADMIN_FULL_NAME=Site Admin
FIRST_ADMIN_PHONE=+254700000000
```

</details>

### Then run it

```bash
pip install -r requirements.txt
```
```bash
alembic upgrade head
```
```bash
uvicorn app.main:app --reload
```

> [!TIP]
> `.env` is gitignored — **never commit it**. Use a different `SECRET_KEY` for every environment; changing it invalidates every token already issued.

<br>

---

<div align="center">

**Vendora** &nbsp;·&nbsp; FastAPI &nbsp;·&nbsp; SQLAlchemy 2.0 &nbsp;·&nbsp; PostgreSQL

<sub>Interactive documentation lives at <code>/docs</code> once the server is running.</sub>

</div>
