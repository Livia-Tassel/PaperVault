"""Copy compact final local evidence into the reviewable documentation tree."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ["acceptance-source.json", "acceptance-public-paper.json", "acceptance-frozen.json",
           "queue-acceptance.json", "search-benchmark.json", "gallery-benchmark.json",
           "pdf-geometry-browser.json", "outline-ui-acceptance.json", "excel-csv.json",
           "pytest-final.xml", "uninstall-retention.json", "release-manifest.json",
           "metadata-refresh-ui.json", "native-exception-investigation.json",
           "installed-desktop/report.json", "install-layout.json",
           "ui-review/review.json", "ui-redesign-regression.json"]


def main():
    destination = ROOT / "docs/verification"
    destination.mkdir(parents=True, exist_ok=True)
    copied = []
    for relative in REPORTS:
        source = ROOT / "artifacts" / relative
        if source.is_file():
            name = relative.replace("/", "-")
            shutil.copyfile(source, destination / name)
            copied.append(name)
    print(f"Preserved {len(copied)} verification reports")


if __name__ == "__main__":
    main()
