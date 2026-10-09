"""Native 0.2 reading/note/migration and same-ID restored-library isolation test.

Works with a debug app now and the installed release later; never uses port 8765.
The legacy fixture is prepared by the verified old frozen 0.1.x backend, then the
new app must migrate it while preserving its PDF and manual metadata files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from urllib.parse import urlsplit

from legacy_fixture import seed_legacy_library
from native_client import NativeClient, ROOT, wait_until


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', type=Path, default=ROOT / 'apps/desktop/src-tauri/target/x86_64-pc-windows-msvc/debug/papervault.exe')
    parser.add_argument('--legacy-backend', type=Path, default=ROOT / '.test-data/installed/PaperVault/papervault-backend.exe')
    parser.add_argument('--prepared-fixture', type=Path, help='Reuse the owned legacy fixture manifest after upgrading the installer')
    parser.add_argument('--expect-version')
    parser.add_argument('--expect-frontend', help='Expected embedded Vite entry filename from the final dist/index.html')
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/native-reading')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    root = (ROOT / '.test-data/reading-migration').resolve()
    assert root.is_relative_to(ROOT / '.test-data')
    root.mkdir(parents=True, exist_ok=True)
    fixture = Path(tempfile.mkdtemp(prefix='reading-', dir=root)).resolve()
    a_path, b_path = fixture / '原始论文库', fixture / '备份副本'
    report = {'passed': False, 'app': str(args.app.resolve()), 'fixture': str(fixture), 'phases': []}
    client = NativeClient(args.app, fixture, a_path, args.output)
    try:
        sys.path.insert(0, str(ROOT / 'backend'))
        from papervault.backup import restore_backup
        if args.prepared_fixture:
            prepared_path = args.prepared_fixture.resolve()
            allowed = (ROOT / '.test-data', ROOT / 'tests/fixtures')
            assert any(prepared_path.is_relative_to(directory) for directory in allowed)
            prepared = json.loads(prepared_path.read_text(encoding='utf-8'))
            archive = (prepared_path.parent / prepared['archive']).resolve()
            assert any(archive.is_relative_to(directory) for directory in allowed)
            assert hashlib.sha256(archive.read_bytes()).hexdigest() == prepared['archive_sha256']
            restore_backup(archive, a_path)
            legacy = prepared['legacy']
        else:
            legacy = seed_legacy_library(args.legacy_backend, fixture, a_path)
        report['legacy'] = legacy
        client.start()
        version = client.execute("return window.__TAURI_INTERNALS__.invoke('plugin:app|version')")
        if args.expect_version:
            assert version == args.expect_version, version
        report['desktop_version'] = version
        scripts = client.execute("return [...document.scripts].map(script=>script.src).filter(Boolean)")
        report['document_scripts'] = scripts
        if args.expect_frontend:
            assert args.expect_frontend in [Path(urlsplit(src).path).name for src in scripts], scripts
            report['frontend_bundle'] = args.expect_frontend
        assert client.api('/health')['version'] == (args.expect_version or version)
        paper_id = legacy['paper_id']
        paper = client.api(f'/papers/{paper_id}')
        assert paper['notes'] == 'Legacy personal note must survive' and paper['tags'] == ['legacy-retained']
        with sqlite3.connect(a_path / 'database/papervault.db') as database:
            assert database.execute('SELECT version_num FROM alembic_version').fetchone()[0] == '0002'
        for relative, digest in legacy['retained_sha256'].items():
            assert hashlib.sha256((a_path / relative).read_bytes()).hexdigest() == digest
        report['phases'].append('real_0001_library_migrated_with_pdf_and_manual_metadata_unchanged')

        client.api(f'/papers/{paper_id}', 'PATCH', {'sections': [{
            'title': 'Repeated native location', 'level': 1, 'page_index': 0,
            'location': {'page_index': 0, 'bbox': [50, 690, 450, 735]},
        }]})

        client.click("//button[contains(@class,'paper-primary')]")
        wait_until(lambda: client.execute("return [...document.querySelectorAll('.pdf-page canvas')].some(e=>e.width>0)"), 'Migrated PDF did not render')
        client.click("//button[normalize-space()='目录']")
        outline = "//*[contains(@class,'outline')]//button[contains(.,'Repeated native location')]"
        scroll_positions = []
        report['repeated_outline_scroll_top'] = scroll_positions
        for attempt in range(2):
            report['outline_click_attempt'] = attempt + 1
            client.execute("document.querySelector('.pdf-scroll').scrollTop=800; return true")
            wait_until(lambda: client.execute("return document.querySelector('.pdf-scroll').scrollTop>500"), 'Reader did not scroll away from the heading')
            client.click(outline)
            wait_until(lambda: client.execute("return document.querySelector('.pdf-scroll').scrollTop<300 && Boolean(document.querySelector('.pdf-highlight'))"), 'Repeated outline click did not return to its source location')
            scroll_positions.append(client.execute("return document.querySelector('.pdf-scroll').scrollTop"))
        report['phases'].append('same_outline_item_relocates_after_manual_scroll_twice')
        client.fill("//input[@aria-label='PDF 页码']", '2\ue007')
        wait_until(lambda: client.execute("return document.querySelector('[aria-label=\"PDF 页码\"]')?.value==='2'"), 'Reader did not reach page 2')
        client.click("//button[@aria-label='添加本页书签']")
        wait_until(lambda: len(client.api(f'/annotations?paper_id={paper_id}&kind=bookmark')['items']) == 1, 'Native bookmark was not persisted')
        bookmark = client.api(f'/annotations?paper_id={paper_id}&kind=bookmark')['items'][0]
        assert bookmark['locations'][0]['page_index'] == 1
        client.click("//aside//button[@aria-label='笔记与书签']")
        wait_until(lambda: client.api(f'/papers/{paper_id}/reading-state')['page_index'] == 1, 'Reading position was not flushed before navigation')
        report['phases'].append('native_reader_page_change_bookmark_and_navigation_flush')

        note = client.api(f'/papers/{paper_id}/annotations', 'POST', {'kind': 'note', 'title': 'Scope-copy annotation', 'body': 'Original shared note', 'locations': []})
        archive = client.api('/backups', 'POST', {'destination': str(fixture / 'library-copy.zip')})['path']
        # Restore the verified archive without opening B; use the same production
        # restoration routine while A's backend and UI remain active.
        restore_backup(Path(archive), b_path)
        identity_a = client.api('/library')
        client.switch_library(b_path)
        identity_b = client.api('/library')
        assert identity_a['id'] == identity_b['id'] and identity_a['path'] != identity_b['path']
        assert client.api(f'/annotations/{note["id"]}')['body'] == note['body']
        client.click("//aside//button[@aria-label='笔记与书签']")

        def remove_note():
            client.click("//button[@aria-label='删除笔记 Scope-copy annotation']")
            client.click("//*[@role='dialog']//button[normalize-space()='删除笔记']")
            wait_until(lambda: client.execute("return Boolean(document.querySelector('.annotation-undo'))"), 'Delete did not expose undo')

        remove_note()
        client.switch_library(a_path)
        wait_until(lambda: client.execute("return document.querySelector('h1')?.textContent==='笔记与书签'"), 'A notes route was not restored')
        assert client.execute("return !document.querySelector('.annotation-undo') && !document.querySelector('[role=dialog]')")
        assert not client.api(f'/annotations/{note["id"]}')['deleted']
        remove_note()
        client.screenshot('library-a-with-undo')
        client.switch_library(b_path)
        wait_until(lambda: client.execute("return document.querySelector('h1')?.textContent==='笔记与书签'"), 'B notes route was not restored')
        assert client.execute("return !document.querySelector('.annotation-undo') && !document.querySelector('[role=dialog]')")
        removed_b = next(item for item in client.api('/annotations?deleted=true')['items'] if item['id'] == note['id'])
        assert removed_b['deleted'] and removed_b['version'] == 2
        report['phases'].append('same_id_different_path_library_switch_clears_editor_and_undo_on_same_notes_route')

        before = client.api(f'/papers/{paper_id}')
        denied = client.api(f'/papers/{paper_id}', 'PATCH', {'notes': 'Delayed A write must never reach B'},
                            scope=f"{identity_a['id']}:{identity_a['path']}", expect=409)
        assert denied['code'] == 'library_switched'
        assert client.api(f'/papers/{paper_id}')['notes'] == before['notes']
        assert next(item for item in client.api('/annotations?deleted=true')['items'] if item['id'] == note['id'])['version'] == 2
        report['phases'].append('delayed_old_scope_patch_rejected_without_changing_restored_library')
        client.screenshot('library-b-without-stale-undo')

        client.click("(//main//button[normalize-space()='新建笔记'])[1]")
        client.fill("//*[@role='dialog']//input[@aria-label='选择来源论文']", 'Legacy migration fixture')
        wait_until(lambda: client.execute("return [...document.querySelectorAll('[role=listbox] [role=option]')].some(button=>button.textContent.includes('Legacy migration fixture')&&!button.disabled)"), 'Source-paper search did not settle')
        client.click("//*[@role='listbox']//button[@role='option' and contains(.,'Legacy migration fixture') and not(@disabled)]")
        client.fill("//*[@role='dialog']//input[@aria-label='笔记标题']", 'Native 0.2 note')
        client.fill("//*[@role='dialog']//textarea[@aria-label='笔记内容']", 'native02marker created through the installed desktop UI')
        client.click("//*[@role='dialog']//button[normalize-space()='保存笔记']")
        def saved_note():
            return next((item for item in client.api('/annotations?kind=note')['items'] if item['title'] == 'Native 0.2 note'), None)
        wait_until(saved_note, 'Native note was not created')
        created = saved_note()
        client.fill("//*[@role='dialog']//textarea[@aria-label='笔记内容']", 'native02marker updated and persisted')
        client.click("//*[@role='dialog']//button[normalize-space()='保存笔记']")
        wait_until(lambda: client.api(f'/annotations/{created["id"]}')['body'] == 'native02marker updated and persisted', 'Native note edit did not persist')
        client.click("//*[@role='dialog']//button[@aria-label='关闭对话框']")
        client.fill("//input[@aria-label='搜索笔记']", 'native02marker')
        wait_until(lambda: client.execute("return document.querySelectorAll('.annotation-row').length===1 && document.querySelector('.annotation-row')?.textContent.includes('Native 0.2 note')"), 'Native note search did not find the saved content')
        assert any(item['id'] == created['id'] for item in client.api('/search?q=native02marker')['notes'])
        exported = client.api('/annotations/export', 'POST', {'ids': [created['id'], bookmark['id']], 'format': 'json'})
        assert 'native02marker' in json.dumps(exported) and bookmark['id'] in json.dumps(exported)
        markdown = client.api('/annotations/export', 'POST', {'ids': [created['id']], 'format': 'markdown'}, raw=True).decode('utf-8-sig')
        assert 'native02marker' in markdown and 'Legacy migration fixture' in markdown
        (args.output / 'notes-export.json').write_text(json.dumps(exported, ensure_ascii=False, indent=2), encoding='utf-8')
        (args.output / 'notes-export.md').write_text(markdown, encoding='utf-8')
        client.click("//button[@aria-label='删除笔记 Native 0.2 note']")
        client.click("//*[@role='dialog']//button[normalize-space()='删除笔记']")
        wait_until(lambda: client.execute("return Boolean(document.querySelector('.annotation-undo'))"), 'Native note deletion did not offer undo')
        client.click("//*[contains(@class,'annotation-undo')]//button[normalize-space()='撤销']")
        wait_until(lambda: any(item['id'] == created['id'] for item in client.api('/annotations?kind=note')['items']), 'Native note undo did not restore the record')
        client.screenshot('native-note-created-edited-searched-and-restored')
        report['phases'].append('native_note_create_edit_search_delete_undo_and_real_json_markdown_exports')

        before_cancel = client.api(f'/annotations/{created["id"]}')
        client.execute("window.__saveCancelSuccess=[]; window.__saveCancelObserver=new MutationObserver(()=>{for(const e of document.querySelectorAll('.toast'))if(e.textContent.includes('笔记已导出'))window.__saveCancelSuccess.push(e.textContent)});window.__saveCancelObserver.observe(document.body,{childList:true,subtree:true,characterData:true});return true")
        client.click("//main//*[contains(@class,'collection-toolbar')]//button[normalize-space()='导出']")
        client.click("//*[@role='dialog']//button[normalize-space()='导出笔记']")
        destination = fixture / 'cancelled-exports' / 'must-not-exist.md'
        report['native_save_cancel'] = client.cancel_native_save_dialog(destination)
        wait_until(lambda: client.execute("return ![...document.querySelectorAll('[role=dialog] button')].some(e=>e.textContent.includes('正在导出'))"), 'Export did not finish handling native cancellation')
        assert client.execute("return window.__saveCancelSuccess.length") == 0
        assert client.api(f'/annotations/{created["id"]}') == before_cancel
        assert not destination.exists() and not list(destination.parent.iterdir())
        client.execute("window.__saveCancelObserver.disconnect();return true")
        report['native_save_cancel'].update({'success_toasts': 0, 'destination_files': 0, 'annotation_unchanged': True})
        report['phases'].append('actual_windows_save_dialog_cancel_has_no_success_toast_file_or_annotation_loss')
        client.screenshot('native-save-cancelled')
        client.wm_close()
        client.assert_exit()
        report['phases'].append('window_and_sidecar_exit_cleanly')
        report['passed'] = True
        print('PASS: native reading/bookmark, real legacy migration, same-ID backup-copy isolation, stale-scope rejection')
    except Exception as error:
        report['error'] = str(error)
        if client.session:
            try:
                report['visible_errors'] = client.execute("return [...document.querySelectorAll('[role=alert]')].map(e=>e.textContent)")
                client.screenshot('failure')
            except Exception:
                pass
        raise
    finally:
        (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        client.close()


if __name__ == '__main__':
    main()
