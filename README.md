```text
 $$$$$$\             $$\               $$\       $$\             $$\
$$  __$$\            $$ |              $$ |      \__|            $$ |
$$ /  \__| $$$$$$\ $$$$$$\    $$$$$$\  $$ |      $$\  $$$$$$$\ $$$$$$\
$$ |       \____$$\\_$$  _|   \____$$\ $$ |      $$ |$$  _____|\_$$  _|
$$ |       $$$$$$$ | $$ |     $$$$$$$ |$$ |      $$ |\$$$$$$\    $$ |
$$ |  $$\ $$  __$$ | $$ |$$\ $$  __$$ |$$ |      $$ | \____$$\   $$ |$$\
\$$$$$$  |\$$$$$$$ | \$$$$  |\$$$$$$$ |$$$$$$$$\ $$ |$$$$$$$  |  \$$$$  |
 \______/  \_______|  \____/  \_______|\________|\__|\_______/    \____/
 
 
┏┓ ╻ ╻   ┏━╸╻ ╻┏━╸┏┳┓╻┏━┓┏━╸┏━┓┏━╸┏━╸
┣┻┓┗┳┛   ┃  ┣━┫┣╸ ┃┃┃┃┗━┓┣╸ ┣┳┛┣╸ ┣╸
┗━┛ ╹    ┗━╸╹ ╹┗━╸╹ ╹╹┗━┛╹  ╹┗╸┗━╸┗━╸
```

---

## About ChemIsFree

Please consider supporting our cause by donating [here](https://paypal.me/Chemisfree)! **ChemIsFree** is a collaborative non-profit network, self-organized and managed by students and young professionals who believe in free and open access tools for life sciences and education. For more information, feel free to reach out via e-mail on chemisfree2026@gmail.com or [linkedIn](https://www.linkedin.com/company/chemisfree).

---

# CataList

**CataList** is a smart desktop application designed for laboratories, researchers, and stockroom managers to efficiently organize and visualize chemical inventories.

It automatically translates standard chemical identifiers into structures, calculates molecular properties, and standardizes your data.

---

# 1. Core Capabilities

CataList processes inventory spreadsheets and automatically renders chemical structures from:

- Chemical Name  
- CAS Registry Number  
- SMILES string  

### 🔹 Data Triangulation (Auto-Lookup)
If a record contains only a Name, CAS, or SMILES, CataList queries online chemical databases to retrieve missing identifiers.

### 🔹 Automated 2D Depiction
Reads SMILES strings and generates standardized, high-resolution 2D chemical structures directly in the interface.

### 🔹 Property Calculation
Computes key physicochemical descriptors locally:

- Molecular Weight (MW)
- LogP
- TPSA
- Hydrogen Bond Donors (HBD)
- Hydrogen Bond Acceptors (HBA)
- Rotatable Bonds

### 🔹 Smart Categorization
Automatically analyzes and tags molecules by functional groups:

- Carboxylic Acids  
- Primary Amines  
- Halogens  
- and more  

Enables rapid chemical-class filtering.

### 🔹 Advanced Cheminformatics Search
Users can draw a molecule to perform:

- Exact Search  
- Substructure Search  
- Similarity Search (Tanimoto coefficient)  

Across the entire inventory.

---

# 2. How to Use CataList

## 2.1 Importing Data

Supported formats:

- `.csv`
- `.xlsx`
- `.xls`
- `.sdf`
- `.smi`

### Import Steps

1. Click **Import**
2. Select one or multiple files
3. If importing spreadsheets (`.csv`, `.xlsx`), map your columns (e.g., assign "Product Name" → "Name")

### Smart Processing During Import

- If SMILES is present → Structure is generated instantly.
- If SMILES is missing → Name or CAS is used for online lookup before display.

---

## 2.2 Navigating and Viewing

### View Toggles
Switch between:

- **Table View** (spreadsheet style)
- **Grid View** (visual card layout)

### Detailed View
Double-click any chemical structure image to:

- View all data fields
- Perform manual edits
- Copy high-resolution structure image to clipboard

---

## 2.3 Editing and Data Integrity

CataList strictly maintains consistency between identifiers and structures.

### Manual Edits
- Edit directly inside the table.
- If Name, CAS, or SMILES is modified, a background lookup is triggered.

### Approving Changes
If a new match is found:
- Confirmation dialog appears.
- Clicking **Yes** overwrites the row with:
  - Correct CAS
  - Name
  - SMILES
  - Regenerated structure

### Undo System
Press: Ctrl + Z

Reverts:
- Text edits
- Structure updates  

As a single unified action.

### Restore Default
Right-click a row → **Restore Default**

Reverts the chemical to its original state when the file was first opened.

---

## 2.4 Calculating Properties

Click **Calculate Properties** to generate descriptors.

CataList creates a consolidated **Properties** column containing:

- MW  
- LogP  
- TPSA  
- HBD  
- HBA  
- Rotatable Bonds  

Use the **Sort** dropdown to order inventory numerically (e.g., MW Ascending).

---

## 2.5 Searching and Filtering

### 🔎 Text Search
Filter instantly by:
- Name
- CAS
- Formula fragment

### 🧪 Category Filter
Use dropdown checklist to filter by chemical class:
- e.g., "Aldehyde" AND "Halogen"

### ⚠ Missing Info
Enable **Missing Info** checkbox to identify unresolved rows.

### 🧬 Structure Search
1. Click **Structure Search**
2. Draw a scaffold
3. Run:
   - Exact
   - Substructure
   - Similarity search

---

## 2.6 Exporting Data

CataList automatically saves catalogs, but keeping external backups is recommended.

### Supported Export Formats

- `.sdf`
- `.csv`
- `.smi`
- `.xlsx`

Exporting to Excel (`.xlsx`) generates a formatted spreadsheet including embedded 2D structure images.

---

# 3. License

CataList is provided **100% free of charge** for both personal and commercial use.

---
# 4. Data Safety

Your data is 100% safe. CataList does not keep any online record of your data. It makes API calls to PubChem, CACTUS and other public databases when trying to retrieve SMILES strings from a IUPAC name or CAS number, similar to a manual search. All other functions are 100% locally managed and the data never leave your computer.

---
# 5. Support & Feedback

For questions, collaborations, or feedback:

📧 kampasisdionisis@gmail.com  
📧 chemisfree2026@gmail.com  
📧 https://www.linkedin.com/company/chemisfree

---

**ChemIsFree – Open tools for life sciences.**
