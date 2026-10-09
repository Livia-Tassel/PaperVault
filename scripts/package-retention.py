"""Prepare and verify a real test library outside the NSIS installation directory."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import uuid

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / 'artifacts' / 'uninstall-retention.json'


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('prepare', 'verify'))
    parser.add_argument('--phase', default='after_uninstall')
    args = parser.parse_args()
    if args.action == 'prepare':
        sys.path.insert(0, str(ROOT / 'backend'))
        from papervault.library import Library
        directory = ROOT / '.test-data' / 'uninstall-retention' / str(uuid.uuid4())
        directory.mkdir(parents=True)
        original = directory / '原始文档.pdf'
        original.write_bytes((ROOT / 'tests/fixtures/academic.pdf').read_bytes())
        library = Library(directory / '研究资料库')
        try:
            paper, _ = library.import_file(original)
            expected = {'title': '卸载后保留的真实论文', 'notes': 'retain-metadata-after-uninstall', 'tags': ['保留测试']}
            library.update_paper(paper['id'], expected)
            managed = library.pdf(paper['id'])
            metadata = library.root / 'papers' / paper['id'] / 'metadata.json'
            database = library.db.path
        finally:
            library.close()
        files = {str(path): digest(path) for path in (original, managed, metadata, database)}
        report = {'passed': False, 'prepared': True, 'library': str(library.root), 'paper_id': paper['id'],
                  'database': str(database), 'expected_metadata': expected, 'sha256_before': files, 'verified_phases': []}
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Prepared a real independent library, original PDF, managed PDF, metadata JSON and SQLite database')
        return
    report = json.loads(REPORT.read_text(encoding='utf-8'))
    try:
        for name, expected in report['sha256_before'].items():
            path = Path(name).resolve()
            assert path.is_relative_to(ROOT / '.test-data' / 'uninstall-retention'), path
            assert path.is_file() and digest(path) == expected, f'File changed or missing: {path}'
        with sqlite3.connect(report['database']) as connection:
            assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            row = connection.execute('SELECT overrides_json FROM papers WHERE id=?', (report['paper_id'],)).fetchone()
            assert row
            metadata = json.loads(row[0])
            for key, expected in report['expected_metadata'].items():
                assert metadata[key] == expected, (key, metadata)
        report['verified_phases'].append(args.phase)
        report['passed'] = True
        print(f'PASS {args.phase}: original/managed PDF, metadata and database bytes retained; SQLite integrity and edits valid')
    except Exception as error:
        report['passed'] = False
        report['error'] = str(error)
        raise
    finally:
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()

