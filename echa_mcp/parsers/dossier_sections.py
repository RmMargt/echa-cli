"""Generic parser for ECHA dossier Sections 4, 5, and 6."""

import re
from typing import Iterable, Optional

from bs4 import BeautifulSoup

from ..clients.echa_client import ECHAClient
from .common import clean_value
from .section7_parser import select_best_dossier

DOC_ID_RE = re.compile(r"((?:IUC5-)?[A-Za-z0-9-]+_[A-Za-z0-9-]+)")


def parse_section_index(index_html: str, sections: Iterable[str]) -> dict[str, dict]:
    """Return dossier document links grouped by Section 4/5/6 subsection."""
    requested = set(sections)
    grouped: dict[str, dict] = {}

    if "4" in requested:
        grouped.update(_parse_section4_index(index_html))
    if "5" in requested:
        grouped.update(_parse_collapsed_section_index(index_html, "5", "id_5_Environmentalfateandpathways"))
    if "6" in requested:
        grouped.update(_parse_collapsed_section_index(index_html, "6", "id_6_Ecotoxicologicalinformation"))

    return grouped


async def parse_dossier_sections(
    client: ECHAClient,
    substance_index: str,
    sections: Iterable[str],
    target_section: Optional[str] = None,
    max_studies: int = 50,
) -> dict:
    """Fetch and parse Sections 4/5/6 from the best REACH dossier."""
    dossier = await select_best_dossier(client, substance_index)
    if not dossier:
        return {"error": f"No suitable dossier found for substance {substance_index}"}

    asset_id = dossier["asset_id"]
    index_html = await client.get_dossier_index(asset_id)
    if not index_html:
        return {"error": f"Could not load dossier index for {asset_id}"}

    section_docs = parse_section_index(index_html, sections)
    if target_section:
        section_docs = {
            sec: docs
            for sec, docs in section_docs.items()
            if sec == target_section or sec.startswith(f"{target_section}.")
        }

    parsed_sections = {}
    for sec_num in sorted(section_docs, key=_section_sort_key):
        docs = section_docs[sec_num]
        sec_data = {"summaries": [], "studies": []}

        for doc in docs.get("summaries", []):
            html = await client.get_document_html(asset_id, doc["doc_id"])
            if html:
                sec_data["summaries"].append(parse_document(html, doc["name"], "Summary", sec_num))

        for doc in docs.get("studies", [])[:max_studies]:
            html = await client.get_document_html(asset_id, doc["doc_id"])
            if html:
                sec_data["studies"].append(parse_document(html, doc["name"], "Study", sec_num))

        if sec_data["summaries"] or sec_data["studies"]:
            parsed_sections[sec_num] = sec_data

    return {
        "substance_index": substance_index,
        "dossier_info": {
            "asset_id": asset_id,
            "registration_number": dossier.get("registration_number", ""),
            "subtype": dossier.get("subtype", ""),
            "role": dossier.get("role", ""),
        },
        "sections": parsed_sections,
        "total_summaries": sum(len(s["summaries"]) for s in parsed_sections.values()),
        "total_studies": sum(len(s["studies"]) for s in parsed_sections.values()),
    }


def parse_document(html: str, name: str, doc_type: str, section: str) -> dict:
    """Parse one ECHA HTML document into nested label/value blocks."""
    soup = BeautifulSoup(html, "html.parser")
    h4 = soup.find("h4")
    result = {
        "name": name or (h4.get_text(" ", strip=True) if h4 else ""),
        "type": doc_type,
        "section": section,
        "fields": {},
    }

    article = soup.find("article")
    if not article:
        return result

    for block in article.find_all("section", class_=re.compile(r"das-block"), recursive=False):
        h3 = block.find("h3")
        if not h3:
            continue
        block_name = clean_value(h3.get_text(" ", strip=True))
        block_value = _extract_block(block)
        if block_name and block_value:
            _add_key(result["fields"], block_name, block_value)

    return result


