from pathlib import Path
import logging
from modules import file_manager, latex_builder, validator, logger
from pipeline import grobid_parse, extract_text_and_formulas, translate_text_blocks
import fitz

# ------------------------
# CONFIG
# ------------------------
INPUT_DIR = Path("pdfs")
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

log = logger.get_logger("batch_pipeline")

# ------------------------
# PDF İşleme Fonksiyonu
# ------------------------
def process_pdf(pdf_path: Path):
    log.info(f"PDF işleniyor: {pdf_path.name}")

    # 1) Grobid ile TEI XML parse
    try:
        tei_xml = grobid_parse(pdf_path)
    except Exception as e:
        log.error(f"Grobid hatası ({pdf_path.name}): {e}")
        return False

    # 2) Metin ve formülleri ayır
    text_blocks, formulas = extract_text_and_formulas(tei_xml)

    # 3) Metinleri çevir (formüller korunur)
    try:
        translated_blocks = translate_text_blocks(text_blocks)
    except Exception as e:
        log.error(f"Çeviri hatası ({pdf_path.name}): {e}")
        return False

    # 4) Görselleri ayıkla
    doc = fitz.open(pdf_path)
    page_images = {}
    for i, page in enumerate(doc):
        img_paths = []
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            pix = fitz.Pixmap(doc, xref)
            img_path = OUTPUT_DIR / f"{pdf_path.stem}_page_{i+1}_img_{img_index}.png"
            pix.save(img_path)
            img_paths.append(img_path)
            pix = None
        if img_paths:
            page_images[i+1] = img_paths

    # 5) LaTeX oluştur ve PDF üret
    output_tex = OUTPUT_DIR / (pdf_path.stem + "_translated.tex")
    latex_builder.build_latex_document(
        text_blocks=translated_blocks,
        formulas=formulas,
        images=page_images,
        output_path=output_tex
    )

    # 6) Validator ile derle ve kontrol et
    if validator.validate_latex(output_tex):
        log.info(f"PDF başarıyla oluşturuldu: {output_tex.with_suffix('.pdf')}")
        return True
    else:
        log.error(f"PDF oluşturulamadı: {output_tex.with_suffix('.pdf')}")
        return False

# ------------------------
# BATCH ÇALIŞTIRMA
# ------------------------
def main():
    log.info("Batch pipeline başlatılıyor...")
    pdf_files = file_manager.list_pdfs(INPUT_DIR)
    if not pdf_files:
        log.error(f"{INPUT_DIR} içinde PDF bulunamadı!")
        return

    success_count = 0
    for pdf in pdf_files:
        if process_pdf(pdf):
            success_count += 1

    log.info(f"Batch tamamlandı: {success_count}/{len(pdf_files)} PDF başarıyla işlendi.")

if __name__ == "__main__":
    main()
