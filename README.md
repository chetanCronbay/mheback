# MHE Bazar — Backend (Django)

A concise, easy-to-understand guide to this repository. This README explains purpose, how to run the project, the development workflow, and documents the HTTP API so anyone (even without Django knowledge) can use or test the backend.

---

## Table of contents

- What is this repo
- Quickstart (setup & run)
- Development workflow
- Authentication & security
- API: common endpoints & examples
- File uploads, media, and static files
- Tests, migrations, and troubleshooting
- Key files & references

---

## What is this repo

This repository is the backend API for "MHE Bazar" — an e-commerce-like service for products, rentals, quotes, vendor applications, orders, payments, blogs, newsletters, and user management.

Key apps:
- users — accounts, vendor applications, reviews, contact forms, newsletter & training registrations
- products — categories, products, cart, wishlist, quotes, rentals
- order_management — orders, order items, deliveries, payments (Razorpay)
- blogs — blog CRUD
- banners — site banners

See router registration in [`mhe_backend.urls.router`](mhe_backend/urls.py) for the canonical set of API routes: [`mhe_backend/urls.py`](mhe_backend/urls.py).

---

## Quickstart — run locally

Prereqs:
- Python 3.11+ (match repo environment)
- Virtualenv or venv
- (Optional) PostgreSQL or MySQL — repository includes SQLite db for simple local runs

1. Clone / open this repo.
2. Create virtual env and install:
   ```sh
   python -m venv .venv
   source .venv/bin/activate   # or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```
   Files: [requirements.txt](requirements.txt)

3. Add environment variables. Create a `.env` in repo root with at least:
   - SECRET_KEY (see [`mhe_backend.settings.SECRET_KEY`](mhe_backend/settings.py))
   - DATABASE_URL (optional — `dj_database_url` supported)
   - RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET for payments (optional)
   Example:
   ```
   SECRET_KEY=change-me
   DATABASE_URL=sqlite:///db.sqlite3
   ```

4. Run migrations and create superuser:
   ```sh
   python manage.py migrate
   python manage.py createsuperuser
   ```
   See [manage.py](manage.py)

5. Start the server:
   ```sh
   python manage.py runserver
   ```
   Open http://127.0.0.1:8000/

---

## Development workflow

- Use feature branches and descriptive commit messages (conventional commits recommended).
- Run tests while developing:
  ```sh
  python manage.py test
  ```
- Use `select_related` and `prefetch_related` for query optimization (project rules: `Rules`).
- Store secrets in `.env` (see [`mhe_backend/settings.py`](mhe_backend/settings.py)).
- Serve media in dev; configure S3 or cloud storage in production (see MEDIA settings in [`mhe_backend/settings.py`](mhe_backend/settings.py)).

---

## Authentication & security

Primary auth:
- JWT (access + refresh) using simplejwt. Obtain tokens at `/api/token/` and refresh at `/api/token/refresh/`.
  - Controller: [`users.views.EmailTokenObtainPairView`](users/views.py)
- Google OAuth token exchange endpoint: `/api/google/login/` handled by [`users.views.GoogleLogin`](users/views.py).

Password reset flow:
- Request OTP: POST `/api/forgot-password/` -> [`users.views.ForgotPasswordRequestView`](users/views.py). Stores OTP in cache (10 min).
- Reset password: POST `/api/reset-password/` with `{ email, otp, new_password }` -> [`users.views.ResetPasswordView`](users/views.py).

Rate limiting & security helpers:
- IP-based rate limiter: [`util.security.IPRateLimiter`](util/security.py)
- Other security utilities: [`util.security.TokenGenerator`](util/security.py) and logger utilities.
- Throttle classes configured in settings: [`util.throttle.WriteOnlyAnonRateThrottle`](util/throttle.py) and [`util.throttle.WriteOnlyUserRateThrottle`](util/throttle.py).

---

## API Reference (overview)

Base path for router endpoints: `/api/` (see [`mhe_backend/urls.py`](mhe_backend/urls.py))

Common resource endpoints (RESTful patterns: list, retrieve, create, update, partial_update, destroy):

- Roles
  - GET/POST /api/roles/ — [`users.views.RoleViewSet`](users/views.py)
- Users
  - GET/POST /api/users/ — [`users.views.UserViewSet`](users/views.py)
  - POST /api/register/ — registration: [`users.views.RegisterView`](users/views.py)
  - POST /api/token/ — JWT: [`users.views.EmailTokenObtainPairView`](users/views.py)
  - POST /api/token/refresh/ — refresh token
  - POST /api/google/login/ — Google login: [`users.views.GoogleLogin`](users/views.py)

- Products & catalog
  - /api/categories/ — [`products.views.CategoryViewSet`](products/views.py)
  - /api/subcategories/ — [`products.views.SubcategoryViewSet`](products/views.py)
  - /api/products/ — [`products.views.ProductViewSet`](products/views.py)

- Cart & Wishlist
  - /api/cart/ — [`products.views.CartViewSet`](products/views.py)
  - /api/wishlist/ — [`products.views.WishlistViewSet`](products/views.py)

- Quotes & Rentals
  - /api/quotes/ — [`products.views.QuoteViewSet`](products/views.py)
  - /api/rentals/ — [`products.views.RentalViewSet`](products/views.py)

