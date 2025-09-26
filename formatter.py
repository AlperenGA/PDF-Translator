import re
from pathlib import Path
import subprocess

LATEX_TEMPLATE = r"""
\documentclass[12pt]{article}
\usepackage[utf8]{inputenc}
\usepackage{amsmath, graphicx, booktabs}
\usepackage{geometry}
\geometry{margin=2cm}
\begin{document}

%s

\end{document}
"""

def format_table(table_soup):
    rows = table_soup.find_all("row")
    latex = "\\begin{tabular}{%s}\n" % ("c" * len(rows[0].find_all("cell")))
    latex += "\\toprule\n"
    for row in rows:
        cells = [c.get_text(strip=True) for c in row.find_all("cell")]
        latex += " & ".join(cells) + " \\\\\n"
    latex += "\\bottomrule\n\\end{tabular}\n"
    return latex

def build_latex(blocks, images):
    latex_blocks = []
    for i, block in enumerate(blocks, start=1):
        if block["type"] == "text":
            latex_blocks.append(block["content"])
        elif block["type"] == "formula":
            latex_blocks.append(f"\\[{block['content']}\\]")
        elif block["type"] == "table":
            latex_blocks.append(format_table(block["content"]))
        if i in images:
            for img in images[i]:
                latex_blocks.append(f"\\includegraphics[width=0.5\\textwidth]{{{img}}}")
    return LATEX_TEMPLATE % "\n\n".join(latex_blocks)

def save_pdf(latex_content: str, output_file: Path):
    tex_file = output_file.with_suffix(".tex")
    tex_file.write_text(latex_content, encoding="utf-8")
    subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "-output-directory", str(output_file.parent), str(tex_file)],
        check=True
    )
