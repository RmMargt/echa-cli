"""
Common HTML parsing utilities shared by Section 2 and Section 7 parsers.

Provides field extraction, document link scanning, and value cleaning
from ECHA dossier HTML pages.
"""

import re
from typing import Optional
from bs4 import BeautifulSoup, Tag


# ─── HTML Field Extraction ────────────────────────────────────

def extract_field_value(container: Tag, label_text: str) -> str:
    """
    Extract value from ECHA's label/value pair HTML structure.

    Structure pattern:
        <div class="das-field_label">Label:</div>
        <div class="das-field_value">Value</div>
    """
    for label_el in container.find_all(class_="das-field_label"):
        if label_text.lower() in label_el.get_text(strip=True).lower():
            value_el = label_el.find_next_sibling(class_="das-field_value")
            if value_el:
                return clean_value(value_el.get_text(strip=True))
    return ""


def extract_all_field_values(container: Tag, label_text: str) -> list[str]:
    """Extract all matching values for a given label (some fields repeat)."""
    values = []
    for label_el in container.find_all(class_="das-field_label"):
        if label_text.lower() in label_el.get_text(strip=True).lower():
            value_el = label_el.find_next_sibling(class_="das-field_value")
            if value_el:
                v = clean_value(value_el.get_text(strip=True))
                if v:
                    values.append(v)
    return values


def extract_table_data(container: Tag) -> list[dict[str, str]]:
    """Extract data from an HTML table within a container."""
    table = container.find("table")
    if not table:
        return []

    rows = []
    headers = []
    for th in table.find_all("th"):
        headers.append(th.get_text(strip=True))

    for tr in table.find_all("tr")[1:]:  # skip header row
        cells = tr.find_all("td")
        if cells:
            row = {}
            for i, cell in enumerate(cells):
                key = headers[i] if i < len(headers) else f"col_{i}"
                row[key] = clean_value(cell.get_text(strip=True))
            rows.append(row)

    return rows


# ─── Value Cleaning ──────────────────────────────────────────

EMPTY_MARKERS = {
    "", "-", "—", "[Empty]", "[Not publishable]",
    "not specified", "not available", "no data",
}

# Pre-computed for hot-path clean_value function
_EMPTY_MARKERS_LOWER = frozenset(m.lower() for m in EMPTY_MARKERS)


def clean_value(text: str) -> str:
    """Clean extracted text value, removing ECHA-specific empty markers."""
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    if text.lower() in _EMPTY_MARKERS_LOWER:
        return ""
    return text


def clean_multiline(text: str) -> str:
    """Clean multi-line text, preserving meaningful line breaks."""
    if not text:
        return ""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n".join(lines)


# ─── Document Link Scanning ──────────────────────────────────

def scan_document_links(
    index_html: str, section_prefix: str
) -> tuple[list[dict], list[dict]]:
    """
    Scan dossier index.html for document links under a specific section.

    Args:
        index_html: The full HTML content of the dossier index page.
        section_prefix: The section number prefix to filter by (e.g., "7" for Section 7,
                        "2.1" for Section 2.1 GHS).

    Returns:
        Tuple of (summary_docs, study_docs), each a list of dicts with:
        - doc_id: document ID for URL construction
        - name: document display name
        - type: "Summary" or "Study"
    """
    soup = BeautifulSoup(index_html, "html.parser")
    summaries = []
    studies = []

    # Find all document links in the index
    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        name = link.get_text(strip=True)

        # Match pattern: documents/{doc_id}.html
        match = re.search(r"documents/(\d+)\.html", href)
        if not match:
            continue

        doc_id = match.group(1)

        # Determine if this link belongs to the target section
        # Check parent elements for section markers
        if not _is_in_section(link, section_prefix):
            continue

        doc_info = {"doc_id": doc_id, "name": name}

        if "summary" in name.lower() or name.startswith("S-"):
            doc_info["type"] = "Summary"
            summaries.append(doc_info)
        else:
            doc_info["type"] = "Study"
            studies.append(doc_info)

    return summaries, studies


def scan_all_section_links(index_html: str) -> dict[str, list[dict]]:
    """
    Scan index.html and group all document links by their section number.

    Returns a dict like:
    {
        "7.2": [{"doc_id": "123", "name": "...", "type": "Study"}, ...],
        "2.1": [...],
    }
    """
    soup = BeautifulSoup(index_html, "html.parser")
    sections: dict[str, list[dict]] = {}

    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        name = link.get_text(strip=True)

        match = re.search(r"documents/(\d+)\.html", href)
        if not match:
            continue

        doc_id = match.group(1)
        section = _detect_section(link)
        if not section:
            continue

        doc_type = "Summary" if ("summary" in name.lower() or name.startswith("S-")) else "Study"
        doc_info = {"doc_id": doc_id, "name": name, "type": doc_type}

        if section not in sections:
            sections[section] = []
        sections[section].append(doc_info)

    return sections


def _is_in_section(el: Tag, section_prefix: str) -> bool:
    """Check if an element is within a section matching the prefix."""
    # Walk up the DOM looking for section indicators
    current = el.parent
    while current:
        text = current.get_text(strip=True) if hasattr(current, "get_text") else ""
        # Look for section number patterns like "7.2" or "2.1"
        if re.search(rf"(?:^|\s){re.escape(section_prefix)}(?:\.\d+)?(?:\s|$)", text[:50]):
            return True
        # Check id and class attributes
        attrs = current.get("id", "") + " " + " ".join(current.get("class", []))
        if section_prefix.replace(".", "_") in attrs or section_prefix.replace(".", "-") in attrs:
            return True
        current = current.parent
        # Don't search too far up
        if current and current.name == "body":
            break
    return False


def _detect_section(el: Tag) -> Optional[str]:
    """Detect the section number for a document link element."""
    current = el.parent
    while current:
        el_id = current.get("id", "")
        # Common ECHA patterns: "section_7_2", "section-7-2"
        match = re.search(r"section[_-](\d+(?:[_-]\d+)*)", el_id)
        if match:
            return match.group(1).replace("_", ".").replace("-", ".")
        current = current.parent
        if current and current.name == "body":
            break
    return None


# ─── Substance Name Selection ────────────────────────────────

def select_best_name(names: list[str]) -> str:
    """
    Select the best chemical name from a list of candidates.

    Preferred: shortest name that looks like a common/IUPAC name (not a UUID).
    """
    if not names:
        return ""

    # Filter out UUIDs and very long identifiers
    candidates = [n for n in names if len(n) < 200 and not re.search(r"[0-9a-f]{8}-", n)]
    if not candidates:
        candidates = names

    # Sort by length, prefer shorter common names
    candidates.sort(key=lambda n: (len(n), n))
    return candidates[0]


def select_best_cas(cas_list: list[str]) -> str:
    """
    Select the best CAS number from candidates.

    Standard format: digits-digits-digit (e.g., 50-00-0)
    """
    CAS_PATTERN = re.compile(r"^\d{2,7}-\d{2}-\d$")
    for cas in cas_list:
        if CAS_PATTERN.match(cas.strip()):
            return cas.strip()
    return cas_list[0] if cas_list else ""
