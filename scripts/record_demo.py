"""Record actual installed PaperVault operations in an isolated demo library."""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import traceback

import cv2

from native_client import NativeClient, ROOT, wait_until


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


class OwnedWindow:
    def __init__(self, client):
        self.client = client
        self.user = ctypes.windll.user32
        self.callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        self.user.EnumWindows.argtypes = [self.callback, wintypes.LPARAM]
        self.user.EnumChildWindows.argtypes = [wintypes.HWND, self.callback, wintypes.LPARAM]
        self.user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.user.IsWindowVisible.argtypes = [wintypes.HWND]
        self.user.IsWindow.argtypes = [wintypes.HWND]
        self.user.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.user.SetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPCWSTR]
        self.user.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        self.user.SetForegroundWindow.argtypes = [wintypes.HWND]
        self.user.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        self.user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self.user.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM, wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
        self.user.SendMessageTimeoutW.restype = ctypes.c_ssize_t
        windows = self.windows()
        self.hwnd = next(h for h in windows if self.title(h) == 'PaperVault')
        self.recording_title = f'PaperVault-Demo-{client.application.pid}'

    def windows(self):
        found = []

        @self.callback
        def inspect(hwnd, _):
            pid = wintypes.DWORD()
            self.user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == self.client.application.pid and self.user.IsWindowVisible(hwnd):
                found.append(hwnd)
            return True

        self.user.EnumWindows(inspect, 0)
        return found

    def title(self, hwnd):
        buf = ctypes.create_unicode_buffer(1024)
        self.user.GetWindowTextW(hwnd, buf, len(buf))
        return buf.value

    def class_name(self, hwnd):
        buf = ctypes.create_unicode_buffer(256)
        self.user.GetClassNameW(hwnd, buf, len(buf))
        return buf.value

    def edit_text(self, hwnd):
        buf = ctypes.create_unicode_buffer(32768)
        result = ctypes.c_size_t()
        self.user.SendMessageTimeoutW(hwnd, 0x000D, len(buf), ctypes.cast(buf, ctypes.c_void_p).value, 2, 1000, ctypes.byref(result))
        return buf.value

    def prepare(self, width=1920, height=960):
        self.user.ShowWindow(self.hwnd, 9)
        self.user.SetForegroundWindow(self.hwnd)
        # Request an exact client region, excluding title bar and other apps.
        for _ in range(3):
            client, outer = wintypes.RECT(), wintypes.RECT()
            self.user.GetClientRect(self.hwnd, ctypes.byref(client))
            self.user.GetWindowRect(self.hwnd, ctypes.byref(outer))
            outer_width = width + (outer.right - outer.left) - client.right
            outer_height = height + (outer.bottom - outer.top) - client.bottom
            assert self.user.SetWindowPos(self.hwnd, 0, 40, 40, outer_width, outer_height, 0x0040)
            time.sleep(.3)
        assert self.user.SetWindowTextW(self.hwnd, self.recording_title)
        return self.client.execute('return {width:innerWidth,height:innerHeight,dpr:devicePixelRatio}')

    def move_to(self, xpath):
        encoded = json.dumps(xpath)
        rect = self.client.execute(f'''const e=document.evaluate({encoded},document,null,XPathResult.FIRST_ORDERED_NODE_TYPE,null).singleNodeValue;
if(!e)return null;e.scrollIntoView({{block:'nearest',inline:'nearest'}});const r=e.getBoundingClientRect();return {{x:r.x+r.width/2,y:r.y+r.height/2,width:innerWidth}};''')
        if not rect:
            return
        client = wintypes.RECT()
        self.user.GetClientRect(self.hwnd, ctypes.byref(client))
        scale = client.right / rect['width']
        point = wintypes.POINT(round(rect['x'] * scale), round(rect['y'] * scale))
        self.user.ClientToScreen(self.hwnd, ctypes.byref(point))
        initial = wintypes.POINT()
        self.user.GetCursorPos(ctypes.byref(initial))
        for step in range(1, 13):
            p = step / 12
            self.user.SetCursorPos(round(initial.x + (point.x - initial.x) * p), round(initial.y + (point.y - initial.y) * p))
            time.sleep(.018)

    def save_dialog(self, destination):
        destination = Path(destination).resolve()
        assert destination.is_relative_to(self.client.fixture) and not destination.exists()
        destination.parent.mkdir(parents=True, exist_ok=True)
        found = []

        def locate():
            found[:] = [h for h in self.windows() if self.class_name(h) == '#32770']
            return len(found) == 1

        wait_until(locate, 'Owned native Save dialog did not appear')
        dialog = found[0]
        edits, buttons = [], []

        @self.callback
        def inspect(hwnd, _):
            kind, value = self.class_name(hwnd), self.edit_text(hwnd)
            if kind == 'Edit' and value.lower().endswith('.csv'):
                edits.append(hwnd)
            if kind == 'Button' and ('保存' in value or value.replace('&', '').startswith('Save')):
                buttons.append(hwnd)
            return True

        self.user.EnumChildWindows(dialog, inspect, 0)
        assert len(edits) == 1 and len(buttons) == 1, (edits, buttons)
        text = ctypes.create_unicode_buffer(str(destination))
        result = ctypes.c_size_t()
        assert self.user.SendMessageTimeoutW(edits[0], 0x000C, 0, ctypes.cast(text, ctypes.c_void_p).value, 2, 1000, ctypes.byref(result))
        assert self.edit_text(edits[0]) == str(destination)
        time.sleep(1.5)
        assert self.user.PostMessageW(buttons[0], 0x00F5, 0, 0)
        wait_until(lambda: not self.user.IsWindow(dialog), 'Native Save dialog did not complete')
        wait_until(lambda: destination.is_file() and destination.stat().st_size > 0, 'CSV was not actually written')
        return {'path': str(destination), 'bytes': destination.stat().st_size,
                'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(), 'actual_native_dialog': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', action='store_true')
    parser.add_argument('--fixture', type=Path)
    args = parser.parse_args()
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = ROOT / 'artifacts/demo' / ('probe-' + stamp if args.probe else 'capture-' + stamp)
    output.mkdir(parents=True)
    fixture = (args.fixture or ROOT / '.test-data/demo' / stamp).resolve()
    assert fixture.is_relative_to(ROOT / '.test-data/demo')
    fixture.mkdir(parents=True, exist_ok=True)
    library = fixture / '演示论文库'
    source = ROOT / '.test-data/external/expanded-corpus/ml-simcse-emnlp2021.pdf'
    sample = fixture / 'SimCSE.pdf'
    if not sample.exists():
        shutil.copyfile(source, sample)
    assert hashlib.sha256(sample.read_bytes()).digest() == hashlib.sha256(source.read_bytes()).digest()
    binary = ROOT / '.test-data/installed/PaperVault/papervault.exe'
    ffmpeg = ROOT / '.tools/video-python/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe'
    raw = output / 'capture.mp4'
    report = {'passed': False, 'fixture': str(fixture), 'source': str(sample), 'raw_video': str(raw),
              'output_directory': str(ROOT / 'artifacts/demo/final'), 'cues': [], 'events': [], 'cuts': []}
    client, window, recorder, log = None, None, None, None
    clock_start = 0
    try:
        client = NativeClient(binary, fixture, library, output, models=ROOT / '.cache/models').start()
        report['desktop_version'] = client.execute("return window.__TAURI_INTERNALS__.invoke('plugin:app|version')")
        assert report['desktop_version'] == '0.2.2'
        wait_until(lambda: bool(client.execute('return document.querySelector(".workspace-bar")')), 'Demo library did not open')
        assert client.api('/models')['ready'], 'Local models must be ready before recording'
        client.click("//aside//button[@aria-label='设置']")
        client.click("//button[normalize-space()='深色']")
        client.click("//aside//button[@aria-label='论文库']")
        wait_until(lambda: client.execute('return !document.querySelector(".toast,.loading")'), 'Initial UI did not settle')
        window = OwnedWindow(client)
        report['viewport'] = window.prepare()
        client.screenshot('before-recording')
        report['capture_method'] = 'Actual WebView2 CDP screencast; operating-system Save dialog excluded and disclosed in subtitles'
        log = (output / 'webview-capture.log').open('w', encoding='utf-8')
        address = client.capabilities['ms:edgeOptions']['debuggerAddress']
        recorder = subprocess.Popen(['node', str(ROOT / 'scripts/capture_webview.mjs'),
                                     '--debugger-address', address, '--output-dir', str(output), '--ffmpeg', str(ffmpeg)],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
        ready = json.loads(recorder.stdout.readline())
        assert ready['type'] == 'ready', ready
        clock_start = time.monotonic() - (time.time() - ready['epoch_ms'] / 1000)
        time.sleep(1)
        assert recorder.poll() is None, (output / 'webview-capture.log').read_text(encoding='utf-8')

        def now():
            return round(time.monotonic() - clock_start, 3)

        def scene(text, action=None, hold=4):
            start = now()
            print(json.dumps({'stage': text, 'raw_time': start}, ensure_ascii=False), flush=True)
            report['events'].append({'text': text, 'start': start})
            if action:
                action()
            end = max(start + hold, now() + 1.2)
            report['cues'].append({'start': start, 'end': min(end, start + 5.5), 'text': text})
            write_json(output / 'capture-status.json', report)
            time.sleep(max(0, end - now()))

        def click(xpath):
            window.move_to(xpath)
            client.click(xpath)

        def fill(xpath, value):
            window.move_to(xpath)
            client.fill(xpath, value)

        def visible_images():
            return client.execute('return [...document.images].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&r.top<innerHeight&&r.bottom>0}).every(e=>e.complete&&e.naturalWidth>0)')

        if args.probe:
            scene('录制工具检查：打开设置', lambda: click("//aside//button[@aria-label='设置']"), hold=3)
            scene('录制工具检查：返回论文库', lambda: click("//aside//button[@aria-label='论文库']"), hold=3)
        else:
            assert client.api('/papers?limit=10')['total'] == 0, 'Recording requires a fresh empty demo library'
            scene('PaperVault 0.2.2 · Windows 实际操作演示')
            scene('从本机导入一篇真实论文', lambda: click("//button[@aria-label='更多导入选项']"), 3)
            scene('选择 SimCSE 原始 PDF', lambda: fill("//*[@role='dialog']//input", str(sample)), 3)
            start_import = now()
            click("//*[@role='dialog']//button[normalize-space()='开始导入']")
            wait_until(lambda: client.api('/papers?limit=10')['total'] == 1, 'Real import did not create a paper')
            paper = client.api('/papers?limit=10')['items'][0]
            paper_id = paper['id']
            click("//aside//button[@aria-label='解析任务']")
            scene('模型在本机处理 PDF，任务页显示实际阶段', hold=5)
            cut_start = now()
            wait_until(lambda: client.api(f'/papers/{paper_id}')['status'] in ('completed', 'failed'), 'Real parsing timed out', timeout=600)
            assert client.api(f'/papers/{paper_id}')['status'] == 'completed'
            parse_finished = now()
            if parse_finished - cut_start > 6:
                report['cuts'].append({'start': cut_start, 'end': parse_finished, 'reason': 'Real parsing wait removed; explicitly disclosed on screen'})
            report['import_to_completion_seconds'] = round(parse_finished - start_import, 3)
            scene('本地解析完成；等待过程已剪辑', hold=4)
            resources = client.api(f'/resources?paper_id={paper_id}&limit=1000')['items']
            figure = next(r for r in resources if r['kind'] == 'figure' and r['number'] == 'G.1')
            table = next(r for r in resources if r['kind'] == 'table' and r['number'] == 'A.1')
            report['paper'] = client.api(f'/papers/{paper_id}')
            report['selected_resources'] = [figure, table]
            scene('论文与提取结果保存在当前论文库', lambda: click("//aside//button[@aria-label='论文库']"), 3)
            click(f"//button[@data-workspace-focus='paper:{paper_id}']")
            wait_until(lambda: client.execute('return [...document.querySelectorAll(".pdf-page canvas")].some(c=>c.width>0)'), 'Original PDF did not render', 45)
            scene('阅读原始 PDF，右侧查看论文信息', hold=5)
            click("//button[@aria-label='查找 PDF 文字']")
            scene('在 PDF 中查找 contrastive', lambda: fill("//input[@aria-label='查找 PDF 中的文字']", 'contrastive'), 5)
            wait_until(lambda: client.execute('return /\\d+\\s*\\/\\s*\\d+/.test(document.querySelector(".reader-find [role=status]")?.textContent||"")'), 'PDF find did not return matches', 45)
            scene('跳转到下一处匹配', lambda: click("//button[@aria-label='下一个匹配']"), 3)
            click("//button[@aria-label='关闭 PDF 查找']")
            scene('图片面板列出这篇论文的提取结果', lambda: click("//button[@role='tab' and starts-with(normalize-space(),'图片')]"), 3)
            click("//button[contains(@class,'detail-resource')][strong[normalize-space()='Figure G.1']]")
            wait_until(visible_images, 'Figure preview not ready')
            scene('Figure G.1：查看图片、图注和来源页码', hold=5)

            def locate(page):
                click("//*[@role='dialog']//button[normalize-space()='查看原文']")
                wait_until(lambda: client.execute(f'''const h=document.querySelector('.pdf-page[data-page="{page}"] .pdf-highlight');
if(!h)return false;const r=h.getBoundingClientRect(),v=document.querySelector('.pdf-scroll').getBoundingClientRect();return r.bottom>v.top&&r.top<v.bottom;'''), 'Source region not visibly highlighted', 45)

            scene('查看原文：定位到第 17 页的图像区域', lambda: locate(17), 5)
            click("//button[@role='tab' and starts-with(normalize-space(),'表格')]")
            click("//button[contains(@class,'detail-resource')][strong[normalize-space()='Table A.1']]")
            wait_until(lambda: client.execute('return Boolean(document.querySelector(".resource-preview table"))'), 'Table preview missing')
            scene('Table A.1：直接查看结构化表格', hold=5)
            scene('切换原始截图，对照表头和数值', lambda: click("//*[@role='dialog']//button[normalize-space()='原始截图']"), 4)
            scene('返回表格内容，选择需要的导出格式', lambda: click("//*[@role='dialog']//button[normalize-space()='表格内容']"), 4)

            def export_csv():
                click("//*[@role='dialog']//button[normalize-space()='CSV']")
                report['csv_export'] = window.save_dialog(fixture / '导出' / 'SimCSE_Table_A.1.csv')
                wait_until(lambda: client.execute('return document.body.innerText.includes("资源已导出")'), 'No actual export success notification')

            scene('导出 CSV；系统保存对话框已略去', export_csv, 5)
            scene('CSV 不保留合并单元格；可用原图核对', hold=4)
            scene('表格也能定位回第 13 页的原始区域', lambda: locate(13), 4)
            fill("//input[@aria-label='PDF 页码']", '2\ue007')
            scene('为当前页添加书签', lambda: click("//button[@aria-label='添加本页书签']"), 3)
            click("//button[@role='tab' and starts-with(normalize-space(),'笔记')]")
            click("//button[normalize-space()='全部笔记']")
            click("//*[contains(@class,'annotation-panel-toolbar')]//button[normalize-space()='笔记']")

            def edit_note():
                fill("//*[@role='dialog']//input[@aria-label='笔记标题']", 'SimCSE 阅读记录')
                fill("//*[@role='dialog']//textarea[@aria-label='笔记内容']", '对照 Table A.1，记录不同模型的 batch size 与 learning rate。')

            scene('添加阅读笔记，记录需要回看的内容', edit_note, 5)
            scene('保存笔记', lambda: click("//*[@role='dialog']//button[normalize-space()='保存笔记']"), 3)
            assert any(a['title'] == 'SimCSE 阅读记录' for a in client.api(f'/annotations?paper_id={paper_id}')['items'])
            click("//button[contains(@class,'sidebar-search')]")
            scene('全文搜索覆盖论文、图表、正文和笔记', lambda: fill("//input[@aria-label='全局全文搜索']", 'SimCSE'), 5)
            wait_until(lambda: client.execute('return document.querySelectorAll(".search-result").length>0'), 'Actual search has no results')
            scene('也可以用中文搜索刚保存的阅读记录', lambda: fill("//input[@aria-label='全局全文搜索']", '阅读记录'), 4)
            wait_until(lambda: client.execute('return document.querySelector(".search-result")?.innerText.includes("SimCSE 阅读记录")'), 'Saved note was not indexed')
            scene('从搜索结果打开对应论文和笔记', lambda: click("//button[contains(@class,'search-result')][contains(.,'SimCSE 阅读记录')]"), 4)
            scene('本片使用真实 PDF 与实际解析结果', hold=4)
            scene('演示论文：Gao / Yao / Chen · SimCSE\nACL Anthology · EMNLP 2021 · CC BY 4.0', hold=5)
        report['raw_duration_seconds'] = now()
        recorder.communicate(b'q\n', timeout=120)
        assert recorder.returncode == 0, 'Window capture failed'
        recorder = None
        video = cv2.VideoCapture(str(raw))
        report['raw_video_metadata'] = {'width': int(video.get(cv2.CAP_PROP_FRAME_WIDTH)),
                                        'height': int(video.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                                        'fps': video.get(cv2.CAP_PROP_FPS), 'frames': int(video.get(cv2.CAP_PROP_FRAME_COUNT))}
        ok, frame = video.read()
        assert ok and frame.std() > 8, 'Recorded frame is missing or blank'
        cv2.imwrite(str(output / 'capture-first-frame.png'), frame)
        if args.probe:
            video.set(cv2.CAP_PROP_POS_MSEC, 2500)
            changed, settings_frame = video.read()
            assert changed and abs(settings_frame.astype('float32') - frame.astype('float32')).mean() > 4, 'Capture did not reflect real UI changes'
            cv2.imwrite(str(output / 'capture-settings-frame.png'), settings_frame)
        video.release()
        cursor = 0
        report['clips'] = []
        for cut in report['cuts']:
            report['clips'].append({'start': cursor, 'end': cut['start']})
            cursor = cut['end']
        report['clips'].append({'start': cursor, 'end': report['raw_duration_seconds']})
        report['passed'] = True
        window.user.SetWindowTextW(window.hwnd, 'PaperVault')
        client.wm_close()
        client.assert_exit()
        print(json.dumps({'passed': True, 'timeline': str(output / 'timeline.json'), 'fixture': str(fixture)}, ensure_ascii=False), flush=True)
    except Exception:
        report['error'] = traceback.format_exc()
        if client:
            try:
                client.screenshot('capture-failure')
            except Exception:
                pass
        raise
    finally:
        if recorder and recorder.poll() is None:
            recorder.communicate(b'q\n', timeout=120)
        if log:
            log.close()
        if window:
            window.user.SetWindowTextW(window.hwnd, 'PaperVault')
        if client:
            client.close()
        write_json(output / 'timeline.json', report)


if __name__ == '__main__':
    main()
