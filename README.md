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

Please consider supporting our cause by donating [here](https://paypal.me/Chemisfree)! **ChemIsFree** is a collaborative project dedicated to creating and/or curating free/open-source chemistry tools. For more information, feel free to check out our website https://chemisfree.github.io/website/index.html (still under development) reach out via e-mail on chemisfree2026@gmail.com or [LinkedIn](https://www.linkedin.com/company/chemisfree).

---

# CataList

**CataList** is a smart desktop application designed for laboratories, researchers, and stockroom managers to efficiently organize and visualize chemical inventories.

It automatically translates standard chemical identifiers into structures, calculates molecular properties, and standardizes your data.

<img width="865" height="316" alt="image" src="https://github.com/user-attachments/assets/275ca692-fd7c-4d35-bb6a-3971b994d3fa" />

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

<img width="865" height="501" alt="image" src="https://github.com/user-attachments/assets/575c1264-7b86-4bcf-9776-7a24032fc9c2" />

### Detailed View
Double-click any chemical structure image to:

- View all data fields
- Perform manual edits
- Copy high-resolution structure image to clipboard

<img width="198" height="280" alt="image" src="https://github.com/user-attachments/assets/1c377eb4-a37e-4cac-b756-4154e039b2b7" />

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

<img width="878" height="507" alt="image" src="https://github.com/user-attachments/assets/38f85824-8ab5-451a-a002-e5362d070758" />

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

<img width="865" height="499" alt="image" src="https://github.com/user-attachments/assets/a88f98fa-17e7-4a4a-8fa5-f7c057a163c9" />

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

<img width="3674" height="2116" alt="Picture65" src="https://github.com/user-attachments/assets/0258d16f-d1c7-43c4-8ac4-a611cc65b7ca" />

### ⚠ Missing Info
Enable **Missing Info** checkbox to identify unresolved rows.

### 🧬 Structure Search
1. Click **Structure Search**
2. Draw a scaffold
3. Run:
   - Exact
   - Substructure
   - Similarity search

<img width="865" height="497" alt="image" src="https://github.com/user-attachments/assets/a30d2ec7-192a-4a13-a024-e107fbb77a9e" />

---

## 2.6 Exporting Data

CataList automatically saves catalogs, but keeping external backups is recommended.

### Supported Export Formats

- `.sdf`
- `.csv`
- `.smi`
- `.xlsx`

Exporting to Excel (`.xlsx`) generates a formatted spreadsheet including embedded 2D structure images.

<img width="889" height="563" alt="image" src="https://github.com/user-attachments/assets/be91d49d-fab6-4358-b6f9-3e354c9357aa" />

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
