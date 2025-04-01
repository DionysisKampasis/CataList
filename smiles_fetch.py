import re
import xml.etree.ElementTree as ET
from datetime import *

import pubchempy as pcp
import requests

from benchmark import timer_function  # noqa
from chemistry_functions import *

# Compile the regex patterns once at module level
CAS_PATTERN_1 = re.compile(r"^\d{2,7}-\d{2}-\d$")
CAS_PATTERN_2 = re.compile(r"^\d{10}$")

CACTUS_TIMEOUT = 15
CHEMSPIDER_API_KEY = None
SMILES_CACHE = {}


# Initialize a compound data dictionary with default values
def initialize_compound_data():
    return {
        "NAME": None,
        "CAS": None,
        "SMILES": None,
        "Formula": None,
        "Category": [],
        "StructureImage": None,
        "Date Added": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Detail": ""
    }


@timer_function
def is_valid_cas(input_data):
    return bool(CAS_PATTERN_1.match(input_data)) or bool(CAS_PATTERN_2.match(input_data))


@timer_function
def is_valid_smiles(input_data):
    return Chem.MolFromSmiles(input_data) is not None


@timer_function
def fetch_compound_by_cas(cas, compound_data):
    try:
        compounds = pcp.get_compounds(cas, 'name')
        if compounds:
            comp = compounds[0]
            compound_data["NAME"] = (comp.iupac_name if hasattr(comp, "iupac_name") and comp.iupac_name else
                                     comp.synonyms[0] if hasattr(comp, "synonyms") and comp.synonyms else "N/A")
            compound_data["SMILES"] = comp.canonical_smiles if hasattr(comp, "canonical_smiles") else None
    except Exception as e:
        print(f"Error retrieving compound from PubChem for CAS {cas}: {e}")
    return compound_data


@timer_function
def fetch_compound_by_smiles(smiles, compound_data):
    """Fetch compound information using SMILES string."""
    try:
        compounds = pcp.get_compounds(smiles, 'smiles')
        if compounds:
            comp = compounds[0]
            compound_data["NAME"] = (comp.iupac_name if hasattr(comp, "iupac_name") and comp.iupac_name else
                                     comp.synonyms[0] if hasattr(comp, "synonyms") and comp.synonyms else "N/A")
            if hasattr(comp, "xref") and comp.xref.get('cas'):
                compound_data["CAS"] = comp.xref['cas']
    except Exception as e:
        print(f"Error retrieving compound from PubChem for SMILES {smiles}: {e}")
    return compound_data


@timer_function
def fetch_compound_by_name(name, compound_data):
    """Fetch compound information using chemical name."""
    try:
        compounds = pcp.get_compounds(name, 'name')
        if compounds:
            comp = compounds[0]
            canonical_name = comp.iupac_name if hasattr(comp, "iupac_name") and comp.iupac_name else None
            compound_data["NAME"] = canonical_name if canonical_name else name
            compound_data["SMILES"] = comp.canonical_smiles if hasattr(comp, "canonical_smiles") else None
            if hasattr(comp, "xref") and comp.xref.get('cas'):
                compound_data["CAS"] = comp.xref['cas']
    except Exception as e:
        print(f"Error retrieving compound from PubChem for name {name}: {e}")
    return compound_data


@timer_function
def supplement_compound_data(compound_data):
    """Supplement missing compound data from alternative sources."""
    if not compound_data["SMILES"] and (compound_data["CAS"] or compound_data["NAME"]):
        compound_data["SMILES"] = get_smiles(compound_data["NAME"], compound_data["CAS"])

    if compound_data["SMILES"]:
        compound_data["Formula"] = calculate_formula(compound_data["SMILES"])
        compound_data["StructureImage"] = generate_structure_image(compound_data["SMILES"])
        compound_data["Category"] = categorize_molecule(compound_data["SMILES"])

    if compound_data["NAME"] and not compound_data["CAS"] and compound_data["SMILES"]:
        compound_data["CAS"] = get_cas(compound_data["NAME"], compound_data["SMILES"])

    if not compound_data["NAME"] and compound_data["SMILES"]:
        compound_data["NAME"] = get_name(compound_data["SMILES"])

    return compound_data


@timer_function
def fetch_compound_info(input_data):
    """Main function to fetch compound information from various identifiers."""
    if not input_data:
        return None

    compound_data = initialize_compound_data()

    if is_valid_cas(input_data):
        compound_data["CAS"] = input_data
        compound_data = fetch_compound_by_cas(input_data, compound_data)
    elif is_valid_smiles(input_data):
        compound_data["SMILES"] = input_data
        compound_data = fetch_compound_by_smiles(input_data, compound_data)
    else:
        compound_data["NAME"] = input_data
        compound_data = fetch_compound_by_name(input_data, compound_data)

    compound_data = supplement_compound_data(compound_data)
    return compound_data


@timer_function
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
            @timer_function
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


@timer_function
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


@timer_function
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


@timer_function
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


@timer_function
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


@timer_function
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


@timer_function
def get_smiles_from_cache(identifier):
    return SMILES_CACHE.get(identifier)


@timer_function
def set_smiles_in_cache(identifier, smiles):
    SMILES_CACHE[identifier] = smiles
