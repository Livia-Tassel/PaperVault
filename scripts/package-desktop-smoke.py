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
import urllib.parse
import urllib.request

import psutil


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--driver', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('artifacts/desktop-smoke'))
    parser.add_argument('--pdf', type=Path, help='Optional real PDF to import and parse through the desktop UI')
    parser.add_argument('--models', type=Path, help='Offline model directory for the optional real parse check')
    parser.add_argument('--expect-figures', type=int)
    parser.add_argument('--expect-tables', type=int)
    parser.add_argument('--expect-version', help='Expected native desktop version; backend protocol version is independent')
    parser.add_argument('--capture-ui', action='store_true', help='Save populated workbench, gallery, task and settings screenshots')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'report.json').write_text(json.dumps({'passed': False, 'status': 'running', 'app': str(args.app.resolve())}), encoding='utf-8')
    project_root = Path(__file__).resolve().parent.parent
    test_root = (project_root / '.test-data' / 'packaging').resolve()
    if not test_root.is_relative_to(project_root):
        raise ValueError('Test cleanup directory must remain inside the project')
    test_root.mkdir(parents=True, exist_ok=True)
    # Keep the synthetic library and isolated profile as inspectable evidence.
    # WebView2 may still flush its cache after WebDriver deletes the session.
    with tempfile.TemporaryDirectory(prefix='PaperVault desktop test ', dir=test_root, delete=False) as temporary:
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
        captured_pages: list[str] = []

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

        def capture(name: str) -> None:
            for _ in range(60):
                settled = request('POST', f'/session/{session}/execute/sync', {'script': "return !document.querySelector('.loading, .toast') && [...document.images].filter(i=>{const r=i.getBoundingClientRect();return r.width>0&&r.height>0&&r.bottom>0&&r.top<innerHeight}).every(i=>i.complete&&i.naturalWidth>0)", 'args': []})['value']
                if settled:
                    break
                time.sleep(0.2)
            assert settled, f'View did not finish rendering for screenshot: {name}'
            screenshot = request('GET', f'/session/{session}/screenshot')['value']
            (args.output / f'{name}.png').write_bytes(base64.b64decode(screenshot))
            captured_pages.append(name)

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
                'browserName': 'webview2', 'ms:edgeOptions': {'binary': str(args.app.resolve()),
                    'webviewOptions': {'userDataFolder': str(Path(temporary) / 'webview')}},
            }}})
            session = created['value']['sessionId']
            owned = [process for process in psutil.Process(driver.pid).children(recursive=True)
                     if process.name().lower() == 'papervault.exe' and Path(process.exe()).resolve() == args.app.resolve()]
            assert len(owned) == 1, 'Native process ownership is ambiguous'
            native_app = owned[0]
            prefix = f'/session/{session}'
            request('POST', prefix + '/timeouts', {'script': 100000, 'pageLoad': 100000, 'implicit': 10000})
            for _ in range(150):
                ipc_ready = request('POST', prefix + '/execute/sync', {'script': 'return Boolean(window.__TAURI_INTERNALS__?.invoke)', 'args': []})['value']
                if ipc_ready:
                    break
                time.sleep(0.1)
            assert ipc_ready, 'Native WebView2 IPC did not initialize'
            checks = request('POST', prefix + '/execute/async', {'script': '''
const done = arguments[arguments.length - 1];
(async () => {
  const connection = await window.__TAURI_INTERNALS__.invoke('backend_connection');
  const response = await fetch(connection.baseUrl + '/health', {headers: {Authorization: 'Bearer ' + connection.token}});
  const health = await response.json();
  const denied = await fetch(connection.baseUrl + '/papers');
  return {native: Boolean(window.__TAURI_INTERNALS__), appVersion: await window.__TAURI_INTERNALS__.invoke('plugin:app|version'), baseUrl: connection.baseUrl, healthStatus: response.status,
          unauthorizedStatus: denied.status, health};
})().then(result => done({ok:true, result}), error => done({ok:false, error:String(error)}));
''', 'args': []})['value']
            assert checks.get('ok'), checks
            assert checks['result']['native'] and checks['result']['healthStatus'] == 200, checks
            assert checks['result']['unauthorizedStatus'] in (401, 403), checks
            if args.expect_version:
                assert checks['result']['appVersion'] == args.expect_version, checks
            for _ in range(50):
                body = request('POST', prefix + '/execute/sync', {'script': 'return document.body.innerText', 'args': []})['value']
                if 'PaperVault' in body:
                    break
                time.sleep(0.2)
            assert 'PaperVault' in body, body
            # The brand mounts before /library resolves. Wait for this specific
            # test library and its workspace before testing navigation; initial
            # library-scoped session restoration can otherwise replace a click.
            for _ in range(150):
                library_ready = request('POST', prefix + '/execute/sync', {'script': "return Boolean(document.querySelector('.workspace-bar')) && document.querySelector('[aria-label=\"切换论文库\"]')?.title === arguments[0]", 'args': [str(Path(temporary) / '论文库')]})['value']
                if library_ready:
                    break
                time.sleep(0.1)
            assert library_ready, 'The isolated native library did not finish opening'
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
                if args.capture_ui and label == '设置':
                    element = request('POST', prefix + '/element', {'using': 'xpath', 'value': "//button[normalize-space()='深色']"})['value'][element_key]
                    request('POST', prefix + f'/element/{element}/click', {})
                    assert request('POST', prefix + '/execute/sync', {'script': "return document.documentElement.dataset.theme", 'args': []})['value'] == 'dark'
            parsed = None
            if args.pdf:
                element = request('POST', prefix + '/element', {'using': 'css selector', 'value': 'input[type=file]'})['value'][element_key]
                request('POST', prefix + f'/element/{element}/value', {'text': str(args.pdf.resolve())})
                deadline = time.monotonic() + 600
                opened_while_parsing = False
                notes_element = None
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
                        if not opened_while_parsing and status in ('queued', 'running', 'parsing'):
                            element = request('POST', prefix + '/element', {'using': 'xpath', 'value': "//aside//button[.//span[normalize-space()='论文库']]"})['value'][element_key]
                            request('POST', prefix + f'/element/{element}/click', {})
                            element = request('POST', prefix + '/element', {'using': 'css selector', 'value': '.paper-primary'})['value'][element_key]
                            request('POST', prefix + f'/element/{element}/click', {})
                            notes_element = request('POST', prefix + '/element', {'using': 'xpath', 'value': "//label[span[normalize-space()='个人备注']]/textarea"})['value'][element_key]
                            request('POST', prefix + f'/element/{notes_element}/value', {'text': 'Native unsaved draft'})
                            opened_while_parsing = True
                        if status in ('completed', 'complete', 'ready', 'success', 'parsed'):
                            parsed = {'paper_id': paper['id'], 'status': status, 'figure_count': paper.get('figure_count'), 'table_count': paper.get('table_count')}
                            break
                        if status in ('failed', 'error'):
                            raise AssertionError(('Real desktop parse failed', paper))
                    time.sleep(1)
                assert parsed, 'Real desktop import/parse did not finish before timeout'
                assert opened_while_parsing, 'The live metadata refresh scenario was not exercised'
                title_element = request('POST', prefix + '/element', {'using': 'xpath', 'value': "//label[span[normalize-space()='标题']]/textarea"})['value'][element_key]
                for _ in range(70):
                    title_value = request('GET', prefix + f'/element/{title_element}/property/value')['value']
                    if title_value == (paper.get('title') or ''):
                        break
                    time.sleep(0.2)
                assert title_value == (paper.get('title') or ''), ('Automatic metadata did not refresh', title_value, paper.get('title'))
                assert request('GET', prefix + f'/element/{notes_element}/property/value')['value'] == 'Native unsaved draft'
                parsed['pristine_metadata_refreshed'] = True
                parsed['unsaved_notes_preserved'] = True
                if args.expect_figures is not None:
                    assert parsed['figure_count'] == args.expect_figures, parsed
                if args.expect_tables is not None:
                    assert parsed['table_count'] == args.expect_tables, parsed
                for _ in range(70):
                    counts = request('POST', prefix + '/execute/sync', {'script': "return ['图片库','表格库'].map(label=>{const b=[...document.querySelectorAll('aside button')].find(e=>e.querySelector('span')?.textContent===label);return Number(b?.querySelector('small')?.textContent||0)});", 'args': []})['value']
                    if counts == [parsed.get('figure_count', 0), parsed.get('table_count', 0)]:
                        break
                    time.sleep(0.2)
                assert counts == [parsed.get('figure_count', 0), parsed.get('table_count', 0)], ('Sidebar counts did not refresh', counts, parsed)
                if parsed.get('figure_count', 0):
                    element = request('POST', prefix + '/element', {'using': 'xpath', 'value': "//aside//button[.//span[normalize-space()='图片库']]"})['value'][element_key]
                    request('POST', prefix + f'/element/{element}/click', {})
                    element = request('POST', prefix + '/element', {'using': 'xpath', 'value': "//*[@role='dialog']//button[normalize-space()='放弃修改']"})['value'][element_key]
                    request('POST', prefix + f'/element/{element}/click', {})
                    parsed['unsaved_navigation_guard'] = True
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
                    if args.capture_ui:
                        # Capture actual imported content before the edit-persistence test.
                        # Theme is selected through Settings, without changing DOM styling.
                        capture('pdf-reader-dark-pristine')
                    element = request('POST', prefix + '/element', {'using': 'xpath', 'value': "//button[normalize-space()='目录']"})['value'][element_key]
                    request('POST', prefix + f'/element/{element}/click', {})
                    element = request('POST', prefix + '/element', {'using': 'xpath', 'value': "//button[normalize-space()='编辑目录与参考文献']"})['value'][element_key]
                    request('POST', prefix + f'/element/{element}/click', {})
                    for label, tag, value in (('章节 1 标题', 'input', 'Native desktop verified section'), ('参考文献（每行一条）', 'textarea', 'Native desktop reference persisted.')):
                        element = request('POST', prefix + '/element', {'using': 'xpath', 'value': f"//label[span[normalize-space()='{label}']]/{tag}"})['value'][element_key]
                        request('POST', prefix + f'/element/{element}/click', {})
                        request('POST', prefix + f'/element/{element}/value', {'text': '\ue009a\ue000\ue003' + value})
                    element = request('POST', prefix + '/element', {'using': 'xpath', 'value': "//button[normalize-space()='保存目录与参考文献']"})['value'][element_key]
                    request('POST', prefix + f'/element/{element}/click', {})
                    for _ in range(50):
                        persisted = request('POST', prefix + '/execute/sync', {'script': "return [...document.querySelectorAll('.reference')].some(e=>e.textContent.includes('Native desktop reference persisted.'))", 'args': []})['value']
                        if persisted:
                            break
                        time.sleep(0.1)
                    assert persisted, 'Edited reference did not persist after the server refresh'
                    element = request('POST', prefix + '/element', {'using': 'xpath', 'value': "//button[normalize-space()='编辑目录与参考文献']"})['value'][element_key]
                    request('POST', prefix + f'/element/{element}/click', {})
                    element = request('POST', prefix + '/element', {'using': 'xpath', 'value': "//label[span[normalize-space()='章节 1 标题']]/input"})['value'][element_key]
                    assert request('GET', prefix + f'/element/{element}/property/value')['value'] == 'Native desktop verified section'
                    parsed['outline_and_references_edit'] = True
                    element = request('POST', prefix + '/element', {'using': 'xpath', 'value': "//button[normalize-space()='取消编辑']"})['value'][element_key]
                    request('POST', prefix + f'/element/{element}/click', {})
                    element = request('POST', prefix + '/element', {'using': 'xpath', 'value': "//button[normalize-space()='论文信息']"})['value'][element_key]
                    request('POST', prefix + f'/element/{element}/click', {})
            body = request('POST', prefix + '/execute/sync', {'script': 'return document.body.innerText', 'args': []})['value']
            screenshot = request('GET', prefix + '/screenshot')['value']
            (args.output / 'desktop.png').write_bytes(base64.b64decode(screenshot))
            (args.output / 'visible-text.txt').write_text(body, encoding='utf-8')
            if args.capture_ui:
                capture('pdf-reader' if args.pdf else 'library-empty')
                for label, name in (('论文库', 'library'), ('图片库', 'figures'), ('表格库', 'tables'), ('解析任务', 'tasks'), ('设置', 'settings')):
                    element = request('POST', prefix + '/element', {'using': 'xpath', 'value': f"//aside//button[.//span[normalize-space()='{label}']]"})['value'][element_key]
                    request('POST', prefix + f'/element/{element}/click', {})
                    capture(name)
            request('DELETE', prefix)
            session = None
            backend_port = urllib.parse.urlsplit(checks['result']['baseUrl']).port
            assert backend_port, 'The verified backend URL has no port'
            for _ in range(100):
                try:
                    with socket.create_connection(('127.0.0.1', backend_port), timeout=0.2):
                        backend_closed = False
                except OSError:
                    backend_closed = True
                if backend_closed and not native_app.is_running():
                    break
                time.sleep(0.1)
            assert backend_closed and not native_app.is_running(), 'The owned native app or backend did not exit after session closure'
            report = {'passed': True, 'app': str(args.app.resolve()), 'fixture': temporary, 'checks': checks['result'], 'navigation': navigation, 'parsed': parsed, 'captured_pages': captured_pages,
                      'shutdown': {'owned_app_pid': native_app.pid, 'application_exited': True, 'backend_port_closed': True},
                      'scope': 'Actual Tauri WebView2, packaged sidecar startup, IPC, CSP/CORS authenticated API, access denial, rendered UI. Installer cleanliness and full parsing quality require separate checks.'}
            (args.output / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
            print('PASS: actual Tauri desktop, native IPC, authenticated API, denied anonymous access, screenshot')
        except Exception as error:
            (args.output / 'report.json').write_text(json.dumps({'passed': False, 'app': str(args.app.resolve()), 'error': str(error)}, indent=2, ensure_ascii=False), encoding='utf-8')
            if session:
                try:
                    screenshot = request('GET', f'/session/{session}/screenshot')['value']
                    (args.output / 'failure.png').write_bytes(base64.b64decode(screenshot))
                except Exception:
                    pass
            raise
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
