from io import BytesIO

from PyQt5.QtGui import QPixmap, QImage, QIcon
from rdkit import Chem
from rdkit.Chem import Draw, rdMolDescriptors

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

IMAGE_SIZE = 512


def calculate_formula(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol:
        return rdMolDescriptors.CalcMolFormula(mol)
    return None


def generate_structure_image(smiles):
    if not smiles:
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        print(f"RDKit could not parse SMILES: {smiles}")
        return None
    img = Draw.MolToImage(mol, size=(IMAGE_SIZE, IMAGE_SIZE))
    data = BytesIO()
    img.save(data, format="JPEG")
    data.seek(0)
    qt_img = QImage.fromData(data.read(), "JPEG")
    return QPixmap.fromImage(qt_img)


def categorize_molecule(smiles):
    if not smiles:
        return []
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return []
    categories = []
    for cat, smarts in CATEGORY_SMARTS.items():
        pattern = Chem.MolFromSmarts(smarts)
        if pattern and mol.HasSubstructMatch(pattern):
            categories.append(cat)
    halogens = set()
    for atom in mol.GetAtoms():
        symbol = atom.GetSymbol()
        if symbol in ['Br', 'Cl', 'I', 'F']:
            halogens.add(symbol)
    if halogens:
        categories.append("Halogenated")
        for hl in sorted(halogens):
            categories.append(f"Containing {hl}")
    carboxylate_pattern = Chem.MolFromSmarts("[CX3](=O)[O-]")
    if carboxylate_pattern and mol.HasSubstructMatch(carboxylate_pattern):
        if "Carboxylic acids" not in categories:
            categories.append("Carboxylic acids")
    protonated_primary = Chem.MolFromSmarts("[N+;H2]")
    protonated_secondary = Chem.MolFromSmarts("[N+;H1]")
    protonated_tertiary = Chem.MolFromSmarts("[N+;H0]")
    if protonated_primary and mol.HasSubstructMatch(protonated_primary):
        if "Primary amines" not in categories:
            categories.append("Primary amines")
    if protonated_secondary and mol.HasSubstructMatch(protonated_secondary):
        if "Secondary amines" not in categories:
            categories.append("Secondary amines")
    if protonated_tertiary and mol.HasSubstructMatch(protonated_tertiary):
        if "Tertiary amines" not in categories:
            categories.append("Tertiary amines")
    has_carbon = any(atom.GetSymbol() == "C" for atom in mol.GetAtoms())
    if has_carbon:
        categories.append("Organic")
    else:
        categories.append("Inorganic")
    return categories
