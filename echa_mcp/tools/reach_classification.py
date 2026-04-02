"""
MCP Tools: REACH Registration Classification (GHS + PBT).

Tools:
- echa_get_reach_ghs: Section 2.1 GHS classification from registration dossiers
- echa_get_reach_pbt: Section 2.3 PBT assessment from registration dossiers
"""

import json
import logging
from ..clients.echa_client import get_client
from ..parsers.section2_parser import find_lead_dossiers, parse_section_2_1_ghs, parse_section_2_3_pbt

logger = logging.getLogger(__name__)


async def get_reach_ghs(substance_index: str, cas_number: str) -> str:
    """
    Get REACH registration GHS classification data (Section 2.1).

    Retrieves the GHS hazard classification data from the registrant's
    REACH registration dossier(s). This is different from CLP notifications:
    - CLP notifications are industry self-classifications (any notifier)
    - REACH dossier Section 2.1 is the registrant's own classification

    This tool automatically selects the best available lead dossier
    (Active > Not active, Article 10-full > Article 18) and parses
    the HTML pages to extract GHS classification entries.

    Args:
        substance_index: ECHA substance index (e.g., '100.000.002')
        cas_number: CAS number of the substance (e.g., '50-00-0')

    Returns:
        JSON string with:
        - substance_index, cas_number
        - dossier_count: number of lead dossiers processed
        - dossiers: list of dossier results, each with:
            - dossier_info: asset_id, registration_number, subtype, role
            - ghs_entries: list of GHS classification entries with
              entry_name, general_information, hazard_categories, labelling
    """
    client = get_client()

    # Find lead dossiers
    lead_dossiers = await find_lead_dossiers(client, substance_index)
    if not lead_dossiers:
        return json.dumps(
            {"error": f"No lead dossiers found for substance {substance_index}"},
            indent=2,
        )

    dossiers_result = []

    for dossier_info in lead_dossiers[:3]:  # Process up to 3 lead dossiers
        asset_id = dossier_info["asset_id"]

        ghs_entries = await parse_section_2_1_ghs(client, asset_id)

        dossiers_result.append({
            "dossier_info": {
                "asset_id": asset_id,
                "registration_number": dossier_info.get("registration_number", ""),
                "subtype": dossier_info.get("subtype", ""),
                "role": dossier_info.get("role", ""),
            },
            "ghs_entries": ghs_entries,
        })

    return json.dumps(
        {
            "substance_index": substance_index,
            "cas_number": cas_number,
            "dossier_count": len(dossiers_result),
            "dossiers": dossiers_result,
        },
        ensure_ascii=False,
        indent=2,
    )


async def get_reach_pbt(substance_index: str, cas_number: str) -> str:
    """
    Get REACH registration PBT assessment data (Section 2.3).

    Retrieves the PBT (Persistent, Bioaccumulative, Toxic) / vPvB assessment
    data from the registrant's REACH dossier. This includes:
    - PBT status summaries
    - Conclusions on P/vP, B/vB, and T properties

    Args:
        substance_index: ECHA substance index (e.g., '100.000.002')
        cas_number: CAS number (e.g., '50-00-0')

    Returns:
        JSON with dossier PBT assessment data including summaries and studies.
    """
    client = get_client()

    lead_dossiers = await find_lead_dossiers(client, substance_index)
    if not lead_dossiers:
        return json.dumps(
            {"error": f"No lead dossiers found for substance {substance_index}"},
            indent=2,
        )

    dossiers_result = []

    for dossier_info in lead_dossiers[:3]:
        asset_id = dossier_info["asset_id"]

        pbt_data = await parse_section_2_3_pbt(client, asset_id)

        dossiers_result.append({
            "dossier_info": {
                "asset_id": asset_id,
                "registration_number": dossier_info.get("registration_number", ""),
                "subtype": dossier_info.get("subtype", ""),
                "role": dossier_info.get("role", ""),
            },
            "pbt_assessment": pbt_data,
        })

    return json.dumps(
        {
            "substance_index": substance_index,
            "cas_number": cas_number,
            "dossier_count": len(dossiers_result),
            "dossiers": dossiers_result,
        },
        ensure_ascii=False,
        indent=2,
    )
