"""
Section 7 Parser: Toxicological Information.

Ported from ECHA_Toxicology.py (ECHAToxicologyScraperV71 class).
Converts synchronous HTML scraping to async functions returning structured dicts.
"""

import re
import logging
from typing import Optional
from bs4 import BeautifulSoup

from ..clients.echa_client import ECHAClient
from .common import extract_field_value, extract_all_field_values, clean_value

logger = logging.getLogger(__name__)

# Section 7 subsection mapping (endpoint text → section number)
ENDPOINT_TO_SECTION = {
    "basic toxicokinetics": "7.1",
    "dermal absorption": "7.1",
    "acute toxicity: oral": "7.2",
    "acute toxicity: inhalation": "7.2",
    "acute toxicity: dermal": "7.2",
    "acute toxicity: other routes": "7.2",
    "skin irritation": "7.3",
    "eye irritation": "7.3",
    "skin sensitisation": "7.4",
    "respiratory sensitisation": "7.4",
    "repeated dose toxicity: oral": "7.5",
    "repeated dose toxicity: inhalation": "7.5",
    "repeated dose toxicity: dermal": "7.5",
    "repeated dose toxicity: other": "7.5",
    "genetic toxicity in vitro": "7.6",
    "genetic toxicity in vivo": "7.6",
    "carcinogenicity": "7.7",
    "toxicity to reproduction": "7.8",
    "developmental toxicity / teratogenicity": "7.8",
    "toxicity to reproduction: other studies": "7.8",
    "neurotoxicity": "7.9",
    "immunotoxicity": "7.9",
    "specific investigations: other studies": "7.9",
    "health surveillance data": "7.10",
    "epidemiological data": "7.10",
    "direct observations: clinical cases": "7.10",
    "exposure related observations in humans": "7.10",
}


def identify_section(endpoint_text: str) -> str:
    """Map endpoint description text to Section 7 subsection number."""
    text_lower = endpoint_text.strip().lower()
    for pattern, section in ENDPOINT_TO_SECTION.items():
        if pattern in text_lower:
            return section
    return "7.0"  # Unknown subsection


# ─── Dossier Selection ────────────────────────────────────────

async def select_best_dossier(client: ECHAClient, substance_index: str) -> Optional[dict]:
    """
    Find the best dossier for toxicology data.

    Priority: Active > Not active, Article 10 full > Article 18, Lead role preferred.
    """
    for status in ["Active", "Not active"]:
        data = await client.get_dossier_list(substance_index, status=status)
        if not data:
            continue

        results = data.get("items", [])
        if not results:
            continue

        # Score each dossier
        scored = []
        for d in results:
            asset_id = d.get("assetExternalId", "")
            if not asset_id:
                continue

            score = 0
            reach_info = d.get("reachDossierInfo", {}) or {}
            subtype = reach_info.get("dossierSubtype", "")
            role = reach_info.get("registrationRole", "")

            if "Article 10" in subtype and "full" in subtype.lower():
                score += 10
            elif "Article 10" in subtype:
                score += 5
            elif "Article 18" in subtype:
                score += 1

            if "Lead" in role:
                score += 3

            scored.append({
                "asset_id": asset_id,
                "registration_number": d.get("registrationNumber", ""),
                "subtype": subtype,
                "role": role,
                "status": status,
                "date": d.get("lastUpdatedDate", ""),
                "score": score,
            })

        if scored:
            scored.sort(key=lambda x: x["score"], reverse=True)
            return scored[0]

    return None


# ─── Section 7 Parsing ───────────────────────────────────────

