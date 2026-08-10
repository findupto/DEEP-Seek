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

## Current MVP

- SQLite database created automatically on first run.
- Login with role-based users.
- Product/menu management.
- POS cart with quantity controls.
- Cash, card, and other payment methods.
- Sales are stored with invoice numbers.
- Printable receipt preview through a save-to-text option.
- Daily sales summary.

## Run

Python 3.10+ is recommended. The application uses only the Python standard library.

```bash
python app.py
```

The database is stored locally as `pos.db`.
