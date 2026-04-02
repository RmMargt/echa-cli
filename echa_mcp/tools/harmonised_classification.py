"""
MCP Tool: Harmonised (Annex VI) Classification.

Fetches the official EU harmonised classification for a substance
from the CLP Regulation Annex VI.
"""

import json
import logging
from ..clients.echa_client import get_client
from ..data.hcode_mapping import HAZARD_TO_HCODE

logger = logging.getLogger(__name__)


async def get_harmonised_classification(substance_index: str) -> str:
    """
    Get harmonised classification (Annex VI, CLP Regulation) for a substance.

    The harmonised classification is the official EU classification adopted
    by the European Commission, as opposed to industry self-classifications
    (CLP notifications). Not all substances have a harmonised classification.

    This retrieves data from the C&L Inventory's harmonised classification section,
    including hazard classes, H-codes, SCL, M-factors, ATE values, and notes.

    Args:
        substance_index: ECHA substance index (e.g., '100.000.002')

    Returns:
        JSON string with:
        - substance_index: queried substance
        - has_harmonised: boolean indicating if harmonised classification exists
        - classifications: list of classification objects with:
            - classification_id, index_number
            - hazard_categories, hcodes
            - signal_word, pictograms
            - hazard_statements, precautionary_statements
            - specific_concentration_limits, m_factors
            - acute_toxicity_estimates, notes
    """
    client = get_client()

    data = await client.get_harmonised_classifications(substance_index)
    if not data:
        return json.dumps(
            {
                "substance_index": substance_index,
                "has_harmonised": False,
                "message": "No harmonised classification found. This substance may only "
                           "have industry (CLP notification) classifications. "
                           "Use echa_get_clp_classification to check.",
                "classifications": [],
            },
            indent=2,
        )

    classifications_raw = data if isinstance(data, list) else data.get("classifications", [])
    classifications = []

    for cls_item in classifications_raw:
        cid = str(cls_item.get("classificationId", cls_item.get("id", "")))
        if not cid:
            continue

        entry = {
            "classification_id": cid,
            "index_number": cls_item.get("indexNumber", ""),
            "hazard_categories": [],
            "hcodes": [],
            "signal_word": "",
            "pictograms": [],
            "hazard_statements": "",
            "precautionary_statements": "",
            "specific_concentration_limits": [],
            "m_factors": [],
            "acute_toxicity_estimates": [],
            "notes": [],
        }

        # Classification detail
        detail = await client.get_harmonised_classification_detail(cid)
        if detail:
            categories = []
            items = detail if isinstance(detail, list) else detail.get("classifications", [])
            for item in items:
                cat = item.get("hazardCategory", item.get("category", ""))
                if cat:
                    categories.append(cat)

            entry["hazard_categories"] = categories
            entry["hcodes"] = list(set(
                HAZARD_TO_HCODE.get(cat, "") for cat in categories
                if HAZARD_TO_HCODE.get(cat)
            ))

        # Labelling
        labelling = await client.get_harmonised_labelling(cid)
        if labelling and isinstance(labelling, dict):
            entry["signal_word"] = labelling.get("signalWord", "")
            entry["hazard_statements"] = labelling.get("hazardStatements", "")
            entry["precautionary_statements"] = labelling.get("precautionaryStatements", "")

        # Pictograms
        pictograms = await client.get_harmonised_pictograms(cid)
        if pictograms:
            if isinstance(pictograms, list):
                entry["pictograms"] = [p.get("name", str(p)) for p in pictograms]

        # SCL
        scl = await client.get_harmonised_scl(cid)
        if scl:
            entry["specific_concentration_limits"] = scl if isinstance(scl, list) else scl.get("limits", [])

        # M-factors
        m_factors = await client.get_harmonised_m_factors(cid)
        if m_factors:
            entry["m_factors"] = m_factors if isinstance(m_factors, list) else m_factors.get("mFactors", [])

        # ATE
        ate = await client.get_harmonised_ate(cid)
        if ate:
            entry["acute_toxicity_estimates"] = ate if isinstance(ate, list) else ate.get("estimates", [])

        # Notes
        notes = await client.get_harmonised_notes(cid)
        if notes:
            entry["notes"] = notes if isinstance(notes, list) else notes.get("notes", [])

        classifications.append(entry)

    return json.dumps(
        {
            "substance_index": substance_index,
            "has_harmonised": len(classifications) > 0,
            "classifications": classifications,
        },
        ensure_ascii=False,
        indent=2,
    )
