from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import logging
from config import MODEL_NAME, SRC_LANG, TGT_LANG
import re

logging.basicConfig(level=logging.INFO)

# Model ve tokenizer yükleme
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)

# Çeviri dışında tutulacak patternler (matematik formülleri, LaTeX, semboller, sayılar, tablolar)
MATH_PATTERN = re.compile(
    r"(\$.*?\$|\\\[.*?\\\]|\\\(.*?\\\)|\{.*?\}|[∑∫√∞≠≈≤≥→←±÷×∂∆∇πµθλΩ]|[0-9]+(\.[0-9]+)?)"
)

def translate_text(text: str) -> str:
    """Türkçeden İngilizceye çeviri yapar, formülleri ve sembolleri korur"""
    if not text.strip():
        return text

    # Matematiksel kısımları korumak için parçala
    parts = MATH_PATTERN.split(text)

    translated_parts = []
    for i, part in enumerate(parts):
        if not part.strip():
            translated_parts.append(part)
            continue

        # Eğer bu parça matematiksel formül veya sembol ise çeviri yapma
        if MATH_PATTERN.fullmatch(part):
            translated_parts.append(part)
        else:
            # Çeviri uygula
            inputs = tokenizer(part, return_tensors="pt", truncation=True)
            translated_tokens = model.generate(
                **inputs,
                forced_bos_token_id=tokenizer.lang_code_to_id[TGT_LANG],
                max_length=512
            )
            translated_text = tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)[0]
            translated_parts.append(translated_text)

    return "".join(translated_parts)
