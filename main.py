import argparse
from pathlib import Path
import logging

from modules import pdf_utils, translator, latex_builder
from pipeline import process_pdf  # pipeline.py içinde olacak ana işleyici

logging.basicConfig(level=logging.INFO)


def main():
    parser = argparse.ArgumentParser(description="Academic PDF Translator")
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Çevrilecek PDF dosyası veya klasörü"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="output",
        help="Çeviri sonrası çıktıların kaydedileceği klasör"
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Eğer klasörse, içindeki tüm PDF'leri bul
    if input_path.is_dir():
        pdf_files = pdf_utils.list_pdfs(input_path)
    else:
        pdf_files = [input_path]

    if not pdf_files:
        logging.error("Hiç PDF bulunamadı!")
        return

    for pdf_file in pdf_files:
        logging.info(f"İşleniyor: {pdf_file}")
        try:
            process_pdf(pdf_file, output_dir)
            logging.info(f"✅ Başarılı: {pdf_file.name} çevrildi ve kaydedildi.")
        except Exception as e:
            logging.error(f"❌ Hata oluştu {pdf_file.name}: {e}")


if __name__ == "__main__":
    main()
