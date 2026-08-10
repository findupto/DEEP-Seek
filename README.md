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

The recommended launcher is `run_pos.py`. The UI is designed for desktop POS monitors, laptops and smaller displays with responsive sizing and accessibility controls.

- Horizontally scrollable module navigation for narrow displays.
- Consistent modern ttk controls, tables, spacing and typography.
- Light and dark appearance options.
- High-contrast option for improved readability.
- Adjustable interface scale from 90% to 140%.
- Compact navigation preference for smaller displays.
- Keyboard scaling shortcuts: `Ctrl +`, `Ctrl -`, `Ctrl + 0`.
- Keyboard-focus friendly controls and dialog shortcuts.
- Dedicated Display & Accessibility settings.
- Eye-friendly table row heights and touch-friendly controls.

Preferences are stored locally in `ui_preferences.json`.

## Modules

Customers, Suppliers, Products, Analytics, Stats, Staff, Counter Persons, Riders, Kitchen, Settings and Printers are available from the responsive navigation bar.

## Printers

Bluetooth discovery, saved printer configuration, automatic reconnect and editable 80mm receipt themes are supported. See `PRINTERS.md` for setup details.

## Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Then run:

```bash
python run_pos.py
```

The SQLite database is stored locally as `pos.db`.
