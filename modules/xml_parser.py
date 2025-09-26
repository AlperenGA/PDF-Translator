from bs4 import BeautifulSoup

def extract_blocks(tei_xml: str):
    soup = BeautifulSoup(tei_xml, "lxml")

    blocks = []
    for elem in soup.find_all(["p", "formula", "table"]):
        if elem.name == "p":
            blocks.append({"type": "text", "content": elem.get_text()})
        elif elem.name == "formula":
            blocks.append({"type": "formula", "content": elem.get_text()})
        elif elem.name == "table":
            blocks.append({"type": "table", "content": elem})
    return blocks
