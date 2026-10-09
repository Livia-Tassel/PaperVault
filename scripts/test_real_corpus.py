"""Audit real PDFs through the installed frozen backend; never alter the auto baseline.

Example: .venv/Scripts/python.exe scripts/test_real_corpus.py --manifest tests/corpus/sources-*.json
Manifests accept a list, or {sources: [...]}; entries use local_path/path/pdf.
This validates integrity and workflows, not extraction precision/recall. Human
review of the retained source pages, crops and tables is still required.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import glob
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import queue
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
from urllib.parse import quote
from uuid import uuid4

import httpx
from PIL import Image
import psutil
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_SHA256 = '40f03cbfe81ad7ab701680627cf9e777dc5903f7d0c377537985babbf0ac8b8a'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def file_evidence(path):
    path = Path(path).resolve()
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest(path)}


def error_record(stage, error):
    return {'stage': stage, 'type': type(error).__name__, 'message': str(error), 'traceback': traceback.format_exc()}


def assert_equal(expected, actual, label, directory):
    if expected != actual:
        evidence = {'expected': expected, 'actual': actual}
        if isinstance(expected, dict) and isinstance(actual, dict):
            evidence['field_differences'] = {
                key: {'expected': expected.get(key), 'actual': actual.get(key),
                      'expected_has_key': key in expected, 'actual_has_key': key in actual}
                for key in expected.keys() | actual.keys()
                if expected.get(key) != actual.get(key) or (key in expected) != (key in actual)}
        target = directory / f'{label}-difference.json'
        write_json(target, evidence)
        raise AssertionError(f'{label} differs; full field comparison: {target}')


def summarize(report):
    return {'papers': len(report['papers']), 'papers_passed': sum(p['passed'] for p in report['papers']),
            'papers_failed': sum(not p['passed'] for p in report['papers']),
            'resources': sum(len(p['resources']) for p in report['papers']),
            'resource_failures': sum(not r['passed'] for p in report['papers'] for r in p['resources'])}


def load_sources(manifests, pdfs):
    sources = []
    for pattern in manifests:
        matches = sorted(glob.glob(pattern))
        if not matches:
            raise FileNotFoundError(f'No manifest matches {pattern}')
        for name in matches:
            manifest = Path(name).resolve()
            value = json.loads(manifest.read_text(encoding='utf-8-sig'))
            entries = value if isinstance(value, list) else next((value[k] for k in ('sources', 'items', 'papers') if k in value), [])
            if not isinstance(entries, list) or not entries:
                raise ValueError(f'Manifest contains no source list: {manifest}')
            for entry in entries:
                source = {'path': entry} if isinstance(entry, str) else dict(entry)
                raw = next((source[k] for k in ('local_path', 'path', 'pdf') if source.get(k)), None)
                if not raw:
                    raise ValueError(f'Missing local PDF path: {source}')
                path = Path(raw)
                if not path.is_absolute():
                    # Repository-relative paths are preferred; filenames may be
                    # relative to their manifest for portable corpus folders.
                    path = ROOT / path if (ROOT / path).exists() else manifest.parent / path
                source.update(local_path=str(path.resolve()), manifest=str(manifest), manifest_sha256=digest(manifest))
                sources.append(source)
    sources.extend({'local_path': str(Path(pdf).resolve()), 'selection': 'explicit --pdf'} for pdf in pdfs)
    unique = {}
    for source in sources:
        key = os.path.normcase(source['local_path'])
        if key in unique:
            unique[key].setdefault('additional_manifest_entries', []).append(source)
        else:
            unique[key] = source
    if not unique:
        raise ValueError('Provide --manifest and/or --pdf')
    return list(unique.values())


class FrozenBackend:
    """No imports from backend/ and no source paths in the child environment."""

    def __init__(self, binary, directory, models, label='baseline', expected_version='0.2.0'):
        self.binary, self.directory, self.models, self.label = binary, directory, models, label
        self.expected_version = expected_version
        self.process = self.client = None
        self.errors, self.peak_memory = [], 0
        self.stop_sampling = threading.Event()
        self.forced_termination = False
        self.port = None

    def __enter__(self):
        env = dict(os.environ)
        for name in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV', 'PAPERVAULT_LIBRARY_PATH', 'PAPERVAULT_CONFIG_PATH', 'PAPERVAULT_MODELS_PATH'):
            env.pop(name, None)
        env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
        token = secrets.token_hex(32)
        self.directory.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        self.process = subprocess.Popen([str(self.binary)], cwd=self.binary.parent, env=env, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8',
                                        errors='replace', creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.lines = queue.Queue()

        def capture(stream, filename, ready=False):
            with (self.directory / filename).open('w', encoding='utf-8') as target:
                for line in stream:
                    target.write(line)
                    target.flush()
                    if ready:
                        self.lines.put(line)
                    else:
                        self.errors.append(line)

        self.readers = [threading.Thread(target=capture, args=(self.process.stdout, f'{self.label}-stdout.jsonl', True), daemon=True),
                        threading.Thread(target=capture, args=(self.process.stderr, f'{self.label}-stderr.log'), daemon=True)]
        for reader in self.readers:
            reader.start()

        def sample():
            while not self.stop_sampling.wait(.2):
                self.sample_memory()

        self.sampler = threading.Thread(target=sample, daemon=True)
        self.sampler.start()
        self.process.stdin.write(json.dumps({'token': token, 'config_path': str(self.directory / 'config'),
                                              'models_path': str(self.models)}) + '\n')
        self.process.stdin.flush()
        try:
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError('Frozen backend exited: ' + ''.join(self.errors)[-6000:])
                try:
                    event = json.loads(self.lines.get(timeout=.2))
                except (queue.Empty, ValueError):
                    continue
                if event.get('type') == 'ready':
                    self.port = event['port']
                    assert event['protocol'] == 1 and self.port not in (8765, 1420), event
                    self.client = httpx.Client(base_url=f'http://127.0.0.1:{self.port}/api/v1',
                                               headers={'Authorization': 'Bearer ' + token}, timeout=180, trust_env=False)
                    for _ in range(100):
                        try:
                            self.health = self.call('GET', '/health').json()
                            assert self.health['version'] == self.expected_version, self.health
                            self.startup_seconds = time.perf_counter() - started
                            return self
                        except httpx.TransportError:
                            time.sleep(.1)
            raise TimeoutError('Frozen backend did not become ready')
        except BaseException:
            self.__exit__()
            raise

    def sample_memory(self):
        try:
            parent = psutil.Process(self.process.pid)
            total = 0
            for process in [parent, *parent.children(recursive=True)]:
                try:
                    total += process.memory_info().rss
                except psutil.Error:
                    pass
            self.peak_memory = max(self.peak_memory, total)
        except psutil.Error:
            pass

    def call(self, method, route, **kwargs):
        result = self.client.request(method, route, **kwargs)
        if result.status_code >= 400:
            raise RuntimeError(f'{method} {route}: HTTP {result.status_code} {result.text[:5000]}')
        return result

    def scope(self, library):
        self.client.headers['X-PaperVault-Library'] = quote(f"{library['id']}:{library['path']}", safe='')

    def __exit__(self, *_):
        if self.client:
            self.client.close()
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.close()
                self.process.wait(timeout=25)
            except (subprocess.TimeoutExpired, OSError):
                self.forced_termination = True
                parent = psutil.Process(self.process.pid)
                children = parent.children(recursive=True)
                for process in reversed(children):
                    try:
                        process.kill()
                    except psutil.Error:
                        pass
                self.process.kill()
                self.process.wait(timeout=10)
        self.stop_sampling.set()
        for reader in getattr(self, 'readers', []):
            reader.join(timeout=2)
        port_closed = True
        if self.port:
            with socket.socket() as probe:
                probe.settimeout(.5)
                port_closed = probe.connect_ex(('127.0.0.1', self.port)) != 0
        self.shutdown = {'returncode': self.process.returncode if self.process else None,
                         'forced_termination': self.forced_termination, 'backend_port_closed': port_closed}


def list_resources(backend, paper_id):
    result = []
    while True:
        batch = backend.call('GET', '/resources', params={'paper_id': paper_id, 'limit': 500, 'offset': len(result)}).json()
        result.extend(batch['items'])
        if len(result) >= batch['total']:
            assert len(result) == batch['total']
            return result
        if not batch['items']:
            raise AssertionError('Resource pagination stopped before total')


def geometry(path):
    reader = PdfReader(path, strict=False)
    if reader.is_encrypted and not reader.decrypt(''):
        raise ValueError('Encrypted PDF cannot be inspected without a password')
    return [{'page_index': i, 'media_box': list(map(float, page.mediabox)),
             'crop_box': list(map(float, page.cropbox)), 'rotation': int(page.get('/Rotate', 0)) % 360,
             'user_unit': float(page.get('/UserUnit', 1))} for i, page in enumerate(reader.pages)]


def validate_locations(resource, pages):
    assert resource.get('locations'), 'Resource has no original PDF location'
    for location in resource['locations']:
        index, box = location.get('page_index'), location.get('bbox')
        assert isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(pages), location
        assert isinstance(box, list) and len(box) == 4 and all(isinstance(x, (int, float)) and math.isfinite(x) for x in box), location
        assert box[0] < box[2] and box[1] < box[3], location
        media, crop = pages[index]['media_box'], pages[index]['crop_box']
        visible = [max(media[0], crop[0]), max(media[1], crop[1]), min(media[2], crop[2]), min(media[3], crop[3])]
        assert box[0] >= visible[0] - .5 and box[1] >= visible[1] - .5 and box[2] <= visible[2] + .5 and box[3] <= visible[3] + .5, {'location': location, 'visible_box': visible}
    return {'coordinate_space': 'pdf_user_space', 'segments': len(resource['locations']), 'bounds_tolerance_points': .5}


def inspect_export(data, format_name):
    if format_name in ('png', 'thumbnail') or format_name.startswith('segment_'):
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            assert min(image.size) > 0
            return {'format': image.format, 'width': image.width, 'height': image.height}
    if format_name == 'csv':
        rows = list(csv.reader(io.StringIO(data.decode('utf-8-sig')), strict=True))
        return {'rows': len(rows), 'columns': max(map(len, rows), default=0), 'empty': not rows}
    if format_name == 'html':
        text = data.decode('utf-8')
        assert re.search(r'<table(?:\s|>)', text, re.I) and re.search(r'</table\s*>', text, re.I), 'No complete HTML table'
        return {'characters': len(text)}
    assert data, 'Empty original asset'
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        return {'format': image.format, 'width': image.width, 'height': image.height}


def audit_resource(backend, resource, pages, output, dpis):
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / 'resource-auto.json', resource)
    result = {'id': resource['id'], 'kind': resource['kind'], 'caption': resource.get('caption'),
              'locations': resource.get('locations'), 'warnings': resource.get('warnings', []),
              'needs_review': resource.get('needs_review'), 'errors': [], 'exports': [], 'auto_json': str(output / 'resource-auto.json')}

    def check(stage, action):
        try:
            return action()
        except Exception as error:
            result['errors'].append(error_record(stage, error))
            return None

    result['geometry'] = check('geometry', lambda: validate_locations(resource, pages))
    formats = [(f'png-{dpi}', 'png', {'dpi': dpi}) for dpi in dpis]
    if resource['kind'] == 'table':
        formats.extend((name, name, {}) for name in ('csv', 'html'))
    formats.extend((name, name, {}) for name in resource.get('files', {}) if name not in ('csv', 'html', 'png'))
    for label, format_name, params in formats:
        def export():
            data = backend.call('GET', f"/resources/{resource['id']}/files/{format_name}", params=params).content
            suffix = '.png' if format_name in ('png', 'thumbnail') or format_name.startswith('segment_') else '.' + format_name
            target = output / (label + suffix)
            target.write_bytes(data)
            proof = file_evidence(target)
            proof.update(format=format_name, dpi=params.get('dpi'), decoded=inspect_export(data, format_name))
            result['exports'].append(proof)
        check('export:' + label, export)
    caption = str(resource.get('caption') or '').strip()
    if caption:
        def search():
            query = ' '.join(caption.split())
            if len(query) > 950:
                query = query[:950]
                if ' ' in query:
                    query = query.rsplit(' ', 1)[0]
            matches = backend.call('GET', '/search', params={'q': query}).json()
            write_json(output / 'caption-search.json', {'query': query, 'results': matches})
            group = 'figures' if resource['kind'] == 'figure' else 'tables'
            hit = next((hit for hit in matches[group] if hit['id'] == resource['id']), None)
            assert hit, 'Caption query did not return this resource among the API top 25 results'
            assert hit['paper_id'] == resource['paper_id'] and hit['location'] == resource['locations'][0], hit
            return {'query': query, 'resource_id': hit['id'], 'paper_id': hit['paper_id'], 'location': hit['location']}
        result['caption_search'] = check('caption_search', search)
    else:
        result['caption_search'] = {'not_applicable': 'Auto parser returned no caption; no caption was fabricated'}
    result['passed'] = not result['errors']
    write_json(output / 'validation.json', result)
    return result


def audit_paper(backend, source, library, output, timeout, dpis, save_report, result):
    path = Path(source['local_path'])
    result.update(source=source, passed=False, errors=[], resources=[], progress=[])
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    backend.peak_memory = 0
    paper_id = None
    try:
        result['source_pdf'] = file_evidence(path)
        expected = source.get('sha256') or source.get('pdf_sha256')
        if expected:
            assert result['source_pdf']['sha256'].casefold() == expected.casefold(), 'PDF differs from manifest SHA256'
        pages = geometry(path)
        result['page_count'] = len(pages)
        write_json(output / 'source-pages.json', pages)
        imported = backend.call('POST', '/papers/import-paths', json={'paths': [str(path)]}).json()
        write_json(output / 'import.json', imported)
        assert not imported.get('errors'), imported
        if not imported.get('items'):
            raise AssertionError(f'No new paper imported (duplicate inputs are reported explicitly): {imported}')
        paper_id = result['paper_id'] = imported['items'][0]['id']
        deadline, previous = time.monotonic() + timeout, None
        while time.monotonic() < deadline:
            jobs = backend.call('GET', '/jobs').json()['items']
            job = next((j for j in jobs if j['paper_id'] == paper_id), None)
            if job:
                state = {key: job.get(key) for key in ('id', 'status', 'phase', 'pages_done', 'pages_total', 'resources_count', 'error')}
                if state != previous:
                    previous = state
                    result['progress'].append({'seconds': round(time.perf_counter() - started, 3), **state})
                    write_json(output / 'progress.json', result['progress'])
                    print(json.dumps({'source': path.name, **state}, ensure_ascii=False), flush=True)
                    save_report()
                if job['status'] == 'completed':
                    result['job'] = job
                    break
                if job['status'] in ('failed', 'cancelled', 'interrupted'):
                    raise RuntimeError(f'Parser terminal failure: {job}')
            time.sleep(.5)
        else:
            if job:
                backend.call('POST', f"/jobs/{job['id']}/cancel")
            raise TimeoutError(f'Parse exceeded {timeout}s; cancellation requested')
        result['parse_seconds'] = round(time.perf_counter() - started, 3)
        paper = backend.call('GET', f'/papers/{paper_id}').json()
        write_json(output / 'paper-auto.json', paper)
        result['paper_json'] = str(output / 'paper-auto.json')
        assert not paper.get('edited_fields'), 'Auto baseline already contains manual overrides'
        result['warnings'] = paper.get('warnings', [])
        resources = list_resources(backend, paper_id)
        write_json(output / 'resources-auto.json', resources)
        result['counts'] = {kind: sum(r['kind'] == kind for r in resources) for kind in ('figure', 'table')}
        result['counts']['resources'] = len(resources)
        assert paper['figure_count'] == result['counts']['figure'] and paper['table_count'] == result['counts']['table']
        source_dir = Path(library['path']) / 'papers' / paper_id
        revision = source_dir / 'revisions' / paper['active_revision']
        result['source_revision'] = str(revision)
        result['parser_artifacts'] = []
        for name in ('structure.json', 'docling.json', 'fulltext.md', 'worker.log', 'result.json'):
            artifact = revision / name
            if artifact.is_file():
                shutil.copy2(artifact, output / name)
                result['parser_artifacts'].append({'original': file_evidence(artifact), 'baseline_copy': file_evidence(output / name)})
        for name in ('structure.json', 'docling.json', 'fulltext.md'):
            assert (output / name).is_file(), f'Missing raw parser artifact {name}'
        structure = json.loads((output / 'structure.json').read_text(encoding='utf-8'))
        result['parser_warnings'] = structure.get('warnings', [])
        result['engine'] = structure.get('engine')
        result['source_pdf_hash_preserved'] = digest(source_dir / 'original.pdf') == result['source_pdf']['sha256']
        assert result['source_pdf_hash_preserved']
        api_pdf = backend.call('GET', f'/papers/{paper_id}/pdf').content
        assert hashlib.sha256(api_pdf).hexdigest() == result['source_pdf']['sha256'], 'API PDF hash differs'
        for resource in resources:
            try:
                result['resources'].append(audit_resource(backend, resource, pages, output / 'resources' / resource['id'], dpis))
            except Exception as error:
                result['resources'].append({'id': resource.get('id'), 'passed': False, 'errors': [error_record('resource_unexpected', error)]})
            save_report()
        assert backend.call('GET', f'/papers/{paper_id}').json() == paper, 'Read-only audit changed paper metadata'
        assert list_resources(backend, paper_id) == resources, 'Read-only audit changed resource metadata'
        result['auto_baseline_unchanged'] = True
        result['passed'] = all(r['passed'] for r in result['resources'])
    except Exception as error:
        result['errors'].append(error_record('paper', error))
    finally:
        result['seconds'] = round(time.perf_counter() - started, 3)
        result['peak_backend_worker_rss_bytes'] = backend.peak_memory
        if path.is_file() and result.get('source_pdf'):
            result['input_pdf_hash_unchanged'] = digest(path) == result['source_pdf']['sha256']
            result['passed'] = result['passed'] and result['input_pdf_hash_unchanged']
        if paper_id:
            try:
                write_json(output / 'paper-final.json', backend.call('GET', f'/papers/{paper_id}').json())
            except Exception as error:
                result['errors'].append(error_record('final_paper_read', error))
                result['passed'] = False
        write_json(output / 'report.json', result)
    return result


def exercise_copy(backend, library, paper_id, directory):
    """All writes occur in a restored copy; the accuracy baseline stays untouched."""
    baseline = backend.call('GET', f'/papers/{paper_id}').json()
    backup = backend.call('POST', '/backups', json={}).json()['path']
    copied = directory / 'editable-copy'
    backend.call('POST', '/backups/restore', json={'path': backup, 'destination': str(copied)})
    copied_library = backend.call('GET', '/library').json()
    assert Path(copied_library['path']).resolve() == copied.resolve()
    assert copied_library['id'] == library['id'] and copied_library['path'] != library['path']
    backend.scope(copied_library)
    marker = 'Real corpus isolated edit ' + uuid4().hex
    paper_patch_response = backend.call('PATCH', f'/papers/{paper_id}', json={'notes': marker, 'tags': ['corpus-copy-validation']}).json()
    resources = list_resources(backend, paper_id)
    edited_resources = []
    if resources:
        edited_resources.append(backend.call('PATCH', f"/resources/{resources[0]['id']}", json={'caption': marker}).json())
    table = next((r for r in resources if r['kind'] == 'table' and (r.get('table') or {}).get('rows') and r['table']['rows'][-1]), None)
    if table:
        table_data = json.loads(json.dumps(table['table']))
        table_data['rows'][-1][-1] = marker
        table_data['cells'] = []
        patched = backend.call('PATCH', f"/resources/{table['id']}", json={'table': table_data}).json()
        edited_resources = [r for r in edited_resources if r['id'] != patched['id']] + [patched]
        assert marker in backend.call('GET', f"/resources/{table['id']}/files/csv").text
    # GET adds derived similar_papers that PATCH intentionally does not return.
    # Capture the complete GET contract after every manual write, then compare
    # all its fields to the same GET contract after restore and restart.
    edited = backend.call('GET', f'/papers/{paper_id}').json()
    edited_resources = [backend.call('GET', f"/resources/{r['id']}").json() for r in edited_resources]
    write_json(directory / 'copy-expected-after-all-writes.json', {'paper': edited, 'resources': edited_resources,
               'paper_patch_response': paper_patch_response, 'get_additional_fields': sorted(edited.keys() - paper_patch_response.keys())})
    edited_backup = backend.call('POST', '/backups', json={}).json()['path']
    restored = directory / 'edited-restored'
    backend.call('POST', '/backups/restore', json={'path': edited_backup, 'destination': str(restored)})
    restored_library = backend.call('GET', '/library').json()
    backend.scope(restored_library)
    assert_equal(edited, backend.call('GET', f'/papers/{paper_id}').json(), 'restored-paper', directory)
    for resource in edited_resources:
        assert_equal(resource, backend.call('GET', f"/resources/{resource['id']}").json(), 'restored-resource-' + resource['id'], directory)
    return {'paper_id': paper_id, 'baseline_paper': baseline, 'edited_paper': edited, 'edited_resources': edited_resources,
            'original_library': library, 'editable_library': copied_library, 'restored_library': restored_library,
            'baseline_backup': file_evidence(backup), 'edited_backup': file_evidence(edited_backup)}


def recheck_existing(args):
    """Reuse untouched parse evidence; rerun only copy/edit/backup/restart checks."""
    previous_path = args.existing_report.resolve()
    report = json.loads(previous_path.read_text(encoding='utf-8'))
    assert report['papers'] and all(p.get('auto_baseline_unchanged') for p in report['papers'])
    binary, models = args.backend.resolve(), args.models.resolve()
    assert digest(binary) == args.expect_sha256.lower() == report['backend_sha256']
    directory = Path(report['work_directory']) / ('copy-recheck-' + uuid4().hex[:8])
    assert directory.resolve().is_relative_to(ROOT / '.test-data')
    directory.mkdir(parents=True)
    archive = args.report.resolve().parent / 'failed-attempts' / (directory.name + '-original-report.json')
    archive.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(previous_path, archive)
    report['previous_attempt'] = {'report': file_evidence(archive), 'workflow_passed': report['passed'], 'errors': report.get('errors', [])}
    report['passed'], report['errors'] = False, []
    report['copy_recheck'] = {'work_directory': str(directory), 'no_model_parsing': True,
                              'command': subprocess.list2cmdline([sys.executable, *sys.argv])}
    started = time.perf_counter()
    backend = FrozenBackend(binary, directory, models, 'copy-recheck', args.expect_version)
    try:
        # Verify every retained parser artifact and source PDF before exercising
        # any copy; a successful recheck must not hide modified baseline files.
        checked = 0
        for paper in report['papers']:
            assert digest(paper['source']['local_path']) == paper['source_pdf']['sha256']
            original = Path(report['auto_baseline_library']['path']) / 'papers' / paper['paper_id'] / 'original.pdf'
            assert digest(original) == paper['source_pdf']['sha256']
            for artifact in paper['parser_artifacts']:
                for key in ('original', 'baseline_copy'):
                    assert digest(artifact[key]['path']) == artifact[key]['sha256'], artifact[key]['path']
                    checked += 1
        report['copy_recheck']['baseline_artifact_hashes_verified'] = checked
        with backend:
            library = backend.call('POST', '/library/open', json={'path': report['auto_baseline_library']['path']}).json()
            backend.scope(library)
            for paper in report['papers']:
                expected = json.loads(Path(paper['paper_json']).read_text(encoding='utf-8'))
                assert_equal(expected, backend.call('GET', f"/papers/{paper['paper_id']}").json(), 'baseline-paper-' + paper['paper_id'], directory)
                auto_resources = json.loads((Path(paper['paper_json']).parent / 'resources-auto.json').read_text(encoding='utf-8'))
                assert_equal(auto_resources, list_resources(backend, paper['paper_id']), 'baseline-resources-' + paper['paper_id'], directory)
            report['copy_exercise'] = exercise_copy(backend, library, report['papers'][0]['paper_id'], directory)
        report['shutdown'] = backend.shutdown
        copy = report['copy_exercise']
        restart = FrozenBackend(binary, directory, models, 'copy-restart', args.expect_version)
        with restart:
            reopened = restart.call('GET', '/library').json()
            assert reopened['path'] == copy['restored_library']['path']
            restart.scope(reopened)
            assert_equal(copy['edited_paper'], restart.call('GET', f"/papers/{copy['paper_id']}").json(), 'restarted-paper', directory)
            for resource in copy['edited_resources']:
                assert_equal(resource, restart.call('GET', f"/resources/{resource['id']}").json(), 'restarted-resource-' + resource['id'], directory)
            baseline = restart.call('POST', '/library/open', json={'path': library['path']}).json()
            restart.scope(baseline)
            assert_equal(copy['baseline_paper'], restart.call('GET', f"/papers/{copy['paper_id']}").json(), 'unchanged-baseline-paper', directory)
            copy['restart_and_baseline_isolation_passed'] = True
        copy['shutdown'] = restart.shutdown
        report['passed'] = all(p['passed'] for p in report['papers']) and all(not state['forced_termination'] and state['backend_port_closed'] for state in (backend.shutdown, restart.shutdown))
    except Exception as error:
        report['errors'].append(error_record('copy_recheck', error))
    finally:
        if hasattr(backend, 'shutdown'):
            report['shutdown'] = backend.shutdown
        report['copy_recheck']['seconds'] = round(time.perf_counter() - started, 3)
        report['copy_recheck']['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        report['summary'] = summarize(report)
        write_json(args.report, report)
        write_json(directory / 'copy-recheck-report.json', report)
        print(json.dumps({'report': str(args.report.resolve()), 'workflow_passed': report['passed'], **report['summary']}, ensure_ascii=False), flush=True)
    return 0 if report['passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', action='append', default=[], help='JSON source manifest or glob; repeatable')
    parser.add_argument('--source-id', nargs='+', default=[], help='Optionally select manifest IDs while retaining original provenance')
    parser.add_argument('--pdf', nargs='+', action='extend', default=[], help='One or more real PDFs; repeatable')
    parser.add_argument('--backend', type=Path, default=ROOT / '.test-data/installed/PaperVault/papervault-backend.exe')
    parser.add_argument('--expect-version', default='0.2.0', help='Explicit frozen version; defaults preserve the original 0.2.0 audit')
    parser.add_argument('--expect-sha256', default=EXPECTED_SHA256, help='Explicit verified frozen binary hash; never inferred from the tested executable')
    parser.add_argument('--models', type=Path, default=ROOT / '.cache/models')
    parser.add_argument('--report', type=Path, default=ROOT / 'artifacts/real-corpus/installed-backend-report.json')
    parser.add_argument('--timeout', type=int, default=1200, help='Parse timeout per paper, in seconds')
    parser.add_argument('--dpi', type=int, choices=(150, 300), nargs='+', default=[300], help='300 is always included')
    parser.add_argument('--exercise-copy', action='store_true', help='Edit/backup/restore/restart only a separate copy after the auto baseline')
    parser.add_argument('--existing-report', type=Path, help='Rerun only copy/edit/backup/restart using a completed unedited corpus baseline; never reparse')
    parser.add_argument('--list-only', action='store_true', help='Resolve inputs without starting the backend')
    args = parser.parse_args()
    if args.existing_report:
        return recheck_existing(args)
    sources = load_sources(args.manifest, args.pdf)
    if args.source_id:
        selected_ids = set(args.source_id)
        sources = [source for source in sources if source.get('id') in selected_ids]
        assert {source.get('id') for source in sources} == selected_ids, 'Some requested manifest source IDs were not found'
    if args.list_only:
        print(json.dumps(sources, ensure_ascii=False, indent=2))
        return 0
    binary, models = args.backend.resolve(), args.models.resolve()
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8]
    directory = ROOT / '.test-data' / 'real-corpus' / run_id
    output = args.report.resolve().parent / 'runs' / run_id
    directory.mkdir(parents=True)
    output.mkdir(parents=True)
    report = {'passed': False, 'run_id': run_id, 'started_at_utc': datetime.now(timezone.utc).isoformat(),
              'work_directory': str(directory), 'artifacts': str(output), 'backend': str(binary), 'sources': sources,
              'backend_origin': 'installed' if binary.is_relative_to(ROOT / '.test-data/installed') else 'explicit_frozen_executable',
              'command': subprocess.list2cmdline([sys.executable, *sys.argv]), 'papers': [], 'errors': [],
              'offline_environment': {'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'PYTHONPATH': None, 'VIRTUAL_ENV': None},
              'machine': {'platform': platform.platform(), 'logical_cpus': psutil.cpu_count(), 'memory_bytes': psutil.virtual_memory().total},
              'scope': 'Unedited auto extraction integrity/workflow audit. Counts are observed, never assumed ground truth; precision/recall requires manual source-page review.'}

    def save():
        write_json(args.report, report)
        write_json(output / 'installed-backend-report.json', report)

    started = time.perf_counter()
    backend = FrozenBackend(binary, directory, models, expected_version=args.expect_version)
    try:
        report['backend_sha256'] = digest(binary)
        assert report['backend_sha256'] == args.expect_sha256.lower(), 'Frozen backend differs from the explicitly expected SHA256'
        report['models_manifest'] = file_evidence(models / 'papervault-models.json')
        with backend:
            report.update(health=backend.health, backend_port=backend.port, backend_pid=backend.process.pid,
                          backend_startup_seconds=round(backend.startup_seconds, 3))
            assert backend.call('GET', '/models').json()['ready'], 'Local model bundle is not ready; this runner never downloads models'
            library = backend.call('POST', '/library/open', json={'path': str(directory / 'auto-baseline')}).json()
            report['auto_baseline_library'] = library
            backend.scope(library)
            save()
            for index, source in enumerate(sources, 1):
                record = {'source': source, 'passed': False, 'errors': [], 'resources': [], 'progress': []}
                report['papers'].append(record)
                audit_paper(backend, source, library, output / f'{index:03d}-{Path(source["local_path"]).stem[:70]}',
                            args.timeout, sorted(set([300, *args.dpi])), save, record)
                save()
            if args.exercise_copy:
                selected = next((p for p in report['papers'] if p.get('auto_baseline_unchanged')), None)
                if not selected:
                    raise AssertionError('No parsed baseline paper is available for the separate edit exercise')
                report['copy_exercise'] = exercise_copy(backend, library, selected['paper_id'], directory)
                save()
        report['shutdown'] = backend.shutdown
        if args.exercise_copy and report.get('copy_exercise'):
            copy = report['copy_exercise']
            restart = FrozenBackend(binary, directory, models, 'restart', args.expect_version)
            with restart:
                reopened = restart.call('GET', '/library').json()
                assert reopened['path'] == copy['restored_library']['path']
                restart.scope(reopened)
                assert restart.call('GET', f"/papers/{copy['paper_id']}").json() == copy['edited_paper']
                for resource in copy['edited_resources']:
                    assert restart.call('GET', f"/resources/{resource['id']}").json() == resource
                # Re-open baseline only to prove copy edits never reached it.
                original = restart.call('POST', '/library/open', json={'path': library['path']}).json()
                restart.scope(original)
                assert restart.call('GET', f"/papers/{copy['paper_id']}").json() == copy['baseline_paper']
                copy['restart_and_baseline_isolation_passed'] = True
            copy['shutdown'] = restart.shutdown
        report['passed'] = bool(report['papers']) and all(p['passed'] for p in report['papers']) and not backend.forced_termination and backend.shutdown['backend_port_closed']
    except Exception as error:
        report['errors'].append(error_record('run', error))
    finally:
        if hasattr(backend, 'shutdown'):
            report['shutdown'] = backend.shutdown
        report['seconds'] = round(time.perf_counter() - started, 3)
        report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        report['summary'] = summarize(report)
        save()
        print(json.dumps({'report': str(args.report.resolve()), 'workflow_passed': report['passed'], **report['summary']}, ensure_ascii=False), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
