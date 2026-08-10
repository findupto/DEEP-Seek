# POS Management Modules

The expanded POS is available in `pos.py` and uses the same SQLite `pos.db` database.

## Modules

- Dashboard: business overview cards and balances.
- Customers: searchable customer list, dues/credits/advance/payment transactions, current balance, and clickable transaction history.
- Suppliers: searchable supplier list, dues/credits/advance/payment transactions, current balance, and clickable transaction history.
- Products: search/filter, add, edit, delete selected, CSV bulk upload and CSV download.
- Analytics: daily order and sales history.
- Stats: operational counts and balances.
- Staff: staff records with role and salary.
- Counter Persons: staff records dedicated to counter operations.
- Riders: staff records dedicated to delivery riders.
- Kitchen: preparation workflow placeholder ready for POS order integration.
- Settings: business configuration screen.

## Product CSV

CSV columns supported for upload/download:

`id,name,price,category,stock`

The `id` column is optional when importing; imported rows are added as new products.

## Party balance rules

- Due: increases outstanding balance.
- Credit: increases outstanding balance.
- Advance: decreases outstanding balance.
- Payment: decreases outstanding balance.

Each transaction is stored in `party_transactions` and can be opened from the party list by double-clicking the customer or supplier.

## Run

```bash
python pos.py
```

Default users remain:

- admin / 0099
- owner / 0099
- cashier / 0099
- accountant / 0099
