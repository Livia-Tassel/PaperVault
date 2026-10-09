"""Record a populated real-paper library and cross-paper searches in installed UI."""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
import traceback
from urllib.parse import quote

from native_client import NativeClient, ROOT, wait_until
from record_demo import OwnedWindow, write_json


def literal(value):
    assert "'" not in value
    return "'" + value + "'"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation', type=Path, default=ROOT / 'artifacts/demo-library/preparation.json')
    args = parser.parse_args()
    prepared = json.loads(args.preparation.read_text(encoding='utf-8'))
    assert prepared['passed'] and prepared['shutdown']['backend_port_closed']
    library = Path(prepared['library_path']).resolve()
    assert library.is_relative_to(ROOT / '.test-data/demo-library')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = ROOT / 'artifacts/demo-library' / ('capture-' + stamp)
    fixture = ROOT / '.test-data/demo-library' / ('ui-' + stamp)
    output.mkdir(parents=True)
    fixture.mkdir(parents=True)
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    report = {'passed': False, 'title': 'PaperVault 多论文资料库与联合搜索',
              'preparation': str(args.preparation.resolve()),
              'preparation_sha256': hashlib.sha256(args.preparation.read_bytes()).hexdigest(),
              'library': str(library), 'fixture': str(fixture),
              'raw_video': str(output / 'capture.mp4'),
              'output_directory': str(ROOT / 'artifacts/demo-library/main'), 'cues': [], 'events': [],
              'scope': 'Real installed UI with eight pre-parsed publisher PDFs. Tags are added visibly through the UI; no invented paper content.'}
    client = window = recorder = log = None
    try:
        app = ROOT / '.test-data/installed/PaperVault/papervault.exe'
        client = NativeClient(app, fixture, library, output, models=ROOT / '.cache/models').start()
        report['desktop_version'] = client.execute("return window.__TAURI_INTERNALS__.invoke('plugin:app|version')")
        assert report['desktop_version'] == '0.2.2'
        info = client.api('/library')
        assert Path(info['path']).resolve() == library and info['paper_count'] == 8
        papers = client.api('/papers?limit=100')['items']
        assert len(papers) == 8 and all(p['status'] == 'completed' for p in papers)
        paper_map = {p['id']: p for p in papers}
        source_map = {p['source_id']: p['paper_id'] for p in prepared['papers']}
        report['library_counts'] = info
        report['papers'] = papers
        client.click("//aside//button[@aria-label='设置']")
        client.click("//button[normalize-space()='深色']")
        client.click("//aside//button[@aria-label='论文库']")
        client.click("//button[@aria-label='列表视图']")
        wait_until(lambda: client.execute('return document.querySelectorAll(".paper-item").length===8'), 'Eight real papers are not visible')
        window = OwnedWindow(client)
        report['viewport'] = window.prepare()
        client.screenshot('populated-library-before-recording')
        log = (output / 'webview-capture.log').open('w', encoding='utf-8')
        recorder = subprocess.Popen(['node', str(ROOT / 'scripts/capture_webview.mjs'), '--debugger-address',
                                     client.capabilities['ms:edgeOptions']['debuggerAddress'], '--output-dir', str(output),
                                     '--ffmpeg', str(ROOT / '.tools/video-python/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe')],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        ready = json.loads(recorder.stdout.readline())
        assert ready['type'] == 'ready'
        started = time.monotonic() - (time.time() - ready['epoch_ms'] / 1000)

        def now():
            return round(time.monotonic() - started, 3)

        def click(xpath):
            window.move_to(xpath)
            client.click(xpath)

        def fill(xpath, text):
            window.move_to(xpath)
            client.fill(xpath, text)

        def scene(text, action=None, hold=4):
            start = now()
            print(json.dumps({'stage': text, 'raw_time': start}, ensure_ascii=False), flush=True)
            if action:
                action()
            end = max(start + hold, now() + 1.3)
            report['events'].append({'text': text, 'start': start, 'end': end})
            report['cues'].append({'text': text, 'start': start, 'end': min(start + 5.5, end)})
            write_json(output / 'capture-status.json', report)
            time.sleep(max(0, end - now()))

        def scroll(y):
            client.execute(f'document.querySelector(".page-content").scrollTo({{top:{y},behavior:"smooth"}})')

        def images_ready():
            return client.execute('return [...document.images].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&r.top<innerHeight&&r.bottom>0}).every(e=>e.complete&&e.naturalWidth>0)')

        def group(name):
            click(f"//*[contains(@class,'search-tabs')]//button[starts-with(normalize-space(),{literal(name)})]")

        def show_region(location):
            page = location['page_index'] + 1
            wait_until(lambda: client.execute(f'''const p=document.querySelector('.pdf-page[data-page="{page}"]');
const h=p?.querySelector('.pdf-highlight');if(!h||!p?.querySelector('canvas')?.width||p.dataset.textReady!=='true')return false;
const r=h.getBoundingClientRect(),v=document.querySelector('.pdf-scroll').getBoundingClientRect();return r.bottom>v.top&&r.top<v.bottom;'''), 'Actual source region did not render visibly', timeout=45)

        scene('8 篇真实论文，组成同一个本地论文库', hold=5)
        scene('这些论文已提前完成真实的本地解析', hold=4)
        scene('切换卡片视图，浏览标题和摘要', lambda: click("//button[@aria-label='卡片视图']"), 5)
        scene('BERT、BART、SciBERT、SimCSE 等论文集中管理', lambda: scroll(480), 5)
        scroll(0)
        click("//button[@aria-label='列表视图']")
        tagged_ids = [source_map[key] for key in ('diverse-macbert', 'diverse-chinesebert', 'ml-mt5-naacl2021')]

        def select_papers():
            for paper_id in tagged_ids:
                click(f"//article[contains(@class,'paper-item')][.//button[@data-workspace-focus='paper:{paper_id}']]//button[@role='checkbox']")
                time.sleep(.4)

        scene('选择三篇论文，一次添加同一个标签', select_papers, 5)
        click("//*[contains(@class,'selection-bar')]//button[normalize-space()='添加标签']")
        scene('用标签整理一组预训练相关论文', lambda: fill("//*[@role='dialog']//input", '预训练'), 4)
        click("//*[@role='dialog']//button[normalize-space()='保存']")
        wait_until(lambda: all('预训练' in client.api(f'/papers/{p}')['tags'] for p in tagged_ids), 'Bulk tags did not persist')
        scene('按标签筛选，快速缩小阅读范围', lambda: fill("//input[@aria-label='按标签筛选']", '预训练'), 5)
        wait_until(lambda: client.execute('return document.querySelectorAll(".paper-item").length===3'), 'Tag filter did not show three papers')
        report['tagged_paper_ids'] = tagged_ids
        fill("//input[@aria-label='按标签筛选']", '')
        click("//button[contains(@class,'sidebar-search')]")
        query = 'BERT'
        scene('输入 BERT，在整个论文库中联合检索', lambda: fill("//input[@aria-label='全局全文搜索']", query), 5)
        wait_until(lambda: client.execute('return document.querySelectorAll(".search-result").length>0'), 'Cross-paper search did not return results')
        results = client.api('/search?q=' + quote(query))
        group_sources = {kind: sorted({hit['paper_id'] for hit in hits}) for kind, hits in results.items()}
        assert len(group_sources['papers']) >= 2 and len(group_sources['tables']) >= 2 and len(group_sources['content']) >= 2
        report['cross_paper_search'] = {'query': query, 'results': results, 'group_source_paper_ids': group_sources,
                                       'per_group_return_limit': 25, 'counts_are_returned_hits_not_exhaustive_totals': True}
        scene('论文类结果同时命中多篇论文', lambda: group('论文'), 5)
        scene('同一关键词，无需逐篇打开查找', lambda: scroll(350), 4)
        scene('切到表格类结果，寻找相关实验数据', lambda: group('表格'), 5)
        preferred = source_map['ml-scibert-emnlp2019']
        table_hit = next((h for h in results['tables'] if h['paper_id'] == preferred and (h.get('location') or {}).get('bbox')), None)
        if table_hit is None:
            table_hit = next(h for h in results['tables'] if h.get('location') and h['location'].get('bbox'))
        table = client.api('/resources/' + table_hit['id'])
        table_paper = paper_map[table_hit['paper_id']]
        scene('打开一条命中，确认表格内容与所属论文',
              lambda: click(f"//button[@data-workspace-focus='search:tables:{table_hit['id']}']"), 5)
        wait_until(lambda: client.execute('return Boolean(document.querySelector(".resource-preview table"))'), 'Matched table has no structured preview')
        assert client.execute('return document.querySelector(".source-paper").innerText') == table_paper['title']

        def locate_table():
            click("//*[@role='dialog']//button[normalize-space()='查看原文']")
            show_region(table['locations'][0])

        scene('查看原文，直接定位到这篇论文的表格区域', locate_table, 6)
        client.screenshot('table-search-to-original')
        click("//button[contains(@class,'sidebar-search')]")
        scene('保持同一关键词，再查看正文类命中', lambda: group('正文'), 5)
        candidates = [h for h in results['content'] if h['paper_id'] != table_hit['paper_id'] and h.get('location') and h['location'].get('bbox')]
        assert candidates, 'A second paper needs a real located content hit'
        preferred_content = source_map['ml-bart-acl2020']
        content_hit = next((h for h in candidates if h['paper_id'] == preferred_content), candidates[0])
        content_paper = paper_map[content_hit['paper_id']]

        def open_content():
            click(f"//button[@data-workspace-focus='search:content:{content_hit['id']}']")
            show_region(content_hit['location'])

        scene('这条正文结果来自另一篇论文', open_content, 6)
        client.screenshot('different-paper-content-to-original')
        report['selected_hits'] = {'table': {'hit': table_hit, 'paper_title': table_paper['title'], 'resource': table},
                                   'content': {'hit': content_hit, 'paper_title': content_paper['title']}}
        tabs = client.execute('return [...document.querySelectorAll(".workspace-tab [role=tab]")].map(e=>e.title)')
        assert table_paper['title'] in tabs and content_paper['title'] in tabs and table_hit['paper_id'] != content_hit['paper_id']
        scene('两篇论文保留在阅读标签页中，随时切换对照',
              lambda: click(f"//*[contains(@class,'workspace-tab')]//button[@role='tab' and @title={literal(table_paper['title'])}]"), 5)
        scene('切回另一篇论文，继续刚才的阅读位置',
              lambda: click(f"//*[contains(@class,'workspace-tab')]//button[@role='tab' and @title={literal(content_paper['title'])}]"), 5)
        report['open_paper_tabs'] = tabs
        scene('全库图片集中浏览，每张图保留论文来源', lambda: click("//aside//button[@aria-label='图片库']"), 5)
        wait_until(images_ready, 'Gallery images did not load')
        scene('按关键词筛选多篇论文中的图片', lambda: fill("//input[@aria-label='搜索图片']", 'BERT'), 5)
        image_results = client.api('/resources?kind=figure&q=BERT&limit=1000')
        assert len({r['paper_id'] for r in image_results['items']}) >= 2
        report['gallery_figures'] = {'query': 'BERT', 'resources': image_results}
        wait_until(images_ready, 'Filtered figure images did not load')
        scene('浏览结果时，可以直接辨认每张图的出处', lambda: scroll(350), 4)
        click("//aside//button[@aria-label='表格库']")
        gallery_query = next(q for q in ('GLUE', 'BERT') if len({r['paper_id'] for r in client.api('/resources?kind=table&q=' + q + '&limit=1000')['items']}) >= 2)
        scene(f'在全库表格中搜索 {gallery_query}，汇集不同论文的结果', lambda: fill("//input[@aria-label='搜索表格']", gallery_query), 5)
        wait_until(images_ready, 'Table gallery did not settle')
        table_results = client.api('/resources?kind=table&q=' + gallery_query + '&limit=1000')
        report['gallery_tables'] = {'query': gallery_query, 'resources': table_results}
        scene('切换列表，查看图注、来源论文和页码', lambda: click("//button[@aria-label='列表视图']"), 5)
        scene('回到论文库，继续管理和阅读这组文献', lambda: click("//aside//button[@aria-label='论文库']"), 4)
        scene('8 篇公开论文 · 真实本地解析与跨论文关键词检索', hold=4)
        scene('素材来自 ACL Anthology · CC BY 4.0\n完整作者、来源与许可见随附说明', hold=5)
        report['raw_duration_seconds'] = now()
        report['clips'] = [{'start': 0, 'end': report['raw_duration_seconds']}]
        recorder.communicate(b'q\n', timeout=180)
        assert recorder.returncode == 0, 'Actual WebView recording failed'
        recorder = None
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
