from PyQt5.QtWidgets import (
    QMainWindow, QSplitter
)

from app_constants import *  # noqa
from catalog import *
from smiles_fetch import *

# Optional PDF export:
try:
    from fpdf import FPDF
except ImportError:
    FPDF = None


class CustomListWidget(QListWidget):

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window

    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())
        if item:
            menu = QMenu(self)
            renameAction = menu.addAction("Rename Catalog")
            deleteAction = menu.addAction("Delete Catalog")
            action = menu.exec_(self.mapToGlobal(event.pos()))

            if action == renameAction:
                self.rename_catalog(item)
            elif action == deleteAction:
                reply = QMessageBox.question(self, "Delete Catalog",
                                             f"Are you sure you want to permanently delete catalog '{item.text()}'?",
                                             QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    catalog_name = item.text()
                    if catalog_name in self.main_window.catalog_files:
                        path = self.main_window.catalog_files[catalog_name]
                        try:
                            if os.path.exists(path):
                                os.remove(path)
                            del self.main_window.catalog_files[catalog_name]
                            if catalog_name in self.main_window.open_catalog_tabs:
                                widget = self.main_window.open_catalog_tabs[catalog_name]
                                idx = self.main_window.tabWidget.indexOf(widget)
                                self.main_window.tabWidget.removeTab(idx)
                                del self.main_window.open_catalog_tabs[catalog_name]
                            self.takeItem(self.row(item))
                        except Exception as e:
                            QMessageBox.critical(self, "Error", f"Error deleting catalog: {e}")
        else:
            super().contextMenuEvent(event)

    def rename_catalog(self, item):
        old_name = item.text()
        new_name, ok = QInputDialog.getText(
            self, "Rename Catalog",
            "Enter new catalog name:",
            QLineEdit.Normal,
            old_name
        )

        if ok and new_name and new_name != old_name:
            if new_name in self.main_window.catalog_files:
                QMessageBox.warning(self, "Error", "A catalog with this name already exists.")
                return

            try:
                old_path = self.main_window.catalog_files[old_name]
                new_path = os.path.join(os.path.dirname(old_path), f"{new_name}.json")

                # Rename the file
                os.rename(old_path, new_path)

                # Update references in main window
                self.main_window.catalog_files[new_name] = new_path
                del self.main_window.catalog_files[old_name]

                if old_name in self.main_window.open_catalog_tabs:
                    widget = self.main_window.open_catalog_tabs[old_name]
                    self.main_window.open_catalog_tabs[new_name] = widget
                    del self.main_window.open_catalog_tabs[old_name]
                    widget.catalog_name = new_name
                    idx = self.main_window.tabWidget.indexOf(widget)
                    self.main_window.tabWidget.setTabText(idx, new_name)

                # Update the item text
                item.setText(new_name)

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error renaming catalog: {e}")

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chemical Catalog Manager")
        self.resize(1200, 800)
        self.catalog_files = {}  # catalog name -> file path
        self.open_catalog_tabs = {}  # catalog name -> CatalogWidget
        self.controller = None
        self.initUI()
        self.load_existing_catalogs()

    def initUI(self):
        splitter = QSplitter(Qt.Horizontal)
        self.sidebar = QWidget()
        sb_layout = QVBoxLayout(self.sidebar)
        self.btnNewCatalog = QPushButton("New Catalog")
        self.btnNewCatalog.clicked.connect(lambda: self.create_new_catalog())  # Changed this line
        sb_layout.addWidget(self.btnNewCatalog)
        self.listCatalogs = CustomListWidget(self)
        self.listCatalogs.itemDoubleClicked.connect(self.open_catalog_tab)
        sb_layout.addWidget(self.listCatalogs)
        sb_layout.addStretch()
        splitter.addWidget(self.sidebar)
        self.tabWidget = QtWidgets.QTabWidget()
        splitter.addWidget(self.tabWidget)
        splitter.setStretchFactor(1, 4)
        self.setCentralWidget(splitter)

    def set_controller(self, controller):
        self.controller = controller

    def create_new_catalog(self):
        self.controller.create_new_catalog()

    def open_catalog_tab(self, item):
        self.controller.open_catalog_tab(item)

    def load_existing_catalogs(self):
        if not os.path.exists(CATALOGS_FOLDER):
            os.makedirs(CATALOGS_FOLDER)
        for fname in os.listdir(CATALOGS_FOLDER):
            if fname.lower().endswith(".json"):
                name = os.path.splitext(fname)[0]
                path = os.path.join(CATALOGS_FOLDER, fname)
                self.catalog_files[name] = path
                self.listCatalogs.addItem(name)

    def open_catalog(self, name, path, df):
        widget = CatalogWidget(name, path, df)
        self.tabWidget.addTab(widget, name)
        self.tabWidget.setCurrentWidget(widget)
        self.open_catalog_tabs[name] = widget

    def closeEvent(self, event):
        for widget in self.open_catalog_tabs.values():
            widget.save_catalog(silent=True)
        event.accept()


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    model = CatalogModel()
    view = MainWindow()
    controller = CatalogController(model, view)
    view.show()
    sys.exit(app.exec_())
