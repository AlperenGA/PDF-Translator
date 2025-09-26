from pathlib import Path
from modules.logger import get_logger

logger = get_logger(__name__)

def escape_latex(text: str) -> str:
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
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

def build_latex_document(text_blocks: list, formulas: list, images: list, output_path: Path):
    ensure_dir = output_path.parent
    ensure_dir.mkdir(parents=True, exist_ok=True)
    
    latex_content = "\\documentclass[12pt]{article}\n"
    latex_content += "\\usepackage{amsmath, amssymb, graphicx, geometry}\n"
    latex_content += "\\geometry{margin=1in}\n"
    latex_content += "\\begin{document}\n\n"

    for i, block in enumerate(text_blocks):
        latex_content += escape_latex(block) + "\n\n"
        if i < len(formulas):
            latex_content += formulas[i] + "\n\n"

    for img_path in images:
        latex_content += f"\\includegraphics[width=\\linewidth]{{{img_path}}}\n\n"

    latex_content += "\\end{document}"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(latex_content)
    
    logger.info(f"LaTeX document created at {output_path}")
