import re
import fitz
import requests
from bs4 import BeautifulSoup
from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
from pathlib import Path
import logging
import subprocess

# ------------------------
# CONFIG
# ------------------------
GROBID_URL = "http://localhost:8070/api/processFulltextDocument"
MODEL_NAME = "facebook/m2m100_418M"
SRC_LANG = "tr"
TGT_LANG = "en"  # İstediğin dile değiştirebilirsin
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
# 2. TEI XML -> Sayfa Bazlı Metin ve Formüller
# ------------------------
def extract_text_and_formulas(tei_xml: str) -> dict:
    """
    TEI XML'den sayfa bazlı metin ve formülleri çıkarır.
    Return: { sayfa_numarası: [metin blokları] }
    """
    soup = BeautifulSoup(tei_xml, "lxml")
    pages = {}
    current_page = 1
    blocks = []

    for element in soup.find_all(['p', 'formula', 'pb']):
        if element.name == 'pb':  # page break
            if blocks:
                pages[current_page] = blocks
            current_page = int(element.get('n', current_page + 1))
            blocks = []
        else:
            blocks.append(str(element))

    if blocks:
        pages[current_page] = blocks

    return pages

# ------------------------
# 3. Metin Çeviri (Formüller Korunur)
# ------------------------
def translate_text_blocks(text: str) -> str:
    math_blocks = re.findall(r"<formula>(.*?)</formula>", text)
    temp_text = re.sub(r"<formula>.*?</formula>", "FORMULA_PLACEHOLDER", text)

    tokenizer.src_lang = SRC_LANG
    encoded = tokenizer(temp_text, return_tensors="pt")
    generated_tokens = model.generate(
        **encoded,
        forced_bos_token_id=tokenizer.get_lang_id(TGT_LANG)
    )
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
# 5. LaTeX PDF Oluştur (Sayfa + Görsel Uyumlu)
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

def create_latex_pdf(pages: dict, images: dict, output_file: Path):
    """
    Sayfa bazlı metin + görselleri LaTeX ile PDF yapar.
    pages: { sayfa_numarası: [metin blokları] }
    images: { sayfa_numarası: [image_path] }
    """
    full_text = ""
    for page_num in sorted(pages.keys()):
        full_text += f"\\section*{{Sayfa {page_num}}}\n\n"
        for block in pages[page_num]:
            full_text += block + "\n\n"
        if page_num in images:
            for img_path in images[page_num]:
                full_text += f"\\includegraphics[width=0.8\\textwidth]{{{img_path}}}\n\n"
        full_text += "\\newpage\n"
    
    latex_content = LATEX_TEMPLATE % full_text
    tex_file = output_file.with_suffix(".tex")
    with open(tex_file, "w", encoding="utf-8") as f:
        f.write(latex_content)

    subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "-output-directory", str(OUTPUT_DIR), str(tex_file)],
        check=True
    )
    logging.info(f"PDF oluşturuldu: {output_file.with_suffix('.pdf')}")

# ------------------------
# 6. Tek PDF Çeviri (Sayfa Bazlı)
# ------------------------
def translate_pdf(pdf_path: Path):
    logging.info(f"Başlıyor: {pdf_path}")
    
    tei_xml = grobid_parse(pdf_path)
    pages_blocks = extract_text_and_formulas(tei_xml)
    logging.info(f"{sum(len(blks) for blks in pages_blocks.values())} metin bloğu çıkarıldı ({len(pages_blocks)} sayfa).")
    
    translated_pages = {}
    for page_num, blocks in pages_blocks.items():
        translated_blocks = [translate_text_blocks(block) for block in blocks]
        translated_pages[page_num] = translated_blocks
    
    images = extract_images_from_pdf(pdf_path, OUTPUT_DIR)
    output_pdf = OUTPUT_DIR / pdf_path.stem
    create_latex_pdf(translated_pages, images, output_pdf)
    
    logging.info(f"Tamamlandı: {pdf_path}")
