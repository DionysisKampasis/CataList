import time

from PyQt5.QtWidgets import (
    QMainWindow, QSplitter
)

from app_constants import *  # noqa
from catalog import *
from chemistry_functions import *
from smiles_fetch import *

# Optional PDF export:
try:
    from fpdf import FPDF
except ImportError:
    FPDF = None


def timer_function(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        res = func(*args, **kwargs)
        end = time.time()
        print(f"[TIMING] {func.__name__} took {end - start:.4f} sec.")
        return res

    return wrapper


def fetch_compound_info_by_cas(cas):
    try:
        compounds = pcp.get_compounds(cas, 'name')
        if compounds:
            comp = compounds[0]
            if hasattr(comp, "iupac_name") and comp.iupac_name:
                name = comp.iupac_name
            elif comp.synonyms:
                name = comp.synonyms[0]
            else:
                name = "N/A"
            smiles = get_smiles(name, cas)

            # Only calculate formula if missing; if CSV supplies it, it'll be preserved.
            def update_formula(row):
                if pd.notnull(row.get("Formula")) and str(row.get("Formula")).strip() != "":
                    return row["Formula"]
                else:
                    s = row.get("SMILES")
                    if s and isinstance(s, str):
                        return calculate_formula(s) or ""
                    else:
                        return ""

            formula = ""  # We'll update in CatalogWidget if needed.
            structure_image = generate_structure_image(smiles) if smiles else None
            return {"NAME": name, "CAS": cas, "SMILES": smiles,
                    "Formula": formula, "Category": categorize_molecule(smiles),
                    "StructureImage": structure_image,
                    "Date Added": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Detail": ""}
        else:
            print(f"PubChem did not return any compound for CAS {cas}")
            return None
    except Exception as e:
        print(f"Error retrieving compound info for CAS {cas}: {e}")
        return None


class CustomListWidget(QListWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window

    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())
        if item:
            menu = QMenu(self)
            deleteAction = menu.addAction("Delete Catalog")
            action = menu.exec_(self.mapToGlobal(event.pos()))
            if action == deleteAction:
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
        self.btnNewCatalog.clicked.connect(self.create_new_catalog)
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
