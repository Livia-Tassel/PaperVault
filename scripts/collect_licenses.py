"""Generate a versioned inventory and preserve dependency-provided license texts."""
from __future__ import annotations

import importlib.metadata
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    output = ROOT / "docs/third-party-licenses"
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for distribution in sorted(importlib.metadata.distributions(), key=lambda d: d.metadata.get("Name", "").casefold()):
        name = distribution.metadata.get("Name", "unknown")
        if name.casefold() == "papervault":
            continue
        folder = output / re.sub(r"[^a-zA-Z0-9_.-]", "_", name)
        files = []
        for relative in distribution.files or []:
            label = str(relative).replace("\\", "/")
            filename = Path(label).name.casefold()
            if not (filename.startswith(("license", "copying", "notice", "copyright")) or "/licenses/" in label):
                continue
            source = Path(distribution.locate_file(relative))
            if not source.is_file() or source.stat().st_size > 3*1024*1024:
                continue
            folder.mkdir(exist_ok=True)
            target = folder / re.sub(r"[^a-zA-Z0-9_.-]", "_", label)
            shutil.copyfile(source, target)
            files.append(target.relative_to(ROOT / "docs").as_posix())
        records.append({"name": name, "version": distribution.version,
                        "license": distribution.metadata.get("License-Expression") or distribution.metadata.get("License") or
                        [x for x in distribution.metadata.get_all("Classifier", []) if x.startswith("License ::")],
                        "license_files": files})
    (ROOT / "docs/python-dependencies.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Recorded {len(records)} Python distributions and preserved supplied license texts")


if __name__ == "__main__":
    main()
