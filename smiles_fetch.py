import re
import xml.etree.ElementTree as ET
from datetime import *

import pubchempy as pcp
import requests

from chemistry_functions import *

CACTUS_TIMEOUT = 15
CHEMSPIDER_API_KEY = None
SMILES_CACHE = {}


def fetch_compound_info(input_data):
    # Initialize default values
    name = None
    cas = None
    smiles = None
    formula = None
    structure_image = None

    # Determine input type
    if not input_data:
        return None

    # Case 1: CAS number (either standard format or numeric)
    if re.match(r"^\d{2,7}-\d{2}-\d$", input_data) or re.match(r"^\d{10}$", input_data):
        cas = input_data
        try:
            compounds = pcp.get_compounds(cas, 'name')
            if compounds:
                comp = compounds[0]
                name = comp.iupac_name if hasattr(comp, "iupac_name") and comp.iupac_name else \
                    comp.synonyms[0] if hasattr(comp, "synonyms") and comp.synonyms else "N/A"
                smiles = comp.canonical_smiles if hasattr(comp, "canonical_smiles") else None
        except Exception as e:
            print(f"Error retrieving compound from PubChem for CAS {cas}: {e}")

    # Case 2: SMILES string (basic check)
    elif Chem.MolFromSmiles(input_data) is not None:
        smiles = input_data
        try:
            compounds = pcp.get_compounds(smiles, 'smiles')
            if compounds:
                comp = compounds[0]
                name = comp.iupac_name if hasattr(comp, "iupac_name") and comp.iupac_name else \
                    comp.synonyms[0] if hasattr(comp, "synonyms") and comp.synonyms else "N/A"
                if hasattr(comp, "xref") and comp.xref.get('cas'):
                    cas = comp.xref['cas']
        except Exception as e:
            print(f"Error retrieving compound from PubChem for SMILES {smiles}: {e}")

    # Case 3: IUPAC name or other chemical name
    else:
        name = input_data
        try:
            compounds = pcp.get_compounds(name, 'name')
            if compounds:
                comp = compounds[0]
                # Get the canonical IUPAC name if available
                canonical_name = comp.iupac_name if hasattr(comp, "iupac_name") and comp.iupac_name else None
                # Use the canonical name if it exists, otherwise keep the input name
                name = canonical_name if canonical_name else name
                smiles = comp.canonical_smiles if hasattr(comp, "canonical_smiles") else None
                if hasattr(comp, "xref") and comp.xref.get('cas'):
                    cas = comp.xref['cas']
        except Exception as e:
            print(f"Error retrieving compound from PubChem for name {name}: {e}")

    # If we still don't have SMILES, try other sources
    if not smiles and (cas or name):
        smiles = get_smiles(name, cas)

    # Calculate formula and generate image if we have SMILES
    if smiles:
        formula = calculate_formula(smiles)
        structure_image = generate_structure_image(smiles)

    # Final attempt to get missing data
    if name and not cas:
        cas = get_cas(name, smiles) if smiles else None
    if not name and smiles:
        name = get_name(smiles)

    return {
        "NAME": name,
        "CAS": cas,
        "SMILES": smiles,
        "Formula": formula,
        "Category": categorize_molecule(smiles) if smiles else [],
        "StructureImage": structure_image,
        "Date Added": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Detail": ""
    }


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


def cas_to_smiles_cactus(cas):
    url = f"https://cactus.nci.nih.gov/chemical/structure/{cas}/smiles"
    try:
        response = requests.get(url, timeout=CACTUS_TIMEOUT)
        response.raise_for_status()
        smiles = response.text.strip()
        if smiles and smiles != "Structure not found":
            return smiles
        else:
            print(f"Cactus: SMILES not found for CAS '{cas}'")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Cactus: Error retrieving SMILES for CAS '{cas}': {e}")
        return None


def cas_to_smiles_chemspider(cas):
    if not CHEMSPIDER_API_KEY:
        print("ChemSpider API key not provided. Skipping ChemSpider.")
        return None
    url = "http://www.chemspider.com/ChemicalStructure.asmx/GetStructureInfoFromCAS"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = f"casrn={cas}"
    try:
        response = requests.post(url, data=data, headers=headers, timeout=CACTUS_TIMEOUT)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        csid = root.text
        if csid:
            url = "http://www.chemspider.com/ChemicalStructure.asmx/GetExtendedCompoundInfo"
            data = f"csid={csid}"
            response2 = requests.post(url, data=data, headers=headers, timeout=CACTUS_TIMEOUT)
            response2.raise_for_status()
            root2 = ET.fromstring(response2.text)
            for element in root2.findall('.//SMILES'):
                return element.text
        else:
            print(f"ChemSpider: No CSID found for CAS '{cas}'")
            return None
    except requests.exceptions.RequestException as e:
        print(f"ChemSpider: Error retrieving SMILES for CAS '{cas}': {e}")
        return None
    except ChemSpiderException as e:
        print(f"ChemSpider XML parsing error: {e}")
        return None


def cas_to_smiles_pubchem(cas):
    try:
        compounds = pcp.get_compounds(identifier=cas, search_type='name')[0]
        if compounds:
            return compounds.canonical_smiles
        else:
            print(f"PubChem: SMILES not found for CAS '{cas}'")
            return None
    except Exception as e:
        print(f"PubChem: Error retrieving SMILES for CAS '{cas}': {e}")
        return None


def fetch_smiles_pubchem(identifier, search_type):
    try:
        compounds = pcp.get_compounds(identifier=identifier, search_type=search_type)[0]
        if compounds and compounds.canonical_smiles:
            return compounds.canonical_smiles
        else:
            print(f"PubChem: No canonical SMILES found for {search_type} '{identifier}'")
            return None
    except Exception as e:
        print(
            f"PubChem: Error retrieving SMILES for identifier '{identifier}' and search type '{search_type}': {e}")
        return None


def get_smiles(name, cas):
    if isinstance(name, str) and name.startswith('CID'):
        return fetch_smiles_pubchem(name, 'inchikey')
    else:
        smiles = get_smiles_from_cache(cas)
        if smiles is None:
            smiles = cas_to_smiles_pubchem(cas)
            if smiles is None:
                smiles = cas_to_smiles_chemspider(cas)
                if smiles is None:
                    smiles = cas_to_smiles_cactus(cas)
        set_smiles_in_cache(cas, smiles)
        return smiles


def get_smiles_from_cache(identifier):
    return SMILES_CACHE.get(identifier)


def set_smiles_in_cache(identifier, smiles):
    SMILES_CACHE[identifier] = smiles
