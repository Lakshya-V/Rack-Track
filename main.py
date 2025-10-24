import sys
from PyQt5.QtWidgets import QApplication
from ui import MainWindow

sys.argv += ['-platform', 'windows:darkmode=2']

app = QApplication(sys.argv)
app.setStyle("Fusion")
window = MainWindow()
window.showMaximized()

app.exec()