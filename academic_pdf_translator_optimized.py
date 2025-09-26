# academic_pdf_translator_optimized.py

import os
import subprocess
from pathlib import Path
import requests
import fitz
from bs4 import BeautifulSoup
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import re

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
# PDF → TEI XML
# ------------------------
def parse_pdf_with_grobid(pdf_path: Path) -> str:
    with open(pdf_path, "rb") as f:
        response = requests.post(
            GROBID_URL,
            files={"input": f},
            data={"consolidate": "1"}
        )
    if response.status_code != 200:
        raise RuntimeError(f"Grobid parsing failed: {response.status_code}")
    return response.text

# ------------------------
# TEI XML → Metin Blokları
# ------------------------
def extract_text_blocks(tei_xml: str) -> list:
    soup = BeautifulSoup(tei_xml, "lxml")
    paragraphs = [str(p) for p in soup.find_all("p")]
    return paragraphs

# ------------------------
# Metin Çeviri (Formüller Korunur)
# ------------------------
def translate_text(text: str) -> str:
    math_blocks = re.findall(r"<formula>(.*?)</formula>", text)
    temp_text = re.sub(r"<formula>.*?</formula>", "FORMULA_PLACEHOLDER", text)

    inputs = tokenizer(temp_text, return_tensors="pt", truncation=True)
    translated_tokens = model.generate(
        **inputs,
        forced_bos_token_id=tokenizer.lang_code_to_id[TGT_LANG]
    )
    translated = tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)[0]

    for formula in math_blocks:
        translated = translated.replace("FORMULA_PLACEHOLDER", formula, 1)
    return translated

# ------------------------
# PDF/LaTeX Yeniden Yapılandırma
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
    full_text = "\n\n".join(translated_blocks)
    latex_content = LATEX_TEMPLATE % full_text
    tex_file = output_file.with_suffix(".tex")
    with open(tex_file, "w", encoding="utf-8") as f:
        f.write(latex_content)
    subprocess.run(["pdflatex", "-interaction=nonstopmode", "-output-directory", OUTPUT_DIR, str(tex_file)])
    print(f"PDF oluşturuldu: {output_file.with_suffix('.pdf')}")

# ------------------------
# Görseller ve Tabloların Korunması
# ------------------------
def extract_images_from_pdf(pdf_path: Path, output_dir: Path):
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
# ANA PİPELINE
# ------------------------
def translate_pdf(pdf_path: Path):
    print("PDF parsing başlıyor...")
    tei_xml = parse_pdf_with_grobid(pdf_path)
    text_blocks = extract_text_blocks(tei_xml)
    print(f"{len(text_blocks)} metin bloğu çıkarıldı. Çeviri başlıyor...")
    translated_blocks = [translate_text(block) for block in text_blocks]
    output_pdf = OUTPUT_DIR / pdf_path.stem
    create_latex_pdf(translated_blocks, output_pdf)
    extract_images_from_pdf(pdf_path, OUTPUT_DIR)
    print("Pipeline tamamlandı.")

# ------------------------
# ÇALIŞTIRMA
# ------------------------
if __name__ == "__main__":
    input_pdf = Path("sample.pdf")
    translate_pdf(input_pdf)
