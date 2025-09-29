# academic_pdf_translator_batch.py
from pathlib import Path
import logging
from pipeline import translate_pdf
import fitz

# ------------------------
# CONFIG
# ------------------------
INPUT_DIR = Path("pdfs")
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("batch_pipeline")

# ------------------------
# PDF İşleme Fonksiyonu
# ------------------------
def process_pdf(pdf_path: Path):
    log.info(f"PDF işleniyor: {pdf_path.name}")
    try:
        translate_pdf(pdf_path)
        log.info(f"PDF başarıyla işlendi: {pdf_path.name}")
        return True
    except Exception as e:
        log.error(f"PDF işleme hatası ({pdf_path.name}): {e}")
        return False

# ------------------------
# BATCH ÇALIŞTIRMA
# ------------------------
def main():
    log.info("Batch pipeline başlatılıyor...")
    pdf_files = list(INPUT_DIR.glob("*.pdf"))
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
