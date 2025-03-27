import xml.etree.ElementTree as ET

import pubchempy as pcp
import requests

CACTUS_TIMEOUT = 15
CHEMSPIDER_API_KEY = None
SMILES_CACHE = {}


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
