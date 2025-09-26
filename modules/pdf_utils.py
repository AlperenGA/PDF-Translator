import fitz

def extract_images(pdf_path, output_dir):
    doc = fitz.open(pdf_path)
    page_images = {}
    for i, page in enumerate(doc):
        img_paths = []
        for j, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            pix = fitz.Pixmap(doc, xref)
            img_path = output_dir / f"{pdf_path.stem}_p{i+1}_img{j}.png"
            pix.save(img_path)
            img_paths.append(img_path)
            pix = None
        if img_paths:
            page_images[i+1] = img_paths
    return page_images
