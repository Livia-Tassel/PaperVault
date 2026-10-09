"""Exercise actual Win32 WM_CLOSE against the development Tauri window.

The test owns a fresh library/profile and the exact child application it launches.
It deliberately keeps that isolated fixture for inspecting persisted results.
Vite must already be serving the current frontend at port 1420.
"""
from __future__ import annotations

import argparse
import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

import psutil

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', type=Path, default=ROOT / 'apps/desktop/src-tauri/target/x86_64-pc-windows-msvc/debug/papervault.exe')
    parser.add_argument('--driver', type=Path, default=ROOT / '.tools/edgedriver/msedgedriver.exe')
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/native-close-guard')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    fixture_root = (ROOT / '.test-data/workspace-native').resolve()
    assert fixture_root.is_relative_to(ROOT)
    fixture_root.mkdir(parents=True, exist_ok=True)
    fixture = Path(tempfile.mkdtemp(prefix='close-guard-', dir=fixture_root)).resolve()
    assert fixture.is_relative_to(fixture_root)
    library = fixture / '论文库'
    with socket.socket() as reserve:
        reserve.bind(('127.0.0.1', 0))
        port = reserve.getsockname()[1]
    endpoint = f'http://127.0.0.1:{port}'
    environment = dict(os.environ, TAURI_WEBVIEW_AUTOMATION='true', PAPERVAULT_LIBRARY_PATH=str(library),
                       PAPERVAULT_CONFIG_PATH=str(fixture / 'config'), PAPERVAULT_MODELS_PATH=str(fixture / 'no-models'),
                       WEBVIEW2_USER_DATA_FOLDER=str(fixture / 'webview'))
    log = (args.output / 'webdriver.log').open('w', encoding='utf-8')
    driver = subprocess.Popen([str(args.driver.resolve()), f'--port={port}', '--host=127.0.0.1'],
                              env=environment, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
    session = None
    application = None
    report = {'passed': False, 'fixture': str(fixture), 'app': str(args.app.resolve()), 'phases': []}
    key = 'element-6066-11e4-a52e-4f735466cecf'

    def request(method, path, data=None):
        payload = json.dumps(data).encode('utf-8') if data is not None else None
        req = urllib.request.Request(endpoint + path, data=payload, method=method, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=100) as response:
                result = json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(error.read().decode(errors='replace')) from error
        if isinstance(result.get('value'), dict) and result['value'].get('error'):
            raise RuntimeError(result['value'])
        return result.get('value')

    def execute(script):
        return request('POST', f'/session/{session}/execute/sync', {'script': script, 'args': []})

    def element(xpath):
        return request('POST', f'/session/{session}/element', {'using': 'xpath', 'value': xpath})[key]

    def click(xpath):
        request('POST', f'/session/{session}/element/{element(xpath)}/click', {})

    def fill(xpath, value):
        node = element(xpath)
        request('POST', f'/session/{session}/element/{node}/clear', {})
        request('POST', f'/session/{session}/element/{node}/value', {'text': value})

    def screenshot(name):
        raw = request('GET', f'/session/{session}/screenshot')
        (args.output / f'{name}.png').write_bytes(base64.b64decode(raw))

    def wait_until(check, message, timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if check():
                return
            time.sleep(.15)
        raise AssertionError(message)

    def open_session():
        nonlocal session, application
        created = request('POST', '/session', {'capabilities': {'alwaysMatch': {
            'browserName': 'webview2', 'ms:edgeOptions': {'binary': str(args.app.resolve()),
                'webviewOptions': {'userDataFolder': str(fixture / 'webview')}},
        }}})
        session = created['sessionId']
        request('POST', f'/session/{session}/timeouts', {'script': 100000, 'implicit': 10000})
        children = [child for child in psutil.Process(driver.pid).children(recursive=True)
                    if child.name().lower() == 'papervault.exe' and Path(child.exe()).resolve() == args.app.resolve()]
        assert len(children) == 1, 'Could not uniquely establish ownership of the native window process'
        application = children[0]
        wait_until(lambda: execute("return Boolean(window.__TAURI_INTERNALS__?.invoke)"), 'Native IPC did not initialize')
        connection = request('POST', f'/session/{session}/execute/async', {'script': '''
const done=arguments[arguments.length-1];
window.__TAURI_INTERNALS__.invoke('backend_connection').then(value=>done({ok:true,value}),error=>done({ok:false,error:String(error)}));
''', 'args': []})
        assert connection['ok'], connection
        return connection['value']

    def api(connection, path, method='GET', data=None):
        body = json.dumps(data).encode('utf-8') if data is not None else None
        req = urllib.request.Request(connection['baseUrl'] + path, data=body, method=method,
                                     headers={'Authorization': 'Bearer ' + connection['token'], 'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)

    def wm_close():
        assert application and application.is_running()
        windows = []
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32 = ctypes.windll.user32
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

        @callback_type
        def inspect(hwnd, _):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == application.pid and user32.IsWindowVisible(hwnd):
                title = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(hwnd, title, len(title))
                if title.value == 'PaperVault':
                    windows.append(hwnd)
            return True

        user32.EnumWindows(inspect, 0)
        assert len(windows) == 1, f'Unexpected number of owned visible windows: {len(windows)}'
        assert user32.PostMessageW(windows[0], 0x0010, 0, 0), 'WM_CLOSE delivery failed'

    def verify_exit(connection):
        nonlocal session, application
        application.wait(timeout=25)
        backend_port = int(connection['baseUrl'].split(':')[2].split('/')[0])
        def port_closed():
            with socket.socket() as probe:
                probe.settimeout(.5)
                return probe.connect_ex(('127.0.0.1', backend_port)) != 0
        wait_until(port_closed, 'Sidecar remained alive after the native window exited')
        try:
            request('DELETE', f'/session/{session}')
        except Exception:
            pass
        session = None
        application = None

    try:
        wait_until(lambda: driver.poll() is None and _ready(endpoint), 'WebDriver did not start')
        connection = open_session()
        imported = api(connection, '/papers/import-paths', 'POST', {'paths': [str(ROOT / 'tests/fixtures/academic.pdf')], 'recursive': False})
        assert not imported['errors'], imported
        paper = imported['items'][0]
        click("//aside//button[@aria-label='论文库']")
        click("//button[contains(@class,'paper-primary')]")
        wait_until(lambda: execute("return [...document.querySelectorAll('.pdf-page canvas')].some(e=>e.width>0)"), 'PDF did not render')
        fill("//input[@aria-label='PDF 页码']", '2\ue007')
        wait_until(lambda: execute("return document.querySelector('[aria-label=\"PDF 页码\"]')?.value === '2'"), 'PDF page did not advance')
        fill("//label[span[normalize-space()='个人备注']]/textarea", 'Native close saved draft')
        wm_close()
        wait_until(lambda: execute("return [...document.querySelectorAll('[role=dialog]')].some(e=>e.textContent.includes('有未保存的修改'))"), 'WM_CLOSE did not show the unsaved-change guard')
        screenshot('close-guard')
        click("//button[normalize-space()='继续编辑']")
        assert application.is_running() and api(connection, '/health')['status'] == 'ok'
        assert request('GET', f'/session/{session}/element/{element("//label[span[normalize-space()=\'个人备注\']]/textarea")}/property/value') == 'Native close saved draft'
        report['phases'].append('cancel_keeps_window_sidecar_and_draft')
        wm_close()
        click("//button[normalize-space()='保存并继续']")
        verify_exit(connection)
        sys.path.insert(0, str(ROOT / 'backend'))
        from papervault.library import Library
        stored = Library(library, create=False)
        try:
            assert stored.paper(paper['id'])['notes'] == 'Native close saved draft'
            assert stored.reading_state(paper['id'])['page_index'] == 1
        finally:
            stored.close()
        report['phases'].append('save_then_close_persists_draft_and_reading_progress')
        connection = open_session()
        wait_until(lambda: execute("return Boolean(document.querySelector('.paper-workspace'))"), 'Reader tab did not restore after native restart')
        fill("//label[span[normalize-space()='个人备注']]/textarea", 'Native discarded draft')
        wm_close()
        click("//button[normalize-space()='放弃修改']")
        verify_exit(connection)
        stored = Library(library, create=False)
        try:
            assert stored.paper(paper['id'])['notes'] == 'Native close saved draft'
        finally:
            stored.close()
        report['phases'].append('discard_closes_without_overwriting_saved_note')
        report['passed'] = True
        print('PASS: native WM_CLOSE cancel/save/discard, persisted reading state, workspace restart, sidecar cleanup')
    except Exception as error:
        report['error'] = str(error)
        if session:
            try:
                report['visible_errors'] = execute("return [...document.querySelectorAll('[role=alert],.reading-state-error,.reader-save-error')].map(e=>e.textContent)")
                screenshot('failure')
            except Exception:
                pass
        raise
    finally:
        (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        if application and application.is_running():
            # This exact psutil Process was proven to be the test driver's child.
            application.kill()
            application.wait(timeout=10)
        driver.terminate()
        driver.wait(timeout=10)
        log.close()


def _ready(endpoint):
    try:
        with urllib.request.urlopen(endpoint + '/status', timeout=1) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


if __name__ == '__main__':
    main()
