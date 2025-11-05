# Rack-Track

Lightweight desktop library inventory (PyQt5 + SQLite).

Quick start
- Create and activate a Python venv, install requirements, then run setup and the app:

```powershell
python -m venv env
.\env\Scripts\Activate.ps1
pip install -r requirements.txt
python .\setup.py
python .\main.py
```

Default seeded accounts
- Admin: `admin` / `admin`
- Sample client: `a` / `a`

Planned improvements
- Stronger password hashing (bcrypt) and migration path
- Better DB migrations (safe upgrades for `book.id` and schema changes)
- Loans: configurable rules, overdue notifications, fines
- Import: validated bulk CSV import with a preview step
- UI: read-only tables for search results, double-click to edit

Notes
- `setup.py` imports `library_dataset_random.csv` if present; set `REPLACE_BOOKS` in `setup.py` to control whether books are wiped before import.
- Do not commit runtime DB files (`rack-track.db`). It's OK to commit sanitized CSVs for reproducible setup.
