import concurrent.futures
import json
import os
import time
from datetime import datetime
from io import StringIO

import pandas as pd
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
    QInputDialog, QMenu, QListWidget, QListWidgetItem, QDialog, QDialogButtonBox,
    QTextEdit, QComboBox, QCheckBox, QSplitter, QPushButton, QStackedWidget
)

from chemistry_functions import *
from smiles_fetch import *

# Optional PDF export:
try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

REMOVE_COLUMNS = {"Supplier Code", "Lab (Shelf)", "Label", "H", "UUID"}
CATALOGS_FOLDER = "catalogs"  # All catalogs are stored here

DEFAULT_COLS = ["NAME", "CAS", "SMILES", "Formula", "Category", "Date Added", "Detail"]


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


class ClickableLabel(QtWidgets.QLabel):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class CustomTableWidget(QTableWidget):
    deleteRowRequested = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            self.deleteRowRequested.emit()
        else:
            super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        deleteAction = menu.addAction("Delete Selected Row(s)")
        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == deleteAction:
            self.deleteRowRequested.emit()


class EditableHeaderView(QHeaderView):
    def __init__(self, orientation, parent=None, delete_callback=None):
        super().__init__(orientation, parent)
        self.delete_callback = delete_callback
        self.setSectionsClickable(True)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        index = self.logicalIndexAt(event.pos())
        if index >= 0:
            current = self.model().headerData(index, self.orientation(), Qt.DisplayRole)
            new_text, ok = QInputDialog.getText(self, "Edit Header", "New header name:", text=str(current))
            if ok:
                self.model().setHeaderData(index, self.orientation(), new_text)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        index = self.logicalIndexAt(event.pos())
        if index >= 0 and self.delete_callback:
            menu = QMenu(self)
            deleteAction = menu.addAction("Delete Column")
            action = menu.exec_(self.mapToGlobal(event.pos()))
            if action == deleteAction:
                reply = QMessageBox.question(self, "Delete Column",
                                             f"Are you sure you want to permanently delete column '{self.model().headerData(index, self.orientation())}'?",
                                             QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.delete_callback(index)
        else:
            super().contextMenuEvent(event)


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

# noinspection PyUnresolvedReferences
class CatalogWidget(QWidget):
    def __init__(self, catalog_name, file_path, data=None, parent=None):
        super().__init__(parent)
        self.catalog_name = catalog_name
        self.file_path = file_path
        default_cols = DEFAULT_COLS
        if data is None or data.empty:
            self.data = pd.DataFrame(columns=default_cols)
        else:
            self.data = data.copy()
            for col in default_cols:
                if col not in self.data.columns:
                    self.data[col] = ""
        if "Details" in self.data.columns:
            self.data.drop(columns=["Details"], inplace=True)
        if "Detail" not in self.data.columns:
            self.data["Detail"] = ""
        if "Supplier" in self.data.columns:
            self.data["Detail"] = "Supplier: " + self.data["Supplier"].astype(str)
            self.data.drop(columns=["Supplier"], inplace=True)
        if "SMILES" in self.data.columns:
            self.data["SMILES"] = self.data.apply(
                lambda r: r["SMILES"] if r["SMILES"] != "" else get_smiles(r.get("NAME"), r.get("CAS")),
                axis=1
            )

            def update_formula(row):
                if pd.notnull(row.get("Formula")) and str(row.get("Formula")).strip() != "":
                    return row["Formula"]
                else:
                    s = row.get("SMILES")
                    if s and isinstance(s, str):
                        return calculate_formula(s) or ""
                    else:
                        return ""

            self.data["Formula"] = self.data.apply(update_formula, axis=1)
            self.data["Category"] = self.data["SMILES"].apply(
                lambda s: categorize_molecule(s) if s and isinstance(s, str) else []
            )
            self.data["StructureImage"] = self.data["SMILES"].apply(
                lambda s: generate_structure_image(s) if s and isinstance(s, str) else None
            )
        self.last_sorted_column = None
        self.last_sort_order = True
        self._updating_table = False
        self.initUI()
        self.populate_views()

    def initUI(self):
        self.layout = QVBoxLayout(self)
        # Filtering Panel.
        filterLayout = QHBoxLayout()
        filterLayout.addWidget(QLabel("Search:"))
        self.searchEdit = QLineEdit()
        self.searchEdit.textChanged.connect(self.filter_view)
        filterLayout.addWidget(self.searchEdit)
        filterLayout.addWidget(QLabel("Category:"))
        self.categoryCombo = QComboBox()
        subcats = sorted(list(CATEGORY_SMARTS.keys())) + ["Containing Br", "Containing Cl", "Containing F",
                                                          "Containing I", "Boronic acids/esters"]
        self.categoryCombo.addItem("All")
        for sub in subcats:
            self.categoryCombo.addItem(sub)
        self.categoryCombo.currentIndexChanged.connect(self.filter_view)
        filterLayout.addWidget(self.categoryCombo)
        self.orgCheckbox = QCheckBox("Organic")
        self.orgCheckbox.setChecked(True)
        self.orgCheckbox.stateChanged.connect(self.major_checkbox_changed)
        self.inorgCheckbox = QCheckBox("Inorganic")
        self.inorgCheckbox.stateChanged.connect(self.major_checkbox_changed)
        self.allMajorCheckbox = QCheckBox("All (Organic + Inorganic)")
        self.allMajorCheckbox.stateChanged.connect(self.major_checkbox_changed)
        filterLayout.addWidget(QLabel("Major Type:"))
        filterLayout.addWidget(self.orgCheckbox)
        filterLayout.addWidget(self.inorgCheckbox)
        filterLayout.addWidget(self.allMajorCheckbox)
        self.altViewCheckbox = QCheckBox("Alternate View")
        self.altViewCheckbox.stateChanged.connect(self.toggle_alt_view)
        filterLayout.addWidget(self.altViewCheckbox)
        filterLayout.addStretch()
        self.layout.addLayout(filterLayout)

        # Toolbar for catalog actions.
        toolbarLayout = QHBoxLayout()
        self.btnAddColumn = QPushButton("Add Column")
        self.btnAddColumn.clicked.connect(self.add_column)
        self.btnImportCSV = QPushButton("Import CSV")
        self.btnImportCSV.clicked.connect(self.import_csv)
        self.btnAddCAS = QPushButton("Add by CAS")
        self.btnAddCAS.clicked.connect(self.add_by_cas)
        self.btnSaveCatalog = QPushButton("Save Catalog")
        self.btnSaveCatalog.clicked.connect(lambda: self.save_catalog(silent=True))
        self.btnExportCatalog = QPushButton("Export Catalog")
        self.btnExportCatalog.clicked.connect(self.export_catalog)
        toolbarLayout.addWidget(self.btnAddColumn)
        toolbarLayout.addWidget(self.btnImportCSV)
        toolbarLayout.addWidget(self.btnAddCAS)
        toolbarLayout.addWidget(self.btnSaveCatalog)
        toolbarLayout.addWidget(self.btnExportCatalog)
        toolbarLayout.addStretch()
        self.layout.addLayout(toolbarLayout)

        # Stacked view for Table and Grid.
        self.viewStack = QStackedWidget()
        self.table = CustomTableWidget()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        header = EditableHeaderView(Qt.Horizontal, self.table, self.delete_column_by_index)
        self.table.setHorizontalHeader(header)
        self.table.deleteRowRequested.connect(self.delete_selected_rows)
        self.table.horizontalHeader().sectionClicked.connect(self.sort_by_column)
        self.table.itemChanged.connect(self.on_item_changed)
        self.viewStack.addWidget(self.table)
        self.gridView = QListWidget()
        self.gridView.setViewMode(QListWidget.IconMode)
        self.gridView.setIconSize(QSize(150, 150))
        self.gridView.setSpacing(10)
        self.gridView.setResizeMode(QListWidget.Adjust)
        self.gridView.setStyleSheet("QListWidget::item { border: 1px solid gray; margin: 5px; }")
        self.gridView.itemDoubleClicked.connect(self.show_compound_detail)
        self.viewStack.addWidget(self.gridView)
        self.viewStack.setCurrentIndex(0)
        self.layout.addWidget(self.viewStack)

    def populate_views(self):
        self._updating_table = True
        self.table.blockSignals(True)
        self.populate_table()
        self.populate_grid_view()
        self.table.blockSignals(False)
        self._updating_table = False
        self.filter_view()

    def populate_table(self):
        self.table.clear()
        cols = [col for col in self.data.columns if col != "StructureImage"]
        if "Structure" not in cols:
            cols.append("Structure")
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setRowCount(len(self.data))
        for i, (_, row) in enumerate(self.data.iterrows()):
            row_dict = row.to_dict()
            for j, col in enumerate(cols):
                if col == "Structure":
                    smiles = row.get("SMILES", "")
                    pixmap = row.get("StructureImage") if pd.notna(
                        row.get("StructureImage")) else generate_structure_image(smiles)
                    if pixmap:
                        lbl = ClickableLabel()
                        # Scale image to 150x150 so that it fits comfortably
                        lbl.setPixmap(pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                        lbl.setAlignment(Qt.AlignCenter)
                        details = "\n".join(f"{k}: {v}" for k, v in row_dict.items() if k != "StructureImage")
                        lbl.setToolTip(details)
                        lbl.clicked.connect(lambda pix=pixmap: self.show_enlarged_image(pix))
                        self.table.setCellWidget(i, j, lbl)
                    else:
                        item = QTableWidgetItem("N/A")
                        item.setTextAlignment(Qt.AlignCenter)
                        self.table.setItem(i, j, item)
                else:
                    val = row_dict.get(col, "")
                    item = QTableWidgetItem(str(val))
                    item.setTextAlignment(Qt.AlignCenter)
                    if j == 0:
                        item.setData(Qt.UserRole, row_dict)
                    self.table.setItem(i, j, item)
            self.table.setRowHeight(i, 160)
        # Adjust column widths per our specifications.
        for i in range(self.table.columnCount()):
            colName = self.table.horizontalHeaderItem(i).text()
            if colName == "NAME":
                self.table.setColumnWidth(i, 200)
            elif colName == "CAS":
                self.table.setColumnWidth(i, 140)
            elif colName == "SMILES":
                self.table.setColumnWidth(i, 150)
            elif colName == "Formula":
                self.table.setColumnWidth(i, 150)
            elif colName == "Category":
                # Hide the Category column but retain functionality.
                self.table.hideColumn(i)
            elif colName == "Date Added":
                self.table.setColumnWidth(i, 140)
            elif colName == "Detail":
                self.table.setColumnWidth(i, 140)
            elif colName == "Structure":
                self.table.setColumnWidth(i, 320)

    def populate_grid_view(self):
        self.gridView.clear()
        if self.data.empty:
            return
        for _, row in self.data.iterrows():
            pixmap = row.get("StructureImage")
            if pixmap:
                item = QListWidgetItem()
                item.setIcon(QIcon(pixmap))
                item.setText("")
                details = "\n".join(f"{k}: {v}" for k, v in row.to_dict().items() if k != "StructureImage")
                item.setToolTip(details)
                item.setData(Qt.UserRole, row.to_dict())
                self.gridView.addItem(item)

    def row_passes_filter(self, row_data, search_text, sel_cat, major_filter):
        if search_text:
            if not any(search_text in str(val).lower() for key, val in row_data.items() if key != "StructureImage"):
                return False
        cats = row_data.get("Category", [])
        if isinstance(cats, str):
            cats = [x.strip() for x in cats.split(",")]
        if sel_cat != "All" and sel_cat not in cats:
            return False
        if major_filter != "All" and major_filter not in cats:
            return False
        return True

    def filter_view(self):
        search_text = self.searchEdit.text().lower()
        sel_cat = self.categoryCombo.currentText()
        if self.allMajorCheckbox.isChecked():
            major_filter = "All"
        elif self.orgCheckbox.isChecked():
            major_filter = "Organic"
        elif self.inorgCheckbox.isChecked():
            major_filter = "Inorganic"
        else:
            major_filter = "Organic"
        if self.viewStack.currentIndex() == 0:
            for i in range(self.table.rowCount()):
                item = self.table.item(i, 0)
                row_data = item.data(Qt.UserRole) if item is not None else {}
                visible = self.row_passes_filter(row_data, search_text, sel_cat, major_filter)
                self.table.setRowHidden(i, not visible)
        else:
            for i in range(self.gridView.count()):
                item = self.gridView.item(i)
                row_data = item.data(Qt.UserRole)
                visible = self.row_passes_filter(row_data, search_text, sel_cat, major_filter)
                item.setHidden(not visible)

    def major_checkbox_changed(self, state):
        if state == Qt.Checked:
            sender = self.sender()
            if sender == self.orgCheckbox:
                self.inorgCheckbox.blockSignals(True)
                self.allMajorCheckbox.blockSignals(True)
                self.inorgCheckbox.setChecked(False)
                self.allMajorCheckbox.setChecked(False)
                self.inorgCheckbox.blockSignals(False)
                self.allMajorCheckbox.blockSignals(False)
            elif sender == self.inorgCheckbox:
                self.orgCheckbox.blockSignals(True)
                self.allMajorCheckbox.blockSignals(True)
                self.orgCheckbox.setChecked(False)
                self.allMajorCheckbox.setChecked(False)
                self.orgCheckbox.blockSignals(False)
                self.allMajorCheckbox.blockSignals(False)
            elif sender == self.allMajorCheckbox:
                self.orgCheckbox.blockSignals(True)
                self.inorgCheckbox.blockSignals(True)
                self.orgCheckbox.setChecked(False)
                self.inorgCheckbox.setChecked(False)
                self.orgCheckbox.blockSignals(False)
                self.inorgCheckbox.blockSignals(False)
        self.filter_view()

    def toggle_alt_view(self, state):
        if state == Qt.Checked:
            self.viewStack.setCurrentIndex(1)
        else:
            self.viewStack.setCurrentIndex(0)
        self.filter_view()

    def add_column(self):
        col_name, ok = QInputDialog.getText(self, "Add Column", "Enter new column name:")
        if ok and col_name:
            if col_name in self.data.columns:
                QMessageBox.information(self, "Info", f"Column '{col_name}' already exists.")
                return
            self.data[col_name] = ""
            self.populate_views()
            self.save_catalog(silent=True)

    def delete_selected_rows(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return
        reply = QMessageBox.question(self, "Delete Row(s)",
                                     "Are you sure you want to permanently delete the selected row(s)?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            rows = sorted([index.row() for index in selected], reverse=True)
            self.data.drop(self.data.index[rows], inplace=True)
            self.data.reset_index(drop=True, inplace=True)
            self.populate_views()
            self.save_catalog(silent=True)

    def delete_column_by_index(self, idx):
        col_name = self.table.horizontalHeaderItem(idx).text()
        if col_name in DEFAULT_COLS:
            QMessageBox.information(self, "Info", f"Column '{col_name}' cannot be deleted.")
            return
        reply = QMessageBox.question(self, "Delete Column",
                                     f"Are you sure you want to permanently delete the column '{col_name}'?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.data.drop(columns=[col_name], inplace=True)
            self.populate_views()
            self.save_catalog(silent=True)

    def import_csv(self):
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileName(self, "Import CSV", "", "CSV Files (*.csv);;All Files (*)",
                                                  options=options)
        if fileName:
            try:
                df = pd.read_csv(fileName)
                df = df.drop(columns=[c for c in REMOVE_COLUMNS if c in df.columns], errors='ignore')
                for col in ["NAME", "CAS", "SMILES"]:
                    if col not in df.columns:
                        df[col] = ""
                df["SMILES"] = df.apply(
                    lambda r: r["SMILES"] if r["SMILES"] != "" else get_smiles(r.get("NAME"), r.get("CAS")), axis=1)

                def update_formula(row):
                    if pd.notnull(row.get("Formula")) and str(row.get("Formula")).strip() != "":
                        return row["Formula"]
                    else:
                        s = row.get("SMILES")
                        if s and isinstance(s, str):
                            return calculate_formula(s) or ""
                        else:
                            return ""

                df["Formula"] = df.apply(update_formula, axis=1)
                df["Category"] = df["SMILES"].apply(
                    lambda s: categorize_molecule(s) if s and isinstance(s, str) else [])
                df["StructureImage"] = df["SMILES"].apply(
                    lambda s: generate_structure_image(s) if s and isinstance(s, str) else None)
                if "Date Added" not in df.columns:
                    df["Date Added"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if "Detail" not in df.columns:
                    df["Detail"] = ""
                self.data = pd.concat([self.data, df], ignore_index=True)
                self.populate_views()
                self.save_catalog(silent=True)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error importing CSV: {e}")

    def add_by_cas(self):
        text, ok = QInputDialog.getMultiLineText(self, "Add by CAS",
                                                 "Enter one or more CAS numbers (space/newline separated):")
        if ok and text:
            cas_list = [cas.strip() for cas in text.split() if cas.strip()]

            if not cas_list:
                QMessageBox.warning(self, "Invalid Input", "No valid CAS numbers provided.")
                return

            new_rows = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                future_to_cas = {executor.submit(fetch_compound_info_by_cas, cas): cas for cas in cas_list}
                for future in concurrent.futures.as_completed(future_to_cas):
                    result = future.result()
                    if result:
                        result["Date Added"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        result["Detail"] = ""
                        new_rows.append(result)
                    else:
                        QMessageBox.warning(self, "CAS Error",
                                            f"Could not retrieve data for CAS: {future_to_cas[future]}")

            if new_rows:
                new_df = pd.DataFrame(new_rows)
                for col in ["NAME", "CAS", "SMILES", "Formula", "Category", "StructureImage", "Date Added", "Detail"]:
                    if col not in new_df.columns:
                        new_df[col] = ""
                self.data = pd.concat([self.data, new_df], ignore_index=True)
                self.populate_views()
                self.save_catalog(silent=True)

    def export_catalog(self):
        options = ["CSV", "Excel", "PDF"]
        export_type, ok = QInputDialog.getItem(self, "Export Catalog", "Choose export format:", options, 0, False)
        if not ok:
            return
        file_dialog = QFileDialog(self)
        if export_type == "CSV":
            fileName, _ = file_dialog.getSaveFileName(self, "Export to CSV", "", "CSV Files (*.csv)")
            if fileName:
                try:
                    self.data.to_csv(fileName, index=False)
                    QMessageBox.information(self, "Exported", "Catalog exported successfully!")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Error exporting CSV: {e}")
        elif export_type == "Excel":
            fileName, _ = file_dialog.getSaveFileName(self, "Export to Excel", "", "Excel Files (*.xlsx)")
            if fileName:
                try:
                    self.data.to_excel(fileName, index=False)
                    QMessageBox.information(self, "Exported", "Catalog exported successfully!")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Error exporting Excel: {e}")
        elif export_type == "PDF":
            if not FPDF:
                QMessageBox.critical(self, "Error", "FPDF library is required for PDF export.")
                return
            fileName, _ = file_dialog.getSaveFileName(self, "Export to PDF", "", "PDF Files (*.pdf)")
            if fileName:
                try:
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", size=12)
                    cols = list(self.data.columns)
                    for col in cols:
                        pdf.cell(40, 10, str(col), border=1)
                    pdf.ln()
                    for _, row in self.data.iterrows():
                        for col in cols:
                            pdf.cell(40, 10, str(row[col]), border=1)
                        pdf.ln()
                    pdf.output(fileName)
                    QMessageBox.information(self, "Exported", "Catalog exported successfully!")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Error exporting PDF: {e}")

    def save_catalog(self, silent=True):
        try:
            self.data.to_json(self.file_path, orient="records", indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save catalog: {e}")

    def show_enlarged_image(self, pixmap):
        dlg = QDialog(self)
        dlg.setWindowTitle("Enlarged Image")
        vbox = QVBoxLayout(dlg)
        lbl = QLabel()
        lbl.setPixmap(pixmap.scaledToWidth(400, Qt.SmoothTransformation))
        vbox.addWidget(lbl)
        btnBox = QDialogButtonBox(QDialogButtonBox.Close)
        btnBox.rejected.connect(dlg.reject)
        vbox.addWidget(btnBox)
        dlg.exec_()

    def show_compound_detail(self, item):
        data = item.data(Qt.UserRole)
        if data:
            dlg = QDialog(self)
            dlg.setWindowTitle(data.get("NAME", "Compound Detail"))
            vbox = QVBoxLayout(dlg)
            details = "\n".join(f"- {k}: {v}" for k, v in data.items() if k != "StructureImage")
            txt = QTextEdit()
            txt.setReadOnly(True)
            txt.setText(details)
            vbox.addWidget(txt)
            btnBox = QDialogButtonBox(QDialogButtonBox.Close)
            btnBox.rejected.connect(dlg.reject)
            vbox.addWidget(btnBox)
            dlg.exec_()

    def sort_by_column(self, logicalIndex):
        cols = [col for col in self.data.columns if col != "StructureImage"]
        if "Structure" not in cols:
            cols.append("Structure")
        if logicalIndex >= len(cols):
            return
        column_clicked = cols[logicalIndex]
        sort_col = "SMILES" if column_clicked == "Structure" else column_clicked
        ascending = True if self.last_sorted_column != sort_col else not self.last_sort_order
        self.last_sorted_column = sort_col
        self.last_sort_order = ascending
        try:
            if sort_col == "NAME":
                self.data["__sort_key__"] = self.data["NAME"].astype(str).str.lower()
                self.data.sort_values(by="__sort_key__", inplace=True, ascending=ascending, kind='mergesort')
                self.data.drop(columns=["__sort_key__"], inplace=True)
            else:
                self.data.sort_values(by=sort_col, inplace=True, ascending=ascending, kind='mergesort')
        except Exception as e:
            print(f"Error sorting by {sort_col}: {e}")
            return
        self.data.reset_index(drop=True, inplace=True)
        self.populate_views()

    def on_item_changed(self, item):
        if self._updating_table:
            return
        row = item.row()
        if row >= len(self.data):
            return
        col = item.column()
        header_item = self.table.horizontalHeaderItem(col)
        if not header_item:
            return
        col_name = header_item.text()
        if col_name not in self.data.columns:
            return
        new_value = item.text()
        try:
            self.data.at[row, col_name] = new_value
            first_item = self.table.item(row, 0)
            if first_item:
                first_item.setData(Qt.UserRole, self.data.iloc[row].to_dict())
        except Exception as e:
            print(f"Error updating data from table: {e}")


class DataLoaderThread(QThread):
    finished = pyqtSignal(pd.DataFrame)
    error = pyqtSignal(str)
    started_signal = pyqtSignal()

    def __init__(self, filename, is_csv=True, parent=None):
        super().__init__(parent)
        self.filename = filename
        self.is_csv = is_csv

    def run(self):
        try:
            self.started_signal.emit()
            if self.is_csv:
                df = pd.read_csv(self.filename)
                df = df.drop(columns=[c for c in REMOVE_COLUMNS if c in df.columns], errors='ignore')
                for col in ["NAME", "CAS", "SMILES"]:
                    if col not in df.columns:
                        df[col] = ""
                df["SMILES"] = df.apply(
                    lambda r: r["SMILES"] if r["SMILES"] != "" else get_smiles(r.get("NAME"), r.get("CAS")), axis=1)

                def update_formula(row):
                    if pd.notnull(row.get("Formula")) and str(row.get("Formula")).strip() != "":
                        return row["Formula"]
                    else:
                        s = row.get("SMILES")
                        if s and isinstance(s, str):
                            return calculate_formula(s) or ""
                        else:
                            return ""

                df["Formula"] = df.apply(update_formula, axis=1)
                df["Category"] = df["SMILES"].apply(
                    lambda s: categorize_molecule(s) if s and isinstance(s, str) else [])
                df["StructureImage"] = df["SMILES"].apply(
                    lambda s: generate_structure_image(s) if s and isinstance(s, str) else None)
                if "Date Added" not in df.columns:
                    df["Date Added"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if "Detail" not in df.columns:
                    df["Detail"] = ""
            else:
                with open(self.filename, "r") as f:
                    data_loaded = json.load(f)
                df = pd.read_json(StringIO(json.dumps(data_loaded)), orient="records")
                for col in ["NAME", "CAS", "SMILES"]:
                    if col not in df.columns:
                        df[col] = ""
                df["Category"] = df["SMILES"].apply(
                    lambda s: categorize_molecule(s) if s and isinstance(s, str) else [])
                df["StructureImage"] = df["SMILES"].apply(
                    lambda s: generate_structure_image(s) if s and isinstance(s, str) else None)
            self.finished.emit(df)
        except Exception as e:
            self.error.emit(f"Error loading data: {e}")


class CatalogModel:
    def __init__(self):
        self.catalog_files = {}  # catalog name -> file path
        self.load_existing_catalogs()

    def load_existing_catalogs(self):
        if not os.path.exists(CATALOGS_FOLDER):
            os.makedirs(CATALOGS_FOLDER)
        for fname in os.listdir(CATALOGS_FOLDER):
            if fname.lower().endswith(".json"):
                name = os.path.splitext(fname)[0]
                path = os.path.join(CATALOGS_FOLDER, fname)
                self.catalog_files[name] = path

    def create_new_catalog(self, name):
        path = os.path.join(CATALOGS_FOLDER, f"{name}.json")
        df = pd.DataFrame(columns=["NAME", "CAS", "SMILES", "Formula", "Category", "Date Added", "Detail"])
        df.to_json(path, orient="records", indent=2)
        self.catalog_files[name] = path
        return path, df

    def load_catalog(self, name):
        path = self.catalog_files.get(name)
        if path and os.path.exists(path):
            try:
                df = pd.read_json(path, orient="records")
                if df.empty:
                    df = pd.DataFrame(columns=["NAME", "CAS", "SMILES", "Formula", "Category", "Date Added", "Detail"])
            except Exception:
                df = pd.DataFrame(columns=["NAME", "CAS", "SMILES", "Formula", "Category", "Date Added", "Detail"])
        else:
            df = pd.DataFrame(columns=["NAME", "CAS", "SMILES", "Formula", "Category", "Date Added", "Detail"])
        return path, df


class CatalogController:
    def __init__(self, model, view):
        self.model = model
        self.view = view
        self.view.set_controller(self)

    def create_new_catalog(self):
        name, ok = QInputDialog.getText(self.view, "New Catalog", "Enter a name for the new catalog:")
        if ok and name:
            try:
                path, df = self.model.create_new_catalog(name)
                self.view.catalog_files[name] = path
                self.view.listCatalogs.addItem(name)
                self.view.open_catalog(name, path, df)
            except Exception as e:
                QMessageBox.critical(self.view, "Error", f"Could not create catalog: {e}")

    def open_catalog_tab(self, item):
        name = item.text()
        if name in self.view.open_catalog_tabs:
            idx = self.view.tabWidget.indexOf(self.view.open_catalog_tabs[name])
            self.view.tabWidget.setCurrentIndex(idx)
        else:
            path, df = self.model.load_catalog(name)
            self.view.open_catalog(name, path, df)


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


# Usage
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    model = CatalogModel()
    view = MainWindow()
    controller = CatalogController(model, view)
    view.show()
    sys.exit(app.exec_())
