from pathlib import Path
import shutil

def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)

def list_pdfs(input_dir: Path):
    ensure_dir(input_dir)
    return list(input_dir.glob("*.pdf"))

def save_file(path: Path, content: bytes):
    ensure_dir(path.parent)
    with open(path, "wb") as f:
        f.write(content)

def copy_file(src: Path, dst: Path):
    ensure_dir(dst.parent)
    shutil.copy(src, dst)