def _parse_section4_index(index_html: str) -> dict[str, dict]:
    collapsed = _parse_collapsed_section_index(index_html, "4", "id_4_Physicalandchemicalproperties")
    if collapsed:
        return collapsed

    start = index_html.find("4 Physical and chemical properties")
    if start < 0:
        return {}
    end = index_html.find("5 Environmental fate", start)
    section_html = index_html[start:end] if end > 0 else index_html[start:]

    anchors = [(0, "sec", "4.0", "4 Physical and chemical properties")]
    for match in re.finditer(r"<button[^>]*>\s*(4(?:\.\d+)+\s+[^<]+?)\s*</button>", section_html, re.DOTALL):
        title = clean_value(match.group(1))
        sec_num = title.split(" ", 1)[0]
        anchors.append((match.start(), "sec", sec_num, title))

    for match in re.finditer(r"das-docid-([a-f0-9\-]+_[a-f0-9\-]+).*?data-dastttxt=\"([^\"]+)\"", section_html, re.DOTALL):
        name = clean_value(match.group(2))
        if _is_dossier_doc_name(name):
            anchors.append((match.start(), "doc", match.group(1), name))

    return _anchors_to_sections(anchors)


def _parse_collapsed_section_index(index_html: str, prefix: str, collapse_id: str) -> dict[str, dict]:
    section_html = _extract_collapse(index_html, collapse_id)
    if not section_html:
        return {}

    soup = BeautifulSoup(section_html, "html.parser")
    result = {}

    top_docs = _extract_docs_before_nested_button(section_html)
    if top_docs:
        result[f"{prefix}.0"] = {"summaries": [], "studies": []}
        for doc in top_docs:
            _append_doc(result[f"{prefix}.0"], doc)

    for button in soup.find_all("button", class_="das-nav-header"):
        title = clean_value(button.get_text(" ", strip=True))
        match = re.match(r"^(\d+(?:\.\d+)+)\s+.+", title)
        target = (button.get("data-toc-target") or "").lstrip("#")
        if not match or not target:
            continue

        sub_html = _extract_collapse(section_html, target)
        if not sub_html:
            continue
        docs = _extract_docs_before_nested_button(sub_html)
        if not docs:
            continue

        sec_num = match.group(1)
        result[sec_num] = {"summaries": [], "studies": []}
        for doc in docs:
            _append_doc(result[sec_num], doc)

    return result


def _extract_docs_before_nested_button(html: str) -> list[dict]:
    cutoff = html.find("<button")
    effective_html = html[:cutoff] if cutoff > 0 else html
    soup = BeautifulSoup(effective_html, "html.parser")
    docs = []
    for link in soup.find_all("a", class_="das-leaf"):
        doc_id = _extract_doc_id(link)
        name = _leaf_text(link)
        if doc_id and _is_dossier_doc_name(name):
            docs.append({"doc_id": doc_id, "name": name, "type": _doc_type(name)})
    return docs


def _extract_doc_id(link) -> str:
    href = str(link.get("href") or "")
    numeric_match = re.search(r"documents/(\d+)\.html", href)
    if numeric_match:
        return numeric_match.group(1)

    doc_match = DOC_ID_RE.search(href)
    if doc_match:
        return doc_match.group(1)

    classes = " ".join(link.get("class") or [])
    class_match = re.search(r"das-docid-" + DOC_ID_RE.pattern, classes)
    return class_match.group(1) if class_match else ""


def _leaf_text(link) -> str:
    content = link.find("div", class_="das-link-content")
    candidates = (content or link).find_all(attrs={"data-dastttxt": True})
    tooltip_values = [
        clean_value(candidate.get("data-dastttxt", ""))
        for candidate in candidates
        if candidate.name in {"span", "div", "a"}
    ]
    for value in tooltip_values:
        if _is_dossier_doc_name(value):
            return value
    if tooltip_values:
        return tooltip_values[-1]
    return clean_value((content or link).get_text(" ", strip=True))


def _append_doc(section: dict, doc: dict) -> None:
    key = "summaries" if doc["type"] == "Summary" else "studies"
    section[key].append(doc)


def _anchors_to_sections(anchors: list[tuple]) -> dict[str, dict]:
    anchors.sort(key=lambda item: item[0])
    current = "4.0"
    result: dict[str, dict] = {}
    for _, kind, value, name in anchors:
        if kind == "sec":
            current = value
            result.setdefault(current, {"summaries": [], "studies": []})
            continue

        doc = {"doc_id": value, "name": name, "type": _doc_type(name)}
        _append_doc(result.setdefault(current, {"summaries": [], "studies": []}), doc)
    return result


