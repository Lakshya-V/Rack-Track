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
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QComboBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import (
    QIcon,
    QFont,
)
import sqlite3       

connection = sqlite3.connect("rack-track.db")
connection.row_factory = sqlite3.Row # to access columns by name

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

        # Results area (show labelled results including status)
        tab1_layout.result_label = QLabel("", self)
        tab1_layout.result_label.setWordWrap(True)
        tab1_layout.addWidget(tab1_layout.result_label)

        # Note: QMainWindow uses setCentralWidget; don't call setLayout on it
        self.tab.addTab(tab1_content, "Search Book")

        # Create the second tab
        tab2_content = QWidget()
        tab2_layout = QVBoxLayout()
        tab2_content.setLayout(tab2_layout)

        # Book management: filter + table + buttons
        tab2_layout.addWidget(QLabel("Books Management"))
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

        # replace the old results label with a QTableWidget for clear columns
        self.book_table = QTableWidget()
        self.book_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.book_table.setSelectionMode(QTableWidget.SingleSelection)
        self.book_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tab2_layout.addWidget(self.book_table)
        # connect selection change handler once
        self.book_table.itemSelectionChanged.connect(self._on_book_selection_changed)

        # wire buttons
        tab2_layout.add_btn.clicked.connect(self.add_book_dialog)
        tab2_layout.edit_btn.clicked.connect(self.edit_book_dialog)
        tab2_layout.remove_btn.clicked.connect(self.remove_book)
        tab2_layout.book_search.textChanged.connect(lambda t: self.load_books(t))

        self.tab.addTab(tab2_content, "Manage Books")

        tab3_content = QWidget()
        tab3_layout = QVBoxLayout()
        tab3_content.setLayout(tab3_layout)

        tab3_layout.addWidget(QLabel("Clients Management"))
        tab3_layout.client_search = QLineEdit(self)
        tab3_layout.client_search.setPlaceholderText("Filter clients by username/email")
        tab3_layout.addWidget(tab3_layout.client_search)

        crow = QHBoxLayout()
        tab3_layout.addLayout(crow)
        tab3_layout.add_btn = QPushButton("Add Client")
        tab3_layout.edit_btn = QPushButton("Edit Selected")
        tab3_layout.remove_btn = QPushButton("Remove Selected")
        crow.addWidget(tab3_layout.add_btn)
        crow.addWidget(tab3_layout.edit_btn)
        crow.addWidget(tab3_layout.remove_btn)

        # client table
        self.client_table = QTableWidget()
        self.client_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.client_table.setSelectionMode(QTableWidget.SingleSelection)
        self.client_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tab3_layout.addWidget(self.client_table)

        # wire client buttons
        tab3_layout.add_btn.clicked.connect(self.add_client_dialog)
        tab3_layout.edit_btn.clicked.connect(self.edit_client_dialog)
        tab3_layout.remove_btn.clicked.connect(self.remove_client)
        tab3_layout.client_search.textChanged.connect(lambda t: self.load_clients(t))

        # connect selection handler
        self.client_table.itemSelectionChanged.connect(self._on_client_selection_changed)

        # add the tab
        self.tab.addTab(tab3_content, "Manage Clients")

        layout.addWidget(QLabel(f"Welcome Admin: {username}"))
        central.setLayout(layout)
        self.setCentralWidget(central)

        # detect book columns and populate table
        self._book_columns = self._detect_book_columns()
        # set up table headers
        self.book_table.setColumnCount(len(self._book_columns))
        self.book_table.setHorizontalHeaderLabels([c.upper() for c in self._book_columns])
        # load initial book list
        self.load_books()
        # setup clients table and load
        self._client_columns = self._detect_client_columns()
        if hasattr(self, 'client_table') and self._client_columns:
            self.client_table.setColumnCount(len(self._client_columns))
            self.client_table.setHorizontalHeaderLabels([c.upper() for c in self._client_columns])
            self.load_clients()

    def _detect_book_columns(self):
        """Return list of book columns in preferred order depending on DB."""
        cur = connection.cursor()
        try:
            cur.execute("PRAGMA table_info(book)")
            cols = [row[1] for row in cur.fetchall()]
        finally:
            cur.close()
        preferred = ['id', 'title', 'author', 'status', 'rack_column_row', 'year', 'isbn']
        # return intersection in preferred order, then any other columns
        ordered = [c for c in preferred if c in cols]
        for c in cols:
            if c not in ordered:
                ordered.append(c)
        return ordered

    def load_books(self, filter_text=''):
        """Populate the book_table with rows matching optional filter_text."""
        cols = self._book_columns
        if not cols:
            return
        sel_sql = ",".join(cols)
        sql = f"SELECT {sel_sql} FROM book"
        params = ()
        if filter_text:
            sql += " WHERE title LIKE ? OR author LIKE ? OR isbn LIKE ?"
            params = (f"%{filter_text}%", f"%{filter_text}%", f"%{filter_text}%")

        cur = connection.cursor()
        try:
            cur.execute(sql, params)
            rows = cur.fetchall()
        finally:
            cur.close()

        self.book_table.setRowCount(len(rows))
        for r_i, r in enumerate(rows):
            for c_i, col in enumerate(cols):
                val = r[col] if col in r.keys() else ''
                item = QTableWidgetItem(str(val) if val is not None else '')
                self.book_table.setItem(r_i, c_i, item)

        # disable edit/remove when nothing is selected; UI selection handler toggles these
        self.tab.widget(1).layout().edit_btn.setEnabled(False)
        self.tab.widget(1).layout().remove_btn.setEnabled(False)

    def _on_book_selection_changed(self):
        has = bool(self.book_table.selectedItems())
        try:
            layout = self.tab.widget(1).layout()
            layout.edit_btn.setEnabled(has)
            layout.remove_btn.setEnabled(has)
        except Exception:
            pass

    # --- Client helpers ---
    def _detect_client_columns(self):
        cur = connection.cursor()
        try:
            cur.execute("PRAGMA table_info(client)")
            cols = [row[1] for row in cur.fetchall()]
        finally:
            cur.close()
        preferred = ['client_id', 'username', 'email', 'password']
        ordered = [c for c in preferred if c in cols]
        for c in cols:
            if c not in ordered:
                ordered.append(c)
        return ordered

    def load_clients(self, filter_text=''):
        cols = self._detect_client_columns()
        if not cols:
            return
        sel_sql = ",".join(cols)
        sql = f"SELECT {sel_sql} FROM client"
        params = ()
        if filter_text:
            sql += " WHERE username LIKE ? OR email LIKE ?"
            params = (f"%{filter_text}%", f"%{filter_text}%")
        cur = connection.cursor()
        try:
            cur.execute(sql, params)
            rows = cur.fetchall()
        finally:
            cur.close()

        self.client_table.setColumnCount(len(cols))
        self.client_table.setHorizontalHeaderLabels([c.upper() for c in cols])
        self.client_table.setRowCount(len(rows))
        for r_i, r in enumerate(rows):
            for c_i, col in enumerate(cols):
                val = r[col] if col in r.keys() else ''
                self.client_table.setItem(r_i, c_i, QTableWidgetItem(str(val) if val is not None else ''))

        # disable edit/remove initially
        try:
            layout = self.tab.widget(2).layout()
            layout.edit_btn.setEnabled(False)
            layout.remove_btn.setEnabled(False)
        except Exception:
            pass

    def _on_client_selection_changed(self):
        has = bool(self.client_table.selectedItems())
        try:
            layout = self.tab.widget(2).layout()
            layout.edit_btn.setEnabled(has)
            layout.remove_btn.setEnabled(has)
        except Exception:
            pass

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
            status = r['status'] if 'status' in keys else ''
            rcr = r['rack_column_row'] if 'rack_column_row' in keys else ''
            year_val = r['year'] if 'year' in keys else ''
            isbn = r['isbn'] if 'isbn' in keys else ''
            out.append(f"{r_id or isbn}: {title}\n  Author: {author} | Status: {status} | Rack: {rcr} | Year: {year_val} | ISBN: {isbn}")
        self.tab.widget(0).layout().result_label.setText("\n\n".join(out))

    def add_book_dialog(self):
        dlg = BookEditDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            title, author, status, rcr, year, isbn = dlg.get_data()
            local_cur = connection.cursor()
            try:
                local_cur.execute(
                    "INSERT INTO book(title,author,status,rack_column_row,year,isbn) VALUES(?,?,?,?,?,?)",
                    (title, author, status, rcr, year or None, isbn),
                )
                connection.commit()
            finally:
                local_cur.close()
            QMessageBox.information(self, "Added", "Book added successfully.")
            # refresh table
            self.load_books(self.tab.widget(1).layout().book_search.text().strip())

    def edit_book_dialog(self):
        # If a row is selected in the table, edit that; otherwise prompt for pk (id or isbn)
        pk_col = self._book_columns[0] if self._book_columns else 'isbn'
        selected = self.book_table.selectedItems()
        pk_value = None
        if selected:
            # first column value of the selected row
            row_idx = selected[0].row()
            pk_value = self.book_table.item(row_idx, 0).text()
        else:
            prompt = f"Enter book {pk_col} to edit:"
            id_text, ok = QInputDialog.getText(self, "Edit Book", prompt)
            if not ok or not id_text.strip():
                return
            pk_value = id_text.strip()

        # fetch the book by pk
        local_cur = connection.cursor()
        try:
            local_cur.execute(f"SELECT * FROM book WHERE {pk_col} = ?", (pk_value,))
            row = local_cur.fetchone()
        finally:
            local_cur.close()
        if not row:
            QMessageBox.warning(self, "Not found", "No book with that identifier")
            return

        # prepare data tuple in order (title,author,status,rack_column_row,year,isbn)
        data = (
            row['title'] if 'title' in row.keys() else '',
            row['author'] if 'author' in row.keys() else '',
            row['status'] if 'status' in row.keys() else '',
            row['rack_column_row'] if 'rack_column_row' in row.keys() else '',
            row['year'] if 'year' in row.keys() else None,
            row['isbn'] if 'isbn' in row.keys() else '',
        )
        dlg = BookEditDialog(parent=self, data=data)
        if dlg.exec() == QDialog.Accepted:
            title, author, status, rcr, year, isbn = dlg.get_data()
            local_cur = connection.cursor()
            try:
                local_cur.execute(
                    f"UPDATE book SET title=?,author=?,status=?,rack_column_row=?,year=?,isbn=? WHERE {pk_col}=?",
                    (title, author, status, rcr, year or None, isbn, pk_value),
                )
                connection.commit()
            finally:
                local_cur.close()
            QMessageBox.information(self, "Updated", "Book updated.")
            self.load_books(self.tab.widget(1).layout().book_search.text().strip())

    def remove_book(self):
        # remove selected row if present, else prompt for pk
        pk_col = self._book_columns[0] if self._book_columns else 'isbn'
        selected = self.book_table.selectedItems()
        if selected:
            row_idx = selected[0].row()
            pk_value = self.book_table.item(row_idx, 0).text()
        else:
            id_text, ok = QInputDialog.getText(self, "Remove Book", f"Enter book {pk_col} to remove:")
            if not ok or not id_text.strip():
                return
            pk_value = id_text.strip()

        if QMessageBox.question(self, "Confirm", f"Delete book {pk_value}?") != QMessageBox.Yes:
            return
        local_cur = connection.cursor()
        try:
            local_cur.execute(f"DELETE FROM book WHERE {pk_col} = ?", (pk_value,))
            connection.commit()
        finally:
            local_cur.close()
        QMessageBox.information(self, "Removed", "Book removed.")
        self.load_books(self.tab.widget(1).layout().book_search.text().strip())

    def add_client_dialog(self) :
        dlg = ClientEditDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            username, password, email = dlg.get_data()
            cur = connection.cursor()
            try:
                cur.execute("INSERT INTO client(username,password,email) VALUES(?,?,?)", (username, password, email))
                connection.commit()
            finally:
                cur.close()
            QMessageBox.information(self, "Added", "Client added.")
            self.load_clients(self.tab.widget(2).layout().client_search.text().strip())

    def edit_client_dialog(self) :
        # edit selected client or prompt for identifier
        cols = self._detect_client_columns()
        pk_col = cols[0] if cols else 'client_id'
        selected = self.client_table.selectedItems()
        if selected:
            row_idx = selected[0].row()
            pk_value = self.client_table.item(row_idx, 0).text()
        else:
            id_text, ok = QInputDialog.getText(self, "Edit Client", f"Enter client {pk_col} to edit:")
            if not ok or not id_text.strip():
                return
            pk_value = id_text.strip()

        cur = connection.cursor()
        try:
            cur.execute(f"SELECT * FROM client WHERE {pk_col} = ?", (pk_value,))
            row = cur.fetchone()
        finally:
            cur.close()
        if not row:
            QMessageBox.warning(self, "Not found", "No client with that identifier")
            return
        data = (
            row['username'] if 'username' in row.keys() else '',
            row['password'] if 'password' in row.keys() else '',
            row['email'] if 'email' in row.keys() else '',
        )
        dlg = ClientEditDialog(parent=self, data=data)
        if dlg.exec() == QDialog.Accepted:
            username, password, email = dlg.get_data()
            cur = connection.cursor()
            try:
                cur.execute(f"UPDATE client SET username=?,password=?,email=? WHERE {pk_col}=?", (username, password, email, pk_value))
                connection.commit()
            finally:
                cur.close()
            QMessageBox.information(self, "Updated", "Client updated.")
            self.load_clients(self.tab.widget(2).layout().client_search.text().strip())

    def remove_client(self) :
        cols = self._detect_client_columns()
        pk_col = cols[0] if cols else 'client_id'
        selected = self.client_table.selectedItems()
        if selected:
            row_idx = selected[0].row()
            pk_value = self.client_table.item(row_idx, 0).text()
        else:
            id_text, ok = QInputDialog.getText(self, "Remove Client", f"Enter client {pk_col} to remove:")
            if not ok or not id_text.strip():
                return
            pk_value = id_text.strip()
        if QMessageBox.question(self, "Confirm", f"Delete client {pk_value}?") != QMessageBox.Yes:
            return
        cur = connection.cursor()
        try:
            cur.execute(f"DELETE FROM client WHERE {pk_col} = ?", (pk_value,))
            connection.commit()
        finally:
            cur.close()
        QMessageBox.information(self, "Removed", "Client removed.")
        self.load_clients(self.tab.widget(2).layout().client_search.text().strip())


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

        layout.addWidget(QLabel("Status:"))
        self.status_box = QComboBox()
        # common statuses
        self.status_box.addItems(["available", "checked out", "reserved", "lost"]) 
        layout.addWidget(self.status_box)

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
            # data should be (title, author, status, rack_column_row, year, isbn)
            title, author, status, rack_column_row, year, isbn = data
            self.title_edit.setText(title or "")
            self.author_edit.setText(author or "")
            # set status if present in list, otherwise add it
            if status:
                idx = self.status_box.findText(status)
                if idx >= 0:
                    self.status_box.setCurrentIndex(idx)
                else:
                    self.status_box.addItem(status)
                    self.status_box.setCurrentText(status)
            self.rack_column_row_edit.setText(rack_column_row or "")
            self.year_edit.setText(str(year) if year is not None else "")
            # isbn may be stored as integer in the DB — convert to str for setText
            self.isbn_edit.setText(str(isbn) if isbn is not None else "")

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
            self.status_box.currentText().strip(),
            self.rack_column_row_edit.text().strip(),
            year,
            self.isbn_edit.text().strip(),
        )

    

class ClientEditDialog(QDialog):
    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        self.setWindowTitle("Client")
        self.resize(360, 160)
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Username:"))
        self.username_edit = QLineEdit()
        layout.addWidget(self.username_edit)

        layout.addWidget(QLabel("Password:"))
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password_edit)

        layout.addWidget(QLabel("Email:"))
        self.email_edit = QLineEdit()
        layout.addWidget(self.email_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if data:
            username, password, email = data
            self.username_edit.setText(username or "")
            # password may be stored hashed; leave blank by default to keep existing
            self.password_edit.setText(password or "")
            self.email_edit.setText(email or "")

        self.setLayout(layout)

    def accept(self):
        if not self.username_edit.text().strip():
            QMessageBox.warning(self, "Validation", "Username required")
            return
        super().accept()

    def get_data(self):
        return (
            self.username_edit.text().strip(),
            self.password_edit.text(),
            self.email_edit.text().strip(),
        )


