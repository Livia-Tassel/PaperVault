"""Bind the final installer to installed-file verification and source history."""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prior-uninstall-version', help='Version of an existing uninstall-retention report; never implies a rerun for this release')
    args = parser.parse_args()
    version = json.loads((ROOT / 'apps/desktop/package.json').read_text(encoding='utf-8'))['version']
    layout = json.loads((ROOT / "artifacts/install-layout.json").read_text(encoding="utf-8-sig"))
    native = json.loads((ROOT / 'artifacts/installed-desktop/report.json').read_text(encoding='utf-8'))
    assert layout['version'] == version and native['checks']['appVersion'] == version
    assert native['passed'] and native['parsed']['pdf_region_highlight']
    prior_retention = None
    if args.prior_uninstall_version:
        retention_path = ROOT / 'docs/verification/uninstall-retention.json'
        retention = json.loads(retention_path.read_text(encoding='utf-8-sig'))
        assert retention['passed'] and {'after_uninstall', 'after_reinstall'} <= set(retention['verified_phases'])
        prior_retention = {'version': args.prior_uninstall_version, 'passed': True,
                           'evidence': retention_path.relative_to(ROOT).as_posix(),
                           'evidence_sha256': hashlib.sha256(retention_path.read_bytes()).hexdigest()}
    installer = Path(layout["installer_path"])
    with installer.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    assert digest.casefold() == layout["installer_sha256"].casefold()
    report = {
        "version": version, "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_worktree_dirty": bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()),
        "installer": {"path": installer.relative_to(ROOT).as_posix(), "bytes": installer.stat().st_size,
                      "sha256": digest, "signed": False},
        "application_sha256": layout["application_sha256"], "backend_sha256": layout["backend_sha256"],
        "license_files_verified": layout["license_files_verified"],
        "source_archives_verified": layout["source_archives_verified"],
        "verification": {"real_pdf_workflow": True, "installed_tauri": True, "uninstall_retention": False,
                         "clean_windows_vm": False, "hosted_ci_executed": False},
        "prior_version_uninstall_retention": prior_retention,
        "known_diagnostics": "See TEST_REPORT.md and native-exception-investigation.json; one historical native diagnostic was not reproduced.",
    }
    (ROOT / "artifacts/release-manifest.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    installer.with_suffix(".exe.sha256").write_text(f"{digest}  {installer.name}\n", encoding="utf-8")
    print(f"Verified installer: {installer.name}, {installer.stat().st_size} bytes, SHA256 {digest}")


if __name__ == "__main__":
    main()
