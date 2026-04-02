"""
MCP Tool: CLP Industry (Notification) Classification.

Ported from ECHA_CLP_Classification.py.
Fetches all CLP notification classifications for a substance via JSON APIs.
"""

import json
import logging
from ..clients.echa_client import get_client
from ..data.hcode_mapping import HAZARD_TO_HCODE

logger = logging.getLogger(__name__)


async def get_clp_classification(substance_index: str) -> str:
    """
    Get CLP notification (industry) classification data for a substance.

    Retrieves all CLP self-classifications notified by industry under the
    CLP Regulation. Includes hazard categories, H-codes, signal words,
    pictograms, SCL, M-factors, and labelling.

    This is the 'C&L Inventory' notification data on ECHA, NOT the
    harmonised classification (Annex VI). For harmonised classification,
    use echa_get_harmonised_classification.

    Args:
        substance_index: ECHA substance index (e.g., '100.000.002')

    Returns:
        JSON string with classification data including hazard categories,
        H-codes, signal words, pictograms, labelling statements.
    """
    client = get_client()

    # Step 1: Get classification list
    data = await client.get_clp_classifications(substance_index)
    if not data:
        return json.dumps(
            {"error": f"No CLP classification data found for {substance_index}"},
            indent=2,
        )

    # API returns {"items": [...]}
    classifications_raw = data.get("items", [])
    if not classifications_raw:
        return json.dumps(
            {"substance_index": substance_index, "total_classifications": 0, "classifications": []},
            indent=2,
        )

    classifications = []

    for cls_item in classifications_raw:
        cid = str(cls_item.get("classificationId", ""))
        if not cid:
            continue

        entry = {
            "classification_id": cid,
            "data_source": cls_item.get("dataSource", ""),
            "notification_percentage": cls_item.get("substanceNotificationPercentage", 0),
            "annex_i_compliant": cls_item.get("clpAnnexIComplianceFlag", False),
            "last_update": cls_item.get("lastUpdateDate", ""),
            "hazard_categories": [],
            "hcodes": [],
            "signal_word": "",
            "pictograms": [],
            "labelling": [],
            "specific_concentration_limits": [],
            "m_factors": [],
        }

        # Step 2: Get classification detail (hazard categories)
        detail = await client.get_clp_classification_detail(cid)
        if detail:
            items = detail.get("items", [])
            categories = []
            hcodes_set = set()
            for item in items:
                cat = item.get("hazardClassAndCategoryCode", "")
                if cat:
                    categories.append(cat)
                    mapped = HAZARD_TO_HCODE.get(cat, "")
                    if mapped:
                        hcodes_set.add(mapped)
                # Also get H-codes directly from API
                for hs in item.get("hazardStatements", []):
                    hcode = hs.get("hazardStatementCode", "")
                    if hcode:
                        hcodes_set.add(hcode)

            entry["hazard_categories"] = categories
            entry["hcodes"] = sorted(hcodes_set)

        # Step 3: Get labelling
        labelling = await client.get_clp_labelling(cid)
        if labelling:
            lab_items = labelling.get("items", [])
            signal_words = set()
            lab_entries = []
            for item in lab_items:
                sw = item.get("signalWord", {})
                if sw:
                    signal_words.add(sw.get("signalWordText", ""))
                hs = item.get("hazardStatement", {})
                if hs:
                    lab_entries.append({
                        "code": hs.get("hazardStatementCode", ""),
                        "text": hs.get("hazardStatementText", ""),
                    })
            entry["signal_word"] = ", ".join(signal_words - {""})
            entry["labelling"] = lab_entries

        # Step 4: Get pictograms
        pictograms = await client.get_clp_pictograms(cid)
        if pictograms:
            pic_items = pictograms.get("items", [])
            entry["pictograms"] = [
                {"code": p.get("code", ""), "text": p.get("text", "")}
                for p in pic_items
            ]

        # Step 5: Get SCL
        scl = await client.get_clp_scl(cid)
        if scl:
            entry["specific_concentration_limits"] = scl.get("items", [])

        # Step 6: Get M-factors
        m_factors = await client.get_clp_m_factors(cid)
        if m_factors:
            entry["m_factors"] = m_factors.get("items", [])

        classifications.append(entry)

    result = {
        "substance_index": substance_index,
        "total_classifications": len(classifications),
        "classifications": classifications,
    }

    return json.dumps(result, ensure_ascii=False, indent=2)
