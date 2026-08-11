# MK Pizza & Ice Bar POS

Python desktop Point of Sale system for **MK Pizza & Ice Bar**, Bhakkar, Pakistan.

## Business defaults

- Business: MK Pizza & Ice Bar
- Address: Collage Road Abbas Chowk, Bhakkar, Pakistan
- Phone: 0316 9700025
- Currency: Rs.
- Tax: 0%

## POS UI

The recommended launcher is `run_pos.py`. The desktop client remains local-first and operates without cloud/provider connections.

- Minimal, low-motion interface with generous whitespace.
- Deep navy navigation, soft neutral surfaces and restrained metallic-gold actions.
- Responsive window sizing, DPI handling and touch-friendly controls.
- Keyboard focus and accessible interface scaling.

## Enterprise completion layer

`enterprise_completion_patch.py` adds deterministic accounting and inventory valuation primitives without replacing existing POS tables:

- Double-entry journals with debit/credit balance enforcement.
- Chart of accounts, trial balance and P&L.
- FIFO and weighted-average inventory layers.
- Automatic cost calculation for valued stock issues.
- Wastage/spoilage accounting.
- AP/AR ledgers and tax liability accounts.
- Locked accounting periods.
- Store-scoped journals and document numbering.
- Idempotent offline sync queue and conflict storage.
- Tamper-evident SHA-256 audit chain with verification.
- Robust invoice/document sequence allocation.

`enterprise_services.py` provides optional production services:

- PBKDF2 password hashing and verification.
- Login-attempt rate limiting primitive.
- Generic payment terminal/wallet adapter.
- Generic SMS/email adapter.
- Generic routing/geocoding adapter for ETA/geofence integrations.
- Encrypted database backups using Fernet when `cryptography` is installed.
- Restore integrity verification.

## Optional API / mobile PWA

`enterprise_backend.py` is a real optional FastAPI service for multi-user/cloud operation. The desktop POS does not depend on it.

```bash
pip install -r requirements-enterprise.txt
uvicorn enterprise_backend:app --host 0.0.0.0 --port 8080
```

Endpoints include `/health`, `/api/pnl`, `/api/trial-balance`, `/api/sync`, and `/api/gps/{rider_id}`. Set `POS_API_TOKEN` for API authentication and `POS_CORS` to restrict browser origins.

The `pwa/` client is installable on phones/tablets and reads the same API. When the API is unavailable, the existing desktop POS remains usable locally.

## Provider model

All external integrations are optional and administrator-controlled. An administrator can configure provider URLs/tokens through the existing provider administration UI. No fake credentials are bundled.

- SMS/email provider
- Card terminal/wallet provider
- Cloud synchronization backend
- GPS/routing provider
- Webhooks and notification channels

Unconfigured or unavailable providers never need to block local sales; operations can be queued for retry.

## Validation

```bash
python health_check.py
pip install -r requirements-enterprise.txt
python -m pytest -q tests/test_enterprise_completion.py
```

GitHub Actions also runs the enterprise regression tests on `main` and pull requests.

## Run desktop POS

```bash
pip install -r requirements.txt
python run_pos.py
```

The SQLite database is stored locally as `pos.db`. Existing production data is preserved while enterprise tables are added automatically.
