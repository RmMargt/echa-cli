"""
Section 2 Parser: GHS Classification (2.1) and PBT Assessment (2.3).

Ported from 单个物质信息抓取.py (ECHASection2Parser class).
Converts synchronous requests + HTML parsing to async functions returning dicts.
"""

import re
import logging
from typing import Optional
from bs4 import BeautifulSoup

from ..clients.echa_client import ECHAClient
from .common import extract_field_value, clean_value

logger = logging.getLogger(__name__)


# ─── Dossier Selection ────────────────────────────────────────

async def find_lead_dossiers(client: ECHAClient, substance_index: str) -> list[dict]:
    """
    Find all 'lead' dossiers for a substance (Active + Article 10-full preferred).

    Returns list of dossier info dicts with keys:
    - asset_id, registration_number, subtype, role, status, date, url
    """
    lead_dossiers = []

    for status in ["Active", "Not active"]:
        data = await client.get_dossier_list(substance_index, status=status)
        if not data:
            continue

        results = data.get("items", [])
        for d in results:
            asset_id = d.get("assetExternalId", "")
            if not asset_id:
                continue

            reach_info = d.get("reachDossierInfo", {}) or {}
            subtype = reach_info.get("dossierSubtype", "")
            role = reach_info.get("registrationRole", "")

            # Only interested in full registrations with lead role
            if "Lead" not in role:
                continue

            dossier_info = {
                "asset_id": asset_id,
                "registration_number": d.get("registrationNumber", ""),
                "subtype": subtype,
                "role": role,
                "status": status,
                "date": d.get("lastUpdatedDate", ""),
                "url": f"https://chem.echa.europa.eu/html-pages-prod/{asset_id}/index.html",
            }
            lead_dossiers.append(dossier_info)

        if lead_dossiers:
            break  # Prefer Active dossiers, only fallback to Not active

    # Sort: Article 10-full > Article 18 > others
    def sort_key(d):
        s = d["subtype"]
        if "Article 10" in s and "full" in s.lower():
            return 0
        elif "Article 10" in s:
            return 1
        elif "Article 18" in s:
            return 2
        return 3

    lead_dossiers.sort(key=sort_key)
    return lead_dossiers


# ─── Section 2.1 GHS Parser ──────────────────────────────────

async def parse_section_2_1_ghs(
    client: ECHAClient, asset_id: str
) -> list[dict]:
    """
    Parse Section 2.1 GHS classification entries from a dossier.

    Returns list of GHS entry dicts with keys:
    - entry_name, general_information, hazard_categories, labelling
    """
    index_html = await client.get_dossier_index(asset_id)
    if not index_html:
        return []

    # Find Section 2.1 document links
    doc_links = _scan_section_docs(index_html, section="2.1")
    if not doc_links:
        logger.info("No Section 2.1 documents found for asset %s", asset_id)
        return []

    entries = []

    # Process summaries first, then studies
    summaries = [d for d in doc_links if d["type"] == "Summary"]
    studies = [d for d in doc_links if d["type"] == "Study"]

    for doc in summaries + studies:
        html = await client.get_document_html(asset_id, doc["doc_id"])
        if not html:
            continue

        try:
            entry = _parse_ghs_document(html, doc["name"])
            if entry:
                entries.append(entry)
        except Exception as e:
            logger.warning("Failed to parse GHS doc %s: %s", doc["doc_id"], e)

    return entries


def _parse_ghs_document(html: str, name: str) -> Optional[dict]:
    """Parse a single GHS classification document HTML."""
    soup = BeautifulSoup(html, "html.parser")

    entry = {"entry_name": name, "general_information": {}, "hazard_categories": [], "labelling": {}}

    # General information fields
    gi = entry["general_information"]
    gi["Name"] = extract_field_value(soup, "Name")
    gi["NotClassified"] = extract_field_value(soup, "Not classified")
    gi["Implementation"] = extract_field_value(soup, "Implementation")
    gi["TypeClassification"] = extract_field_value(soup, "Type of classification")
    gi["Remarks"] = extract_field_value(soup, "Remarks")
    gi["Composition"] = extract_field_value(soup, "Related composition")

    # Hazard categories - look for the classification table or list
    for row in soup.find_all(class_="das-field_value"):
        text = row.get_text(strip=True)
        # Match patterns like "Acute Tox. 4 (Oral)" or "Skin Corr. 1A"
        if re.search(r"(?:Acute|Skin|Eye|Resp\.|Muta\.|Carc\.|Repr\.|STOT|Asp\.|Aquatic|Flam)", text):
            cats = [c.strip() for c in text.split(",") if c.strip()]
            for cat in cats:
                if cat and cat not in entry["hazard_categories"]:
                    entry["hazard_categories"].append(cat)

    # Labelling
    lab = entry["labelling"]
    lab["SignalWord"] = extract_field_value(soup, "Signal word")
    lab["HazardPictogram"] = extract_field_value(soup, "Hazard pictogram")
    lab["HazardStatements"] = extract_field_value(soup, "Hazard statements")
    lab["PrecautionaryStatements"] = extract_field_value(soup, "Precautionary statements")

    return entry


