from pathlib import Path
from pipeline import process_pdf

def test_pipeline_runs(tmp_path):
    sample = Path("pdfs/sample.pdf")
    if sample.exists():
        process_pdf(sample)
        assert (Path("output") / "sample.pdf").exists()
