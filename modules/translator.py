from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import logging
from config import MODEL_NAME, SRC_LANG, TGT_LANG

logging.basicConfig(level=logging.INFO)

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)

def translate_text(text: str) -> str:
    if not text.strip():
        return text
    inputs = tokenizer(text, return_tensors="pt", truncation=True)
    translated_tokens = model.generate(
        **inputs,
        forced_bos_token_id=tokenizer.lang_code_to_id[TGT_LANG],
        max_length=512
    )
    return tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)[0]
