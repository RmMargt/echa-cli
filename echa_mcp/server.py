#!/usr/bin/env python3
"""
ECHA Chemical Data MCP Server.

Provides tools to query European Chemicals Agency (ECHA) data:
- Substance basic info (CAS, EC, names)
- CLP notification classification (industry self-classification)
- Harmonised classification (Annex VI, CLP Regulation)
- REACH registration classification (dossier Section 2.1 GHS, 2.3 PBT)
- Toxicological information (dossier Section 7)

Also exposes H-code mapping table as an MCP Resource.
"""

import json
import logging

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    raise ImportError(
        "MCP SDK is required for the server. "
        "Install with: pip install echa-cli[mcp]"
    )

from .models.substance import SubstanceInfoInput, DossierListInput
from .models.classification import (
    CLPClassificationInput,
    HarmonisedClassificationInput,
    REACHGHSInput,
    REACHPBTInput,
)
from .models.toxicology import (
    ToxicologySummaryInput,
    ToxicologyStudiesInput,
    ToxicologyFullInput,
)
from .tools.substance import get_substance_info, list_dossiers
from .tools.clp_classification import get_clp_classification
from .tools.harmonised_classification import get_harmonised_classification
from .tools.reach_classification import get_reach_ghs, get_reach_pbt
from .tools.toxicology import (
    get_toxicology_summary,
    get_toxicology_studies,
    get_toxicology_full,
)
from .data.hcode_mapping import get_hcode_mapping_markdown, get_hcode_mapping_json
from .clients.echa_client import get_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

# ─── Initialize MCP Server ───────────────────────────────────

mcp = FastMCP("echa_mcp", host="0.0.0.0", port=7082)


# ─── Graceful Shutdown ───────────────────────────────────────

import atexit
import signal
import asyncio


async def _shutdown_client():
    """Close the httpx client to release connection pool resources."""
    client = get_client()
    await client.close()
    logging.getLogger(__name__).info("ECHA client closed gracefully.")


