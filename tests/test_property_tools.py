import json

import pytest

from echa_mcp.tools import properties


@pytest.mark.asyncio
async def test_get_physchem_data_calls_section4_parser(monkeypatch):
    calls = {}

    async def fake_parse(client, substance_index, sections, target_section=None, max_studies=50):
        calls.update(
            {
                "substance_index": substance_index,
                "sections": tuple(sections),
                "target_section": target_section,
                "max_studies": max_studies,
            }
        )
        return {"sections": {"4.2": {"summaries": [], "studies": [{"name": "001"}]}}}

    monkeypatch.setattr(properties, "parse_dossier_sections", fake_parse)

    data = json.loads(await properties.get_physchem_data("100.000.002", "4.2", 3))

    assert calls == {
        "substance_index": "100.000.002",
        "sections": ("4",),
        "target_section": "4.2",
        "max_studies": 3,
    }
    assert data["sections"]["4.2"]["studies"][0]["name"] == "001"


@pytest.mark.asyncio
async def test_get_ecotoxicology_data_calls_section5_and6_parser(monkeypatch):
    calls = {}

    async def fake_parse(client, substance_index, sections, target_section=None, max_studies=50):
        calls.update(
            {
                "substance_index": substance_index,
                "sections": tuple(sections),
                "target_section": target_section,
                "max_studies": max_studies,
            }
        )
        return {"sections": {"6.1.1": {"summaries": [{"name": "S-01"}], "studies": []}}}

    monkeypatch.setattr(properties, "parse_dossier_sections", fake_parse)

    data = json.loads(await properties.get_ecotoxicology_data("100.000.002", "6.1.1", 2))

    assert calls == {
        "substance_index": "100.000.002",
        "sections": ("5", "6"),
        "target_section": "6.1.1",
        "max_studies": 2,
    }
    assert data["sections"]["6.1.1"]["summaries"][0]["name"] == "S-01"
