# pipeline.py
"""
Güncellenmiş, dayanıklı pipeline:
 - grobid_parse(pdf_path) -> TEI XML string
 - extract_text_and_formulas(tei_xml) -> list of blocks (in doc order)
 - translate_blocks(blocks, src_lang, tgt_lang) -> translated blocks (formüller korunur)
 - extract_images_from_pdf(pdf_path, output_dir) -> dict: page -> [paths]
 - create_latex_pdf(translated_blocks_by_page, images_by_page, output_base)
 - translate_pdf(pdf_path) -> main orchestration
"""
from pathlib import Path
import re
import logging
import subprocess
import html
import os
from typing import List, Dict, Tuple

import requests
from bs4 import BeautifulSoup

# Transformers imports in try/except: kullanıcı zaten modeli çektiyse çalışır.
try:
    from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
    TRANSFORMERS_AVAILABLE = True
except Exception:
    TRANSFORMERS_AVAILABLE = False

import fitz  # PyMuPDF

# ------------------------
# CONFIG (ayarlanabilir)
# ------------------------
GROBID_URL = "http://localhost:8070/api/processFulltextDocument"
MODEL_NAME = "facebook/m2m100_418M"  # değiştirebilirsin (m2m, mBART, vs.)
SRC_LANG = "tr"
TGT_LANG = "en"
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# Model (lazy loaded)
tokenizer = None
model = None

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("pipeline")

# ------------------------
# Helpers
# ------------------------
def ensure_model_loaded():
    global tokenizer, model
    if not TRANSFORMERS_AVAILABLE:
        raise RuntimeError("transformers kütüphanesi bulunamadı. pip install transformers sentencepiece torch")
    if tokenizer is None or model is None:
        log.info("Çeviri modeli yükleniyor... (bu adım bir kez olacak, büyük modelse zaman alır)")
        tokenizer = M2M100Tokenizer.from_pretrained(MODEL_NAME)
        model = M2M100ForConditionalGeneration.from_pretrained(MODEL_NAME)
        log.info("Çeviri modeli hazır.")

def escape_latex(text: str) -> str:
    """
    Basit LaTeX kaçış fonksiyonu.
    Formüller bu metodu GEÇMEYECEK şekilde tasarlanmalı (yani formüller yerleştirildikten sonra kaçarız).
    """
    if not text:
        return ""
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "<": r"\textless{}",
        ">": r"\textgreater{}",
    }
    # Örnek olarak önce HTML entity decode
    text = html.unescape(text)
    for k, v in replacements.items():
        text = text.replace(k, v)
    # Normalize whitespace a bit
    text = re.sub(r"\s+\n", "\n", text)
    return text

# ------------------------
# 1) GROBID ile parse
# ------------------------
def grobid_parse(pdf_path: Path, consolidate: int = 1, timeout: int = 120) -> str:
    """
    PDF'i GROBID'e gönderir ve TEI XML sonucunu döndürür.
    """
    log.info(f"GROBID ile parse: {pdf_path}")
    with open(pdf_path, "rb") as f:
        try:
            resp = requests.post(
                GROBID_URL,
                files={"input": f},
                data={"consolidate": str(consolidate)},
                timeout=timeout
            )
        except requests.RequestException as e:
            raise RuntimeError(f"GROBID'e bağlanırken hata: {e}") from e
    if resp.status_code != 200:
        raise RuntimeError(f"GROBID hatası: status={resp.status_code} body={resp.text[:500]}")
    return resp.text

# ------------------------
# 2) TEI XML -> metin blokları (sıra korunur)
# ------------------------
def extract_text_and_formulas(tei_xml: str) -> List[Dict]:
    """
    TEI XML içinden belge sırasını koruyarak 'metin blokları' çıkarır.
    Dönen yapı: list of dict { 'type': 'p'|'head'|'figure'|'table'|'note'|'div' , 'text': '...', 'raw': '<p>...</p>', 'formulas': [..] }
    Formüller raw içinde korunur, ayrıca formulas listesi de içerir.
    """
    log.info("TEI XML parse ediliyor (lxml-xml)...")
    # XML parse: kesinlikle xml parser kullan
    soup = BeautifulSoup(tei_xml, "lxml-xml")  # lxml-xml => özellikli XML parse
    body = soup.find("text")
    if body is None:
        body = soup  # fallback: tüm belge

    blocks = []
    # İlgili tag listesi; belge içindeki sırayı korumak için recursive traversal yapacağız.
    allowed = {"p", "head", "figure", "table", "note", "div", "list", "row", "cell", "head", "figDesc", "label"}
    # iterable over all tags in document order
    for elem in body.find_all(True):
        name = elem.name
        if name not in allowed:
            continue
        raw_html = str(elem)
        # extract formulas inside this element (keep original inner markup)
        formulas = []
        for formula in elem.find_all("formula"):
            # Keep inner XML of formula
            inner = "".join(str(x) for x in formula.contents)
            formulas.append(inner.strip())
        # derive a readable text for translation: strip tags but keep formula placeholders
        text_for_translation = raw_html
        # replace formula elements with a placeholder token so translator doesn't touch them
        if formulas:
            def repl_formula(m, counter=[0]):
                token = f"__FORMULA_{counter[0]}__"
                counter[0] += 1
                return token
            text_for_translation = re.sub(r"<formula[^>]*>.*?</formula>", repl_formula, text_for_translation, flags=re.DOTALL)
        # strip any remaining XML tags for translation input (we want plain text)
        text_plain = re.sub(r"<[^>]+>", " ", text_for_translation)
        text_plain = html.unescape(text_plain)
        text_plain = re.sub(r"\s+", " ", text_plain).strip()
        blocks.append({
            "type": name,
            "raw": raw_html,
            "formulas": formulas,
            "text_plain": text_plain
        })
    log.info(f"{len(blocks)} blok çıkarıldı.")
    return blocks

