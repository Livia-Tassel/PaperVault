"""Exercise a frozen backend through its real stdin and authenticated HTTP API."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import queue
import secrets
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--backend', type=Path, required=True)
    parser.add_argument('--source', action='store_true', help='Treat --backend as Python and run the source module instead of a frozen exe')
    args = parser.parse_args()
    test_root = Path(__file__).resolve().parent.parent / '.test-data' / 'packaging'
    test_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='PaperVault 打包验收 ', dir=test_root) as work:
        token = secrets.token_hex(32)
        command = [str(args.backend.resolve())] + (['-m', 'papervault'] if args.source else [])
        environment = dict(os.environ)
        environment['PYTHONUTF8'] = '1'
        if args.source:
            environment['PYTHONPATH'] = str(Path(__file__).resolve().parent.parent / 'backend')
        process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=environment,
            stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        lines: queue.Queue[str] = queue.Queue()
        diagnostics: list[str] = []
        threading.Thread(target=lambda: [lines.put(line) for line in process.stdout], daemon=True).start()
        threading.Thread(target=lambda: [diagnostics.append(line) for line in process.stderr], daemon=True).start()
        try:
            process.stdin.write(json.dumps({'token': token, 'library_path': str(Path(work) / '论文库'), 'config_path': str(Path(work) / 'config')}) + '\n')
            process.stdin.flush()
            deadline = time.monotonic() + 90
            ready = None
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError('Frozen backend exited: ' + ''.join(diagnostics)[-6000:])
                try:
                    line = lines.get(timeout=0.25)
                except queue.Empty:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if payload.get('type') == 'ready':
                    ready = payload
                    break
            if ready is None or ready.get('protocol') != 1:
                raise RuntimeError('No compatible ready event: ' + ''.join(diagnostics)[-6000:])
            base = f"http://127.0.0.1:{ready['port']}/api/v1"
            request = urllib.request.Request(base + '/health', headers={'Authorization': 'Bearer ' + token})
            for attempt in range(30):
                try:
                    with urllib.request.urlopen(request, timeout=2) as response:
                        assert response.status == 200
                    break
                except (urllib.error.URLError, TimeoutError):
                    if attempt == 29:
                        raise
                    time.sleep(0.1)
            try:
                urllib.request.urlopen(base + '/papers', timeout=10)
                raise AssertionError('Unauthenticated library access was allowed')
            except urllib.error.HTTPError as error:
                assert error.code in (401, 403), error.code
            request = urllib.request.Request(base + '/library', headers={'Authorization': 'Bearer ' + token})
            with urllib.request.urlopen(request, timeout=10) as response:
                library = json.load(response)
            assert library.get('path'), ('Library failed to initialize', library, ''.join(diagnostics)[-6000:])
            process.stdin.close()
            process.wait(timeout=15)
            assert process.returncode == 0, process.returncode
            print('PASS: backend startup, authenticated health, unauthorized access rejected, stdin EOF shutdown')
        except Exception:
            print('Backend diagnostics:\n' + ''.join(diagnostics)[-12000:])
            raise
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)


if __name__ == '__main__':
    main()
