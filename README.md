# MK Pizza & Ice Bar POS

Python desktop Point of Sale system for **MK Pizza & Ice Bar**, Bhakkar, Pakistan.

## Business defaults

- Business: MK Pizza & Ice Bar
- Address: Collage Road Abbas Chowk, Bhakkar, Pakistan
- Phone: 0316 9700025
- Currency: Rs.
- Tax: 0%

## POS UI

The recommended launcher is `run_pos.py`. The desktop client is local-first and does not require cloud/provider connections.

- Responsive Windows/DPI-aware interface with touch-friendly controls.
- Product/menu, orders, kitchen, tables, customers, suppliers, purchasing, inventory, riders, staff, expenses, shifts, reports, printers and settings.
- Product import/export, catalog history, modifiers, product media and operational safeguards.
- Offline operation with SQLite and explicit backup/reset tooling.
- Printer auto-detection/reconnect support for supported Windows/Bluetooth/ESC-POS devices.

## Enterprise accounting

`enterprise_completion_patch.py` adds deterministic accounting and inventory valuation without replacing the existing POS tables:

- Double-entry journals with balance enforcement.
- Chart of accounts, trial balance and P&L.
- FIFO and weighted-average inventory valuation.
- COGS, wastage/spoilage, AP/AR and tax liability primitives.
- Locked accounting periods and store-scoped journals.
- Idempotent sync queue and conflict storage.
- Tamper-evident SHA-256 audit chains with verification.
- Atomic document-number allocation.

## Security and production services

`enterprise_services.py` provides PBKDF2 password hashing, rate limiting, provider adapters and encrypted backups. `enterprise_backend.py` is optional and is **secure by default**:

- `/health` and `/ready` remain available for monitoring.
- Business API endpoints require `POS_API_TOKEN` unless `POS_API_ALLOW_ANONYMOUS=true` is explicitly enabled.
- CORS defaults to localhost; production deployments should set `POS_CORS` explicitly.
- GPS coordinates are validated before storage.
- API database connections are closed on every request path.

Example server setup:

```bash
pip install -r requirements-enterprise.txt
set POS_API_TOKEN=<long-random-secret>
set POS_CORS=http://localhost:8080
uvicorn enterprise_backend:app --host 0.0.0.0 --port 8080
```

The `pwa/` client can be installed on phones/tablets and uses the same API. The desktop POS continues to work when the API is unavailable.

## Providers

External providers are optional and administrator-controlled. No fake credentials are bundled.

- SMS/email
- Card terminal/wallet
- Cloud synchronization
- GPS/routing
- Webhooks/notifications

Unavailable providers must not block local sales; supported operations can be queued for retry.

## Validation

Run the full local validation suite:

```bash
python health_check.py
python smoke_test.py
python -m pytest -q tests
```

GitHub Actions validates the project on Python 3.11, 3.12 and 3.13, compiles the complete source tree, runs all tests, the offline health check and the launcher smoke test.

## Run desktop POS

```bash
pip install -r requirements.txt
python run_pos.py
```

The SQLite database is stored locally as `pos.db`. Existing production data is preserved while enterprise tables are added automatically.