def _extract_collapse(html: str, collapse_id: str) -> str:
    match = re.search(rf'<div[^>]*class="collapse"[^>]*id="{re.escape(collapse_id)}"[^>]*>', html)
    if not match:
        return ""
    start = match.end()
    depth = 1
    pos = start
    while depth > 0 and pos < len(html):
        open_pos = html.find("<div", pos)
        close_pos = html.find("</div>", pos)
        if close_pos < 0:
            break
        if open_pos >= 0 and open_pos < close_pos:
            depth += 1
            pos = open_pos + 4
        else:
            depth -= 1
            if depth == 0:
                return html[start:close_pos]
            pos = close_pos + 6
    return html[start:pos]


def _extract_block(block) -> object:
    result = {}

    for field in block.find_all("div", class_="das-field", recursive=False):
        label = field.find("div", class_="das-field_label")
        value = field.find("div", class_="das-field_value")
        if not label or not value:
            continue
        label_text = clean_value(label.get_text(" ", strip=True))
        value_text = _extract_value(value)
        if label_text and value_text:
            _add_key(result, label_text, value_text)

    for sub_block in block.find_all("section", class_=re.compile(r"das-block"), recursive=False):
        if "das-block_repeatable" in (sub_block.get("class") or []):
            for inner in sub_block.find_all("section", class_=re.compile(r"das-block"), recursive=False):
                _append_block(result, inner)
        else:
            _append_block(result, sub_block)

    if result:
        return result

    html_value = block.find("div", class_="das-field_value_html")
    if html_value:
        return clean_value(html_value.get_text(" ", strip=True))
    value = block.find("div", class_="das-field_value")
    return _extract_value(value) if value else ""


def _append_block(result: dict, block) -> None:
    h3 = block.find("h3")
    if not h3:
        return
    key = clean_value(h3.get_text(" ", strip=True))
    value = _extract_block(block)
    if key and value:
        _add_key(result, key, value)


def _extract_value(value_div) -> str:
    range_el = value_div.find("span", class_="i6PhysicalQuantityRange")
    if range_el:
        return _extract_quantity_range(range_el)

    quantity = value_div.find("span", class_="i6PhysicalQuantity")
    if quantity:
        value = quantity.find("span", class_="value")
        unit = quantity.find("span", class_="unit")
        return clean_value(" ".join(part.get_text(" ", strip=True) for part in (value, unit) if part))

    checked = value_div.find("span", class_="das-value_checkbox-checked")
    unchecked = value_div.find("span", class_="das-value_checkbox-unchecked")
    if checked or unchecked:
        return "checked" if checked else "unchecked"

    html_value = value_div.find("div", class_="das-field_value_html")
    if html_value:
        return clean_value(html_value.get_text(" ", strip=True))

    return clean_value(value_div.get_text(" ", strip=True))


def _extract_quantity_range(range_el) -> str:
    lower = _extract_quantity_part(range_el.find("span", class_="lower"))
    upper = _extract_quantity_part(range_el.find("span", class_="upper"))
    unit = range_el.find("span", class_="unit")
    unit_text = unit.get_text(" ", strip=True) if unit else ""

    if lower and upper:
        value = f"{lower} - {upper}"
    else:
        value = lower or upper
    if unit_text:
        value = f"{value} {unit_text}" if value else unit_text
    return clean_value(value)


def _extract_quantity_part(part) -> str:
    if not part:
        return ""
    qualifier = part.find("span", class_="qualifier")
    value = part.find("span", class_="value")
    return clean_value(" ".join(el.get_text(" ", strip=True) for el in (qualifier, value) if el))


def _add_key(target: dict, key: str, value: object) -> None:
    if key in target:
        existing = target[key]
        if isinstance(existing, list):
            existing.append(value)
        else:
            target[key] = [existing, value]
    else:
        target[key] = value


def _doc_type(name: str) -> str:
    return "Summary" if name.lower().startswith("s-") or "summary" in name.lower() else "Study"


def _is_dossier_doc_name(name: str) -> bool:
    return bool(re.match(r"^(S-\d+|\d{3})\s*\|", name) or "summary" in name.lower())


def _section_sort_key(section: str) -> tuple[int, ...]:
    return tuple(int(part) for part in section.split(".") if part.isdigit())
