CATEGORY_SMARTS = {
    "Aldehyde": "[CX3H1](=O)[#6]",
    "Primary amines": "[NX3H2][#6]",
    "Secondary amines": "[NX3H1]([#6])[#6]",
    "Tertiary amines": "[NX3]([#6])([#6])[#6]",
    "Alcohols": "[OX2H][#6]",
    "Esters": "[CX3](=O)O[CX4]",
    "Ethers": "[OX2]([CX4])[CX4]",
    "Carboxylic acids": "[CX3](=O)O[HX1]",
    "Amides": "[NX3][CX3](=O)[#6]",
    "Aromatic": "[c]",
    "Cyclic": "[#6]1[#6]2[#6]3[#6]4[#6]51",
    "Heterocyclic": "[!#6]",
    "Linear": "[#6]-*-[#6]",
    "Boronic acids/esters": "[$([B](O)(O)),$([B](OC(C)(C)C)(OC(C)(C)C))]"
}

IMAGE_SIZE = 1024

CATALOGS_FOLDER = "catalogs"  # All catalogs are stored here
DEFAULT_COLS = ["NAME", "CAS", "SMILES", "Formula", "Category", "Date Added", "Detail", "Supplier"]
REMOVE_COLUMNS = {"Supplier Code", "Lab (Shelf)", "Label", "H", "UUID"}
