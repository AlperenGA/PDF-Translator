from pathlib import Path
from typing import Dict, List

LATEX_HEADER = r"""
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

LATEX_FOOTER = r"""
\end{document}
"""


def escape_latex(text: str) -> str:
    """
    LaTeX'te özel karakterlerden dolayı hata çıkmasını engeller.
    """
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\^{}",
        "\\": r"\textbackslash{}",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text


def build_latex_document(
    translated_pages: Dict[int, List[str]],
    formulas: Dict[int, List[str]],
    images: Dict[int, List[Path]]
) -> str:
    """
    PDF'ten alınan çeviri, formül ve görselleri LaTeX dokümanına dönüştürür.
    Sayfa sırası korunur.
    """
    content = [LATEX_HEADER]

    for page_num in sorted(translated_pages.keys()):
        content.append(f"% Page {page_num}\n")

        # Çeviri metinleri
        for paragraph in translated_pages[page_num]:
            paragraph = paragraph.strip()
            if paragraph:
                content.append(escape_latex(paragraph) + "\n\n")

        # Formüller
        if page_num in formulas:
            for formula in formulas[page_num]:
                content.append("\\begin{equation}\n")
                content.append(formula.strip() + "\n")
                content.append("\\end{equation}\n\n")

        # Görseller
        if page_num in images:
            for img_path in images[page_num]:
                content.append("\\begin{figure}[ht]\n")
                content.append("\\centering\n")
                content.append(f"\\includegraphics[width=0.9\\textwidth]{{{img_path.name}}}\n")
                content.append("\\end{figure}\n\n")

        # Sayfa sonu
        content.append("\\clearpage\n")

    content.append(LATEX_FOOTER)
    return "".join(content)


def save_latex_file(output_path: Path, latex_code: str):
    """
    LaTeX çıktısını .tex dosyasına kaydeder.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(latex_code)
