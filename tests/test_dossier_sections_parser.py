from echa_mcp.parsers.dossier_sections import parse_section_index, parse_document


def test_parse_section_index_groups_physchem_and_ecotox_docs():
    index_html = """
    <html><body>
      4 Physical and chemical properties
      <button class="das-nav-header">4.2 Melting / freezing point</button>
      <a class="das-leaf das-docid-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa_bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb">
        <div class="das-link-content">S-01 | Melting point summary</div>
        <span data-dastttxt="S-01 | Melting point summary"></span>
      </a>
      <a class="das-leaf das-docid-cccccccc-cccc-cccc-cccc-cccccccccccc_dddddddd-dddd-dddd-dddd-dddddddddddd">
        <div class="das-link-content">001 | key study | experimental</div>
        <span data-dastttxt="001 | key study | experimental"></span>
      </a>
      5 Environmental fate and pathways
      <div class="collapse" id="id_5_Environmentalfateandpathways">
        <button class="das-nav-header" data-toc-target="#id_5_1_1">5.1.1 Hydrolysis</button>
        <div class="collapse" id="id_5_1_1">
          <a class="das-leaf" href="eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee_ffffffff-ffff-ffff-ffff-ffffffffffff">
            <div class="das-link-content">S-01 | Hydrolysis summary</div>
          </a>
          <a class="das-leaf" href="11111111-1111-1111-1111-111111111111_22222222-2222-2222-2222-222222222222">
            <div class="das-link-content">001 | key study | experimental result</div>
          </a>
        </div>
      </div>
      <div class="collapse" id="id_6_Ecotoxicologicalinformation">
        <button class="das-nav-header" data-toc-target="#id_6_1_1">6.1.1 Short-term toxicity to fish</button>
        <div class="collapse" id="id_6_1_1">
          <a class="das-leaf" href="documents/333.html">
            <div class="das-link-content">S-01 | Fish summary</div>
          </a>
        </div>
      </div>
    </body></html>
    """

    sections = parse_section_index(index_html, ("4", "5", "6"))

    assert sections["4.2"]["summaries"][0]["doc_id"].startswith("aaaaaaaa-")
    assert sections["4.2"]["studies"][0]["doc_id"].startswith("cccccccc-")
    assert sections["5.1.1"]["summaries"][0]["name"] == "S-01 | Hydrolysis summary"
    assert sections["5.1.1"]["studies"][0]["doc_id"].startswith("11111111-")
    assert sections["6.1.1"]["summaries"][0]["doc_id"] == "333"


def test_parse_section_index_groups_collapsed_physchem_iuc5_docs():
    index_html = """
    <html><body>
      <button data-toc-target="#id_4_Physicalandchemicalproperties">
        4 Physical and chemical properties
      </button>
      <div class="collapse" id="id_4_Physicalandchemicalproperties">
        <button class="das-nav-header" data-toc-target="#id_44_Density">4.4 Density</button>
        <div class="collapse" id="id_44_Density">
          <a class="das-leaf das-docid-IUC5-5ebdde83-339b-494f-a295-74dffad94e7f_72e64fd8-8976-41f2-8467-d967eeaad3de"
             href="IUC5-5ebdde83-339b-494f-a295-74dffad94e7f_72e64fd8-8976-41f2-8467-d967eeaad3de">
            <div class="das-link-content">
              <svg data-dastttxt="Inherited by template"></svg>
              <span data-dastttxt="S-01 | Summary">S-01 | Summary</span>
            </div>
          </a>
          <a class="das-leaf das-docid-IUC5-3e61fd0b-e6a9-4b53-bab7-72d550e86da5_72e64fd8-8976-41f2-8467-d967eeaad3de"
             href="IUC5-3e61fd0b-e6a9-4b53-bab7-72d550e86da5_72e64fd8-8976-41f2-8467-d967eeaad3de">
            <div class="das-link-content">
              <svg data-dastttxt="Inherited by template"></svg>
              <span data-dastttxt="001 | Key | Experimental study">001 | Key | Experimental study</span>
            </div>
          </a>
        </div>
      </div>
    </body></html>
    """

    sections = parse_section_index(index_html, ("4",))

    assert sections["4.4"]["summaries"][0]["name"] == "S-01 | Summary"
    assert sections["4.4"]["summaries"][0]["doc_id"].startswith("IUC5-5ebdde83")
    assert sections["4.4"]["studies"][0]["name"] == "001 | Key | Experimental study"
    assert sections["4.4"]["studies"][0]["doc_id"].startswith("IUC5-3e61fd0b")


def test_parse_document_extracts_nested_fields_and_quantity_ranges():
    html = """
    <html><body>
      <h4>Melting / freezing point</h4>
      <article>
        <section class="das-block AdministrativeData">
          <h3 class="das-block_label">Administrative data</h3>
          <div class="das-field">
            <div class="das-field_label">Endpoint</div>
            <div class="das-field_value"><span class="phrase">melting point</span></div>
          </div>
        </section>
        <section class="das-block ResultsAndDiscussion">
          <h3 class="das-block_label">Results and discussion</h3>
          <section class="das-block_repeatable">
            <section class="das-block MeltingPoint">
              <h3 class="das-block_label">#1 - Melting / freezing point</h3>
              <div class="das-field">
                <div class="das-field_label">Melting / freezing point</div>
                <div class="das-field_value">
                  <span class="i6PhysicalQuantityRange">
                    <span class="lower"><span class="value">-92</span></span>
                    <span class="upper"><span class="value">-90</span></span>
                    <span class="unit">deg C</span>
                  </span>
                </div>
              </div>
            </section>
          </section>
        </section>
      </article>
    </body></html>
    """

    record = parse_document(html, "001 | key study | experimental", "Study", "4.2")

    assert record["name"] == "001 | key study | experimental"
    assert record["type"] == "Study"
    assert record["section"] == "4.2"
    assert record["fields"]["Administrative data"]["Endpoint"] == "melting point"
    assert (
        record["fields"]["Results and discussion"]["#1 - Melting / freezing point"]["Melting / freezing point"]
        == "-92 - -90 deg C"
    )
