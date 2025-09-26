import requests
from bs4 import BeautifulSoup
import re

from config import GROBID_URL

def parse_pdf_with_grobid(pdf_path):
    with open(pdf_path, "rb") as f:
        response = requests.post(
            GROBID_URL,
            files={"input": f},
            data={"consolidate": "1"}
        )
    response.raise_for_status()
    return response.text

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
