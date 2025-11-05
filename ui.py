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
    QComboBox,
    QScrollArea,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import (
    QIcon,
    QFont,
)
import sqlite3       
from datetime import datetime
from datetime import timedelta

connection = sqlite3.connect("rack-track.db")
connection.row_factory = sqlite3.Row # to access columns by name


def ensure_loans_table():
    """Create a simple loans table for issue/return tracking if it doesn't exist."""
    cur = connection.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS loans (
                loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                client_username TEXT,
                book_pk TEXT,
                book_title TEXT,
                issued_at TEXT,
                due_date TEXT,
                returned_at TEXT
            )
            """
        )
        connection.commit()
    finally:
        cur.close()


def ensure_book_id_column():
    """Ensure book table has an 'id' column. If missing, add it and populate from rowid.

    This avoids OperationalError when code references 'id' alongside 'isbn'.
    The added 'id' will not be the PRIMARY KEY (we keep existing isbn PK) but
    will be populated with rowid values for stable numeric ids.
    """
    cur = connection.cursor()
    try:
        cur.execute("PRAGMA table_info(book)")
        cols = [r[1] for r in cur.fetchall()]
        if 'id' not in cols:
            # add id column (nullable integer)
            cur.execute("ALTER TABLE book ADD COLUMN id INTEGER")
            # populate id from rowid for existing rows
            try:
                cur.execute("UPDATE book SET id = rowid WHERE id IS NULL")
            except Exception:
                # some sqlite builds or edge cases could fail; ignore but continue
                pass
            # create index for faster lookups
            try:
                cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_book_id ON book(id)")
            except Exception:
                pass
            connection.commit()
    finally:
        cur.close()
# ensure helpful compatibility columns exist at startup
try:
    ensure_loans_table()
except Exception:
    # if DB is locked or not writable, we'll attempt again later when needed
    pass

# loan policy defaults
MAX_LOANS = 5
LOAN_DAYS = 14

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

    # ---- Client window helpers: search, checkout, my loans ----
    def _detect_book_columns_client(self):
        cur = connection.cursor()
        try:
            cur.execute("PRAGMA table_info(book)")
            cols = [row[1] for row in cur.fetchall()]
        finally:
            cur.close()
        preferred = ['id', 'title', 'author', 'status', 'rack_column_row', 'year', 'isbn']
        ordered = [c for c in preferred if c in cols]
        for c in cols:
            if c not in ordered:
                ordered.append(c)
        return ordered

    def load_search_results(self, filter_text=''):
        cols = self._detect_book_columns_client()
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

        self.search_table.setColumnCount(len(cols))
        self.search_table.setHorizontalHeaderLabels([c.upper() for c in cols])
        self.search_table.setRowCount(len(rows))
        for r_i, r in enumerate(rows):
            for c_i, col in enumerate(cols):
                val = r[col] if col in r.keys() else ''
                self.search_table.setItem(r_i, c_i, QTableWidgetItem(str(val) if val is not None else ''))

    def checkout_selected(self):
        # ensure loans table
        ensure_loans_table()
        # find selected book in search_table
        selected = self.search_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Select book", "Please select a book to check out.")
            return
        row_idx = selected[0].row()
        # assume first column is pk (id or isbn)
        pk_val = self.search_table.item(row_idx, 0).text()
        # get title
        title = self.search_table.item(row_idx, 1).text() if self.search_table.columnCount() > 1 else ''
        # determine client id/username stored on this window
        client_id = getattr(self, 'client_id', None)
        client_username = getattr(self, 'username', '')

        # check book availability
        cur = connection.cursor()
        try:
            cur.execute("SELECT * FROM book WHERE isbn = ? OR id = ?", (pk_val, pk_val))
            book_row = cur.fetchone()
        finally:
            cur.close()
        if book_row and 'status' in book_row.keys() and book_row['status'] == 'checked out':
            QMessageBox.warning(self, "Unavailable", "Book is already checked out.")
            return

        # enforce max loans per client
        cur = connection.cursor()
        try:
            if client_id is not None:
                cur.execute("SELECT COUNT(*) FROM loans WHERE client_id = ? AND returned_at IS NULL", (client_id,))
            else:
                cur.execute("SELECT COUNT(*) FROM loans WHERE client_username = ? AND returned_at IS NULL", (client_username,))
            out_count = cur.fetchone()[0]
        finally:
            cur.close()

        if out_count >= MAX_LOANS:
            QMessageBox.warning(self, "Limit reached", f"You already have {out_count} outstanding loans (max {MAX_LOANS}). Return some books before checking out more.")
            return

        # insert loan with due date and mark book checked out
        issued_at = datetime.now()
        due = (issued_at + timedelta(days=LOAN_DAYS)).isoformat()
        issued_at_iso = issued_at.isoformat()
        cur = connection.cursor()
        try:
            cur.execute(
                "INSERT INTO loans (client_id, client_username, book_pk, book_title, issued_at, due_date, returned_at) VALUES (?,?,?,?,?,?,NULL)",
                (client_id, client_username, pk_val, title, issued_at_iso, due),
            )
            cur.execute("UPDATE book SET status = 'checked out' WHERE isbn = ? OR id = ?", (pk_val, pk_val))
            connection.commit()
        finally:
            cur.close()

        QMessageBox.information(self, "Checked out", "Book checked out successfully.")
        # refresh my loans and search results
        self.load_my_loans()
        self.load_search_results(self.search_table.item(row_idx, 0).text())

    def load_my_loans(self):
        ensure_loans_table()
        cur = connection.cursor()
        try:
            if getattr(self, 'client_id', None) is not None:
                cur.execute("SELECT loan_id, book_pk, book_title, issued_at, due_date, returned_at FROM loans WHERE client_id = ? ORDER BY issued_at DESC", (self.client_id,))
            else:
                cur.execute("SELECT loan_id, book_pk, book_title, issued_at, due_date, returned_at FROM loans WHERE client_username = ? ORDER BY issued_at DESC", (getattr(self, 'username', ''),))
            rows = cur.fetchall()
        finally:
            cur.close()

        cols = ['LOAN_ID', 'BOOK', 'TITLE', 'ISSUED_AT', 'DUE_DATE', 'RETURNED_AT']
        self.my_loans_table.setColumnCount(len(cols))
        self.my_loans_table.setHorizontalHeaderLabels(cols)
        self.my_loans_table.setRowCount(len(rows))
        for r_i, r in enumerate(rows):
            self.my_loans_table.setItem(r_i, 0, QTableWidgetItem(str(r['loan_id'])))
            self.my_loans_table.setItem(r_i, 1, QTableWidgetItem(str(r['book_pk'])))
            self.my_loans_table.setItem(r_i, 2, QTableWidgetItem(str(r['book_title'])))
            self.my_loans_table.setItem(r_i, 3, QTableWidgetItem(str(r['issued_at'])))
            self.my_loans_table.setItem(r_i, 4, QTableWidgetItem(str(r.get('due_date') or '')))
            self.my_loans_table.setItem(r_i, 5, QTableWidgetItem(str(r['returned_at'] or '')))

    def return_selected(self):
        selected = self.my_loans_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Select loan", "Please select a loan to return.")
            return
        row_idx = selected[0].row()
        loan_id = self.my_loans_table.item(row_idx, 0).text()
        book_pk = self.my_loans_table.item(row_idx, 1).text()
        now = datetime.now().isoformat()
        cur = connection.cursor()
        try:
            cur.execute("UPDATE loans SET returned_at = ? WHERE loan_id = ?", (now, loan_id))
            cur.execute("UPDATE book SET status = 'available' WHERE isbn = ? OR id = ?", (book_pk, book_pk))
            connection.commit()
        finally:
            cur.close()
        QMessageBox.information(self, "Returned", "Book marked as returned.")
        self.load_my_loans()

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
            try:
                local_cur.execute("SELECT client_id FROM client WHERE username = ? AND password = ?", (username, password))
                row = local_cur.fetchone()
            finally:
                local_cur.close()

            if row:
                client_id = row['client_id'] if 'client_id' in row.keys() else None
                client_window = ClientWindow(client_id=client_id, username=username, parent=self)
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
        self.resize(1200, 800)
        central = QWidget()
        layout = QVBoxLayout()
        self.tab = QTabWidget()
        layout.addWidget(self.tab)
        tab1_content = QWidget()
        tab1_layout = QVBoxLayout()
        tab1_content.setLayout(tab1_layout)

        # top row: left = search controls, right = vertical action buttons
        top_row = QHBoxLayout()
        left_col = QVBoxLayout()
        right_buttons = QVBoxLayout()

        # Search controls (left)
        left_col.search_input = QLineEdit(self)
        left_col.search_input.setPlaceholderText("Enter title, author, year or ISBN to search")
        left_col.addWidget(left_col.search_input)

        left_col.search_button = QPushButton("SEARCH BOOK", self)
        left_col.search_button.setStyleSheet("margin-top: 0px; margin-bottom: 5px;padding:10px; font-size:15px;")
        left_col.show_all = QPushButton("SHOW ALL BOOKS", self)
        left_col.show_all.setStyleSheet("margin-top: 0px; margin-bottom: 5px;padding:10px; font-size:15px;")
        left_col.addWidget(left_col.search_button)
        left_col.addWidget(left_col.show_all)

        # Vertical action buttons (right)
        right_buttons.available = QPushButton("AVAILABLE BOOKS")
        right_buttons.issue = QPushButton("CHECKED OUT BOOKS")
        right_buttons.lost = QPushButton("LOST BOOKS")
        right_buttons.addWidget(right_buttons.available)
        right_buttons.addWidget(right_buttons.issue)
        right_buttons.addWidget(right_buttons.lost)
        right_buttons.setAlignment(Qt.AlignTop)

        top_row.addLayout(left_col)
        top_row.addLayout(right_buttons)
        tab1_layout.addLayout(top_row)

        tab1_layout.search_input = left_col.search_input
        tab1_layout.search_button = left_col.search_button
        tab1_layout.show_all = left_col.show_all
        tab1_layout.available = right_buttons.available
        tab1_layout.issue = right_buttons.issue
        tab1_layout.lost = right_buttons.lost

        left_col.search_button.clicked.connect(self.search_book)
        left_col.show_all.clicked.connect(self.show_books)
        right_buttons.issue.clicked.connect(self.show_issued_books)
        right_buttons.lost.clicked.connect(self.show_lost_books)
        right_buttons.available.clicked.connect(self.show_available_books)

        # Results area (show labelled results including status)
        tab1_layout.result_label = QLabel("", self)
        tab1_layout.result_label.setWordWrap(True)
        # Put the result label into a scroll area so long search outputs scroll
        tab1_layout.scroll_area = QScrollArea()
        tab1_layout.scroll_area.setWidgetResizable(True)
        _result_container = QWidget()
        _result_layout = QVBoxLayout()
        _result_layout.setContentsMargins(0, 0, 0, 0)
        _result_layout.addWidget(tab1_layout.result_label)
        _result_container.setLayout(_result_layout)
        tab1_layout.scroll_area.setWidget(_result_container)
        tab1_layout.addWidget(tab1_layout.scroll_area)

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

        # ensure table scrollbars appear when needed
        self.book_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.book_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

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
        self.client_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.client_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # wire client buttons
        tab3_layout.add_btn.clicked.connect(self.add_client_dialog)
        tab3_layout.edit_btn.clicked.connect(self.edit_client_dialog)
        tab3_layout.remove_btn.clicked.connect(self.remove_client)
        tab3_layout.client_search.textChanged.connect(lambda t: self.load_clients(t))

        # connect selection handler
        self.client_table.itemSelectionChanged.connect(self._on_client_selection_changed)

        # add the tab
        self.tab.addTab(tab3_content, "Manage Clients")

        # --- Issue summary tab for admin: who issued how many books ---
        tab4_content = QWidget()
        tab4_layout = QVBoxLayout()
        tab4_content.setLayout(tab4_layout)
        tab4_layout.addWidget(QLabel("Issue Summary (who issued how many books)"))
        tab4_layout.refresh_btn = QPushButton("Refresh")
        tab4_layout.addWidget(tab4_layout.refresh_btn)

        self.issue_table = QTableWidget()
        self.issue_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tab4_layout.addWidget(self.issue_table)

        tab4_layout.refresh_btn.clicked.connect(self.load_issue_summary)
        self.tab.addTab(tab4_content, "Issue Summary")

        layout.addWidget(QLabel(f"Welcome Admin: {username}"))
        central.setLayout(layout)
        # Wrap the central widget in a scroll area so the admin UI is scrollable on small screens
        admin_scroll = QScrollArea()
        admin_scroll.setWidgetResizable(True)
        admin_scroll.setWidget(central)
        self.setCentralWidget(admin_scroll)

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
        # load issue summary table
        try:
            self.load_issue_summary()
        except Exception:
            # non-fatal if loans table missing or other issue
            pass

    def show_lost_books(self):
        local_cur = connection.cursor()
        try :
            local_cur.execute("SELECT * FROM book WHERE status = 'lost'")
            data = local_cur.fetchall()
        finally:
            local_cur.close()
        if not data:
            self.tab.widget(0).layout().result_label.setText("No lost books found.")
            return
        out = []
        for r in data:
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
    def show_issued_books(self):
        local_cur = connection.cursor()
        try :
            local_cur.execute("SELECT * FROM book WHERE status = 'checked out'")
            data = local_cur.fetchall()
        finally:
            local_cur.close()
        if not data:
            self.tab.widget(0).layout().result_label.setText("No checked out books found.")
            return
        out = []
        for r in data:
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

    # ...existing code...
    def show_available_books(self):
        local_cur = connection.cursor()
        try:
            local_cur.execute("SELECT * FROM book WHERE status = 'available'")
            data = local_cur.fetchall()
        finally:
            local_cur.close()
        if not data:
            self.tab.widget(0).layout().result_label.setText("No available books found.")
            return
        out = []
        for r in data:
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
# ...existing code...

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

    def show_books(self) :
        local_cur = connection.cursor()
        try :
            local_cur.execute("SELECT * FROM book")
            data = local_cur.fetchall()
        finally :
            local_cur.close()

        if not data:
            self.tab.widget(0).layout().result_label.setText("No books found.")
            return

        out = []
        for r in data:
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

    def load_issue_summary(self):
        """Populate the admin issue summary table showing number of outstanding loans per client."""
        ensure_loans_table()
        cur = connection.cursor()
        try:                                                   
            cur.execute("UPDATE loans SET fine = CASE WHEN due_date IS NOT NULL AND returned_at IS NULL AND due_date < ? THEN CAST((JULIANDAY(?) - JULIANDAY(due_date)) AS INTEGER) * 1 ELSE 0 END", (datetime.now().isoformat(), datetime.now().isoformat()))
            cur.execute(
                "SELECT client_id, client_username, COUNT(*) as issued_count, fine FROM loans WHERE returned_at IS NULL GROUP BY client_id, client_username ORDER BY issued_count DESC"
            )
            rows = cur.fetchall()
        finally:
            cur.close()
        # also compute overdue counts per client (due_date < now and not returned)
        now_iso = datetime.now().isoformat()
        cur = connection.cursor()
        overdue_map = {}
        try:
            cur.execute(
                "SELECT client_id, client_username, COUNT(*) as overdue_count, fine FROM loans WHERE returned_at IS NULL AND due_date IS NOT NULL AND due_date < ? GROUP BY client_id, client_username",
                (now_iso,)
            )
            overdue_rows = cur.fetchall()
            for orow in overdue_rows:
                key = (orow['client_id'], orow['client_username'])
                overdue_map[key] = orow['overdue_count']
        finally:
            cur.close()

        cols = ['CLIENT', 'ISSUED_COUNT', 'OVERDUE', 'FINE']
        self.issue_table.setColumnCount(len(cols))
        self.issue_table.setHorizontalHeaderLabels(cols)
        self.issue_table.setRowCount(len(rows))
        for r_i, r in enumerate(rows):
            client = r['client_username'] if 'client_username' in r.keys() and r['client_username'] else (str(r['client_id']) if 'client_id' in r.keys() and r['client_id'] else 'unknown')
            count = r['issued_count'] if 'issued_count' in r.keys() else ''
            overdue = overdue_map.get((r['client_id'], r['client_username']), 0)
            self.issue_table.setItem(r_i, 0, QTableWidgetItem(str(client)))
            self.issue_table.setItem(r_i, 1, QTableWidgetItem(str(count)))
            self.issue_table.setItem(r_i, 2, QTableWidgetItem(str(overdue)))
            self.issue_table.setItem(r_i, 3, QTableWidgetItem(str(r['fine']) if 'fine' in r.keys() else '0'))

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
    def __init__(self, client_id=None, username="", parent=None):
        super().__init__(parent)
        # store client identity (may be None if unavailable)
        self.client_id = client_id
        self.username = username
        self.setWindowTitle(f"Client - {username}")
        self.resize(1200, 800)
        central = QWidget()
        layout = QVBoxLayout()
        self.tab = QTabWidget()
        layout.addWidget(self.tab)
        tab1_content = QWidget()
        tab1_layout = QVBoxLayout()
        tab1_content.setLayout(tab1_layout)
        tab1_layout.search_input = QLineEdit(self)
        tab1_layout.search_input.setPlaceholderText("Enter title, author, year or ISBN to search")
        tab1_layout.addWidget(tab1_layout.search_input)

        tab1_layout.search_button = QPushButton("SEARCH BOOK", self)
        tab1_layout.search_button.setStyleSheet("margin-top: 0px; margin-bottom: 5px;padding:10px; font-size:15px;")
        tab1_layout.show_all = QPushButton("SHOW ALL BOOKS", self)
        tab1_layout.show_all.setStyleSheet("margin-top: 0px; margin-bottom: 5px;padding:10px; font-size:15px;")
        tab1_layout.addWidget(tab1_layout.search_button)
        tab1_layout.addWidget(tab1_layout.show_all)
        # search results table for checkout
        self.search_table = QTableWidget()
        self.search_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.search_table.setSelectionMode(QTableWidget.SingleSelection)
        self.search_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tab1_layout.addWidget(self.search_table)

        # checkout button
        tab1_layout.checkout_btn = QPushButton("Check Out Selected")
        tab1_layout.checkout_btn.setStyleSheet("padding:8px; font-size:14px;")
        tab1_layout.addWidget(tab1_layout.checkout_btn)
        self.tab.addTab(tab1_content, "Search Books")

        # Create the My Loans tab for this client
        tab2_content = QWidget()
        tab2_layout = QVBoxLayout()
        tab2_content.setLayout(tab2_layout)
        tab2_layout.addWidget(QLabel("My Loans"))
        tab2_layout.refresh_btn = QPushButton("Refresh")
        tab2_layout.addWidget(tab2_layout.refresh_btn)

        self.my_loans_table = QTableWidget()
        self.my_loans_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.my_loans_table.setSelectionMode(QTableWidget.SingleSelection)
        self.my_loans_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tab2_layout.addWidget(self.my_loans_table)
        # ensure tables show scrollbars when content overflows
        self.my_loans_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.my_loans_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        tab2_layout.return_btn = QPushButton("Return Selected")
        tab2_layout.addWidget(tab2_layout.return_btn)
        self.tab.addTab(tab2_content, "My Loans")
        tab3_content = QWidget()
        tab3_layout = QVBoxLayout()
        tab3_content.setLayout(tab3_layout)
        tab3_layout.addWidget(QLabel("Profile Information"))
        local_cur = connection.cursor()
        try :
            local_cur.execute("SELECT * FROM client WHERE client_id = ?", (client_id,))
            connection.commit()
            row = local_cur.fetchone()
        finally :
            local_cur.close()
        tab3_layout.addWidget(QLabel(f"Username: {row['username'] if row and 'username' in row.keys() else ''}"))
        tab3_layout.addWidget(QLabel(f"Email: {row['email'] if row and 'email' in row.keys() else ''}"))
        tab3_layout.change_password_btn = QPushButton("Change Password")
        tab3_layout.addWidget(tab3_layout.change_password_btn)
        tab3_layout.change_password_btn.setStyleSheet("padding:15px; font-size:20px;margin-bottom:300px; margin-right:150px;margin-left:150px;")

        self.tab.addTab(tab3_content,"My Profile")

        # wire client search/checkout and loans buttons
        tab1_layout.search_button.clicked.connect(lambda: self.load_search_results(tab1_layout.search_input.text().strip()))
        tab1_layout.show_all.clicked.connect(lambda: self.load_search_results(''))
        tab1_layout.checkout_btn.clicked.connect(self.checkout_selected)
        tab2_layout.refresh_btn.clicked.connect(self.load_my_loans)
        tab2_layout.return_btn.clicked.connect(self.return_selected)
        tab3_layout.change_password_btn.clicked.connect(self.change_password)

        layout.addWidget(QLabel(f"Welcome Client: {username}"))
        central.setLayout(layout)
        # wrap client central widget in a scroll area so pages scroll on small windows
        client_scroll = QScrollArea()
        client_scroll.setWidgetResizable(True)
        client_scroll.setWidget(central)
        self.setCentralWidget(client_scroll)

    def change_password(self) :
        dlg = ChangePasswordDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            new_password = dlg.get_new_password()
        else:
            return
        local_cur = connection.cursor()
        try :
            local_cur.execute("UPDATE client SET password = ? WHERE client_id = ?",(str(new_password), str(self.client_id)))
            connection.commit()
        finally :
            local_cur.close()
        QMessageBox.information(self, "Password Changed", "Your password has been updated successfully.")

    def checkout_selected(self):
        # ensure loans table
        ensure_loans_table()
        # find selected book in search_table
        selected = self.search_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Select book", "Please select a book to check out.")
            return
        row_idx = selected[0].row()
        # assume first column is pk (id or isbn)
        pk_val = self.search_table.item(row_idx, 0).text()
        # get title
        title = self.search_table.item(row_idx, 1).text() if self.search_table.columnCount() > 1 else ''
        # determine client id/username stored on this window
        client_id = getattr(self, 'client_id', None)
        client_username = getattr(self, 'username', '')

        # check book availability
        cur = connection.cursor()
        try:
            cur.execute("SELECT * FROM book WHERE isbn = ? OR id = ?", (pk_val, pk_val))
            book_row = cur.fetchone()
        finally:
            cur.close()
        if book_row and 'status' in book_row.keys() and book_row['status'] == 'checked out':
            QMessageBox.warning(self, "Unavailable", "Book is already checked out.")
            return

        # enforce max loans per client
        cur = connection.cursor()
        try:
            if client_id is not None:
                cur.execute("SELECT COUNT(*) FROM loans WHERE client_id = ? AND returned_at IS NULL", (client_id,))
            else:
                cur.execute("SELECT COUNT(*) FROM loans WHERE client_username = ? AND returned_at IS NULL", (client_username,))
            out_count = cur.fetchone()[0]
        finally:
            cur.close()

        if out_count >= MAX_LOANS:
            QMessageBox.warning(self, "Limit reached", f"You already have {out_count} outstanding loans (max {MAX_LOANS}). Return some books before checking out more.")
            return

        # insert loan with due date and mark book checked out
        issued_at = datetime.now()
        due = (issued_at + timedelta(days=LOAN_DAYS)).isoformat()
        issued_at_iso = issued_at.isoformat()
        cur = connection.cursor()
        try:
            cur.execute(
                "INSERT INTO loans (client_id, client_username, book_pk, book_title, issued_at, due_date, returned_at) VALUES (?,?,?,?,?,?,NULL)",
                (client_id, client_username, pk_val, title, issued_at_iso, due),
            )
            cur.execute("UPDATE book SET status = 'checked out' WHERE isbn = ? OR id = ?", (pk_val, pk_val))
            connection.commit()
        finally:
            cur.close()

        QMessageBox.information(self, "Checked out", "Book checked out successfully.")
        # refresh my loans and search results
        self.load_my_loans()
        self.load_search_results(self.search_table.item(row_idx, 0).text())

    def load_my_loans(self):
        ensure_loans_table()
        cur = connection.cursor()
        try:
            if getattr(self, 'client_id', None) is not None:
                cur.execute("SELECT loan_id, book_pk, book_title, issued_at, due_date, returned_at FROM loans WHERE client_id = ? ORDER BY issued_at DESC", (self.client_id,))
            else:
                cur.execute("SELECT loan_id, book_pk, book_title, issued_at, due_date, returned_at FROM loans WHERE client_username = ? ORDER BY issued_at DESC", (getattr(self, 'username', ''),))
            rows = cur.fetchall()
        finally:
            cur.close()

        cols = ['LOAN_ID', 'BOOK', 'TITLE', 'ISSUED_AT', 'DUE_DATE', 'RETURNED_AT']
        self.my_loans_table.setColumnCount(len(cols))
        self.my_loans_table.setHorizontalHeaderLabels(cols)
        self.my_loans_table.setRowCount(len(rows))
        for r_i, r in enumerate(rows):
            self.my_loans_table.setItem(r_i, 0, QTableWidgetItem(str(r['loan_id'])))
            self.my_loans_table.setItem(r_i, 1, QTableWidgetItem(str(r['book_pk'])))
            self.my_loans_table.setItem(r_i, 2, QTableWidgetItem(str(r['book_title'])))
            self.my_loans_table.setItem(r_i, 3, QTableWidgetItem(str(r['issued_at'])))
            self.my_loans_table.setItem(r_i, 4, QTableWidgetItem(str(r['due_date'] or '')))
            self.my_loans_table.setItem(r_i, 5, QTableWidgetItem(str(r['returned_at'] or '')))

    def return_selected(self):
        selected = self.my_loans_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Select loan", "Please select a loan to return.")
            return
        row_idx = selected[0].row()
        loan_id = self.my_loans_table.item(row_idx, 0).text()
        book_pk = self.my_loans_table.item(row_idx, 1).text()
        now = datetime.now().isoformat()
        cur = connection.cursor()
        try:
            cur.execute("UPDATE loans SET returned_at = ? WHERE loan_id = ?", (now, loan_id))
            cur.execute("UPDATE book SET status = 'available' WHERE isbn = ? OR id = ?", (book_pk, book_pk))
            connection.commit()
        finally:
            cur.close()
        QMessageBox.information(self, "Returned", "Book marked as returned.")
        self.load_my_loans()

        # keep a reference to any opened child window so it doesn't get garbage collected
        self._child_window = None

    def _detect_book_columns_client(self):
        cur = connection.cursor()
        try:
            cur.execute("PRAGMA table_info(book)")
            cols = [row[1] for row in cur.fetchall()]
        finally:
            cur.close()
        preferred = ['id', 'title', 'author', 'status', 'rack_column_row', 'year', 'isbn']
        ordered = [c for c in preferred if c in cols]
        for c in cols:
            if c not in ordered:
                ordered.append(c)
        return ordered

    def load_search_results(self, filter_text=''):
        cols = self._detect_book_columns_client()
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

        self.search_table.setColumnCount(len(cols))
        self.search_table.setHorizontalHeaderLabels([c.upper() for c in cols])
        self.search_table.setRowCount(len(rows))
        for r_i, r in enumerate(rows):
            for c_i, col in enumerate(cols):
                val = r[col] if col in r.keys() else ''
                self.search_table.setItem(r_i, c_i, QTableWidgetItem(str(val) if val is not None else ''))

class ChangePasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Change Password")
        self.resize(300, 150)
        layout = QVBoxLayout()

        layout.addWidget(QLabel("New Password:"))
        self.new_password_edit = QLineEdit()
        self.new_password_edit.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.new_password_edit)

        layout.addWidget(QLabel("Confirm Password:"))
        self.confirm_password_edit = QLineEdit()
        self.confirm_password_edit.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.confirm_password_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def accept(self):
        new_pass = self.new_password_edit.text()
        confirm_pass = self.confirm_password_edit.text()
        if not new_pass:
            QMessageBox.warning(self, "Validation", "New password cannot be empty.")
            return
        if new_pass != confirm_pass:
            QMessageBox.warning(self, "Validation", "Passwords do not match.")
            return
        super().accept()

    def get_new_password(self):
        return self.new_password_edit.text()
        
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


