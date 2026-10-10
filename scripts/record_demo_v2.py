"""Record a full-frame import-to-asset-retrieval story using the installed app."""
from __future__ import annotations

import ctypes
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import traceback
from urllib.parse import quote

from native_client import NativeClient, ROOT, wait_until
from record_demo import OwnedWindow, write_json
from test_real_corpus import FrozenBackend


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = ROOT / 'artifacts/demo-v2' / ('capture-' + stamp)
    fixture = ROOT / '.test-data/demo-v2' / stamp
    output.mkdir(parents=True)
    fixture.mkdir(parents=True)
    library = fixture / 'PaperVault 演示库'
    prep_path = ROOT / 'artifacts/demo-library/preparation.json'
    prepared = json.loads(prep_path.read_text(encoding='utf-8'))
    assert prepared['passed'] and prepared['shutdown']['backend_port_closed']
    original_library = Path(prepared['library_path']).resolve()
    assert original_library.is_relative_to(ROOT / '.test-data/demo-library')
    source = json.loads((ROOT / 'tests/corpus/sources-control.json').read_text(encoding='utf-8'))['papers'][0]
    assert source['id'] == 'docling-v5'
    source_pdf = ROOT / source['local_path']
    assert digest(source_pdf) == source['sha256']
    sample = fixture / 'Docling Technical Report.pdf'
    shutil.copyfile(source_pdf, sample)
    app = ROOT / '.test-data/installed/PaperVault/papervault.exe'
    backend = app.parent / 'papervault-backend.exe'
    release = json.loads((ROOT / 'docs/verification/0.2.2/release-manifest.json').read_text(encoding='utf-8'))
    assert digest(backend) == release['backend_sha256'].lower()
    report = {'passed': False, 'title': 'PaperVault：找回读过的论文图表', 'fixture': str(fixture),
              'library': str(library), 'preparation': str(prep_path), 'preparation_sha256': digest(prep_path),
              'new_source': source, 'new_source_copy': str(sample), 'backend_sha256': digest(backend),
              'raw_video': str(output / 'capture.mp4'), 'output_directory': str(ROOT / 'artifacts/demo-v2/main'),
              'cues': [], 'cuts': [], 'events': [], 'parse_progress': [],
              'scope': 'Full 1920x1080 actual installed WebView; independent eight-paper backup copy plus one genuinely imported and parsed new paper.'}
    client = window = recorder = log = None
    try:
        with FrozenBackend(backend, fixture / 'copy-backend', ROOT / '.cache/models', 'copy', '0.2.2') as copier:
            original = copier.call('POST', '/library/open', json={'path': str(original_library)}).json()
            copier.scope(original)
            assert original['paper_count'] == 8
            archive = copier.call('POST', '/backups', json={'destination': str(fixture / 'eight-paper-backup.zip')}).json()['path']
            copier.call('POST', '/backups/restore', json={'path': archive, 'destination': str(library)})
            assert Path(copier.call('GET', '/library').json()['path']).resolve() == library
        assert copier.shutdown['backend_port_closed'] and not copier.forced_termination
        report['copy_shutdown'] = copier.shutdown
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        client = NativeClient(app, fixture, library, output, models=ROOT / '.cache/models').start()
        report['desktop_version'] = client.execute("return window.__TAURI_INTERNALS__.invoke('plugin:app|version')")
        assert report['desktop_version'] == '0.2.2' and client.api('/models')['ready']
        assert client.api('/library')['paper_count'] == 8
        wait_until(lambda: client.execute('return !!document.querySelector(".workspace-bar")'), 'Library did not open')
        client.click("//aside//button[@aria-label='设置']")
        client.click("//button[normalize-space()='深色']")
        client.click("//aside//button[@aria-label='论文库']")
        window = OwnedWindow(client)
        report['viewport'] = window.prepare(width=1920, height=1080)
        assert round(report['viewport']['width'] * report['viewport']['dpr']) == 1920
        assert round(report['viewport']['height'] * report['viewport']['dpr']) == 1080
        client.screenshot('full-frame-before-recording')
        log = (output / 'webview-capture.log').open('w', encoding='utf-8')
        recorder = subprocess.Popen(['node', str(ROOT / 'scripts/capture_webview.mjs'), '--debugger-address',
                                     client.capabilities['ms:edgeOptions']['debuggerAddress'], '--output-dir', str(output), '--height', '1080',
                                     '--ffmpeg', str(ROOT / '.tools/video-python/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe')],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        ready = json.loads(recorder.stdout.readline())
        assert ready['type'] == 'ready'
        origin = time.monotonic() - (time.time() - ready['epoch_ms'] / 1000)

        def now():
            return round(time.monotonic() - origin, 3)

        def click(xpath):
            window.move_to(xpath)
            client.click(xpath)

        def fill(xpath, text):
            window.move_to(xpath)
            client.fill(xpath, text)

        def scene(text, action=None, hold=4, position='bottom'):
            start = now()
            print(json.dumps({'stage': text, 'raw_time': start}, ensure_ascii=False), flush=True)
            if action:
                action()
            end = max(start + hold, now() + 1.2)
            report['events'].append({'text': text, 'start': start, 'end': end})
            report['cues'].append({'text': text, 'start': start, 'end': min(end, start + 5.5), 'position': position})
            write_json(output / 'capture-status.json', report)
            time.sleep(max(0, end - now()))

        def gallery_ready(expected):
            wait_until(lambda: client.execute(f'return document.querySelectorAll(".resource-card").length==={min(expected, 24)}'), 'Gallery results not ready')
            wait_until(lambda: client.execute('return [...document.images].filter(e=>{const r=e.getBoundingClientRect();return r.width&&r.height&&r.top<innerHeight&&r.bottom>0}).every(e=>e.complete&&e.naturalWidth>0)'), 'Visible gallery thumbnails not ready')

        def locate(resource):
            click("//*[@role='dialog']//button[normalize-space()='查看原文']")
            page = resource['locations'][0]['page_index'] + 1
            wait_until(lambda: client.execute(f'''const p=document.querySelector('.pdf-page[data-page="{page}"]');
const h=p?.querySelector('.pdf-highlight');if(!h||!p?.querySelector('canvas')?.width||p.dataset.textReady!=='true')return false;
const r=h.getBoundingClientRect(),v=document.querySelector('.pdf-scroll').getBoundingClientRect();return r.bottom>v.top&&r.top<v.bottom;'''), 'Original PDF region not rendered', timeout=45)

        scene('先把一篇新论文导入 PaperVault', lambda: click("//button[@aria-label='更多导入选项']"), 3)
        scene('选择本机 PDF，加入现有论文库', lambda: fill("//*[@role='dialog']//input", str(sample)), 3)
        import_start = now()
        before_ids = {p['id'] for p in client.api('/papers?limit=100')['items']}
        click("//*[@role='dialog']//button[normalize-space()='开始导入']")
        wait_until(lambda: client.api('/papers?limit=100')['total'] == 9, 'New paper was not imported')
        new_paper = next(p for p in client.api('/papers?limit=100')['items'] if p['id'] not in before_ids)
        new_id = new_paper['id']
        click("//aside//button[@aria-label='解析任务']")
        scene('在本机解析正文、图片和表格', hold=5)
        cut_start = now()
        deadline = time.monotonic() + 600
        previous = None
        while time.monotonic() < deadline:
            job = next(j for j in client.api('/jobs')['items'] if j['paper_id'] == new_id)
            state = {k: job.get(k) for k in ('status', 'phase', 'pages_done', 'pages_total', 'resources_count')}
            if state != previous:
                report['parse_progress'].append({'raw_time': now(), **state})
                previous = state
            if job['status'] in ('completed', 'failed', 'cancelled', 'interrupted'):
                assert job['status'] == 'completed', job
                break
            time.sleep(.4)
        else:
            raise TimeoutError('Real parse did not complete')
        wait_until(lambda: client.execute('return [...document.querySelectorAll(".job-card")].some(e=>e.innerText.includes("Docling Technical Report")&&e.innerText.includes("已完成"))'), 'Task UI did not display actual completion')
        finished = now()
        if finished - cut_start > 5:
            report['cuts'].append({'start': cut_start, 'end': finished, 'reason': 'Actual parser wait removed, explicitly disclosed in subtitle'})
        report['new_parse_seconds'] = round(finished - import_start, 3)
        report['new_paper'] = client.api('/papers/' + new_id)
        report['new_resources'] = client.api('/resources?paper_id=' + new_id + '&limit=1000')['items']
        assert digest(library / 'papers' / new_id / 'original.pdf') == source['sha256']
        scene('解析完成，图表已入库；等待过程已剪辑', hold=3)
        click("//aside//button[@aria-label='论文库']")
        click(f"//button[@data-workspace-focus='paper:{new_id}']")
        wait_until(lambda: client.execute("""return document.querySelector('.pdf-page[data-page="1"]')?.dataset.textReady === 'true'"""), 'New PDF did not render', timeout=45)
        scene('新论文和已有文献，共用同一个索引', lambda: click("//button[@role='tab' and starts-with(normalize-space(),'图片')]"), 4)
        scene('现在，试着找回一张只记得关键词的图表', hold=3)

        click("//aside//button[@aria-label='表格库']")
        tables = client.api('/resources?kind=table&q=GLUE&limit=1000')
        assert len({r['paper_id'] for r in tables['items']}) >= 2

        def find_tables():
            fill("//input[@aria-label='搜索表格']", 'GLUE')
            gallery_ready(tables['total'])

        scene('只记得 GLUE？在全库表格里直接搜索', find_tables, 5)
        report['table_search'] = {'query': 'GLUE', 'results': tables}
        scene('不同论文里的相关表格，一次找齐', hold=4)
        original_ids = {p['source_id']: p['paper_id'] for p in prepared['papers']}
        table = next((r for r in tables['items'] if r['paper_id'] == original_ids['ml-bart-acl2020']), tables['items'][0])
        scene('打开表格，核对内容和来源论文', lambda: click(f"//button[@data-workspace-focus='resource:{table['id']}']"), 4)
        wait_until(lambda: client.execute('return !!document.querySelector(".resource-preview table")'), 'Table details are not visible')
        scene('一键回到原文，确认表头、数值和上下文', lambda: locate(table), 5)
        client.screenshot('retrieved-table-original')

        click("//aside//button[@aria-label='图片库']")
        figures = client.api('/resources?kind=figure&q=BERT&limit=1000')
        assert len({r['paper_id'] for r in figures['items']}) >= 2

        def find_figures():
            fill("//input[@aria-label='搜索图片']", 'BERT')
            gallery_ready(figures['total'])

        scene('找图片也一样：输入关键词 BERT', find_figures, 5)
        scene('跨论文浏览图片，每张图都保留出处', hold=4)
        figure = next(r for r in figures['items'] if r['paper_id'] == original_ids['bert-naacl2019'] and r.get('caption') and r.get('locations'))
        scene('打开需要的图，不必再凭记忆翻文件', lambda: click(f"//button[@data-workspace-focus='resource:{figure['id']}']"), 4)
        wait_until(lambda: client.execute('return [...document.querySelectorAll(".resource-preview img")].some(e=>e.complete&&e.naturalWidth>0)'), 'Figure preview did not load')

        def copy_figure():
            click("//*[@role='dialog']//button[normalize-space()='复制图片']")
            wait_until(lambda: client.execute('return document.body.innerText.includes("已复制到剪贴板")'), 'Actual image clipboard copy did not succeed')

        scene('复制图片，就能粘贴进组会 PPT 或文稿', copy_figure, 4, position='top')
        report['copy_image_success'] = True
        scene('需要确认细节？直接定位原始页面', lambda: locate(figure), 5)
        report['figure_search'] = {'query': 'BERT', 'results': figures}
        report['selected_resources'] = {'table': table, 'figure': figure}
        client.screenshot('retrieved-figure-original')
        click("//button[contains(@class,'sidebar-search')]")
        scene('论文、图表和正文，也能在这里统一检索', lambda: fill("//input[@aria-label='全局全文搜索']", 'BERT'), 5)
        report['unified_search'] = client.api('/search?q=' + quote('BERT'))
        assert len({h['paper_id'] for h in report['unified_search']['content']}) >= 2
        scene('记住线索就够了，把找图表的时间省下来', hold=4)
        scene('演示使用 9 篇公开论文\n作者、原始来源与开放许可见随附说明', hold=4)
        report['library_counts'] = client.api('/library')
        report['raw_duration_seconds'] = now()
        cursor = 0
        report['clips'] = []
        for cut in report['cuts']:
            report['clips'].append({'start': cursor, 'end': cut['start']})
            cursor = cut['end']
        report['clips'].append({'start': cursor, 'end': report['raw_duration_seconds']})
        recorder.communicate(b'q\n', timeout=180)
        assert recorder.returncode == 0, 'Native screen capture failed'
        recorder = None
        transport = json.loads((output / 'capture-webview-report.json').read_text(encoding='utf-8'))
        assert transport['source_dimensions'] == {'width': 1920, 'height': 1080}
        assert transport['output_dimensions'] == {'width': 1920, 'height': 1080}
        window.user.SetWindowTextW(window.hwnd, 'PaperVault')
        client.wm_close()
        client.assert_exit()
        report['passed'] = True
        print(json.dumps({'passed': True, 'timeline': str(output / 'timeline.json')}, ensure_ascii=False), flush=True)
    except Exception:
        report['error'] = traceback.format_exc()
        if client:
            try:
                client.screenshot('failure')
            except Exception:
                pass
        raise
    finally:
        if recorder and recorder.poll() is None:
            recorder.communicate(b'q\n', timeout=180)
        if log:
            log.close()
        if window:
            window.user.SetWindowTextW(window.hwnd, 'PaperVault')
        if client:
            client.close()
        write_json(output / 'timeline.json', report)


if __name__ == '__main__':
    main()