def _handle_shutdown(*args):
    """Sync shutdown handler for atexit/signals."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_shutdown_client())
        else:
            loop.run_until_complete(_shutdown_client())
    except Exception:
        pass  # Best effort


atexit.register(_handle_shutdown)
signal.signal(signal.SIGTERM, _handle_shutdown)
signal.signal(signal.SIGINT, _handle_shutdown)


# ─── Tool Registration ───────────────────────────────────────

# Domain 1: Substance Basic Information

@mcp.tool(
    name="echa_get_substance_info",
    annotations={
        "title": "Get ECHA Substance Info",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def tool_get_substance_info(substance_index: str) -> str:
    """Get basic information for a chemical substance from ECHA CHEM database.

    Retrieves CAS number, EC number, chemical names, IUPAC name,
    and molecular formula for a given substance index.

    Args:
        substance_index: ECHA substance index (e.g., '100.000.002' for Formaldehyde)

    Returns:
        JSON with substance identifiers and names
    """
    return await get_substance_info(substance_index)


@mcp.tool(
    name="echa_list_dossiers",
    annotations={
        "title": "List ECHA REACH Dossiers",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def tool_list_dossiers(substance_index: str, status: str = "Active", max_results: int = 10) -> str:
    """List REACH registration dossiers for a substance.

    Returns all REACH registration dossiers including registration numbers,
    types (Article 10-full, Article 18), and registrant roles.
    Sorted by last updated date (newest first). Defaults to 10 results.

    Args:
        substance_index: ECHA substance index (e.g., '100.000.002')
        status: Registration status filter: 'Active' or 'Not active'
        max_results: Maximum number of dossiers to return (default 10)

    Returns:
        JSON with dossier list including asset IDs and registration details
    """
    return await list_dossiers(substance_index, status, max_results)


# Domain 2: CLP Classification (Industry Notification)

@mcp.tool(
    name="echa_get_clp_classification",
    annotations={
        "title": "Get CLP Notification Classification",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def tool_get_clp_classification(substance_index: str, max_results: int = 5) -> str:
    """Get CLP notification (industry self-classification) data.

    Retrieves all CLP self-classifications notified by industry under the
    CLP Regulation. Includes hazard categories, H-codes, signal words,
    pictograms, SCL, and M-factors.
    Sorted by notification percentage (most common first). Defaults to top 5.

    For the official EU harmonised classification, use echa_get_harmonised_classification.

    Args:
        substance_index: ECHA substance index (e.g., '100.000.002')
        max_results: Maximum number of classification entries to return (default 5)

    Returns:
        JSON with all notification classifications and their details
    """
    return await get_clp_classification(substance_index, max_results)


# Domain 2b: Harmonised Classification (Annex VI)

@mcp.tool(
    name="echa_get_harmonised_classification",
    annotations={
        "title": "Get Harmonised Classification (Annex VI)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def tool_get_harmonised_classification(substance_index: str) -> str:
    """Get harmonised classification (Annex VI, CLP Regulation).

    Returns the official EU classification adopted by the European Commission.
    Not all substances have harmonised classifications. Includes hazard categories,
    H-codes, SCL, M-factors, ATE values, and regulatory notes.

    Args:
        substance_index: ECHA substance index (e.g., '100.000.002')

    Returns:
        JSON with harmonised classification data or indication that none exists
    """
    return await get_harmonised_classification(substance_index)


# Domain 3: REACH Registration Classification (HTML)

@mcp.tool(
    name="echa_get_reach_ghs",
    annotations={
        "title": "Get REACH GHS Classification (Section 2.1)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def tool_get_reach_ghs(substance_index: str, cas_number: str) -> str:
    """Get GHS classification from REACH registration dossier (Section 2.1).

    Retrieves the registrant's own GHS hazard classification from their
    REACH dossier. This may differ from CLP notifications.

    Args:
        substance_index: ECHA substance index (e.g., '100.000.002')
        cas_number: CAS number (e.g., '50-00-0')

    Returns:
        JSON with GHS classification entries from lead dossiers
    """
    return await get_reach_ghs(substance_index, cas_number)


@mcp.tool(
    name="echa_get_reach_pbt",
    annotations={
        "title": "Get REACH PBT Assessment (Section 2.3)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def tool_get_reach_pbt(substance_index: str, cas_number: str) -> str:
    """Get PBT assessment from REACH registration dossier (Section 2.3).

    Retrieves PBT/vPvB assessment data including PBT status and
    conclusions on Persistence, Bioaccumulation, and Toxicity properties.

    Args:
        substance_index: ECHA substance index (e.g., '100.000.002')
        cas_number: CAS number (e.g., '50-00-0')

    Returns:
        JSON with PBT assessment summaries and study conclusions
    """
    return await get_reach_pbt(substance_index, cas_number)


# Domain 4: Toxicological Information (HTML)

@mcp.tool(
    name="echa_get_toxicology_summary",
    annotations={
        "title": "Get Toxicology Summary (Section 7 - Fast)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def tool_get_toxicology_summary(substance_index: str) -> str:
    """Get toxicology summary and DN(M)ELs from REACH dossier (Section 7).

    Returns ONLY summary documents and DNEL/DMEL values. This is much
    faster than the full query. Use this for a quick overview of
    toxicological endpoints.

    Sections: 7.1-7.10 (toxicokinetics, acute tox, irritation,
    sensitisation, repeated dose, genotox, carcinogenicity,
    reproductive tox, neurotox/immunotox, human data)

    Args:
        substance_index: ECHA substance index (e.g., '100.000.002')

    Returns:
        JSON with DN(M)ELs and summary data per section
    """
    return await get_toxicology_summary(substance_index)


@mcp.tool(
    name="echa_get_toxicology_studies",
    annotations={
        "title": "Get Toxicology Studies (Section 7)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def tool_get_toxicology_studies(substance_index: str, section: str = None, max_studies: int = 50) -> str:
    """Get individual toxicology study records from REACH dossier.

    Returns study-level data with species, route, effect levels, and conclusions.
    Can be filtered to a specific subsection (e.g., '7.2' for acute toxicity).

    Args:
        substance_index: ECHA substance index (e.g., '100.000.002')
        section: Optional section filter (e.g., '7.2' for acute toxicity)
        max_studies: Maximum number of studies to parse (default 50)

    Returns:
        JSON with study records per section
    """
    return await get_toxicology_studies(substance_index, section, max_studies)


@mcp.tool(
    name="echa_get_toxicology_full",
    annotations={
        "title": "Get Complete Toxicology Data (Section 7 - Slow)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def tool_get_toxicology_full(substance_index: str) -> str:
    """Get COMPLETE toxicology data from REACH dossier (Section 7).

    Downloads and parses ALL summaries and studies (up to 400).
    WARNING: This can be very slow for data-rich substances.

    For faster alternatives:
    - echa_get_toxicology_summary: summaries + DNELs only
    - echa_get_toxicology_studies: studies with optional section filter

    Args:
        substance_index: ECHA substance index (e.g., '100.000.002')

    Returns:
        Complete JSON with DN(M)ELs, summaries, and studies
    """
    return await get_toxicology_full(substance_index)


# ─── MCP Resource: H-code Mapping ────────────────────────────

@mcp.resource("echa://hcode-mapping")
async def resource_hcode_mapping() -> str:
    """GHS Hazard Category to H-code mapping table.

    Reference table mapping GHS hazard category short codes
    (e.g., 'Acute Tox. 4 (Oral)') to H statement codes (e.g., 'H302').
    Covers physical, health, and environmental hazards.
    """
    return get_hcode_mapping_markdown()


@mcp.resource("echa://hcode-mapping-json")
async def resource_hcode_mapping_json() -> str:
    """GHS Hazard Category to H-code mapping as JSON dict."""
    return json.dumps(get_hcode_mapping_json(), indent=2)


# ─── Entry Point ──────────────────────────────────────────────

def main():
    """Run the ECHA MCP server with Streamable HTTP transport."""
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
