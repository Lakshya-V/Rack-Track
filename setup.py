import sqlite3

connection = sqlite3.connect("rack-track.db")
cur = connection.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS client (client_id INT PRIMARY KEY, username VARCHAR(255), password VARCHAR(255), email VARCHAR(255) UNIQUE);")
cur.execute("CREATE TABLE IF NOT EXISTS admin (admin_id INT PRIMARY KEY, username VARCHAR(255), password VARCHAR(255), email VARCHAR(255) UNIQUE);")
cur.execute("CREATE TABLE IF NOT EXISTS book (title VARCHAR(255), author VARCHAR(255), status VARCHAR(255), rack_column_row VARCHAR(255), year INT, isbn INT PRIMARY KEY);")
cur.execute("INSERT INTO book (title, author, status, rack_column_row, year, isbn) values('The Great Gatsby','F. Scott Fitzgerald','available', '4/5/4', 1925,9780743273565);")
cur.execute("INSERT INTO client (client_id, username, password, email) values(1,'a','a','a@gmail.com');")
cur.execute("INSERT INTO admin (admin_id, username, password, email) values(1,'admin','admin','admin@gmail.com')")
connection.commit()
connection.close()