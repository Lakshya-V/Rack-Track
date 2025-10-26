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
        admin_btn.setStyleSheet("background-color: green; font-size: 16px; padding: 22px; margin-bottom: 15px; margin-right:80px; margin-left:80px; margin-top:10px")
        client_btn = QPushButton("CLIENT")
        client_btn.setStyleSheet("background-color: blue; font-size: 16px; padding: 25px; margin-bottom: 50px; margin-right:80px; margin-left:80px; margin-top:10px")
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


