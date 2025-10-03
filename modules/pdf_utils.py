import fitz  # PyMuPDF
from pathlib import Path
import shutil
import logging

logging.basicConfig(level=logging.INFO)

def extract_images(pdf_path: Path, output_dir: Path):
    """
    PDF içindeki tüm görselleri çıkarır ve PNG olarak kaydeder.
    Çıkan görsellerin sayfa bazlı path listesini döner.
    """
    doc = fitz.open(pdf_path)
    page_images = {}

    for i, page in enumerate(doc):
        img_paths = []
        for j, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            pix = fitz.Pixmap(doc, xref)

            if pix.n < 5:  # RGB veya Gray
                img_path = output_dir / f"{pdf_path.stem}_p{i+1}_img{j}.png"
                pix.save(img_path)
            else:  # CMYK ise dönüştür
                pix0 = fitz.Pixmap(fitz.csRGB, pix)
                img_path = output_dir / f"{pdf_path.stem}_p{i+1}_img{j}.png"
                pix0.save(img_path)
                pix0 = None

            img_paths.append(img_path)
            pix = None

        if img_paths:
            page_images[i + 1] = img_paths

    logging.info(f"{pdf_path} içinden {sum(len(v) for v in page_images.values())} görsel çıkarıldı.")
    return page_images


def extract_text(pdf_path: Path):
    """
    PDF içindeki tüm metni sayfa bazlı olarak döner.
    Formüller LaTeX/MathML olarak metin içinde korunur.
    """
    doc = fitz.open(pdf_path)
    page_texts = {}

    for i, page in enumerate(doc):
        text = page.get_text("text")
        page_texts[i + 1] = text

    logging.info(f"{pdf_path} içinden {len(page_texts)} sayfalık metin çıkarıldı.")
    return page_texts


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def list_pdfs(input_dir: Path):
    ensure_dir(input_dir)
    return list(input_dir.glob("*.pdf"))


def save_file(path: Path, content: bytes):
    ensure_dir(path.parent)
    with open(path, "wb") as f:
        f.write(content)


def copy_file(src: Path, dst: Path):
    ensure_dir(dst.parent)
    shutil.copy(src, dst)
