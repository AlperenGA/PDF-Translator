import xml.etree.ElementTree as ET

def parse_tei(xml_content):
    """
    TEI XML çıktısını parse eder ve bloklara ayırır.
    Dönüş listesi: [{ "type": "paragraph"/"formula"/"pb", "content": "..." }]
    """
    items = []
    try:
        root = ET.fromstring(xml_content)

        # Tüm body içeriğini gez
        for elem in root.iter():
            tag = elem.tag.lower()
            if tag.endswith("p"):  # paragraf
                text = (elem.text or "").strip()
                if text:
                    items.append({"type": "paragraph", "content": text})
            elif "formula" in tag:  # formüller
                formula = (elem.text or "").strip()
                if formula:
                    items.append({"type": "formula", "content": formula})
            elif tag.endswith("pb"):  # page break
                items.append({"type": "pb", "content": ""})

    except Exception as e:
        items.append({"type": "error", "content": f"XML parse error: {e}"})

    return items