async def parse_section_7(
    client: ECHAClient,
    asset_id: str,
    target_section: Optional[str] = None,
    max_studies: int = 400,
) -> dict:
    """
    Parse Section 7 toxicological data from a dossier.

    Args:
        client: ECHA async client
        asset_id: Dossier asset external ID
        target_section: If specified, only parse this subsection (e.g., "7.2")
        max_studies: Maximum number of study documents to process

    Returns dict with keys:
    - dossier_info: basic dossier info
    - dnmels: Derived No/Minimal Effect Levels
    - sections: dict mapping section number → {"summaries": [...], "studies": [...]}
    """
    index_html = await client.get_dossier_index(asset_id)
    if not index_html:
        return {"error": f"Could not load dossier index for {asset_id}"}

    # Scan for Section 7 documents
    all_docs = _scan_section7_docs(index_html)

    if target_section:
        # Filter to only the requested subsection
        filtered = {k: v for k, v in all_docs.items() if k == target_section}
        all_docs = filtered

    result = {
        "dossier_info": {"asset_id": asset_id},
        "dnmels": [],
        "sections": {},
    }

    # Process each subsection
    study_count = 0

    for section_num, docs in sorted(all_docs.items()):
        section_data = {"summaries": [], "studies": []}

        # Process summaries first
        summaries = [d for d in docs if d["type"] == "Summary"]
        for doc in summaries:
            html = await client.get_document_html(asset_id, doc["doc_id"])
            if not html:
                continue
            try:
                soup = BeautifulSoup(html, "html.parser")
                del html  # Release raw HTML early
                parsed = _parse_toxicology_document_from_soup(soup, doc["name"], "Summary", section_num)
                section_data["summaries"].append(parsed)

                # Extract DN(M)ELs from summaries — reuse existing soup
                dnmels = _extract_dnmels_from_soup(soup)
                if dnmels:
                    result["dnmels"].extend(dnmels)
                del soup  # Release soup after use
            except Exception as e:
                logger.warning("Failed to parse summary %s: %s", doc["doc_id"], e)

        # Process studies (limited)
        studies = [d for d in docs if d["type"] == "Study"]
        for doc in studies:
            if study_count >= max_studies:
                break
            html = await client.get_document_html(asset_id, doc["doc_id"])
            if not html:
                continue
            try:
                parsed = _parse_toxicology_document(html, doc["name"], "Study", section_num)
                section_data["studies"].append(parsed)
                study_count += 1
                del html  # Release raw HTML early
            except Exception as e:
                logger.warning("Failed to parse study %s: %s", doc["doc_id"], e)

        result["sections"][section_num] = section_data

    return result


def _parse_toxicology_document(
    html: str, name: str, doc_type: str, section: str
) -> dict:
    """Parse a single toxicology document (Summary or Study)."""
    soup = BeautifulSoup(html, "html.parser")
    return _parse_toxicology_document_from_soup(soup, name, doc_type, section)


def _parse_toxicology_document_from_soup(
    soup: BeautifulSoup, name: str, doc_type: str, section: str
) -> dict:
    """Parse a single toxicology document from a pre-parsed BeautifulSoup object."""

    result = {
        "name": name,
        "type": doc_type,
        "section": section,
        "fields": {},
    }

    fields = result["fields"]

    # Common fields across all document types
    fields["endpoint"] = extract_field_value(soup, "Endpoint")
    fields["type_of_information"] = extract_field_value(soup, "Type of information")
    fields["adequacy"] = extract_field_value(soup, "Adequacy of study")
    fields["reliability"] = extract_field_value(soup, "Reliability")

    if doc_type == "Study":
        # Study-specific fields
        fields["guideline"] = extract_field_value(soup, "Guideline")
        fields["qualifier"] = extract_field_value(soup, "Qualifier")
        fields["glp"] = extract_field_value(soup, "GLP compliance")
        fields["species"] = extract_field_value(soup, "Species")
        fields["strain"] = extract_field_value(soup, "Strain")
        fields["sex"] = extract_field_value(soup, "Sex")
        fields["route"] = extract_field_value(soup, "Route of administration")
        fields["vehicle"] = extract_field_value(soup, "Vehicle")
        fields["dose_descriptor"] = extract_field_value(soup, "Dose descriptor")
        fields["effect_level"] = extract_field_value(soup, "Effect level")
        fields["basis_for_effect"] = extract_field_value(soup, "Basis for effect level")

        # Results / Conclusions
        fields["results"] = extract_field_value(soup, "Results")
        fields["conclusions"] = extract_field_value(soup, "Conclusions")
        fields["executive_summary"] = extract_field_value(soup, "Executive summary")

        # Specific fields for certain sections
        if section in ("7.6",):  # Genetic toxicity
            fields["test_type"] = extract_field_value(soup, "Test type")
            fields["metabolic_activation"] = extract_field_value(soup, "Metabolic activation")
            fields["genotoxicity"] = extract_field_value(soup, "Genotoxicity")
            fields["cytotoxicity"] = extract_field_value(soup, "Cytotoxicity")

        if section in ("7.3",):  # Irritation
            fields["irritation_parameter"] = extract_field_value(soup, "Parameter")
            fields["score"] = extract_field_value(soup, "Score")

        if section in ("7.4",):  # Sensitisation
            fields["test_system"] = extract_field_value(soup, "Test system")

    else:  # Summary
        fields["key_value_for_csr"] = extract_field_value(soup, "Key value for chemical safety assessment")
        fields["discussion"] = extract_field_value(soup, "Discussion")
        fields["long_description"] = extract_field_value(soup, "Description of key information")
        fields["additional_information"] = extract_field_value(soup, "Additional information")

    return result


