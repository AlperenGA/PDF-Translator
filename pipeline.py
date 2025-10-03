# pipeline.py
"""
PDF → GROBID parse → text & formulas → translation (preserve formulas) →
image extraction → LaTeX → final translated PDF
"""

from pathlib import Path
import re, logging, subprocess, html, os
from typing import List, Dict

import requests
from bs4 import BeautifulSoup
import fitz  # PyMuPDF

# ------------------------
# CONFIG
# ------------------------
GROBID_URL = "http://localhost:8070/api/processFulltextDocument"
MODEL_NAME = "facebook/m2m100_418M"
SRC_LANG, TGT_LANG = "tr", "en"
OUTPUT_DIR = Path("output"); OUTPUT_DIR.mkdir(exist_ok=True)

# ------------------------
# Logging
# ------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("pipeline")

# ------------------------
# Translation model (lazy)
# ------------------------
try:
    from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
    _TRANSFORMERS = True
except ImportError:
    _TRANSFORMERS = False

tokenizer, model = None, None
def ensure_model_loaded():
    global tokenizer, model
    if not _TRANSFORMERS:
        raise RuntimeError("transformers kütüphanesi gerekli (pip install transformers sentencepiece torch)")
    if tokenizer is None or model is None:
        log.info("Çeviri modeli yükleniyor...")
        tokenizer = M2M100Tokenizer.from_pretrained(MODEL_NAME)
        model = M2M100ForConditionalGeneration.from_pretrained(MODEL_NAME)
        log.info("Model hazır.")

# ------------------------
# Helpers
# ------------------------
def escape_latex(text: str) -> str:
    """LaTeX kaçışları (formüller hariç)."""
    if not text: return ""
    replacements = {
        "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
        "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
        "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
        "<": r"\textless{}", ">": r"\textgreater{}",
    }
    text = html.unescape(text)
    for k,v in replacements.items():
        text = text.replace(k,v)
    return re.sub(r"\s+\n", "\n", text)

# ------------------------
# 1) GROBID parse
# ------------------------
def grobid_parse(pdf_path: Path, consolidate: int = 1, timeout: int = 120) -> str:
    log.info(f"GROBID parse başlatılıyor: {pdf_path}")
    with open(pdf_path, "rb") as f:
        resp = requests.post(
            GROBID_URL,
            files={"input": f},
            data={"consolidate": str(consolidate)},
            timeout=timeout
        )
    if resp.status_code != 200:
        raise RuntimeError(f"GROBID hata {resp.status_code}: {resp.text[:500]}")
    return resp.text

# ------------------------
# 2) TEI XML → bloklar
# ------------------------
def extract_text_and_formulas(tei_xml: str) -> List[Dict]:
    soup = BeautifulSoup(tei_xml, "lxml-xml")
    body = soup.find("text") or soup
    blocks, allowed = [], {"p","head","figure","table","note","div","list","row","cell","figDesc","label"}

    for elem in body.find_all(True):
        if elem.name not in allowed: continue
        raw_html = str(elem)
        formulas = ["".join(str(x) for x in f.contents).strip() for f in elem.find_all("formula")]
        text_plain = raw_html
        if formulas:
            def repl(m,c=[0]):
                token=f"__FORMULA_{c[0]}__"; c[0]+=1; return token
            text_plain = re.sub(r"<formula[^>]*>.*?</formula>", repl, raw_html, flags=re.DOTALL)
        text_plain = re.sub(r"<[^>]+>", " ", text_plain)
        text_plain = html.unescape(re.sub(r"\s+"," ",text_plain)).strip()
        blocks.append({"type": elem.name,"raw": raw_html,"formulas": formulas,"text_plain": text_plain})
    log.info(f"{len(blocks)} blok çıkarıldı.")
    return blocks

# ------------------------
# 3) Çeviri
# ------------------------
def translate_blocks(blocks: List[Dict], src_lang=SRC_LANG, tgt_lang=TGT_LANG) -> List[Dict]:
    ensure_model_loaded()
    for i, b in enumerate(blocks):
        plain = b.get("text_plain") or ""
        if not plain: b["translated"]=""; continue
        try:
            tokenizer.src_lang = src_lang
            inputs = tokenizer(plain, return_tensors="pt", truncation=True)
            gen = model.generate(
                **inputs,
                forced_bos_token_id=tokenizer.get_lang_id(tgt_lang),
                max_length=min(1024, len(inputs["input_ids"][0])*3),
                num_beams=4, early_stopping=True
            )
            out = tokenizer.batch_decode(gen, skip_special_tokens=True)[0]
            # formül placeholderları geri koy
            for idx, f in enumerate(b.get("formulas", [])):
                out = out.replace(f"__FORMULA_{idx}__", f"[[FORMULA_{i}_{idx}]]{f}[[/FORMULA_{i}_{idx}]]", 1)
            b["translated"]=out
        except Exception as e:
            log.warning(f"Çeviri hatası (blok {i}): {e}"); b["translated"]=plain
    return blocks

