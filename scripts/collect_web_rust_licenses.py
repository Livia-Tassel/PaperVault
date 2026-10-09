"""Preserve license notices from the exact npm/Cargo lockfile dependency sets."""
from __future__ import annotations

import json
import re
import shutil
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "docs/third-party-licenses"


def copy_notices(folder: Path, label: str):
    files = []
    if not folder.is_dir():
        return files
    candidates = list(folder.glob("*"))
    for child in folder.iterdir():
        if child.is_dir() and child.name in ("licenses", "cmaps", "standard_fonts", "LICENSES"):
            candidates.extend(child.rglob("*"))
    for source in candidates:
        if not source.is_file() or not source.name.lower().startswith(("license", "licence", "copying", "notice", "copyright")):
            continue
        destination = OUTPUT / label / re.sub(r"[^a-zA-Z0-9_.-]", "_", source.relative_to(folder).as_posix())
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        files.append(destination.relative_to(ROOT / "docs").as_posix())
    return files


def main():
    records = []
    desktop = ROOT / "apps/desktop"
    lock = json.loads((desktop / "package-lock.json").read_text(encoding="utf-8"))
    for path, value in lock["packages"].items():
        if not path:
            continue
        folder = desktop / path
        metadata_file = folder / "package.json"
        metadata = json.loads(metadata_file.read_text(encoding="utf-8")) if metadata_file.is_file() else {}
        name = metadata.get("name", path.rsplit("node_modules/", 1)[-1])
        label = "npm-" + re.sub(r"[^a-zA-Z0-9_.-]", "_", name)
        records.append({"ecosystem": "npm", "name": name, "version": value.get("version"),
                        "license": metadata.get("license", value.get("license")), "installed": folder.exists(),
                        "license_files": copy_notices(folder, label)})
    cargo = tomllib.loads((desktop / "src-tauri/Cargo.lock").read_text(encoding="utf-8"))
    registries = list((ROOT / ".tools/cargo/registry/src").glob("*"))
    for package in cargo["package"]:
        if "source" not in package:
            continue
        name, version = package["name"], package["version"]
        folder = next((registry / f"{name}-{version}" for registry in registries
                       if (registry / f"{name}-{version}").is_dir()), None)
        metadata = tomllib.loads((folder / "Cargo.toml").read_text(encoding="utf-8"))["package"] if folder else {}
        files = copy_notices(folder, f"rust-{name}-{version}") if folder else []
        records.append({"ecosystem": "cargo", "name": name, "version": version,
                        "license": metadata.get("license"), "source_available": folder is not None,
                        "license_files": files})
    target = ROOT / "docs/web-rust-dependencies.json"
    supplements_path = ROOT / "docs/license-supplements.json"
    if supplements_path.is_file():
        supplements = {(item["ecosystem"], item["name"], item["version"]): item
                       for item in json.loads(supplements_path.read_text(encoding="utf-8"))}
        for record in records:
            supplemental = supplements.get((record["ecosystem"], record["name"], record["version"]))
            if supplemental:
                files = sorted(set(record["license_files"] + supplemental.get("license_files", [])))
                record.update(supplemental)
                record["license_files"] = files
                for relative in files:
                    if not (ROOT / "docs" / relative).is_file():
                        raise FileNotFoundError(f"Missing supplemental license: {relative}")
    target.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    for ecosystem in ("npm", "cargo"):
        group = [r for r in records if r["ecosystem"] == ecosystem]
        print(f"{ecosystem}: {len(group)} locked packages, {sum(bool(r['license_files']) for r in group)} with local license texts")


if __name__ == "__main__":
    main()
