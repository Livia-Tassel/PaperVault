"""Bind the final installer to installed-file verification and source history."""
import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prior-uninstall-version', help='Version of an existing uninstall-retention report; never implies a rerun for this release')
    parser.add_argument('--reading-report', type=Path, default=ROOT / 'artifacts/installed-reading/report.json')
    parser.add_argument('--source-commit', default='HEAD', help='Production source revision; later evidence-only commits do not change the binary')
    args = parser.parse_args()
    version = json.loads((ROOT / 'apps/desktop/package.json').read_text(encoding='utf-8'))['version']
    layout = json.loads((ROOT / "artifacts/install-layout.json").read_text(encoding="utf-8-sig"))
    native = json.loads((ROOT / 'artifacts/installed-desktop/report.json').read_text(encoding='utf-8'))
    assert layout['version'] == version and native['checks']['appVersion'] == version
    assert native['passed'] and native['parsed']['pdf_region_highlight']
    resources = json.loads((ROOT / 'apps/desktop/src-tauri/tauri.bundle.conf.json').read_text(encoding='utf-8'))['bundle']['resources']
    documents = layout['bundled_documents_verified']
    for source, destination in resources.items():
        if source.startswith('../../../docs/') and not source.endswith('/'):
            expected_hash = hashlib.sha256((ROOT / source.removeprefix('../../../')).read_bytes()).hexdigest()
            assert documents[destination].casefold() == expected_hash, destination
            assert hashlib.sha256((Path(layout['install_root']) / destination).read_bytes()).hexdigest() == expected_hash, destination
    reading = None
    frontend_entry = None
    if tuple(map(int, version.split('.')[:2])) >= (0, 2):
        reading = json.loads(args.reading_report.read_text(encoding='utf-8'))
        assert reading['passed'] and reading['desktop_version'] == version
        assert Path(reading['app']).resolve() == Path(native['app']).resolve()
        entry = re.search(r'<script[^>]+src="([^"]+)"', (ROOT / 'apps/desktop/dist/index.html').read_text(encoding='utf-8'))
        assert entry, 'Cannot identify final frontend entry'
        frontend_entry = Path(entry.group(1)).name
        assert reading['frontend_bundle'] == frontend_entry
        assert any(src.endswith('/' + frontend_entry) for src in reading['document_scripts'])
        for phase in ('real_0001_library_migrated_with_pdf_and_manual_metadata_unchanged',
                      'same_outline_item_relocates_after_manual_scroll_twice',
                      'same_id_different_path_library_switch_clears_editor_and_undo_on_same_notes_route',
                      'delayed_old_scope_patch_rejected_without_changing_restored_library',
                      'actual_windows_save_dialog_cancel_has_no_success_toast_file_or_annotation_loss',
                      'native_note_create_edit_search_delete_undo_and_real_json_markdown_exports'):
            assert phase in reading['phases'], phase
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
        "source_commit": subprocess.check_output(["git", "rev-parse", "--verify", args.source_commit + '^{commit}'], cwd=ROOT, text=True).strip(),
        "source_worktree_dirty": bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()),
        "installer": {"path": installer.relative_to(ROOT).as_posix(), "bytes": installer.stat().st_size,
                      "sha256": digest, "signed": False},
        "application_sha256": layout["application_sha256"], "backend_sha256": layout["backend_sha256"],
        "frontend_bundle": frontend_entry,
        "license_files_verified": layout["license_files_verified"],
        "source_archives_verified": layout["source_archives_verified"],
        "bundled_documents_verified": documents,
        "verification": {"real_pdf_workflow": True, "installed_tauri": True, "uninstall_retention": False,
                         "installed_reading_notes_legacy_migration": bool(reading),
                         "same_id_restored_library_isolation": bool(reading),
                         "clean_windows_vm": False, "hosted_ci_executed": False},
        "prior_version_uninstall_retention": prior_retention,
        "known_diagnostics": "See TEST_REPORT.md and native-exception-investigation.json; one historical native diagnostic was not reproduced.",
    }
    (ROOT / "artifacts/release-manifest.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    installer.with_suffix(".exe.sha256").write_text(f"{digest}  {installer.name}\n", encoding="utf-8")
    print(f"Verified installer: {installer.name}, {installer.stat().st_size} bytes, SHA256 {digest}")


if __name__ == "__main__":
    main()
