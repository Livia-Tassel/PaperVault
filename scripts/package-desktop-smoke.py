"""Real Windows WebView2 desktop smoke test; does not use browser-only mocks.

Pass either a built release exe or the exe from an actual NSIS installation.
The matching Microsoft Edge WebDriver is a separate test tool, not a runtime dependency.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--driver', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('artifacts/desktop-smoke'))
    parser.add_argument('--pdf', type=Path, help='Optional real PDF to import and parse through the desktop UI')
    parser.add_argument('--models', type=Path, help='Offline model directory for the optional real parse check')
    parser.add_argument('--expect-figures', type=int)
    parser.add_argument('--expect-tables', type=int)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    test_root = Path(__file__).resolve().parent.parent / '.test-data' / 'packaging'
    test_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='PaperVault desktop test ', dir=test_root) as temporary:
        with socket.socket() as reserve:
            reserve.bind(('127.0.0.1', 0))
            port = reserve.getsockname()[1]
        endpoint = f'http://127.0.0.1:{port}'
        environment = dict(os.environ)
        environment.pop('PYTHONPATH', None)
        environment.pop('VIRTUAL_ENV', None)
        environment.update({
            'TAURI_WEBVIEW_AUTOMATION': 'true',
            'PAPERVAULT_LIBRARY_PATH': str(Path(temporary) / '论文库'),
            'PAPERVAULT_CONFIG_PATH': str(Path(temporary) / 'config'),
            'WEBVIEW2_USER_DATA_FOLDER': str(Path(temporary) / 'webview'),
        })
        if args.models:
            environment['PAPERVAULT_MODELS_PATH'] = str(args.models.resolve())
        log = (args.output / 'webdriver.log').open('w', encoding='utf-8')
        driver = subprocess.Popen([str(args.driver.resolve()), f'--port={port}', '--host=127.0.0.1'], env=environment,
                                  stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        session = None

        def request(method: str, path: str, data: dict | None = None) -> dict:
            payload = json.dumps(data).encode() if data is not None else None
            req = urllib.request.Request(endpoint + path, data=payload, method=method, headers={'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(req, timeout=100) as response:
                    result = json.load(response)
            except urllib.error.HTTPError as error:
                raise RuntimeError(error.read().decode(errors='replace')) from error
            if isinstance(result.get('value'), dict) and result['value'].get('error'):
                raise RuntimeError(result['value'])
            return result

        try:
            for attempt in range(100):
                try:
                    request('GET', '/status')
                    break
                except (urllib.error.URLError, TimeoutError):
                    if attempt == 99:
                        raise
                    time.sleep(0.1)
            created = request('POST', '/session', {'capabilities': {'alwaysMatch': {
                'browserName': 'webview2', 'ms:edgeOptions': {'binary': str(args.app.resolve())},
            }}})
            session = created['value']['sessionId']
            prefix = f'/session/{session}'
            request('POST', prefix + '/timeouts', {'script': 100000, 'pageLoad': 100000, 'implicit': 10000})
            checks = request('POST', prefix + '/execute/async', {'script': '''
const done = arguments[arguments.length - 1];
(async () => {
  const connection = await window.__TAURI_INTERNALS__.invoke('backend_connection');
  const response = await fetch(connection.baseUrl + '/health', {headers: {Authorization: 'Bearer ' + connection.token}});
  const health = await response.json();
  const denied = await fetch(connection.baseUrl + '/papers');
  return {native: Boolean(window.__TAURI_INTERNALS__), healthStatus: response.status,
          unauthorizedStatus: denied.status, health};
})().then(result => done({ok:true, result}), error => done({ok:false, error:String(error)}));
''', 'args': []})['value']
            assert checks.get('ok'), checks
            assert checks['result']['native'] and checks['result']['healthStatus'] == 200, checks
            assert checks['result']['unauthorizedStatus'] in (401, 403), checks
            for _ in range(50):
                body = request('POST', prefix + '/execute/sync', {'script': 'return document.body.innerText', 'args': []})['value']
                if 'PaperVault' in body:
                    break
                time.sleep(0.2)
            assert 'PaperVault' in body, body
            navigation = []
            element_key = 'element-6066-11e4-a52e-4f735466cecf'
            for label in ('图片库', '表格库', '解析任务', '设置', '论文库'):
                element = request('POST', prefix + '/element', {'using': 'xpath', 'value': f"//aside//button[.//span[normalize-space()='{label}']]"})['value'][element_key]
                request('POST', prefix + f'/element/{element}/click', {})
                for attempt in range(30):
                    heading = request('POST', prefix + '/execute/sync', {'script': "return document.querySelector('h1')?.textContent || ''", 'args': []})['value']
                    if label in heading:
                        break
                    time.sleep(0.1)
                assert label in heading, (label, heading)
                navigation.append(label)
            parsed = None
            if args.pdf:
                element = request('POST', prefix + '/element', {'using': 'css selector', 'value': 'input[type=file]'})['value'][element_key]
                request('POST', prefix + f'/element/{element}/value', {'text': str(args.pdf.resolve())})
                deadline = time.monotonic() + 600
                while time.monotonic() < deadline:
                    data = request('POST', prefix + '/execute/async', {'script': '''
const done=arguments[arguments.length-1];
(async()=>{const c=await window.__TAURI_INTERNALS__.invoke('backend_connection');
const r=await fetch(c.baseUrl+'/papers',{headers:{Authorization:'Bearer '+c.token}});
return await r.json();})().then(done,e=>done({error:String(e)}));
''', 'args': []})['value']
                    items = data.get('items', [])
                    if items:
                        paper = items[0]
                        status = paper.get('parse_status', paper.get('status'))
                        if status in ('completed', 'complete', 'ready', 'success', 'parsed'):
                            parsed = {'paper_id': paper['id'], 'status': status, 'figure_count': paper.get('figure_count'), 'table_count': paper.get('table_count')}
                            break
                        if status in ('failed', 'error'):
                            raise AssertionError(('Real desktop parse failed', paper))
                    time.sleep(1)
                assert parsed, 'Real desktop import/parse did not finish before timeout'
                if args.expect_figures is not None:
                    assert parsed['figure_count'] == args.expect_figures, parsed
                if args.expect_tables is not None:
                    assert parsed['table_count'] == args.expect_tables, parsed
                if parsed.get('figure_count', 0):
                    element = request('POST', prefix + '/element', {'using': 'xpath', 'value': "//aside//button[.//span[normalize-space()='图片库']]"})['value'][element_key]
                    request('POST', prefix + f'/element/{element}/click', {})
                    element = request('POST', prefix + '/element', {'using': 'css selector', 'value': '.resource-card-image'})['value'][element_key]
                    request('POST', prefix + f'/element/{element}/click', {})
                    element = request('POST', prefix + '/element', {'using': 'xpath', 'value': "//*[@role='dialog']//button[contains(.,'查看原文')]"})['value'][element_key]
                    request('POST', prefix + f'/element/{element}/click', {})
                    for _ in range(100):
                        located = request('POST', prefix + '/execute/sync', {'script': "const h=document.querySelector('.pdf-highlight');const t=document.querySelector('.pdf-reader .textLayer');return Boolean(h&&h.getBoundingClientRect().width>0&&t&&t.childElementCount>0);", 'args': []})['value']
                        if located:
                            break
                        time.sleep(0.2)
                    assert located, 'Figure did not render and highlight in the original PDF'
                    parsed['pdf_region_highlight'] = True
            screenshot = request('GET', prefix + '/screenshot')['value']
            (args.output / 'desktop.png').write_bytes(base64.b64decode(screenshot))
            (args.output / 'visible-text.txt').write_text(body, encoding='utf-8')
            report = {'passed': True, 'app': str(args.app.resolve()), 'checks': checks['result'], 'navigation': navigation, 'parsed': parsed,
                      'scope': 'Actual Tauri WebView2, packaged sidecar startup, IPC, CSP/CORS authenticated API, access denial, rendered UI. Installer cleanliness and full parsing quality require separate checks.'}
            (args.output / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
            print('PASS: actual Tauri desktop, native IPC, authenticated API, denied anonymous access, screenshot')
        finally:
            if session:
                try:
                    request('DELETE', f'/session/{session}')
                except Exception:
                    pass
            driver.terminate()
            driver.wait(timeout=10)
            log.close()


if __name__ == '__main__':
    main()
