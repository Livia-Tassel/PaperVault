"""Real installed UI follow-up for selected corpus papers, using an isolated backup copy.

Run after test_real_corpus.py has stopped its backend. This does not reparse or
modify the unedited extraction baseline. Selected real PDFs and auto resources
are opened using actual native WebView2 controls, then notes/bookmarks are saved
only in the copy. Screenshots are observations, not accuracy ground truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile
import traceback
from urllib.parse import urlsplit

from pypdf import PdfReader

from native_client import NativeClient, ROOT, wait_until
from test_real_corpus import EXPECTED_SHA256, FrozenBackend, digest, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus-report', type=Path, default=ROOT / 'artifacts/real-corpus/installed-backend-report.json')
    parser.add_argument('--paper-id', nargs='+', default=[])
    parser.add_argument('--source-id', nargs='+', default=[], help='Select source manifest IDs rather than generated paper UUIDs')
    parser.add_argument('--assert-source-title', nargs='+', default=[], help='Require these manifest IDs to show their exact known source title in API and native editor')
    parser.add_argument('--resource-mode', choices=('first', 'captioned'), default='captioned', help='Captioned picks the first captioned resource for scientific-image review; all auto counts remain reported')
    parser.add_argument('--resource-number', action='append', default=[], metavar='KIND:NUMBER', help='Require an exact source label, e.g. table:A.1 or figure:G.1; repeat once per kind')
    parser.add_argument('--app', type=Path, default=ROOT / '.test-data/installed/PaperVault/papervault.exe')
    parser.add_argument('--expect-version', default='0.2.0')
    parser.add_argument('--expect-sha256', default=EXPECTED_SHA256)
    parser.add_argument('--release-manifest', type=Path, default=ROOT / 'artifacts/release-manifest.json')
    parser.add_argument('--models', type=Path, default=ROOT / '.cache/models')
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/real-corpus/native')
    args = parser.parse_args()
    required_numbers = dict(value.split(':', 1) for value in args.resource_number)
    assert set(required_numbers) <= {'figure', 'table'} and all(required_numbers.values()), 'Resource-number needs figure/table and a nonempty exact label'
    assert len(required_numbers) == len(args.resource_number), 'Provide at most one required label per resource kind'
    assert args.paper_id or args.source_id, 'Explicitly select the real papers to review'
    corpus = json.loads(args.corpus_report.read_text(encoding='utf-8'))
    assert corpus.get('finished_at_utc') and corpus['shutdown']['backend_port_closed'], 'Wait for the corpus run to finish'
    selected = [paper for paper in corpus['papers'] if paper.get('paper_id') in args.paper_id or paper['source'].get('id') in args.source_id]
    assert selected and len(selected) == len(set(args.paper_id + args.source_id)), 'Every requested paper must resolve uniquely'
    assert set(args.assert_source_title) <= {paper['source'].get('id') for paper in selected}, 'Every title assertion must target a selected source'
    assert all(paper.get('auto_baseline_unchanged') for paper in selected), 'Selected papers need a completed auto baseline'
    backend_path = args.app.resolve().parent / 'papervault-backend.exe'
    assert digest(backend_path) == args.expect_sha256.lower() == corpus['backend_sha256']
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    test_root = ROOT / '.test-data/real-corpus-native'
    test_root.mkdir(parents=True, exist_ok=True)
    fixture = Path(tempfile.mkdtemp(prefix='native-', dir=test_root))
    library_path = fixture / 'real-paper-ui-copy'
    report = {'passed': False, 'app': str(args.app.resolve()), 'backend_sha256': digest(backend_path),
              'corpus_report': str(args.corpus_report.resolve()), 'corpus_report_sha256': digest(args.corpus_report),
              'fixture': str(fixture), 'library': str(library_path), 'papers': [], 'phases': []}
    client = None
    try:
        # Public installed-backend backup/restore; no source Library/database writes.
        preparation = FrozenBackend(backend_path, fixture / 'preparation', args.models.resolve(), 'native-copy', args.expect_version)
        with preparation:
            baseline = preparation.call('POST', '/library/open', json={'path': corpus['auto_baseline_library']['path']}).json()
            preparation.scope(baseline)
            archive = preparation.call('POST', '/backups', json={'destination': str(fixture / 'auto-baseline.zip')}).json()['path']
            preparation.call('POST', '/backups/restore', json={'path': archive, 'destination': str(library_path)})
            assert preparation.call('GET', '/library').json()['path'] == str(library_path)
        assert preparation.shutdown['backend_port_closed'] and not preparation.forced_termination
        report['phases'].append('installed_backend_restored_separate_copy_without_manual_baseline_edits')
        client = NativeClient(args.app, fixture, library_path, output).start()
        report['desktop_version'] = client.execute("return window.__TAURI_INTERNALS__.invoke('plugin:app|version')")
        assert report['desktop_version'] == args.expect_version
        report['document_scripts'] = client.execute('return [...document.scripts].map(s=>s.src).filter(Boolean)')
        manifest = json.loads(args.release_manifest.read_text(encoding='utf-8'))
        assert manifest['frontend_bundle'] in [Path(urlsplit(url).path).name for url in report['document_scripts']]
        wait_until(lambda: client.execute('return Boolean(document.querySelector(".workspace-bar"))') and client.api('/library')['path'] == str(library_path), 'Isolated real-paper copy did not open')
        client.click("//aside//button[@aria-label='设置']")
        client.click("//button[normalize-space()='深色']")

        def capture(name):
            wait_until(lambda: client.execute('return !document.querySelector(".toast,.loading") && [...document.images].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&r.bottom>0&&r.top<innerHeight}).every(e=>e.complete&&e.naturalWidth>0)'), 'Native screenshot did not settle')
            client.screenshot(name)

        for index, record in enumerate(selected, 1):
            paper_id = record['paper_id']
            evidence = {'paper_id': paper_id, 'source': record['source'], 'checks': [], 'resources': []}
            report['papers'].append(evidence)
            paper = client.api(f'/papers/{paper_id}')
            evidence['observed_auto_title'] = paper.get('title')
            assert hashlib.sha256(client.api(f'/papers/{paper_id}/pdf', raw=True)).hexdigest() == record['source_pdf']['sha256']
            resources = client.api(f'/resources?paper_id={paper_id}&limit=1000')['items']
            client.click("//aside//button[@aria-label='论文库']")
            client.fill("//input[@aria-label='搜索论文']", paper['filename'])
            wait_until(lambda: client.execute(f'return Boolean(document.querySelector(\'[data-workspace-focus="paper:{paper_id}"]\'))'), 'Selected real paper did not appear in library search')
            client.click(f"//button[@data-workspace-focus='paper:{paper_id}']")
            wait_until(lambda: client.execute('return [...document.querySelectorAll(".pdf-page canvas")].some(e=>e.width>0&&e.height>0)'), 'Original real PDF did not render', timeout=45)
            if record['source'].get('id') in args.assert_source_title:
                expected_title = ' '.join(record['source']['title'].split())
                assert ' '.join((paper.get('title') or '').split()) == expected_title, {'expected': expected_title, 'actual': paper.get('title')}
                client.click("//button[@role='tab' and normalize-space()='论文信息']")
                wait_until(lambda: client.execute('return document.querySelector("textarea[aria-label=标题]")?.value') == paper['title'], 'The installed native title field does not show the corrected source title')
                evidence['checks'].append('corrected_title_matches_publisher_manifest_and_native_editor')
            capture(f'{index:02d}-original-reader')
            evidence['checks'].append('real_pdf_hash_matches_source_and_native_pdfjs_canvas_rendered')

            # A term comes from the actual PDF text, never a fabricated fixture caption.
            reader = PdfReader(record['source']['local_path'])
            words = re.findall(r'[A-Za-z]{6,}', reader.pages[0].extract_text() or '')
            if words:
                query = words[0]
                client.click("//button[@aria-label='查找 PDF 文字']")
                client.fill("//input[@aria-label='查找 PDF 中的文字']", query)
                wait_until(lambda: client.execute('return /\\d+\\s*\\/\\s*\\d+/.test(document.querySelector(".reader-find [role=status]")?.textContent||"")'), 'A source PDF word was not found by native PDF.js', timeout=45)
                evidence['pdf_find'] = {'query': query, 'status': client.execute('return document.querySelector(".reader-find [role=status]").textContent')}
                capture(f'{index:02d}-pdf-find')
                client.click("//button[@aria-label='关闭 PDF 查找']")

            for kind, label in (('figure', '图片'), ('table', '表格')):
                subset = [r for r in resources if r['kind'] == kind]
                if not subset:
                    assert kind not in required_numbers, f'Required {kind} label {required_numbers.get(kind)} is missing'
                    evidence['resources'].append({'kind': kind, 'count': 0, 'not_applicable': 'No auto resources of this kind'})
                    continue
                if kind in required_numbers:
                    resource_index = next((i for i, item in enumerate(subset) if item.get('number') == required_numbers[kind]), None)
                    assert resource_index is not None, f'Required {kind} label {required_numbers[kind]} is missing'
                else:
                    resource_index = next((i for i, item in enumerate(subset) if str(item.get('caption') or '').strip()), 0) if args.resource_mode == 'captioned' else 0
                resource = subset[resource_index]
                assert resource_index < 24, 'Selected captioned resource is beyond the first detail page; add explicit pagination before reviewing it'
                client.click(f"//button[@role='tab' and starts-with(normalize-space(),'{label}')]")
                client.click(f"(//button[contains(@class,'detail-resource')])[{resource_index + 1}]")
                wait_until(lambda: client.execute('return Boolean(document.querySelector(".resource-detail"))'), 'Real resource detail did not open')
                assert client.execute('return document.querySelector(".resource-meta textarea[aria-label=Caption]")?.value') == (resource.get('caption') or '')
                if kind in required_numbers:
                    expected_name = resource.get('name') or ''
                    assert required_numbers[kind] in expected_name, resource
                    assert client.execute('return document.querySelector(".resource-meta input[aria-label=资源名称]")?.value') == expected_name
                wait_until(lambda: client.execute('return [...document.querySelectorAll(".resource-preview img")].every(e=>e.complete&&e.naturalWidth>0)'), 'Real extracted resource image did not load')
                if kind == 'table':
                    assert client.execute('return Boolean(document.querySelector(".resource-preview table"))'), 'Structured table is not shown'
                capture(f'{index:02d}-{kind}-auto-detail')
                client.click("//button[normalize-space()='查看原文']")
                page = resource['locations'][0]['page_index'] + 1
                wait_until(lambda: client.execute(f'''const page=document.querySelector('.pdf-page[data-page="{page}"]');
const highlight=page?.querySelector('.pdf-highlight');const canvas=page?.querySelector('canvas');
if(!highlight||!canvas?.width||page.dataset.textReady!=='true')return false;
const region=highlight.getBoundingClientRect(), viewport=document.querySelector('.pdf-scroll').getBoundingClientRect();
return region.bottom>viewport.top&&region.top<viewport.bottom;'''), 'Resource source region was not rendered and visibly highlighted in its PDF', timeout=45)
                capture(f'{index:02d}-{kind}-source-region')
                evidence['resources'].append({'kind': kind, 'count': len(subset), 'resource_id': resource['id'],
                                              'selection_mode': args.resource_mode, 'selected_auto_index': resource_index,
                                              'required_number': required_numbers.get(kind), 'observed_number': resource.get('number'), 'observed_name': resource.get('name'),
                                              'caption': resource.get('caption'), 'source_location': resource['locations'][0], 'native_detail_and_location': True})

            target_page = min(2, record['page_count'])
            client.fill("//input[@aria-label='PDF 页码']", f'{target_page}\ue007')
            wait_until(lambda: client.execute('return document.querySelector("[aria-label=\\"PDF 页码\\"]")?.value') == str(target_page), 'Page input did not navigate')
            client.click("//button[@aria-label='添加本页书签']")
            wait_until(lambda: any(a['locations'][0]['page_index'] == target_page - 1 for a in client.api(f'/annotations?paper_id={paper_id}&kind=bookmark')['items']), 'Bookmark was not saved for the real source page')
            client.click("//button[@role='tab' and starts-with(normalize-space(),'笔记')]")
            # Bookmark creation opens that bookmark's editor. Return to the
            # actual paper-note list before using its persistent add button.
            client.click("//button[normalize-space()='全部笔记']")
            client.click("//*[contains(@class,'annotation-panel-toolbar')]//button[normalize-space()='笔记']")
            marker = f'Real corpus native review {index}: ' + paper['filename']
            body = 'Source inspected through the installed reader: ' + record['source'].get('source_url', record['source']['local_path'])
            client.fill("//*[@role='dialog']//input[@aria-label='笔记标题']", marker)
            client.fill("//*[@role='dialog']//textarea[@aria-label='笔记内容']", body)
            client.click("//*[@role='dialog']//button[normalize-space()='保存笔记']")
            wait_until(lambda: any(a['title'] == marker and a['body'] == body for a in client.api(f'/annotations?paper_id={paper_id}&kind=note')['items']), 'Real-paper note was not persisted')
            capture(f'{index:02d}-saved-note-and-bookmark')
            client.click("//aside//button[@aria-label='论文库']")
            wait_until(lambda: client.api(f'/papers/{paper_id}/reading-state')['page_index'] == target_page - 1, 'Reading state did not flush before leaving the real paper')
            evidence['reading_state'] = client.api(f'/papers/{paper_id}/reading-state')
            evidence['annotations'] = client.api(f'/annotations?paper_id={paper_id}')['items']
            assert client.api(f'/resources?paper_id={paper_id}&limit=1000')['items'] == resources, 'Native review changed auto resource metadata'
            evidence['checks'].append('native_note_bookmark_and_reading_position_persisted_in_copy')
            evidence['passed'] = True
            write_json(output / 'report.json', report)
        client.wm_close()
        client.assert_exit()
        client.close()
        client = NativeClient(args.app, fixture, library_path, output).start()
        for evidence in report['papers']:
            paper_id = evidence['paper_id']
            assert client.api(f'/annotations?paper_id={paper_id}')['items'] == evidence['annotations']
            actual = client.api(f'/papers/{paper_id}/reading-state')
            assert actual['page_index'] == evidence['reading_state']['page_index']
        client.wm_close()
        client.assert_exit()
        report['phases'].append('native_restart_retains_real_paper_notes_bookmarks_reading_and_closes_sidecar')
        report['passed'] = True
    except Exception as error:
        report['error'] = str(error)
        report['traceback'] = traceback.format_exc()
        if client and client.session:
            try:
                client.screenshot('failure')
            except Exception:
                pass
        raise
    finally:
        if client:
            client.close()
        write_json(output / 'report.json', report)
        print(json.dumps({'passed': report['passed'], 'report': str(output / 'report.json')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
