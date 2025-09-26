from pathlib import Path

# Model ve Grobid ayarları
MODEL_NAME = "facebook/nllb-200-distilled-600M"
SRC_LANG = "eng_Latn"
TGT_LANG = "tur_Latn"
GROBID_URL = "http://localhost:8070/api/processFulltextDocument"

# Dosya yolları
INPUT_DIR = Path("pdfs")
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
