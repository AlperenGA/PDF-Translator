# pipeline.py
import re
import fitz
import requests
from bs4 import BeautifulSoup
from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
from pathlib import Path
import logging

# ------------------------
# CONFIG
# ------------------------
GROBID_URL = "http://localhost:8070/api/processFulltextDocument"
MODEL_NAME = "facebook/m2m100_418M"
SRC_LANG = "en"
TGT_LANG = "en"  # Başlangıç olarak İngilizce, istediğin dile değiştirebilirsin
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ------------------------
# MODEL LOAD
# ------------------------
logging.info("M2M100 modeli yükleniyor...")
tokenizer = M2M100Tokenizer.from_pretrained(MODEL_NAME)
model = M2M100ForConditionalGeneration.from_pretrained(MODEL_NAME)

# ------------------------
# 1. PDF -> TEI XML
# ------------------------
def grobid_parse(pdf_path: Path) -> str:
    with open(pdf_path, "rb") as f:
        response = requests.post(
            GROBID_URL,
            files={"input": f},
            data={"consolidate": "1"}
        )
    if response.status_code != 200:
        raise RuntimeError(f"Grobid parsing failed for {pdf_path}: {response.status_code}")
    return response.text

# ------------------------
# 2. TEI XML -> Metin Blokları
# ------------------------
def extract_text_and_formulas(tei_xml: str) -> list:
    soup = BeautifulSoup(tei_xml, "lxml")
    paragraphs = [str(p) for p in soup.find_all("p")]
    return paragraphs

# ------------------------
# 3. Metin Çeviri (Formüller Korunur)
# ------------------------
def translate_text_blocks(text: str) -> str:
    math_blocks = re.findall(r"<formula>(.*?)</formula>", text)
    temp_text = re.sub(r"<formula>.*?</formula>", "FORMULA_PLACEHOLDER", text)

    tokenizer.src_lang = SRC_LANG
    encoded = tokenizer(temp_text, return_tensors="pt")
    generated_tokens = model.generate(**encoded, forced_bos_token_id=tokenizer.get_lang_id(TGT_LANG))
    translated = tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0]

    for formula in math_blocks:
        translated = translated.replace("FORMULA_PLACEHOLDER", formula, 1)
    return translated

# ------------------------
# 4. PDF Görselleri Çıkar
# ------------------------
def extract_images_from_pdf(pdf_path: Path, output_dir: Path):
    doc = fitz.open(pdf_path)
    page_images = {}
    for i, page in enumerate(doc):
        img_paths = []
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            pix = fitz.Pixmap(doc, xref)
            img_path = output_dir / f"{pdf_path.stem}_page_{i+1}_img_{img_index}.png"
            pix.save(img_path)
            img_paths.append(img_path)
            pix = None
        if img_paths:
            page_images[i+1] = img_paths
    return page_images

# ------------------------
# 5. LaTeX PDF Oluştur
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

def create_latex_pdf(translated_blocks: list, images: dict, output_file: Path):
    full_text = ""
    for i, block in enumerate(translated_blocks, start=1):
        full_text += block + "\n\n"
        if i in images:
            for img_path in images[i]:
                full_text += f"\\includegraphics[width=0.5\\textwidth]{{{img_path}}}\n\n"

    latex_content = LATEX_TEMPLATE % full_text
    tex_file = output_file.with_suffix(".tex")
    with open(tex_file, "w", encoding="utf-8") as f:
        f.write(latex_content)

    import subprocess
    subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "-output-directory", str(OUTPUT_DIR), str(tex_file)],
        check=True
    )
    logging.info(f"PDF oluşturuldu: {output_file.with_suffix('.pdf')}")

# ------------------------
# 6. Tek PDF Çeviri
# ------------------------
def translate_pdf(pdf_path: Path):
    logging.info(f"Başlıyor: {pdf_path}")
    tei_xml = grobid_parse(pdf_path)
    text_blocks = extract_text_and_formulas(tei_xml)
    logging.info(f"{len(text_blocks)} metin bloğu çıkarıldı.")

    translated_blocks = [translate_text_blocks(block) for block in text_blocks]
    images = extract_images_from_pdf(pdf_path, OUTPUT_DIR)
    output_pdf = OUTPUT_DIR / pdf_path.stem
    create_latex_pdf(translated_blocks, images, output_pdf)
    logging.info(f"Tamamlandı: {pdf_path}")