def _extract_dnmels(html: str) -> list[dict]:
    """Extract DN(M)EL values from a summary document."""
    soup = BeautifulSoup(html, "html.parser")
    return _extract_dnmels_from_soup(soup)


def _extract_dnmels_from_soup(soup: BeautifulSoup) -> list[dict]:
    dnmels = []

    # Look for DNEL/DMEL tables or sections
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]

        # Check if this looks like a DNEL table
        if not any("dnel" in h or "dmel" in h or "most sensitive" in h for h in headers):
            # Also check text before the table
            prev_text = ""
            prev = table.find_previous()
            if prev:
                prev_text = prev.get_text(strip=True).lower()
            if "dnel" not in prev_text and "dmel" not in prev_text and "derived" not in prev_text:
                continue

        for tr in table.find_all("tr")[1:]:
            cells = tr.find_all("td")
            if len(cells) >= 2:
                row = {}
                for i, cell in enumerate(cells):
                    key = headers[i] if i < len(headers) else f"col_{i}"
                    row[key] = clean_value(cell.get_text(strip=True))
                if any(v for v in row.values()):
                    dnmels.append(row)

    # Also look for individual DNEL fields
    for label_text in [
        "DNEL (Workers, acute, systemic, inhalation)",
        "DNEL (Workers, chronic, systemic, inhalation)",
        "DNEL (Workers, acute, systemic, dermal)",
        "DNEL (Workers, chronic, systemic, dermal)",
        "DNEL (Workers, acute, local, inhalation)",
        "DNEL (Workers, chronic, local, inhalation)",
        "DNEL (General population, acute, systemic, inhalation)",
        "DNEL (General population, chronic, systemic, inhalation)",
        "DNEL (General population, acute, systemic, dermal)",
        "DNEL (General population, chronic, systemic, dermal)",
        "DNEL (General population, acute, systemic, oral)",
        "DNEL (General population, chronic, systemic, oral)",
    ]:
        value = extract_field_value(soup, label_text)
        if value:
            dnmels.append({"type": label_text, "value": value})

    return dnmels


# ─── Section 7 Document Link Scanning ─────────────────────────

def _scan_section7_docs(index_html: str) -> dict[str, list[dict]]:
    """
    Scan dossier index.html for Section 7 (Toxicological information) documents.

    Returns dict mapping subsection (e.g., "7.2") to list of doc dicts.
    """
    soup = BeautifulSoup(index_html, "html.parser")
    sections: dict[str, list[dict]] = {}

    # Strategy 1: Look for section headings and their child links
    for heading in soup.find_all(["h2", "h3", "h4", "span", "div", "a"]):
        text = heading.get_text(strip=True)

        # Match section numbers like "7.2", "7.3.1"
        match = re.match(r"^(7\.\d+(?:\.\d+)?)\s", text)
        if not match:
            continue

        section_num = match.group(1)
        # Normalize to main subsection (7.2.1 → 7.2)
        parts = section_num.split(".")
        if len(parts) > 2:
            section_num = f"{parts[0]}.{parts[1]}"

    # Strategy 2: Find all document links and infer section from context
    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        match = re.search(r"documents/(\d+)\.html", href)
        if not match:
            continue

        doc_id = match.group(1)
        name = link.get_text(strip=True)

        # Try to determine section from endpoint text in the link name or nearby text
        section_num = _infer_section_from_context(link, name)
        if not section_num or not section_num.startswith("7"):
            continue

        doc_type = "Summary" if ("summary" in name.lower() or name.startswith("S-")) else "Study"
        doc_info = {"doc_id": doc_id, "name": name, "type": doc_type}

        if section_num not in sections:
            sections[section_num] = []
        sections[section_num].append(doc_info)

    return sections


def _infer_section_from_context(link_el, name: str) -> Optional[str]:
    """Infer section number from link element context."""
    # Check the link name for endpoint keywords
    section = identify_section(name)
    if section != "7.0":
        return section

    # Walk up the DOM for section indicators
    current = link_el.parent
    depth = 0
    while current and depth < 15:
        text = ""
        if hasattr(current, "get_text"):
            text = current.get_text(strip=True)[:300]

        # Look for section number in element text
        match = re.search(r"(7\.\d+)", text)
        if match:
            return match.group(1)

        # Check element ID
        el_id = current.get("id", "") if hasattr(current, "get") else ""
        id_match = re.search(r"7[_.-](\d+)", el_id)
        if id_match:
            return f"7.{id_match.group(1)}"

        current = current.parent
        depth += 1

    return None
