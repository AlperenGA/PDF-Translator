# academic_pdf_translator.py

import os
import subprocess
from pathlib import Path
import requests
import fitz  # PyMuPDF
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

# ------------------------
# CONFIG
# ------------------------
GROBID_URL = "http://localhost:8070/api/processFulltextDocument"
MODEL_NAME = "facebook/nllb-200-distilled-600M"
SRC_LANG = "eng_Latn"
TGT_LANG = "tur_Latn"
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# ------------------------
# MODEL LOAD
# ------------------------
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)

# ------------------------
# 1. PDF -> Grobid (Metin + LaTeX Formüller)
# ------------------------
def parse_pdf_with_grobid(pdf_path: str) -> str:
    """PDF’i Grobid ile işleyip TEI XML metin çıkarır"""
    with open(pdf_path, "rb") as f:
        response = requests.post(
            GROBID_URL,
            files={"input": f},
            data={"consolidate": "1"}
        )
    if response.status_code != 200:
        raise RuntimeError(f"Grobid parsing failed: {response.status_code}")
    return response.text  # TEI XML, formüller LaTeX olarak çıkıyor

# ------------------------
# 2. TEI XML’den Metin Bloklarını Çıkarma (Formülleri Koruyarak)
# ------------------------
from bs4 import BeautifulSoup

def extract_text_blocks(tei_xml: str) -> list:
    """TEI XML’den metin blokları çıkarır, formüller LaTeX olarak korunur"""
    soup = BeautifulSoup(tei_xml, "lxml")
    paragraphs = []
    for p in soup.find_all("p"):
        paragraphs.append(str(p))
    return paragraphs

# ------------------------
# 3. METİN ÇEVİRİSİ
# ------------------------
def translate_text(text: str) -> str:
    """NLLB ile metni çevirir, formülleri olduğu gibi bırakır"""
    # Formülleri basit regex ile çıkarıp geri koymak mümkün
    import re
    math_blocks = re.findall(r"<formula>(.*?)</formula>", text)
    temp_text = re.sub(r"<formula>.*?</formula>", "FORMULA_PLACEHOLDER", text)
    
    inputs = tokenizer(temp_text, return_tensors="pt", truncation=True)
    translated_tokens = model.generate(
        **inputs,
        forced_bos_token_id=tokenizer.lang_code_to_id[TGT_LANG]
    )
    translated = tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)[0]
    
    # Formülleri geri koy
    for formula in math_blocks:
        translated = translated.replace("FORMULA_PLACEHOLDER", formula, 1)
    return translated

# ------------------------
# 4. PDF/LaTeX Yeniden Yapılandırma
# ------------------------
LATEX_TEMPLATE = r"""
\documentclass[12pt]{article}
\usepackage[utf8]{inputenc}
\usepackage{amsmath, graphicx}
\usepackage{geometry}
\geometry{margin=2cm}
\begin{document}

%s

\end{document}
"""

def create_latex_pdf(translated_blocks: list, output_file: Path):
    """Çevirilmiş metin + formüller ile PDF üretir"""
    full_text = "\n\n".join(translated_blocks)
    latex_content = LATEX_TEMPLATE % full_text
    tex_file = output_file.with_suffix(".tex")
    
    with open(tex_file, "w", encoding="utf-8") as f:
        f.write(latex_content)
    
    # PDF oluştur
    subprocess.run(["pdflatex", "-interaction=nonstopmode", "-output-directory", OUTPUT_DIR, str(tex_file)])
    print(f"PDF oluşturuldu: {output_file.with_suffix('.pdf')}")

# ------------------------
# 5. GÖRSELLERİ / TABLOLARI KORUMA (Opsiyonel)
# ------------------------
def extract_images_from_pdf(pdf_path: str, output_dir: Path):
    doc = fitz.open(pdf_path)
    for i, page in enumerate(doc):
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            pix = fitz.Pixmap(doc, xref)
            img_path = output_dir / f"page_{i+1}_img_{img_index}.png"
            pix.save(img_path)
            pix = None
    print(f"Görseller kaydedildi: {output_dir}")

# ------------------------
# 6. ANA PİPELINE
# ------------------------
def translate_pdf(pdf_path: str):
    tei_xml = parse_pdf_with_grobid(pdf_path)
    text_blocks = extract_text_blocks(tei_xml)
    translated_blocks = [translate_text(block) for block in text_blocks]
    output_pdf = OUTPUT_DIR / Path(pdf_path).stem
    create_latex_pdf(translated_blocks, output_pdf)
    extract_images_from_pdf(pdf_path, OUTPUT_DIR)

# ------------------------
# 7. ÇALIŞTIRMA
# ------------------------
if __name__ == "__main__":
    input_pdf = "pdfs/PS4.pdf"  # input PDF dosyan
    translate_pdf(input_pdf)
