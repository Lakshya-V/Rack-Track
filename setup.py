import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "rack-track.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# client and admin tables (simple, non-hashed passwords for initial seeds)
cur.execute(
    "CREATE TABLE IF NOT EXISTS client (client_id INTEGER PRIMARY KEY AUTOINCREMENT, username VARCHAR(255), password VARCHAR(255), email VARCHAR(255) UNIQUE);"
)
cur.execute(
    "CREATE TABLE IF NOT EXISTS admin (admin_id INTEGER PRIMARY KEY AUTOINCREMENT, username VARCHAR(255), password VARCHAR(255), email VARCHAR(255) UNIQUE);"
)
# book table — keep isbn INT PRIMARY KEY to match earlier UI expectations
cur.execute(
    "CREATE TABLE IF NOT EXISTS book (title VARCHAR(255), author VARCHAR(255), status VARCHAR(255), rack_column_row VARCHAR(255), year INT, isbn INT PRIMARY KEY);"
)
# loans table for checkouts/returns (due_date stored as ISO string)
cur.execute(
    "CREATE TABLE IF NOT EXISTS loans (\n        loan_id INTEGER PRIMARY KEY AUTOINCREMENT,\n        client_id INTEGER,\n        client_username TEXT,\n        book_pk TEXT,\n        book_title TEXT,\n        issued_at TEXT,\n        due_date TEXT,\n        returned_at TEXT\n    );"
)

# sample seed
cur.execute(
    "INSERT OR IGNORE INTO book (title, author, status, rack_column_row, year, isbn) values(?,?,?,?,?,?);",
    ("The wonderful Wizard of Oz", "L. Frank Baum", "available", "1/1/1", 1900, 9780486280615),
)
cur.execute(
    "INSERT OR IGNORE INTO client (client_id, username, password, email) values(?,?,?,?);",
    (1, 'a', 'a', 'a@gmail.com'),
)
cur.execute(
    "INSERT OR IGNORE INTO admin (admin_id, username, password, email) values(?,?,?,?);",
    (1, 'admin', 'admin', 'admin@gmail.com'),
)

conn.commit()
conn.close()