# ------------------------
# 3) Çeviri (formüller korunur)
# ------------------------
def translate_blocks(blocks: List[Dict], src_lang: str = SRC_LANG, tgt_lang: str = TGT_LANG) -> List[Dict]:
    """
    Her blokun 'text_plain' alanını çevirir; formüller yerinde korunur.
    Dönen: aynı blok listesi, but 'translated' alanı eklendi.
    """
    ensure_model_loaded()
    translated_blocks = []
    for b_index, block in enumerate(blocks):
        plain = block.get("text_plain", "")
        # If empty or just short, skip translation but keep as-is
        if not plain:
            block["translated"] = ""
            translated_blocks.append(block)
            continue

        # Prepare input: if block contains placeholders __FORMULA_N__, keep them (they are not tags at this state)
        # Tokenizer usage: set source language and generate
        try:
            tokenizer.src_lang = src_lang
            inputs = tokenizer(plain, return_tensors="pt", truncation=True)
            gen = model.generate(
                **inputs,
                forced_bos_token_id=tokenizer.get_lang_id(tgt_lang),
                max_length= max(64, min(1024, len(inputs["input_ids"][0]) * 3)),
                num_beams=4,
                early_stopping=True
            )
            out = tokenizer.batch_decode(gen, skip_special_tokens=True)[0]
            # Out may contain the placeholders as plain text: fine.
            # Now re-insert original formula content instead of placeholders.
            # Build list of placeholders in order:
            # We expect placeholders __FORMULA_0__, __FORMULA_1__, ...
            translated_text = out
            # If block.formulas exists, replace placeholders sequentially
            formulas = block.get("formulas", [])
            for idx, formula in enumerate(formulas):
                placeholder = f"__FORMULA_{idx}__"
                # Place formula in a LaTeX-safe wrapper: we will put it as verbatim block later.
                # For now use a unique marker with index so create_latex_pdf can detect it precisely.
                marker = f"[[FORMULA_START_{b_index}_{idx}]]{formula}[[FORMULA_END_{b_index}_{idx}]]"
                # replace first occurrence to keep order
                translated_text = translated_text.replace(placeholder, marker, 1)
        except Exception as e:
            log.exception(f"Çeviri sırasında hata (blok {b_index}): {e}")
            translated_text = plain  # fallback: orijinal
        block["translated"] = translated_text
        translated_blocks.append(block)
    return translated_blocks

# ------------------------
# 4) PDF görsellerini çıkar
# ------------------------
def extract_images_from_pdf(pdf_path: Path, output_dir: Path) -> Dict[int, List[Path]]:
    doc = fitz.open(pdf_path)
    page_images = {}
    for i, page in enumerate(doc):
        img_paths = []
        for img_idx, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.n >= 5:  # CMYK or with alpha
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                img_path = output_dir / f"{pdf_path.stem}_page_{i+1}_img_{img_idx}.png"
                pix.save(str(img_path))
                pix = None
                img_paths.append(img_path)
            except Exception as e:
                log.warning(f"Resim çıkarılırken hata (sayfa {i+1}, img {img_idx}): {e}")
        if img_paths:
            page_images[i+1] = img_paths
    return page_images

# ------------------------
# 5) LaTeX oluştur ve PDF üret (sayfa bazlı yerleşim)
# ------------------------
LATEX_PREAMBLE = r"""
\documentclass[12pt]{article}
\usepackage[utf8]{inputenc}
\usepackage{amsmath,amssymb}
\usepackage{graphicx}
\usepackage{geometry}
\usepackage{fancyvrb}
\geometry{margin=2cm}
\pagestyle{plain}
\begin{document}
"""

LATEX_POSTAMBLE = r"""
\end{document}
"""

