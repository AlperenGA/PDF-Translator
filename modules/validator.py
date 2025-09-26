from pathlib import Path
import subprocess
from modules.logger import get_logger

logger = get_logger(__name__)

def validate_latex(tex_path: Path) -> bool:
    try:
        cmd = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", str(tex_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"LaTeX compiled successfully: {tex_path}")
            return True
        else:
            logger.error(f"LaTeX compilation failed:\n{result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return False
