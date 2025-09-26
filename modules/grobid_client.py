import requests
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
