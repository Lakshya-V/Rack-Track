from PyQt5.QtWidgets import (
    QPushButton,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QInputDialog,
    QTabWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import (
    QIcon,
    QFont,
)
import sqlite3       # add if book is available or not and check and rectify tab problems

connection = sqlite3.connect("rack-track.db")
connection.row_factory = sqlite3.Row

class MainWindow(QMainWindow):
    """Initial window with Admin and Client buttons."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("RACK-TRACK")
        self.setWindowIcon(QIcon('assets/icon.png'))
        self.setStyleSheet('''QMainWindow{border-image : url('assets/b_g.png') 0 0 0 0 stretch stretch;
            }''')
        central = QWidget()
        layout = QVBoxLayout()
        # push the whole content a bit down so the top text appears lower on large screens
        layout.setContentsMargins(0, 40, 0, 0)

        name = QLabel("WELCOME  TO  RACK-TRACK")
        title = QLabel("________________________CHOOSE  MODE________________________")
        space = QLabel("")

        # make the main title slightly larger and give it a small bottom margin
        title.setFont(QFont("Arial", 22, QFont.Bold))
        name.setFont(QFont("Arial", 25, QFont.Bold))
        name.setStyleSheet("color: white; margin-top: 80px;")
        # keep a small spacer between name and title (reduced from large hardcoded margins)
        space.setFixedHeight(450)
        title.setStyleSheet("color: white; margin-bottom: 8px;")

        title.setAlignment(Qt.AlignCenter)
        name.setAlignment(Qt.AlignCenter)
        space.setAlignment(Qt.AlignCenter)
        layout.addWidget(name)
        layout.addWidget(space)
        layout.addWidget(title)

        button_layout = QVBoxLayout()
        # tighten spacing so title sits closer to the buttons
        button_layout.setSpacing(10)
        admin_btn = QPushButton("ADMIN")
        admin_btn.setStyleSheet("background-color: green; font-size: 16px; padding: 23px; margin-bottom: 15px; margin-right:80px; margin-left:80px; margin-top:10px")
        client_btn = QPushButton("CLIENT")
        client_btn.setStyleSheet("background-color: blue; font-size: 16px; padding: 23px; margin-bottom: 50px; margin-right:80px; margin-left:80px; margin-top:10px")
        button_layout.addWidget(admin_btn)
        button_layout.addWidget(client_btn)

        layout.addLayout(button_layout)
        central.setLayout(layout)
        self.setCentralWidget(central)

        admin_btn.clicked.connect(self.open_admin)
        client_btn.clicked.connect(self.open_client)

        # keep a reference to any opened child window so it doesn't get garbage collected
        self._child_window = None

    def open_admin(self):
        # Repeatedly prompt until the dialog is cancelled or valid credentials are provided.
        while True:
            dlg = CredentialsDialog(role="Admin", parent=self)
            if dlg.exec() != QDialog.Accepted:
                # user cancelled
                return

            username, password = dlg.get_credentials()

            # validate using a local cursor and parameterized query
            local_cur = connection.cursor()
            try:
                local_cur.execute("SELECT 1 FROM admin WHERE username = ? AND password = ?", (username, password))
                result = local_cur.fetchone()
            finally:
                local_cur.close()

            if result:
                admin_window = AdminWindow(username=username, parent=self)
                admin_window.show()
                self._child_window = admin_window
                return
            else:
                # show a short warning and loop to re-prompt
                QMessageBox.warning(self, "Access Denied", "Invalid credentials. Please try again.")

    def open_client(self):
        # For clients we currently just require non-empty credentials (could be validated against a clients table)
        while True:
            dlg = CredentialsDialog(role="Client", parent=self)
            if dlg.exec() != QDialog.Accepted:
                return
            username,password = dlg.get_credentials()          

            local_cur = connection.cursor()
            try :
                local_cur.execute("SELECT 1 FROM client WHERE username = ? AND password = ?", (username, password))
                result = local_cur.fetchone()
            finally :
                local_cur.close()

            if result:
                client_window = ClientWindow(username=username, parent=self)
                client_window.show()
                self._child_window = client_window
                return
            else:
                QMessageBox.warning(self, "Access Denied", "Invalid credentials. Please try again.")


class CredentialsDialog(QDialog):
    """Simple credentials dialog used for both Admin and Client."""

    def __init__(self, role="User", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{role} Login")
        self.setModal(True)

        layout = QVBoxLayout()
        self.resize(350, 150)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: red")
        layout.addWidget(self.error_label)

        layout.addWidget(QLabel("Username:"))
        self.user_edit = QLineEdit()
        layout.addWidget(self.user_edit)

        layout.addWidget(QLabel("Password:"))
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.pass_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def accept(self):
        if not self.user_edit.text().strip() or not self.pass_edit.text():
            self.error_label.setText("Please enter both username and password.")
            return
        super().accept()

    def get_credentials(self):
        return self.user_edit.text().strip(), self.pass_edit.text()


class AdminWindow(QMainWindow):
    def __init__(self, username, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Admin - {username}")
        self.resize(700, 500)
        central = QWidget()
        layout = QVBoxLayout()
        self.tab = QTabWidget()
        layout.addWidget(self.tab)
        tab1_content = QWidget()
        tab1_layout = QVBoxLayout()
        tab1_content.setLayout(tab1_layout)
        # Search controls
        tab1_layout.search_input = QLineEdit(self)
        tab1_layout.search_input.setPlaceholderText("Enter title, author, year or ISBN to search")
        tab1_layout.addWidget(tab1_layout.search_input)

        tab1_layout.search_button = QPushButton("SEARCH BOOK", self)
        tab1_layout.addWidget(tab1_layout.search_button)
        tab1_layout.search_button.clicked.connect(self.search_book)

        # Results area
        tab1_layout.result_label = QLabel("", self)
        tab1_layout.result_label.setWordWrap(True)
        tab1_layout.addWidget(tab1_layout.result_label)


        # Note: QMainWindow uses setCentralWidget; don't call setLayout on it
        self.tab.addTab(tab1_content, "Search Book")

        # Create the second tab
        tab2_content = QWidget()
        tab2_layout = QVBoxLayout()
        tab2_content.setLayout(tab2_layout)

        # Book management: list + buttons
        tab2_layout.addWidget(QLabel("Manage Books"))
        tab2_layout.book_search = QLineEdit(self)
        tab2_layout.book_search.setPlaceholderText("Filter books by title/author")
        tab2_layout.addWidget(tab2_layout.book_search)

        buttons_row = QHBoxLayout()
        tab2_layout.addLayout(buttons_row)
        tab2_layout.add_btn = QPushButton("Add Book")
        tab2_layout.edit_btn = QPushButton("Edit Selected")
        tab2_layout.remove_btn = QPushButton("Remove Selected")
        buttons_row.addWidget(tab2_layout.add_btn)
        buttons_row.addWidget(tab2_layout.edit_btn)
        buttons_row.addWidget(tab2_layout.remove_btn)

        tab2_layout.results_box = QLabel("(No selection)")
        tab2_layout.results_box.setWordWrap(True)
        tab2_layout.addWidget(tab2_layout.results_box)

        # wire buttons
        tab2_layout.add_btn.clicked.connect(self.add_book_dialog)
        tab2_layout.edit_btn.clicked.connect(self.edit_book_dialog)
        tab2_layout.remove_btn.clicked.connect(self.remove_book)

        self.tab.addTab(tab2_content, "Manage Books")
        layout.addWidget(QLabel(f"Welcome Admin: {username}"))
        central.setLayout(layout)
        self.setCentralWidget(central)

    def search_book(self):
        text = self.tab.widget(0).layout().search_input.text().strip()
        if not text:
            self.tab.widget(0).layout().result_label.setText("Please enter a search term.")
            return

        local_cur = connection.cursor()
        # try to interpret as year if it's numeric
        year = None
        if text.isdigit():
            year = int(text)

        try:
            local_cur.execute(
                "SELECT * FROM book WHERE title LIKE ? OR author LIKE ? OR isbn LIKE ? OR year = ?",
                (f"%{text}%", f"%{text}%", f"%{text}%", year),
            )
            rows = local_cur.fetchall()
        finally:
            local_cur.close()

        if not rows:
            self.tab.widget(0).layout().result_label.setText("No books found.")
            return

        out = []
        for r in rows:
            # sqlite3.Row will raise if a column name doesn't exist; handle older DBs gracefully
            keys = list(r.keys())
            r_id = r['id'] if 'id' in keys else ''
            title = r['title'] if 'title' in keys else ''
            author = r['author'] if 'author' in keys else ''
            rcr = r['rack_column_row'] if 'rack_column_row' in keys else ''
            year_val = r['year'] if 'year' in keys else ''
            isbn = r['isbn'] if 'isbn' in keys else ''
            out.append(f"{r_id}: {title} — {author} {rcr} ({year_val}) ISBN:{isbn}")
        self.tab.widget(0).layout().result_label.setText("\n".join(out))

    def add_book_dialog(self):
        dlg = BookEditDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            title, author, rcr, year, isbn = dlg.get_data()
            local_cur = connection.cursor()
            try:
                local_cur.execute("INSERT INTO book(title,author,rack_column_row,year,isbn) VALUES(?,?,?,?,?)", (title, author, rcr, year or None, isbn))
                connection.commit()
            finally:
                local_cur.close()
            QMessageBox.information(self, "Added", "Book added successfully.")

    def edit_book_dialog(self):
        # For simplicity, ask for the book id to edit
        id_text, ok = QInputDialog.getText(self, "Edit Book", "Enter book id to edit:")
        if not ok or not id_text.strip().isdigit():
            return
        book_id = int(id_text.strip())
        local_cur = connection.cursor()
        try:
            local_cur.execute("SELECT * FROM book WHERE id = ?", (book_id,))
            row = local_cur.fetchone()
        finally:
            local_cur.close()
        if not row:
            QMessageBox.warning(self, "Not found", "No book with that id")
            return
        dlg = BookEditDialog(parent=self, data=(row['title'], row['author'], row['year'], row['isbn']))
        if dlg.exec() == QDialog.Accepted:
            title, author, rcr, year, isbn = dlg.get_data()
            local_cur = connection.cursor()
            try:
                local_cur.execute("UPDATE book SET title=?,author=?,rack_column_row=?,year=?,isbn=? WHERE id=?",(title, author, rcr, year or None, isbn, book_id))
                connection.commit()
            finally:
                local_cur.close()
            QMessageBox.information(self, "Updated", "Book updated.")

    def remove_book(self):
        id_text, ok = QInputDialog.getText(self, "Remove Book", "Enter book id to remove:")
        if not ok or not id_text.strip().isdigit():
            return
        book_id = int(id_text.strip())
        if QMessageBox.question(self, "Confirm", f"Delete book {book_id}?") != QMessageBox.Yes:
            return
        local_cur = connection.cursor()
        try:
            local_cur.execute("DELETE FROM book WHERE id = ?", (book_id,))
            connection.commit()
        finally:
            local_cur.close()
        QMessageBox.information(self, "Removed", "Book removed.")


class ClientWindow(QMainWindow):
    def __init__(self, username="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Client - {username}")
        self.resize(700, 500)
        central = QWidget()
        layout = QVBoxLayout()
        self.tab = QTabWidget()
        layout.addWidget(self.tab)
        tab1_content = QWidget()
        tab1_layout = QVBoxLayout()
        tab1_content.setLayout(tab1_layout)
        tab1_layout.addWidget(QLabel("This is the content of Tab 1."))
        self.tab.addTab(tab1_content, "Tab 1 Title")

        # Create the second tab
        tab2_content = QWidget()
        tab2_layout = QVBoxLayout()
        tab2_content.setLayout(tab2_layout)
        tab2_layout.addWidget(QLabel("This is the content of Tab 2."))
        self.tab.addTab(tab2_content, "Tab 2 Title")
        layout.addWidget(QLabel(f"Welcome Client: {username}"))
        central.setLayout(layout)
        self.setCentralWidget(central)


class BookEditDialog(QDialog):
    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        self.setWindowTitle("Book")
        self.resize(400, 200)
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Title:"))
        self.title_edit = QLineEdit()
        layout.addWidget(self.title_edit)

        layout.addWidget(QLabel("Author:"))
        self.author_edit = QLineEdit()
        layout.addWidget(self.author_edit)

        layout.addWidget(QLabel("Rack/Column/Row:"))
        self.rack_column_row_edit = QLineEdit()
        layout.addWidget(self.rack_column_row_edit)

        layout.addWidget(QLabel("Year:"))
        self.year_edit = QLineEdit()
        layout.addWidget(self.year_edit)

        layout.addWidget(QLabel("ISBN:"))
        self.isbn_edit = QLineEdit()
        layout.addWidget(self.isbn_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if data:
            # data should be (title, author, rack_column_row, year, isbn)
            title, author, rack_column_row, year, isbn = data
            self.title_edit.setText(title or "")
            self.author_edit.setText(author or "")
            self.rack_column_row_edit.setText(rack_column_row or "")
            self.year_edit.setText(str(year) if year is not None else "")
            self.isbn_edit.setText(isbn or "")

        self.setLayout(layout)

    def accept(self):
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, "Validation", "Title is required")
            return
        super().accept()

    def get_data(self):
        year_text = self.year_edit.text().strip()
        year = int(year_text) if year_text.isdigit() else None
        return (
            self.title_edit.text().strip(),
            self.author_edit.text().strip(),
            self.rack_column_row_edit.text().strip(),
            year,
            self.isbn_edit.text().strip(),
        )