def create_latex_pdf(translated_blocks: List[Dict], images_by_page: Dict[int, List[Path]], output_base: Path):
    """
    translated_blocks: list in document order with 'translated' content.
    images_by_page: dict mapping page number -> list of image paths
    output_base: Path without extension (e.g. output/PS4)
    """
    log.info("LaTeX içeriği oluşturuluyor...")
    tex_path = output_base.with_suffix(".tex")
    try:
        with open(tex_path, "w", encoding="utf-8") as tex:
            tex.write(LATEX_PREAMBLE)
            current_page = 1
            # Strategy: iterate through blocks in order; we don't always know original page number from TEI.
            # So we'll print blocks sequentially; after printing blocks that correspond to a "page boundary" we inject images_by_page[current_page].
            # Because TEI lacks explicit page markers, we'll simply intersperse images by page index.
            # Simpler: group blocks into pseudo-pages by splitting roughly every N blocks if many pages; BUT earlier we extracted images_by_page explicitly.
            # We'll output all blocks, then append images page-by-page with \clearpage between them to preserve images across pages.
            # This keeps text intact and ensures images present.
            for b in translated_blocks:
                text = b.get("translated", "").strip()
                if not text:
                    continue
                # Replace formula markers back into LaTeX verbatim blocks
                # Markers look like [[FORMULA_START_{b_index}_{idx}]]...[[FORMULA_END_{b_index}_{idx}]]
                def formula_repl(m):
                    inner = m.group(1)
                    # wrap in Verbatim so markup preserved and not touched by LaTeX
                    return "\n\\begin{Verbatim}[fontsize=\\small]\n" + inner + "\n\\end{Verbatim}\n"
                # Replace all occurrences
                text_with_formulas = re.sub(r"\[\[FORMULA_START_[0-9]+_[0-9]+\]\](.*?)\[\[FORMULA_END_[0-9]+_[0-9]+\]\]",
                                            lambda mm: formula_repl(mm), text, flags=re.DOTALL)
                # Escape the remaining text for LaTeX (we assume formulas are already handled)
                # But Verbatim sections above are preserved because they were replaced with LaTeX code already.
                # To avoid escaping LaTeX commands inserted, we will proceed by splitting on Verbatim boundaries.
                pieces = re.split(r"(\\begin\{Verbatim\}.*?\\end\{Verbatim\})", text_with_formulas, flags=re.DOTALL)
                for piece in pieces:
                    if piece.startswith("\\begin{Verbatim}"):
                        tex.write(piece + "\n\n")
                    else:
                        safe = escape_latex(piece)
                        # Keep simple paragraphs
                        tex.write(safe + "\n\n")
            # Append images page by page
            if images_by_page:
                # Page break before images
                tex.write("\n\\clearpage\n")
                for page_no in sorted(images_by_page.keys()):
                    imgs = images_by_page[page_no]
                    tex.write(f"% Images for page {page_no}\n")
                    for img_path in imgs:
                        rel = os.path.relpath(img_path, OUTPUT_DIR)
                        tex.write("\\begin{figure}[ht]\n\\centering\n")
                        tex.write(f"\\includegraphics[width=0.9\\textwidth]{{{rel}}}\n")
                        tex.write("\\end{figure}\n\n")
                    tex.write("\\clearpage\n")
            tex.write(LATEX_POSTAMBLE)
        # Run pdflatex (twice to resolve refs if needed)
        log.info(f"pdflatex çalıştırılıyor: {tex_path}")
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "-output-directory", str(OUTPUT_DIR), str(tex_path)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        # second pass (optional)
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "-output-directory", str(OUTPUT_DIR), str(tex_path)],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        log.info(f"PDF oluşturuldu: {output_base.with_suffix('.pdf')}")
    except subprocess.CalledProcessError as e:
        log.error(f"pdflatex hatası: exit {e.returncode} stdout={e.stdout[:200]} stderr={e.stderr[:200]}")
        raise
    except Exception as e:
        log.exception(f"LaTeX oluşturma sırasında hata: {e}")
        raise

# ------------------------
# 6) Tek PDF çevirme akışı
# ------------------------
def translate_pdf(pdf_path: Path, src_lang: str = SRC_LANG, tgt_lang: str = TGT_LANG):
    """
    Tam pipeline: GROBID -> extract -> translate -> extract images -> build PDF
    """
    log.info(f"Başlıyor: {pdf_path}")
    tei_xml = grobid_parse(pdf_path)
    blocks = extract_text_and_formulas(tei_xml)
    log.info(f"{len(blocks)} blok ile çeviri başlıyor...")
    translated = translate_blocks(blocks, src_lang=src_lang, tgt_lang=tgt_lang)
    images = extract_images_from_pdf(pdf_path, OUTPUT_DIR)
    output_base = OUTPUT_DIR / pdf_path.stem
    create_latex_pdf(translated, images, output_base)
    log.info(f"Tamamlandı: {pdf_path}")

# If module run directly, quick smoke test (kullanıcı isteğe bağlı)
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Kullanım: python pipeline.py /path/to/file.pdf")
        sys.exit(1)
    p = Path(sys.argv[1])
    translate_pdf(p)
