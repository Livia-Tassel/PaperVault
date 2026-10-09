"""Archive release evidence without overwriting prior versions' verification."""
import argparse
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", help="Release to archive; defaults to current package version")
    parser.add_argument("--evidence-root", type=Path, help="Directory holding that exact release's installed reports")
    args = parser.parse_args()
    version = args.release or json.loads((ROOT / "apps/desktop/package.json").read_text(encoding="utf-8"))["version"]
    evidence = args.evidence_root or ROOT / "artifacts" / ("" if version == "0.2.0" else "v" + version.replace(".", ""))
    manifest = json.loads((evidence / "release-manifest.json").read_text(encoding="utf-8"))
    if manifest["version"] != version:
        raise SystemExit("Evidence belongs to a different release; refuse to relabel old results")
    reports = REPORTS if version == "0.2.0" else (
        "release-manifest.json", "install-layout.json", "installed-desktop/report.json", "installed-reading/report.json")
    destination = ROOT / "docs/verification" / version
    missing = [relative for relative in reports if not (evidence / relative).is_file()]
    if missing:
        raise SystemExit("Missing release evidence: " + ", ".join(missing))
    for relative in reports:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(evidence / relative, target)
    print(f"Preserved {len(reports)} verification reports for {version}")


if __name__ == "__main__":
    main()
