"""Fetch pinned, openly licensed publisher PDFs without overwriting existing files."""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import httpx
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent


def validate(path, source):
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != source["sha256"]:
        raise ValueError(f"{source['id']}: SHA256 differs; do not silently change the pinned paper version")
    if len(PdfReader(path).pages) != source["pages"]:
        raise ValueError(f"{source['id']}: page count differs from the source manifest")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="Verify local bytes only; make no network requests")
    parser.add_argument("--manifest", action="append", help="Specific manifest path or glob; repeatable. Defaults to all corpus manifests recursively.")
    args = parser.parse_args()
    sources = []
    manifests = sorted({Path(path) for pattern in args.manifest for path in glob.glob(pattern)}) if args.manifest else sorted((ROOT / "tests/corpus").rglob("sources-*.json"))
    if not manifests:
        raise ValueError("No source manifests matched")
    for manifest in manifests:
        sources.extend(json.loads(manifest.read_text(encoding="utf-8"))["papers"])
    if not sources:
        raise ValueError("No pinned corpus source manifests")
    external_root = (ROOT / ".test-data/external").resolve()
    if not external_root.is_relative_to(ROOT.resolve()):
        raise ValueError("External test directory resolves outside the project")
    with httpx.Client(follow_redirects=True, timeout=120, headers={"User-Agent": "PaperVault-corpus-verification/0.2.1"}) as client:
        for source in sources:
            target = (ROOT / source["local_path"]).resolve()
            if not target.is_relative_to(external_root):
                raise ValueError("Corpus download destination is outside the isolated external test directory")
            if target.exists():
                validate(target, source)
                print(f"Verified existing {source['id']}: {source['pages']} pages")
                continue
            if args.verify_only:
                raise FileNotFoundError(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + "." + uuid4().hex + ".part")
            try:
                with client.stream("GET", source["pdf_url"]) as response:
                    response.raise_for_status()
                    with temporary.open("xb") as stream:
                        total = 0
                        for chunk in response.iter_bytes(1024 * 1024):
                            total += len(chunk)
                            if total > 100 * 1024 * 1024:
                                raise ValueError("Unexpected download above 100 MiB; stop before accepting a changed resource")
                            stream.write(chunk)
                validate(temporary, source)
                temporary.rename(target)
                print(f"Downloaded and verified {source['id']}: {source['pages']} pages")
            finally:
                temporary.unlink(missing_ok=True)
    print(f"Verified {len(sources)} pinned external papers")


if __name__ == "__main__":
    main()