- Contact Forms, Reviews, Banners
  - /api/contact-forms/ — [`users.views.ContactFormViewSet`](users/views.py)
  - /api/reviews/ — [`users.views.ReviewViewSet`](users/views.py) (supports image upload via `upload_images` action)
  - /api/banners/ — [`banners.views.BannerViewSet`](banners/views.py)

- Training & Newsletter
  - /api/training-registrations/ — [`users.views.TrainingRegistrationViewSet`](users/views.py)
  - /api/newsletter-subscriptions/ — [`users.views.NewsletterSubscriptionViewSet`](users/views.py)

- Vendor management
  - POST /api/vendor/apply/ — apply to be vendor (`VendorApplicationView`)
  - GET /api/vendor/my-application/ — view/update own application (`MyVendorApplicationView`)
  - GET /api/vendor/approved/ — list approved vendors (`ApprovedVendorListView`)
  - Additional admin/vendor routes: see [`mhe_backend/urls.py`](mhe_backend/urls.py) and [`users.views.VendorViewSet`](users/views.py)

- Orders & Payments (order_management)
  - /api/orders/ — [`order_management.views.OrderViewSet`](order_management/views.py)
    - Special action: POST /api/orders/create_from_cart/ — create an order from current user's cart (`OrderViewSet.create_from_cart`) — see [`order_management.views.OrderViewSet.create_from_cart`](order_management/views.py)
  - /api/order-items/ — [`order_management.views.OrderItemViewSet`](order_management/views.py)
  - /api/deliveries/ — [`order_management.views.DeliveryViewSet`](order_management/views.py)
  - /api/payments/ — [`order_management.views.PaymentViewSet`](order_management/views.py)
    - POST /api/payments/create_razorpay_order/ — create Razorpay order (`PaymentViewSet.create_razorpay_order`) — config in [`mhe_backend/settings.py`](mhe_backend/settings.py) (RAZORPAY_KEY_ID/SECRET)

- Blogs
  - /api/blogs/ — list/create (`blogs.views.BlogViewSet`) and detail routes use `blog_url` as lookup field: [`blogs.views.BlogViewSet`](blogs/views.py)

Example: obtain JWT token
```sh
curl -X POST http://127.0.0.1:8000/api/token/ -H "Content-Type: application/json" \
  -d '{ "email": "user@example.com", "password": "secret" }'
```

Example: create order from cart (authenticated)
```sh
curl -X POST http://127.0.0.1:8000/api/orders/create_from_cart/ \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{ "shipping_address": { "line1": "...", "city":"...", "pincode": "..." } }'
```
(`OrderViewSet.create_from_cart` in [`order_management/views.py`](order_management/views.py))

---

## File uploads, media & static

- Media files are stored under MEDIA_ROOT (`MEDIA_URL` = `/media/`). See [`mhe_backend/settings.py`](mhe_backend/settings.py).
- Blogs, user profile photos, banners use ImageField/FileField with upload paths defined in model helper functions (`blogs.models.blog_path`, `users.models.user_profile_directory_path`, etc.)
- In production prefer cloud storage (e.g., S3). See comments in [`mhe_backend/settings.py`](mhe_backend/settings.py).

---

## Tests & migrations

- Run migrations:
  ```sh
  python manage.py makemigrations
  python manage.py migrate
  ```
- Run tests:
  ```sh
  python manage.py test
  ```
- Migrations are in each app's `migrations/` directory (e.g., `users/migrations/`, `products/migrations/`, `order_management/migrations/`).

---

## Troubleshooting tips

- SECRET_KEY missing: check [`mhe_backend/settings.py`](mhe_backend/settings.py) — it raises ImproperlyConfigured if SECRET_KEY not set.
- Razorpay errors: verify `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` in `.env` and settings (`mhe_backend/settings.py`).
- Uploads not showing in dev: ensure DEBUG=True and static/media serving in `mhe_backend/urls.py` (the project serves MEDIA in DEBUG).

---

## Key files & symbols (quick links)

- Project settings: [`mhe_backend.settings`](mhe_backend/settings.py)
- URL routing & API router: [`mhe_backend.urls`](mhe_backend/urls.py)
- Manage commands: [manage.py](manage.py)
- Users views & auth: [`users.views.RegisterView`](users/views.py), [`users.views.EmailTokenObtainPairView`](users/views.py), [`users.views.GoogleLogin`](users/views.py), [`users.views.ForgotPasswordRequestView`](users/views.py), [`users.views.ResetPasswordView`](users/views.py)
- Products models: [`products.models.Product`](products/models.py)
- Order flows: [`order_management.views.OrderViewSet`](order_management/views.py), [`order_management.views.PaymentViewSet`](order_management/views.py)
- Blogs: [`blogs.views.BlogViewSet`](blogs/views.py)
- Security utils: [`util.security.IPRateLimiter`](util/security.py), [`util.security.SecurityLogger`](util/security.py)
- Throttles: [`util.throttle.WriteOnlyAnonRateThrottle`](util/throttle.py)

---

## Contributing

- Fork, create a feature branch, write tests, and open a PR with descriptive commit messages.
- Follow the `Rules` and `GEMINI.md` guidelines in the repository.

---

If you want, I can:
- generate a Postman collection for the endpoints,
- add example request/response bodies for each endpoint,
- or prepare a small tutorial on extending the API or adding new features.