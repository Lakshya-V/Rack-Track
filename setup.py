import csv
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "rack-track.db")
CSV_FILE = os.path.join(os.path.dirname(__file__), "library_dataset_random.csv")
# If True the script wipes `book` before importing. Set to False to preserve existing rows.
REPLACE_BOOKS = True


def ensure_tables(conn):
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS client (client_id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password TEXT, email TEXT UNIQUE);")
    cur.execute("CREATE TABLE IF NOT EXISTS admin (admin_id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password TEXT, email TEXT UNIQUE);")
    cur.execute("CREATE TABLE IF NOT EXISTS book (title TEXT, author TEXT, status TEXT, rack_column_row TEXT, year INTEGER, isbn INTEGER PRIMARY KEY);")
    cur.execute("CREATE TABLE IF NOT EXISTS loans (loan_id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, client_username TEXT, book_pk TEXT, book_title TEXT, issued_at TEXT, due_date TEXT, returned_at TEXT, fine INTEGER);")
    # basic seeds
    cur.execute("INSERT OR IGNORE INTO admin (admin_id, username, password, email) VALUES (?,?,?,?);", (1, 'admin', 'admin', 'admin@gmail.com'))
    cur.execute("INSERT OR IGNORE INTO client (client_id, username, password, email) VALUES (?,?,?,?);", (1, 'a', 'a', 'a@gmail.com'))
    conn.commit()


def import_csv(conn, csv_path):
    if not os.path.exists(csv_path):
        print("CSV not found; skipping import.")
        return 0
    cur = conn.cursor()
    inserted = 0
    with open(csv_path, newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader):
            title = (row.get('title') or row.get('Title') or '')[:255]
            author = (row.get('author') or row.get('Author') or '')[:255]
            year = row.get('year') or row.get('Year') or None
            try:
                year = int(year) if year else None
            except Exception:
                year = None
            isbn = row.get('isbn') or row.get('ISBN')
            try:
                isbn = int(isbn) if isbn else None
            except Exception:
                isbn = None
            if not isbn:
                # fallback pseudo-isbn
                isbn = 10**12 + i
            try:
                cur.execute(
                    "INSERT OR IGNORE INTO book (title, author, status, rack_column_row, year, isbn) VALUES (?,?,?,?,?,?);",
                    (title, author, 'available', '', year, isbn),
                )
                if cur.rowcount:
                    inserted += 1
            except Exception:
                continue
    conn.commit()
    print(f"Imported {inserted} books from CSV.")
    return inserted


def ensure_book_id(conn):
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(book);")
    cols = [r[1] for r in cur.fetchall()]
    if 'id' not in cols:
        try:
            cur.execute("ALTER TABLE book ADD COLUMN id INTEGER;")
            cur.execute("UPDATE book SET id = rowid WHERE id IS NULL;")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_book_id ON book(id);")
            conn.commit()
        except Exception:
            pass


def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_tables(conn)
        if REPLACE_BOOKS:
            print("REPLACE_BOOKS=True: wiping existing `book` rows.")
            conn.execute("DELETE FROM book;")
            conn.commit()
        import_csv(conn, CSV_FILE)
        ensure_book_id(conn)
    finally:
        conn.close()


if __name__ == '__main__':
    main()