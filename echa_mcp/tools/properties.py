"""MCP Tools: physicochemical and ecotoxicological dossier data."""

import json
from typing import Optional

from ..clients.echa_client import get_client
from ..parsers.dossier_sections import parse_dossier_sections


async def get_physchem_data(
    substance_index: str,
    section: Optional[str] = None,
    max_studies: int = 50,
) -> str:
    """Get physicochemical property data from REACH dossier Section 4."""
    data = await parse_dossier_sections(
        get_client(),
        substance_index,
        ("4",),
        target_section=section,
        max_studies=max_studies,
    )
    return json.dumps(data, ensure_ascii=False, indent=2)


async def get_ecotoxicology_data(
    substance_index: str,
    section: Optional[str] = None,
    max_studies: int = 50,
) -> str:
    """Get environmental fate and ecotoxicology data from REACH dossier Sections 5 and 6."""
    data = await parse_dossier_sections(
        get_client(),
        substance_index,
        ("5", "6"),
        target_section=section,
        max_studies=max_studies,
    )
    return json.dumps(data, ensure_ascii=False, indent=2)