# ─── Section 2.3 PBT Parser ──────────────────────────────────

async def parse_section_2_3_pbt(
    client: ECHAClient, asset_id: str
) -> dict:
    """
    Parse Section 2.3 PBT assessment data from a dossier.

    Returns dict with keys:
    - summaries: list of PBT assessment summaries
    - studies: list of PBT assessment studies
    """
    index_html = await client.get_dossier_index(asset_id)
    if not index_html:
        return {"summaries": [], "studies": []}

    doc_links = _scan_section_docs(index_html, section="2.3")
    if not doc_links:
        return {"summaries": [], "studies": []}

    summaries = []
    studies = []

    for doc in doc_links:
        html = await client.get_document_html(asset_id, doc["doc_id"])
        if not html:
            continue

        try:
            parsed = _parse_pbt_document(html, doc["name"], doc["type"])
            if doc["type"] == "Summary":
                summaries.append(parsed)
            else:
                studies.append(parsed)
        except Exception as e:
            logger.warning("Failed to parse PBT doc %s: %s", doc["doc_id"], e)

    return {"summaries": summaries, "studies": studies}


def _parse_pbt_document(html: str, name: str, doc_type: str) -> dict:
    """Parse a single PBT assessment document."""
    soup = BeautifulSoup(html, "html.parser")

    result = {
        f"{'summary' if doc_type == 'Summary' else 'study'}_name": name,
        "data": {},
    }

    data = result["data"]

    if doc_type == "Summary":
        data["pbt_status"] = extract_field_value(soup, "PBT status")
    else:
        data["conclusion_on_p_vp"] = extract_field_value(soup, "Conclusion on P / vP")
        data["conclusion_on_b_vb"] = extract_field_value(soup, "Conclusion on B / vB")
        data["conclusion_on_t"] = extract_field_value(soup, "Conclusion on T")

    return result


# ─── Document Link Scanning ──────────────────────────────────

def _scan_section_docs(index_html: str, section: str) -> list[dict]:
    """
    Scan index.html for document links under a given section (e.g., '2.1', '2.3').

    Returns list of dicts with keys: doc_id, name, type
    """
    soup = BeautifulSoup(index_html, "html.parser")
    docs = []

    # Find all document links
    # ECHA uses two href formats:
    #   Old: documents/12345.html
    #   New: {uuid}_{uuid}  (UUID_UUID, no path prefix, no .html)
    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        # Try old numeric format
        match = re.search(r"documents/(\d+)\.html", href)
        if match:
            doc_id = match.group(1)
        else:
            # Try new UUID format: {uuid}_{uuid} (class="das-leaf das-docid-...")
            uuid_match = re.match(
                r"^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_"
                r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$",
                href,
            )
            if not uuid_match:
                continue
            doc_id = uuid_match.group(1)

        name = link.get_text(strip=True)

        # Check if this link belongs to the target section
        # Look for section indicators in parent elements
        parent_text = ""
        current = link.parent
        depth = 0
        while current and depth < 10:
            if hasattr(current, "get_text"):
                parent_text = current.get_text(strip=True)[:200]
                # Look for section pattern like "2.1" or "2.3"
                if re.search(rf"(?:^|\s|\|){re.escape(section)}(?:\s|\||$)", parent_text):
                    break
                # Also check element IDs/classes
                el_id = current.get("id", "")
                el_class = " ".join(current.get("class", []))
                section_normalized = section.replace(".", "_")
                if section_normalized in el_id or section_normalized in el_class:
                    break
            current = current.parent
            depth += 1
        else:
            continue  # Not in target section

        doc_type = "Summary" if ("summary" in name.lower() or "S-" in name) else "Study"
        docs.append({"doc_id": doc_id, "name": name, "type": doc_type})

    return docs
