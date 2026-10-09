"""Check actual fresh frozen outputs against the nine preregistered SimCSE labels."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--cases', type=Path, default=Path('artifacts/real-corpus-expanded/caption-number-cases-ml.json'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding='utf-8'))
    cases = json.loads(args.cases.read_text(encoding='utf-8'))
    result = {'passed': False, 'parser_report': str(args.report.resolve()), 'parser_report_sha256': digest(args.report),
              'cases': str(args.cases.resolve()), 'cases_sha256': digest(args.cases),
              'backend': report['backend'], 'backend_sha256': report['backend_sha256'], 'health': report['health'],
              'checks': [], 'scope': 'Nine explicitly captioned appendix labels only. Does not claim that missing captions, cropping or table structure are repaired.'}
    try:
        assert report['passed'] and report['health']['version'] == '0.2.2'
        paper = next(p for p in report['papers'] if p['source']['id'] == 'ml-simcse-emnlp2021')
        path = Path(paper['paper_json']).parent / 'resources-auto.json'
        resources = json.loads(path.read_text(encoding='utf-8'))
        result['resources_auto'] = str(path)
        result['resources_auto_sha256'] = digest(path)
        assert len(cases['cases']) == 9
        for case in cases['cases']:
            caption = ' '.join(case['caption'].split())
            matches = [r for r in resources if r['kind'] == case['kind'] and ' '.join(r.get('caption', '').split()) == caption]
            check = {'kind': case['kind'], 'expected_number': case['expected_number'], 'caption': case['caption'],
                     'matched_resource_ids': [r['id'] for r in matches], 'actual_numbers': [r.get('number') for r in matches],
                     'passed': len(matches) == 1 and matches[0]['number'] == case['expected_number']}
            result['checks'].append(check)
        assert all(check['passed'] for check in result['checks']), result['checks']
        empty = [r for r in resources if not (r.get('caption') or '').strip()]
        assert all(not r.get('number') for r in empty), 'Empty caption received an invented label'
        excluded = [r for r in empty if r['kind'] == 'figure' and any(location['page_index'] == 15 for location in r['locations'])]
        assert len(excluded) == 1, 'Expected the source FigureF.1 body with its still-missing caption on PDFpage16'
        assert not any(r.get('number') == 'F.1' for r in resources)
        result['excluded_figure_F1'] = {'resource_id': excluded[0]['id'], 'page_index': 15,
                                         'caption': excluded[0]['caption'], 'number': excluded[0]['number'],
                                         'correctly_not_invented': True, 'source_caption_still_missing': True}
        result['empty_caption_resources_checked'] = len(empty)
        result['passed'] = True
    except Exception as error:
        result['error'] = str(error)
        raise
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'passed': result['passed'], 'captioned_labels_checked': len(result['checks']), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
