from pathlib import Path
import requests
from bs4 import BeautifulSoup
import re
from modules import file_manager, latex_builder, validator, logger
from transformers import MarianMTModel, MarianTokenizer

# ==============================
#  CONFIG
# ==============================
INPUT_DIR = Path("pdfs")
OUTPUT_DIR = Path("output")
IMAGE_DIR = OUTPUT_DIR / "images"
GROBID_URL = "http://localhost:8070/api/processFulltextDocument"
MODEL_NAME = "Helsinki-NLP/opus-mt-en-tr"  # hafif akademik çeviri modeli

log = logger.get_logger("pipeline")

# ==============================
#  LOAD TRANSLATION MODEL
# ==============================
log.info("Çeviri modeli yükleniyor...")
tokenizer = MarianTokenizer.from_pretrained(MODEL_NAME)
model = MarianMTModel.from_pretrained(MODEL_NAME)
log.info("Model yüklendi.")

# ==============================
#  FUNCTIONS
# ==============================
def grobid_parse(pdf_path: Path) -> str:
    """Grobid ile PDF’den TEI XML çıkartır."""
    log.info(f"Grobid parsing: {pdf_path}")
    with open(pdf_path, "rb") as f:
        files = {"input": f}
        response = requests.post(GROBID_URL, files=files)
        response.raise_for_status()
        return response.text


def extract_text_and_formulas(tei_xml: str):
    """TEI XML’den metin ve formülleri ayıklar."""
    soup = BeautifulSoup(tei_xml, "lxml")
    # Formüller <formula> tagları ile varsayılır
    formulas = [str(f) for f in soup.find_all("formula")]
    # Metin blokları <p> tagları
    paragraphs = [p.get_text(separator=" ", strip=True) for p in soup.find_all("p")]
    return paragraphs, formulas


def translate_text_blocks(text_blocks: list):
    """Metin bloklarını modele çevirir."""
    translated_blocks = []
    for block in text_blocks:
        inputs = tokenizer(block, return_tensors="pt", truncation=True, max_length=512)
        translated = model.generate(**inputs)
        decoded = tokenizer.decode(translated[0], skip_special_tokens=True)
        translated_blocks.append(decoded)
    return translated_blocks


def main():
    log.info("Pipeline başlatılıyor...")

    pdf_files = file_manager.list_pdfs(INPUT_DIR)
    if not pdf_files:
        log.error(f"{INPUT_DIR} içinde PDF bulunamadı!")
        return

    for pdf_path in pdf_files:
        log.info(f"İşleniyor: {pdf_path.name}")

        # Grobid parsing
        try:
            tei_xml = grobid_parse(pdf_path)
        except Exception as e:
            log.error(f"Grobid parsing hatası: {e}")
            continue

        # Metin ve formüller ayıkla
        text_blocks, formulas = extract_text_and_formulas(tei_xml)

        # Çeviri
        translated_blocks = translate_text_blocks(text_blocks)

        # LaTeX dosyası oluştur
        output_tex = OUTPUT_DIR / (pdf_path.stem + "_translated.tex")
        latex_builder.build_latex_document(
            text_blocks=translated_blocks,
            formulas=formulas,
            images=[],
            output_path=output_tex
        )

        # Validator ile PDF oluştur
        if validator.validate_latex(output_tex):
            log.info(f"PDF başarıyla oluşturuldu: {output_tex.stem}.pdf")
        else:
            log.error(f"PDF oluşturulamadı: {output_tex.stem}")

    log.info("Pipeline tamamlandı.")


if __name__ == "__main__":
    main()
