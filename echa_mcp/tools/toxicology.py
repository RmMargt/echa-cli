"""
MCP Tools: Toxicological Information (Section 7).

Tools:
- echa_get_toxicology_summary: Section 7 summaries + DN(M)ELs only
- echa_get_toxicology_studies: Section 7 individual study records
- echa_get_toxicology_full: Complete Section 7 data (summaries + studies)
"""

import json
import logging
from typing import Optional
from ..clients.echa_client import get_client
from ..parsers.section7_parser import select_best_dossier, parse_section_7

logger = logging.getLogger(__name__)


async def _get_best_dossier_asset(substance_index: str) -> Optional[str]:
    """Find the best dossier and return its asset_id, or None."""
    client = get_client()
    dossier = await select_best_dossier(client, substance_index)
    if not dossier:
        return None
    return dossier.get("asset_id")


async def get_toxicology_summary(substance_index: str) -> str:
    """
    Get toxicological summary data (Section 7) for a substance.

    Returns only summary documents and DN(M)EL (Derived No/Minimal Effect Level)
    values from the best available REACH registration dossier. This is much
    faster than the full toxicology query as it skips individual study records.

    Section 7 subsections covered:
    - 7.1 Toxicokinetics / Dermal absorption
    - 7.2 Acute toxicity (oral, dermal, inhalation)
    - 7.3 Irritation / Corrosion (skin, eye)
    - 7.4 Sensitisation (skin, respiratory)
    - 7.5 Repeated dose toxicity
    - 7.6 Genetic toxicity (in vitro, in vivo)
    - 7.7 Carcinogenicity
    - 7.8 Toxicity to reproduction
    - 7.9 Neurotoxicity / Immunotoxicity
    - 7.10 Human data / Epidemiological data

    Args:
        substance_index: ECHA substance index (e.g., '100.000.002')

    Returns:
        JSON with:
        - dnmels: list of DN(M)EL values
        - sections: dict mapping section number to summaries
    """
    client = get_client()
    dossier = await select_best_dossier(client, substance_index)

    if not dossier:
        return json.dumps(
            {"error": f"No suitable dossier found for substance {substance_index}"},
            indent=2,
        )

    asset_id = dossier["asset_id"]

    # Parse with max_studies=0 to only get summaries
    data = await parse_section_7(client, asset_id, max_studies=0)

    # Only include summaries
    summary_sections = {}
    for sec_num, sec_data in data.get("sections", {}).items():
        summaries = sec_data.get("summaries", [])
        if summaries:
            summary_sections[sec_num] = {"summaries": summaries}

    result = {
        "substance_index": substance_index,
        "dossier_info": {
            "asset_id": asset_id,
            "registration_number": dossier.get("registration_number", ""),
            "subtype": dossier.get("subtype", ""),
            "role": dossier.get("role", ""),
        },
        "dnmels": data.get("dnmels", []),
        "sections": summary_sections,
    }

    return json.dumps(result, ensure_ascii=False, indent=2)


async def get_toxicology_studies(
    substance_index: str, section: str = None, max_studies: int = 50
) -> str:
    """
    Get individual toxicological study records (Section 7).

    Returns study-level data from the REACH registration dossier.
    Can be filtered to a specific subsection for focused queries.

    Args:
        substance_index: ECHA substance index (e.g., '100.000.002')
        section: Optional subsection filter (e.g., '7.2' for acute toxicity only).
            If not specified, returns studies from ALL Section 7 subsections.
        max_studies: Maximum number of studies to parse (default 50)

    Returns:
        JSON with:
        - sections: dict mapping section number to study records
        - Each study includes: name, type, fields (species, route, effect_level, etc.)
    """
    client = get_client()
    dossier = await select_best_dossier(client, substance_index)

    if not dossier:
        return json.dumps(
            {"error": f"No suitable dossier found for substance {substance_index}"},
            indent=2,
        )

    asset_id = dossier["asset_id"]

    data = await parse_section_7(
        client, asset_id, target_section=section, max_studies=max_studies
    )

    # Only include studies
    study_sections = {}
    for sec_num, sec_data in data.get("sections", {}).items():
        studies = sec_data.get("studies", [])
        if studies:
            study_sections[sec_num] = {
                "study_count": len(studies),
                "studies": studies,
            }

    result = {
        "substance_index": substance_index,
        "dossier_info": {
            "asset_id": asset_id,
            "registration_number": dossier.get("registration_number", ""),
        },
        "sections": study_sections,
        "total_studies": sum(
            len(s.get("studies", [])) for s in study_sections.values()
        ),
    }

    if section:
        result["filter_section"] = section

    return json.dumps(result, ensure_ascii=False, indent=2)


async def get_toxicology_full(substance_index: str) -> str:
    """
    Get COMPLETE toxicological data (Section 7) for a substance.

    This is a comprehensive query that retrieves ALL available toxicology data:
    - Summary documents for each subsection
    - Individual study records (up to 400)
    - DN(M)EL (Derived No/Minimal Effect Level) values

    WARNING: This can be slow for substances with many studies, as it downloads
    and parses many HTML pages. Consider using echa_get_toxicology_summary
    for a faster overview, or echa_get_toxicology_studies with a section
    filter for targeted queries.

    Args:
        substance_index: ECHA substance index (e.g., '100.000.002')

    Returns:
        Complete JSON with dnmels, summaries, and studies for all Section 7 subsections.
    """
    client = get_client()
    dossier = await select_best_dossier(client, substance_index)

    if not dossier:
        return json.dumps(
            {"error": f"No suitable dossier found for substance {substance_index}"},
            indent=2,
        )

    asset_id = dossier["asset_id"]

    data = await parse_section_7(client, asset_id, max_studies=100)

    result = {
        "substance_index": substance_index,
        "dossier_info": {
            "asset_id": asset_id,
            "registration_number": dossier.get("registration_number", ""),
            "subtype": dossier.get("subtype", ""),
            "role": dossier.get("role", ""),
        },
        "dnmels": data.get("dnmels", []),
        "sections": data.get("sections", {}),
        "total_summaries": sum(
            len(s.get("summaries", [])) for s in data.get("sections", {}).values()
        ),
        "total_studies": sum(
            len(s.get("studies", [])) for s in data.get("sections", {}).values()
        ),
    }

    return json.dumps(result, ensure_ascii=False, indent=2)