# ------------------------
# 4) PDF görselleri
# ------------------------
def extract_images_from_pdf(pdf_path: Path, outdir: Path) -> Dict[int,List[Path]]:
    doc = fitz.open(pdf_path); page_imgs={}
    for i,page in enumerate(doc, start=1):
        imgs=[]
        for j,img in enumerate(page.get_images(full=True)):
            xref=img[0]
            try:
                pix=fitz.Pixmap(doc,xref)
                if pix.n>=5: pix=fitz.Pixmap(fitz.csRGB,pix)
                ipath=outdir/f"{pdf_path.stem}_p{i}_img{j}.png"
                pix.save(ipath); imgs.append(ipath)
            except Exception as e:
                log.warning(f"Resim çıkarma hatası p{i} img{j}: {e}")
        if imgs: page_imgs[i]=imgs
    return page_imgs

# ------------------------
# 5) LaTeX oluştur
# ------------------------
LATEX_PREAMBLE = r"""\documentclass[12pt]{article}
\usepackage[utf8]{inputenc}
\usepackage{amsmath,amssymb,graphicx,geometry,fancyvrb}
\geometry{margin=2cm}
\begin{document}"""
LATEX_POSTAMBLE = r"\end{document}"

def create_latex_pdf(blocks: List[Dict], images: Dict[int,List[Path]], output_base: Path):
    tex_path=output_base.with_suffix(".tex")
    with open(tex_path,"w",encoding="utf-8") as tex:
        tex.write(LATEX_PREAMBLE+"\n")
        for b in blocks:
            txt=b.get("translated","").strip()
            if not txt: continue
            # formülleri LaTeX Verbatim olarak geri koy
            txt=re.sub(r"\[\[FORMULA_\d+_\d+\]\](.*?)\[\[/FORMULA_\d+_\d+\]\]",
                       lambda m:f"\n\\begin{{Verbatim}}[fontsize=\\small]\n{m.group(1)}\n\\end{{Verbatim}}\n",txt,flags=re.DOTALL)
            # güvenli escape
            parts=re.split(r"(\\begin\{Verbatim\}.*?\\end\{Verbatim\})",txt,flags=re.DOTALL)
            for p in parts:
                tex.write(p if p.startswith("\\begin{Verbatim}") else escape_latex(p))
                tex.write("\n\n")
        # ek görseller
        for p,imgs in sorted(images.items()):
            tex.write("\\clearpage\n% page {p} images\n")
            for ip in imgs:
                rel=os.path.relpath(ip,OUTPUT_DIR)
                tex.write(f"\\includegraphics[width=0.9\\textwidth]{{{rel}}}\n\n")
        tex.write(LATEX_POSTAMBLE)
    # compile twice
    for _ in range(2):
        subprocess.run(
            ["pdflatex","-interaction=nonstopmode","-halt-on-error",
             "-output-directory",str(OUTPUT_DIR),str(tex_path)],
            check=False,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True
        )
    log.info(f"PDF oluşturuldu: {output_base.with_suffix('.pdf')}")

# ------------------------
# 6) Ana orkestrasyon
# ------------------------
def translate_pdf(pdf_path: Path, src_lang=SRC_LANG, tgt_lang=TGT_LANG):
    log.info(f"Çeviri pipeline başlatıldı: {pdf_path}")
    tei=grobid_parse(pdf_path)
    blocks=extract_text_and_formulas(tei)
    blocks=translate_blocks(blocks,src_lang,tgt_lang)
    images=extract_images_from_pdf(pdf_path,OUTPUT_DIR)
    create_latex_pdf(blocks,images,OUTPUT_DIR/pdf_path.stem)
    log.info("Pipeline tamamlandı.")

if __name__=="__main__":
    import sys
    if len(sys.argv)<2: print("Kullanım: python pipeline.py dosya.pdf"); exit(1)
    translate_pdf(Path(sys.argv[1]))
