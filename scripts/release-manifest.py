"""Bind the final installer to installed-file verification and source history."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    layout = json.loads((ROOT / "artifacts/install-layout.json").read_text(encoding="utf-8-sig"))
    installer = Path(layout["installer_path"])
    with installer.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    assert digest.casefold() == layout["installer_sha256"].casefold()
    report = {
        "version": "0.1.0", "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "installer": {"path": installer.relative_to(ROOT).as_posix(), "bytes": installer.stat().st_size,
                      "sha256": digest, "signed": False},
        "application_sha256": layout["application_sha256"], "backend_sha256": layout["backend_sha256"],
        "license_files_verified": layout["license_files_verified"],
        "source_archives_verified": layout["source_archives_verified"],
        "verification": {"real_pdf_workflow": True, "installed_tauri": True, "uninstall_retention": True,
                         "clean_windows_vm": False, "hosted_ci_executed": False},
        "known_diagnostics": "See TEST_REPORT.md and native-exception-investigation.json; one historical native diagnostic was not reproduced.",
    }
    (ROOT / "artifacts/release-manifest.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    installer.with_suffix(".exe.sha256").write_text(f"{digest}  {installer.name}\n", encoding="utf-8")
    print(f"Verified installer: {installer.name}, {installer.stat().st_size} bytes, SHA256 {digest}")


if __name__ == "__main__":
    main()
