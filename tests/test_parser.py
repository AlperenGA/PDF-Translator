from modules.xml_parser import extract_blocks

def test_extract_blocks():
    sample_xml = "<p>Hello</p><formula>x+y</formula>"
    blocks = extract_blocks(sample_xml)
    assert blocks[0]["type"] == "text"
    assert blocks[1]["type"] == "formula"
