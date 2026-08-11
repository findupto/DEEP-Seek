# MK Pizza & Ice Bar POS

Python desktop Point of Sale system for **MK Pizza & Ice Bar**, Bhakkar, Pakistan.

## Business defaults

- Business: MK Pizza & Ice Bar
- Address: Collage Road Abbas Chowk, Bhakkar, Pakistan
- Phone: 0316 9700025
- Currency: Rs.
- Tax: 0%

## Default users

| Username | Role | Password |
| --- | --- | --- |
| admin | Admin | `0099` |
| owner | Owner | `0099` |
| cashier | Cashier | `0099` |
| accountant | Accountant | `0099` |

## POS UI

The recommended launcher is `run_pos.py`. The application is a responsive Tkinter desktop POS for POS monitors, laptops and smaller displays.

- Minimal, low-motion interface with generous whitespace.
- Deep navy navigation, soft neutral surfaces and restrained metallic-gold actions.
- Refined typography with a strong display/body contrast.
- Responsive window sizing, DPI handling and resizable dialogs.
- Horizontally scrollable navigation for narrow displays.
- Light/dark/accessibility preferences and adjustable interface scale.
- Keyboard focus support: `Ctrl+F` focuses POS search, `F5` refreshes the current page, `Esc` closes the top dialog.
- Touch-friendly controls and readable table row heights.
- Preferences are stored locally in `ui_preferences.json`.

## Modules

Customers, Suppliers, Products, Analytics, Stats, Staff, Counter Persons, Riders, Kitchen, Settings and Printers are available from the navigation bar.

### Production operations

- **POS Checkout** — Counter, Takeaway, Dine-in and Delivery orders with customer selection, rider rates, delivery distance/fee, discounts, notes and kitchen dispatch.
- **Order Board** — New, Preparing, Ready, Out for Delivery, Completed and Cancelled lifecycle with order timeline and delivery tracking.
- **Payments** — Paid, partial and later collection workflows with payment references.
- **Returns / Refunds** — Full or partial line refunds, stock restoration, credit-balance adjustment and audit history.
- **Cash Control** — Opening/closing sessions, expected cash and variance tracking.
- **End of Day** — Gross sales, refunds, expenses, net sales, cash expectations and payment-method reconciliation.
- **Expenses** — Operating expense recording and reporting.
- **Stock Control** — Purchases, controlled stock additions/removals, movement history and checkout stock preflight.
- **Customers & Suppliers** — CRUD, archive/restore, balances, transactions and histories.
- **Tables / Dine-in** — Table setup, occupancy and table sessions.
- **Riders / Delivery** — Rider availability, base/per-km/minimum fees and tracking events.
- **Audit Log** — Important operational changes with user, entity, action, details and timestamp.
- **System Health** — SQLite integrity, negative-stock and orphan-record checks plus database export.
- **Backup & Recovery** — Local SQLite backups before upgrades or major changes.

## Printers

Bluetooth discovery, saved printer configuration, automatic reconnect and editable 80mm receipt themes are supported. See `PRINTERS.md` for setup details.

## Validation

Run the offline health check before deployment:

```bash
python health_check.py
```

It compiles the Python modules, imports the canonical launcher, verifies required App methods, checks the production schema in memory and runs SQLite integrity validation without modifying `pos.db`.

## Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Then run:

```bash
python run_pos.py
```

The SQLite database is stored locally as `pos.db`. Production tables are added automatically without removing existing data.
