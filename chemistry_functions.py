from io import BytesIO

from PyQt5.QtGui import QPixmap, QImage
from rdkit import Chem
from rdkit.Chem import Draw, rdMolDescriptors

from app_constants import *  # noqa
from benchmark import timer_function


@timer_function
def calculate_formula(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol:
        return rdMolDescriptors.CalcMolFormula(mol)
    return None


@timer_function
def get_cas(name, smiles):
    if not name and not smiles:
        return None

    try:
        # Try PubChem first by SMILES
        if smiles:
            compounds = pcp.get_compounds(smiles, 'smiles')
        # Fall back to name if SMILES not available or didn't work
        if (not smiles or not compounds) and name:
            compounds = pcp.get_compounds(name, 'name')

        if compounds:
            comp = compounds[0]
            if hasattr(comp, "xref") and comp.xref.get('cas'):
                return comp.xref['cas']
    except Exception as e:
        print(f"Error retrieving CAS for {name or smiles}: {e}")

    return None


@timer_function
def get_name(smiles):
    if not smiles:
        return None
    try:
        compounds = pcp.get_compounds(smiles, 'smiles')
        if compounds:
            comp = compounds[0]
            if hasattr(comp, "iupac_name") and comp.iupac_name:
                return comp.iupac_name
            elif hasattr(comp, "synonyms") and comp.synonyms:
                return comp.synonyms[0]
    except Exception as e:
        print(f"Error retrieving name for SMILES {smiles}: {e}")
    return None


@timer_function
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


@timer_function
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
