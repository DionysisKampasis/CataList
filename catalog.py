import concurrent.futures
import os

import numpy as np
import pandas as pd
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QMenu,
    QLabel, QTableWidgetItem, QHeaderView, QInputDialog, QListWidget, QListWidgetItem, QDialog, QDialogButtonBox,
    QTextEdit, QComboBox, QCheckBox, QPushButton, QStackedWidget, QTableWidget
)

from app_constants import *  # noqa
from image_conversions import *
from smiles_fetch import *


class CatalogWidget(QWidget):

    def __init__(self, catalog_name, file_path, data=None, parent=None):
        super().__init__(parent)
        self.catalog_name = catalog_name
        self.file_path = file_path
        default_cols = DEFAULT_COLS

        # Initialize data
        if data is None or data.empty:
            self.data = pd.DataFrame(columns=default_cols)
        else:
            self.data = data.copy()
            if "StructureImage" in self.data.columns:
                self.data["StructureImage"] = self.data["StructureImage"].apply(
                    lambda b64: base64_to_pixmap(b64) if isinstance(b64, str) else None
                )
            for col in default_cols:
                if col not in self.data.columns:
                    self.data[col] = ""

        # Process SMILES data
        if "SMILES" in self.data.columns:
            self.data["SMILES"] = self.data.apply(
                lambda r: r["SMILES"] if r["SMILES"] != "" else get_smiles(r.get("SMILES"), r.get("CAS")),
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

        self.last_sorted_column = None
        self.last_sort_order = True
        self._updating_table = False

        # Initialize UI
        self.initUI()

        # Now that UI (including table) is initialized, populate it
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
        self.btnAddCAS = QPushButton("Add by identifier")
        self.btnAddCAS.clicked.connect(self.add_by_identifier)
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
        fileName, _ = QFileDialog.getOpenFileName(
            self, "Import CSV", "", "CSV Files (*.csv);;All Files (*)", options=options)

        if fileName:
            try:
                # Read CSV and standardize column names (case-insensitive)
                df = pd.read_csv(fileName)

                # Create a mapping of lowercase column names to original names
                col_mapping = {col.lower(): col for col in df.columns}

                # Standardize column names (we'll use lowercase for comparison)
                required_cols = ['name', 'cas', 'smiles']
                remove_cols = [col.lower() for col in REMOVE_COLUMNS]

                # Drop unwanted columns (case-insensitive)
                cols_to_drop = [col_mapping[col] for col in remove_cols if col in col_mapping]
                df = df.drop(columns=cols_to_drop, errors='ignore')

                # Ensure required columns exist (case-insensitive)
                for col in required_cols:
                    if col not in col_mapping:
                        df[col.upper()] = ""

                # Get the actual column names (preserving original case)
                name_col = next((col for col in df.columns if col.lower() == 'name'), 'NAME')
                cas_col = next((col for col in df.columns if col.lower() == 'cas'), 'CAS')
                smiles_col = next((col for col in df.columns if col.lower() == 'smiles'), 'SMILES')

                # Prepare data for parallel processing
                rows_to_process = []
                for idx, row in df.iterrows():
                    name = str(row.get(name_col, "")) if pd.notna(row.get(name_col)) else ""
                    cas = str(row.get(cas_col, "")) if pd.notna(row.get(cas_col)) else ""
                    smiles = str(row.get(smiles_col, "")) if pd.notna(row.get(smiles_col)) else ""
                    rows_to_process.append((idx, name, cas, smiles))

                # Parallel processing of compound information
                with ThreadPoolExecutor(max_workers=5) as executor:  # Adjust max_workers as needed
                    futures = []
                    for idx, name, cas, smiles in rows_to_process:
                        futures.append(executor.submit(
                            self.process_compound_row,
                            idx, name, cas, smiles, name_col, cas_col, smiles_col, df
                        ))

                    # Update progress as each future completes
                    for future in as_completed(futures):
                        try:
                            idx, updates = future.result()
                            for col, value in updates.items():
                                df.at[idx, col] = value
                        except Exception as e:
                            print(f"Error processing row: {e}")
                            continue

                # Handle Formula column (case-insensitive)
                formula_col = next((col for col in df.columns if col.lower() == 'formula'), None)
                if formula_col:
                    # Rename to standard 'Formula' if it exists with different case
                    if formula_col != 'Formula':
                        df['Formula'] = df[formula_col]
                        df = df.drop(columns=[formula_col])
                else:
                    df['Formula'] = ""

                # Calculate missing formulas from SMILES (parallelized)
                def process_formula_chunk(chunk):
                    results = {}
                    for idx, row in chunk.iterrows():
                        if pd.notnull(row.get('Formula')) and str(row.get('Formula')).strip() != "":
                            results[idx] = row['Formula']
                        else:
                            s = row.get(smiles_col)
                            if s and isinstance(s, str):
                                results[idx] = calculate_formula(s) or ""
                            else:
                                results[idx] = ""
                    return results

                # Split dataframe into chunks for parallel processing
                mask = (df['Formula'].isna()) | (df['Formula'].astype(str).str.strip() == "")
                chunks = np.array_split(df[mask], 4)  # Split into 4 chunks

                with ThreadPoolExecutor() as executor:
                    future_to_chunk = {executor.submit(process_formula_chunk, chunk): chunk for chunk in chunks}
                    for future in as_completed(future_to_chunk):
                        chunk_results = future.result()
                        for idx, formula in chunk_results.items():
                            df.at[idx, 'Formula'] = formula

                # Handle category (parallelized)
                smiles_list = df[smiles_col].tolist()
                with ThreadPoolExecutor() as executor:
                    categories = list(executor.map(
                        lambda s: categorize_molecule(s) if s and isinstance(s, str) else [],
                        smiles_list
                    ))
                df['Category'] = categories

                # Handle structure image (parallelized)
                with ThreadPoolExecutor() as executor:
                    structure_images = list(executor.map(
                        lambda s: generate_structure_image(s) if s and isinstance(s, str) else None,
                        smiles_list
                    ))
                df['StructureImage'] = structure_images

                # Handle date added (case-insensitive)
                date_col = next((col for col in df.columns if col.lower() == 'date added'), None)
                if not date_col:
                    df['Date Added'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                self.data = pd.concat([self.data, df], ignore_index=True)
                self.populate_views()
                self.save_catalog(silent=True)

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error importing CSV: {e}")

    def process_compound_row(self, idx, name, cas, smiles, name_col, cas_col, smiles_col, df):
        """Process a single compound row and return updates"""
        updates = {}

        # If we have SMILES, use that as the primary identifier
        if smiles and is_valid_smiles(smiles):
            compound_data = fetch_compound_info(smiles)
        # Otherwise try CAS if available
        elif cas and is_valid_cas(cas):
            compound_data = fetch_compound_info(cas)
        # Finally try name if nothing else works
        elif name:
            compound_data = fetch_compound_info(name)
        else:
            return idx, updates  # Skip if no valid identifiers

        if compound_data:
            # Update missing fields with fetched data
            if not smiles and compound_data.get("SMILES"):
                updates[smiles_col] = compound_data["SMILES"]
                smiles = compound_data["SMILES"]  # Update for subsequent processing

            if not name and compound_data.get("NAME"):
                updates[name_col] = compound_data["NAME"]

            if not cas and compound_data.get("CAS"):
                updates[cas_col] = compound_data["CAS"]

            # If we still don't have SMILES but have name or CAS, try to get it
            if not smiles and (name or cas):
                fetched_smiles = get_smiles(name, cas)
                if fetched_smiles:
                    updates[smiles_col] = fetched_smiles

        return idx, updates

    def add_by_identifier(self):
        text, ok = QInputDialog.getMultiLineText(self, None,
                                                 "Add by CAS, SMILES or IUPAC, accepts multiple identifiers, separated by newline or white space")
        if ok and text:
            # Split input into separate identifiers
            identifier_list = [identifier.strip() for identifier in text.split() if identifier.strip()]

            if not identifier_list:
                QMessageBox.warning(self, "Invalid Input", "No valid identifiers provided.")
                return

            new_rows = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
                # Submit all identifier lookups in parallel
                future_to_id = {executor.submit(fetch_compound_info, identifier): identifier
                                for identifier in identifier_list}

                for future in concurrent.futures.as_completed(future_to_id):
                    identifier = future_to_id[future]
                    result = future.result()
                    if result:
                        result["Date Added"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        result["Detail"] = ""
                        new_rows.append(result)
                    else:
                        QMessageBox.warning(self, "Lookup Error",
                                            f"Could not retrieve data for identifier: {identifier}")

            if new_rows:
                new_df = pd.DataFrame(new_rows)
                # Ensure all expected columns exist
                for col in ["NAME", "CAS", "SMILES", "Formula", "Category", "StructureImage", "Date Added", "Supplier",
                            "Detail"]:
                    if col not in new_df.columns:
                        new_df[col] = ""

                # Add new compounds to the catalog
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
            data_to_save = self.data.copy()
            if "StructureImage" in data_to_save.columns:
                data_to_save["StructureImage"] = data_to_save["StructureImage"].apply(
                    lambda pix: pixmap_to_base64(pix) if pix and isinstance(pix, QPixmap) else None
                )
            data_to_save.to_json(self.file_path, orient="records", indent=2)
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
        df = pd.DataFrame(columns=["NAME", "CAS", "SMILES", "Formula", "Category", "Date Added", "Supplier", "Detail"])
        df.to_json(path, orient="records", indent=2)
        self.catalog_files[name] = path
        return path, df

    def load_catalog(self, name):
        path = self.catalog_files.get(name)
        if path and os.path.exists(path):
            try:
                df = pd.read_json(path, orient="records")
                if df.empty:
                    df = pd.DataFrame(
                        columns=["NAME", "CAS", "SMILES", "Formula", "Category", "Date Added", "Supplier", "Detail"])
            except Exception:
                df = pd.DataFrame(
                    columns=["NAME", "CAS", "SMILES", "Formula", "Category", "Date Added", "Supplier", "Detail"])
        else:
            df = pd.DataFrame(
                columns=["NAME", "CAS", "SMILES", "Formula", "Category", "Date Added", "Supplier", "Detail"])
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


class ClickableLabel(QtWidgets.QLabel):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
