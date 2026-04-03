"""
MCP Tools: Substance basic information and dossier listing.

Tools:
- echa_get_substance_info: Get substance basic info (CAS, EC, names)
- echa_list_dossiers: List REACH registration dossiers for a substance
"""

import json
from ..clients.echa_client import get_client
from ..parsers.common import select_best_cas


async def get_substance_info(substance_index: str) -> str:
    """
    Get basic information for a chemical substance from ECHA CHEM database.

    Retrieves the substance's CAS number, EC number, chemical name(s),
    IUPAC name, molecular formula, and other identifiers.

    Args:
        substance_index: ECHA substance index (e.g., '100.000.002' for Formaldehyde).

    Returns:
        JSON string with substance info including:
        - substance_index, cas_number, ec_number
        - chemical_name, iupac_name, molecular_formula
        - inchi, smiles
        - all_cas_numbers, all_iupac_names
        - substance_url

    Error: Returns JSON with "error" key if substance not found.
    """
    client = get_client()
    data = await client.get_substance_info(substance_index)

    if not data:
        return json.dumps(
            {"error": f"Substance not found for index: {substance_index}"},
            indent=2,
        )

    # The API returns a flat JSON with rmlXxx fields
    cas_list = data.get("casNumber", []) or []
    ec_list = data.get("ecNumber", []) or []
    iupac_names = data.get("iupacName", []) or []
    ec_names = data.get("ecName", []) or []
    index_numbers = data.get("indexNumber", []) or []

    # Primary identifiers (from rml prefix fields)
    primary_cas = data.get("rmlCas", "")
    primary_ec = data.get("rmlEc", "")
    primary_name = data.get("rmlName", "")
    iupac_name = data.get("rmlIupac", "")
    mol_formula = data.get("rmlMolFormula", "")
    inchi = data.get("rmlInchi", "")
    smiles = data.get("rmlSmiles", "")

    # Use primary CAS, fallback to best from list
    if not primary_cas and cas_list:
        primary_cas = select_best_cas(cas_list)

    result = {
        "substance_index": substance_index,
        "cas_number": primary_cas,
        "ec_number": primary_ec,
        "chemical_name": primary_name,
        "iupac_name": iupac_name,
        "molecular_formula": mol_formula,
        "inchi": inchi,
        "smiles": smiles,
        "index_number": index_numbers[0] if index_numbers else "",
        "all_cas_numbers": cas_list,
        "all_ec_names": ec_names,
        "all_iupac_names": iupac_names[:10],  # Limit to avoid huge output
        "substance_url": f"https://chem.echa.europa.eu/substance-information/{substance_index}",
    }

    return json.dumps(result, ensure_ascii=False, indent=2)


async def list_dossiers(substance_index: str, status: str = "Active", max_results: int = 10) -> str:
    """
    List REACH registration dossiers for a substance.

    Returns dossiers (registrations) filed under REACH regulation,
    sorted by last updated date (newest first). Defaults to 10 results.

    Args:
        substance_index: ECHA substance index (e.g., '100.000.002')
        status: Registration status filter - 'Active' or 'Not active' (default: 'Active')
        max_results: Maximum number of dossiers to return (default 10)

    Returns:
        JSON string with:
        - total_available: total count
        - returned: number returned
        - dossiers: list of dossier info objects

    Error: Returns JSON with "error" key if no dossiers found.
    """
    client = get_client()
    data = await client.get_dossier_list(substance_index, status=status)

    if not data:
        return json.dumps(
            {"error": f"No dossier data for substance {substance_index} (status={status})"},
            indent=2,
        )

    results = data.get("items", [])

    dossiers = []
    for d in results:
        asset_id = d.get("assetExternalId", "")
        if not asset_id:
            continue

        # subtype and role are nested inside reachDossierInfo
        reach_info = d.get("reachDossierInfo", {}) or {}

        dossiers.append({
            "asset_id": asset_id,
            "registration_number": d.get("registrationNumber", ""),
            "subtype": reach_info.get("dossierSubtype", ""),
            "role": reach_info.get("registrationRole", ""),
            "status": d.get("registrationStatus", status),
            "last_updated": d.get("lastUpdatedDate", ""),
            "registration_date": d.get("registrationDate", ""),
            "dossier_url": f"https://chem.echa.europa.eu/html-pages-prod/{asset_id}/index.html",
        })

    total_available = len(dossiers)

    # Sort by last_updated (newest first) and truncate
    dossiers.sort(key=lambda x: x.get("last_updated", ""), reverse=True)
    returned = dossiers[:max_results]

    return json.dumps(
        {
            "total_available": total_available,
            "returned": len(returned),
            "truncated": total_available > len(returned),
            "dossiers": returned,
        },
        ensure_ascii=False,
        indent=2,
    )
