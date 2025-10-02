def build_latex(items, images_by_page=None):
    """
    Çeviri sonrası metin + formülleri düzgün LaTeX formatında PDF’e dönüştürür.
    """
    header = r"""
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
    body = []
    page_idx = 1

    for item in items:
        if item["type"] == "text":
            body.append(item["content"] + "\n\n\\par\n")
        elif item["type"] == "formula":
            body.append("\\begin{equation}\n" + item["content"] + "\n\\end{equation}\n")
        elif item["type"] == "pagebreak":
            # Görselleri ekle
            if images_by_page and page_idx in images_by_page:
                for i, img in enumerate(images_by_page[page_idx]):
                    body.append(
                        "\\begin{figure}[ht]\n\\centering\n"
                        f"\\includegraphics[width=0.9\\textwidth]{{{img}}}\n"
                        "\\end{figure}\n\n"
                    )
            body.append("\\clearpage\n")
            page_idx += 1

    footer = r"""
\end{document}
"""
    return header + "".join(body) + footer
