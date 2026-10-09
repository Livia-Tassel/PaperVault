"""Archive release evidence without overwriting prior versions' verification."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Keep the hierarchy so before/after links remain valid. Existing flat reports
# describe earlier releases and must not be rewritten with a new version.
REPORTS = (
    "release-manifest.json", "install-layout.json", "installed-desktop/report.json",
    "installed-reading/report.json", "acceptance-frozen-v02.json",
    "reading-reparse-frozen-v02.json", "reading-backend-tests.json",
    "backend-release-v02-execution.json", "backend-release-v02-junit.xml",
    "frontend-release-v02.json", "legacy-regression-v02/report.json",
    "workspace-navigation-ui.json", "native-close-guard/report.json",
    "reader-performance/report.json", "annotation-benchmark/report.json",
    "annotation-benchmark/before/report.json", "annotation-benchmark/after/report.json",
    "ui-review-v02/review.json", "ui-review-v02-keyboard/review.json",
    "goal-checkpoint-v02.json", "goal-final-v02.json", "upgrade-v02-final.json",
)


def main():
    version = json.loads((ROOT / "apps/desktop/package.json").read_text(encoding="utf-8"))["version"]
    destination = ROOT / "docs/verification" / version
    missing = [relative for relative in REPORTS if not (ROOT / "artifacts" / relative).is_file()]
    if missing:
        raise SystemExit("Missing release evidence: " + ", ".join(missing))
    for relative in REPORTS:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "artifacts" / relative, target)
    print(f"Preserved {len(REPORTS)} verification reports for {version}")


if __name__ == "__main__":
    main()
