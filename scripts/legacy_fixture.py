"""Create a real 0001 library with the previously verified 0.1.x sidecar."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import queue
import secrets
import sqlite3
import subprocess
import threading
import urllib.request

from native_client import ROOT


def seed_legacy_library(backend: Path, fixture: Path, library: Path):
    token = secrets.token_hex(32)
    stderr = (fixture / 'legacy-backend.log').open('w', encoding='utf-8')
    process = subprocess.Popen([str(backend.resolve())], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr,
                               text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
    lines = queue.Queue()
    threading.Thread(target=lambda: [lines.put(line) for line in process.stdout], daemon=True).start()
    try:
        bootstrap = {'token': token, 'library_path': str(library), 'config_path': str(fixture / 'legacy-config'), 'models_path': str(fixture / 'no-models')}
        process.stdin.write(json.dumps(bootstrap, ensure_ascii=False) + '\n')
        process.stdin.flush()
        ready = json.loads(lines.get(timeout=90))
        assert ready['type'] == 'ready' and ready['protocol'] == 1
        base = f"http://127.0.0.1:{ready['port']}/api/v1"

        def api(path, method='GET', data=None):
            payload = json.dumps(data).encode('utf-8') if data is not None else None
            request = urllib.request.Request(base + path, data=payload, method=method,
                                             headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)

        health = api('/health')
        assert health['version'] in ('0.1.0', '0.1.1'), health
        result = api('/papers/import-paths', 'POST', {'paths': [str(ROOT / 'tests/fixtures/academic.pdf')], 'recursive': False})
        assert not result['errors'] and len(result['items']) == 1
        paper = result['items'][0]
        for job in api('/jobs')['items']:
            if job['paper_id'] == paper['id'] and job['status'] in ('queued', 'running', 'waiting_models'):
                api(f"/jobs/{job['id']}/cancel", 'POST')
        paper = api(f"/papers/{paper['id']}", 'PATCH', {'title': 'Legacy migration fixture', 'notes': 'Legacy personal note must survive', 'tags': ['legacy-retained']})
        archive = Path(api('/backups', 'POST', {'destination': str(fixture / 'legacy-0001.zip')})['path'])
    finally:
        if process.poll() is None:
            try:
                process.stdin.write('{"type":"shutdown"}\n')
                process.stdin.flush()
                process.stdin.close()
                process.wait(timeout=15)
            except Exception:
                process.kill()
                process.wait(timeout=10)
        stderr.close()
    database = library / 'database/papervault.db'
    with sqlite3.connect(database) as connection:
        revision = connection.execute('SELECT version_num FROM alembic_version').fetchone()[0]
        assert revision == '0001', revision
        assert connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='annotations'").fetchone() is None
    retained = [library / 'papers' / paper['id'] / name for name in ('original.pdf', 'metadata.json')]
    result = {'paper_id': paper['id'], 'backend_version': health['version'], 'schema_before': revision,
              'retained_sha256': {str(path.relative_to(library)): hashlib.sha256(path.read_bytes()).hexdigest() for path in retained}}
    (fixture / 'legacy-fixture.json').write_text(json.dumps({'archive': str(archive), 'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'legacy': result}, ensure_ascii=False, indent=2), encoding='utf-8')
    return result
