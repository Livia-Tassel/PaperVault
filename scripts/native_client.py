"""Small real-WebView2 test client; every process/profile belongs to the test."""
from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

import psutil

ROOT = Path(__file__).resolve().parent.parent


def wait_until(check, message, timeout=25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(.15)
    raise AssertionError(message)


class NativeClient:
    element_key = 'element-6066-11e4-a52e-4f735466cecf'

    def __init__(self, app: Path, fixture: Path, library: Path, output: Path):
        self.app, self.fixture, self.library, self.output = app.resolve(), fixture.resolve(), library.resolve(), output.resolve()
        assert self.fixture.is_relative_to(ROOT / '.test-data')
        self.output.mkdir(parents=True, exist_ok=True)
        self.session = None
        self.application = None
        self.driver = None
        self.connection = None
        self.log = None

    def start(self):
        with socket.socket() as reserve:
            reserve.bind(('127.0.0.1', 0))
            port = reserve.getsockname()[1]
        self.endpoint = f'http://127.0.0.1:{port}'
        environment = dict(os.environ, TAURI_WEBVIEW_AUTOMATION='true', PAPERVAULT_LIBRARY_PATH=str(self.library),
                           PAPERVAULT_CONFIG_PATH=str(self.fixture / 'config'), PAPERVAULT_MODELS_PATH=str(self.fixture / 'no-models'))
        environment.pop('PYTHONPATH', None)
        environment.pop('VIRTUAL_ENV', None)
        self.log = (self.output / 'webdriver.log').open('a', encoding='utf-8')
        self.driver = subprocess.Popen([str(ROOT / '.tools/edgedriver/msedgedriver.exe'), f'--port={port}', '--host=127.0.0.1'],
                                       env=environment, stdout=self.log, stderr=self.log, creationflags=subprocess.CREATE_NO_WINDOW)
        def ready():
            try:
                return self.request('GET', '/status') is not None
            except (OSError, urllib.error.URLError):
                return False
        wait_until(ready, 'WebDriver did not start')
        created = self.request('POST', '/session', {'capabilities': {'alwaysMatch': {
            'browserName': 'webview2', 'ms:edgeOptions': {'binary': str(self.app),
                'webviewOptions': {'userDataFolder': str(self.fixture / 'webview')}},
        }}})
        self.session = created['sessionId']
        self.prefix = f'/session/{self.session}'
        self.request('POST', self.prefix + '/timeouts', {'script': 100000, 'implicit': 10000})
        owned = [process for process in psutil.Process(self.driver.pid).children(recursive=True)
                 if process.name().lower() == 'papervault.exe' and Path(process.exe()).resolve() == self.app]
        assert len(owned) == 1, 'Native process ownership is ambiguous'
        self.application = owned[0]
        wait_until(lambda: self.execute("return Boolean(window.__TAURI_INTERNALS__?.invoke)"), 'Native IPC did not initialize')
        result = self.request('POST', self.prefix + '/execute/async', {'script': '''
const done=arguments[arguments.length-1];
window.__TAURI_INTERNALS__.invoke('backend_connection').then(value=>done({ok:true,value}),error=>done({ok:false,error:String(error)}));
''', 'args': []})
        assert result['ok'], result
        self.connection = result['value']
        return self

    def request(self, method, route, data=None):
        payload = json.dumps(data).encode('utf-8') if data is not None else None
        req = urllib.request.Request(self.endpoint + route, data=payload, method=method, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=100) as response:
                result = json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(error.read().decode(errors='replace')) from error
        value = result.get('value')
        if isinstance(value, dict) and value.get('error'):
            raise RuntimeError(value)
        return value

    def execute(self, script):
        return self.request('POST', self.prefix + '/execute/sync', {'script': script, 'args': []})

    def element(self, xpath):
        return self.request('POST', self.prefix + '/element', {'using': 'xpath', 'value': xpath})[self.element_key]

    def click(self, xpath):
        self.request('POST', self.prefix + f'/element/{self.element(xpath)}/click', {})

    def fill(self, xpath, value):
        node = self.element(xpath)
        self.request('POST', self.prefix + f'/element/{node}/click', {})
        # Real editing keys notify React's controlled input tracker; WebDriver
        # clear() can reset only the DOM value before React restores its draft.
        self.request('POST', self.prefix + f'/element/{node}/value', {'text': '\ue009a\ue000\ue003' + value})

    def screenshot(self, name):
        data = self.request('GET', self.prefix + '/screenshot')
        (self.output / f'{name}.png').write_bytes(base64.b64decode(data))

    def api(self, route, method='GET', data=None, scope=None, expect=200, raw=False):
        payload = json.dumps(data).encode('utf-8') if data is not None else None
        headers = {'Authorization': 'Bearer ' + self.connection['token'], 'Content-Type': 'application/json'}
        if scope is not None:
            headers['X-PaperVault-Library'] = urllib.parse.quote(scope, safe='')
        req = urllib.request.Request(self.connection['baseUrl'] + route, data=payload, method=method, headers=headers)
        try:
            response = urllib.request.urlopen(req, timeout=60)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read()
            assert response.status == expect, (route, response.status, body.decode(errors='replace'))
            return body if raw else json.loads(body) if body else None

    def switch_library(self, path):
        self.click("//aside//button[@aria-label='切换论文库']")
        self.fill("//input[@aria-label='论文库目录']", str(path))
        self.click("//*[@role='dialog']//button[contains(.,'打开 / 创建论文库')]")
        wait_until(lambda: Path(self.api('/library')['path']).resolve() == Path(path).resolve(), 'Library did not switch')
        wait_until(lambda: self.execute("return !document.querySelector('[role=dialog]')"), 'Library switch dialog did not close')

    def close(self):
        if self.session and self.application and self.application.is_running():
            try:
                self.request('DELETE', self.prefix)
                self.application.wait(timeout=20)
            except Exception:
                # Exact child process proven in start(); never target another user's app.
                if self.application.is_running():
                    self.application.kill()
                    self.application.wait(timeout=10)
        if self.driver:
            self.driver.terminate()
            self.driver.wait(timeout=10)
        if self.log:
            self.log.close()

    def wm_close(self):
        user32 = ctypes.windll.user32
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
        windows = []

        @callback_type
        def inspect(hwnd, _):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == self.application.pid and user32.IsWindowVisible(hwnd):
                title = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(hwnd, title, len(title))
                if title.value == 'PaperVault':
                    windows.append(hwnd)
            return True

        user32.EnumWindows(inspect, 0)
        assert len(windows) == 1
        assert user32.PostMessageW(windows[0], 0x0010, 0, 0)

    def assert_exit(self):
        self.application.wait(timeout=25)
        port = urllib.parse.urlsplit(self.connection['baseUrl']).port
        def closed():
            with socket.socket() as probe:
                probe.settimeout(.5)
                return probe.connect_ex(('127.0.0.1', port)) != 0
        wait_until(closed, 'Sidecar remained alive after closing the native window')

    def cancel_native_save_dialog(self, destination: Path):
        """Cancel the actual owned Windows common dialog, never a DOM substitute."""
        destination = destination.resolve()
        assert destination.is_relative_to(self.fixture) and not destination.exists()
        destination.parent.mkdir(parents=True, exist_ok=True)
        user32 = ctypes.windll.user32
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.IsWindow.argtypes = [wintypes.HWND]
        user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
        user32.EnumChildWindows.argtypes = [wintypes.HWND, callback_type, wintypes.LPARAM]
        user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
                                              wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
        user32.SendMessageTimeoutW.restype = ctypes.c_ssize_t

        def text(hwnd):
            # GetWindowText only retrieves cross-process captions. WM_GETTEXT
            # must be sent to the owned Edit control to read its actual value.
            length = ctypes.c_size_t()
            if not user32.SendMessageTimeoutW(hwnd, 0x000E, 0, 0, 0x0002, 1000, ctypes.byref(length)):
                return ''
            value = ctypes.create_unicode_buffer(min(length.value + 1, 32768))
            copied = ctypes.c_size_t()
            if not user32.SendMessageTimeoutW(hwnd, 0x000D, len(value), ctypes.cast(value, ctypes.c_void_p).value,
                                             0x0002, 1000, ctypes.byref(copied)):
                return ''
            return value.value

        def class_name(hwnd):
            value = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, value, len(value))
            return value.value

        dialogs = []

        def locate():
            dialogs.clear()

            @callback_type
            def inspect(hwnd, _):
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value == self.application.pid and user32.IsWindowVisible(hwnd) and class_name(hwnd) == '#32770':
                    dialogs.append(hwnd)
                return True

            user32.EnumWindows(inspect, 0)
            return bool(dialogs)

        wait_until(locate, 'The actual Windows Save dialog did not open')
        assert len(dialogs) == 1, 'Owned native Save dialog is ambiguous'
        dialog = dialogs[0]
        edits = []

        @callback_type
        def inspect_child(hwnd, _):
            if class_name(hwnd) == 'Edit' and 'PaperVault-notes' in text(hwnd):
                edits.append(hwnd)
            return True

        def find_filename():
            edits.clear()
            user32.EnumChildWindows(dialog, inspect_child, 0)
            return len(edits) == 1

        try:
            wait_until(find_filename, 'Could not identify the owned Save dialog filename control')
            # Set an explicit test destination before cancellation so any unexpected
            # write would remain in the test fixture and be caught below.
            value = ctypes.create_unicode_buffer(str(destination))
            result = ctypes.c_size_t()
            assert user32.SendMessageTimeoutW(edits[0], 0x000C, 0, ctypes.cast(value, ctypes.c_void_p).value,
                                              0x0002, 1000, ctypes.byref(result))
            assert text(edits[0]) == str(destination)
            proof = {'window_class': '#32770', 'title': text(dialog), 'owner_pid': self.application.pid,
                     'destination': str(destination), 'operation': 'WM_CLOSE on the actual native Save dialog'}
        finally:
            if user32.IsWindow(dialog):
                assert user32.PostMessageW(dialog, 0x0010, 0, 0)
                wait_until(lambda: not user32.IsWindow(dialog), 'Native Save dialog did not cancel')
        assert not destination.exists(), 'Cancel unexpectedly wrote the export destination'
        return proof
