"""Fill notice gaps from versioned official repositories and preserve MPL sources."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import tarfile
import tomllib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote

import httpx

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CATALOG = DOCS / "web-rust-dependencies.json"
SUPPLEMENTS = DOCS / "license-supplements.json"


def repository(value):
    value = value.get("url", "") if isinstance(value, dict) else value or ""
    return value.removeprefix("git+").replace("git://", "https://").removesuffix(".git").rstrip("/")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def client():
    return httpx.Client(follow_redirects=True, timeout=40, transport=httpx.HTTPTransport(retries=2),
                        headers={"User-Agent": "PaperVault-license-collection/0.1"})


def npm_info(name, version):
    with client() as session:
        response = session.get(f"https://registry.npmjs.org/{quote(name, safe='')}/{version}")
        response.raise_for_status()
        return response.json()


def find_license(session, repo, revision, names):
    if not repo.startswith("https://github.com/"):
        raise ValueError(f"Unsupported official repository {repo}")
    path = repo.removeprefix("https://github.com/")
    for name in names:
        url = f"https://raw.githubusercontent.com/{path}/{revision}/{name}"
        response = session.get(url)
        if response.status_code == 404:
            continue
        response.raise_for_status()
        data = response.content
        if len(data) > 100 and b"<html" not in data[:300].lower():
            return name.rsplit("/", 1)[-1], data, url
    raise FileNotFoundError(f"No license file at {repo}@{revision}: {names}")


def supplement(record, local_metadata):
    ecosystem, name, version = record["ecosystem"], record["name"], record["version"]
    meta, folder = local_metadata[(ecosystem, name, version)]
    repo = repository(meta.get("repository"))
    if ecosystem == "npm":
        published = npm_info(name, version)
        revision = published.get("gitHead")
        if not revision:
            # Binary platform packages share the corresponding parent release.
            parent = {"@napi-rs/canvas-win32-x64-msvc": "@napi-rs/canvas",
                      "@rolldown/binding-win32-x64-msvc": "rolldown",
                      "@tauri-apps/cli-win32-x64-msvc": "@tauri-apps/cli"}.get(name)
            if parent:
                revision = npm_info(parent, version).get("gitHead")
        if not revision:
            revision = f"v{version}"
        label = "npm-" + re.sub(r"[^a-zA-Z0-9_.-]", "_", name)
    else:
        vcs = json.loads((folder / ".cargo_vcs_info.json").read_text(encoding="utf-8"))
        revision = vcs["git"]["sha1"]
        label = f"rust-{name}-{version}"
    target = DOCS / "third-party-licenses" / label
    target.mkdir(parents=True, exist_ok=True)
    license_id = str(record["license"])
    sources, files = [], []
    with client() as session:
        if license_id == "MPL-2.0":
            candidates = [["LICENSE", "LICENSE.txt", "LICENSE-MPL-2.0"]]
        elif "MIT" in license_id and "Apache" in license_id:
            candidates = [["LICENSE_MIT", "LICENSE-MIT", "LICENSE-MIT.txt", "LICENSE-MIT.md"],
                          ["LICENSE_APACHE", "LICENSE-APACHE", "LICENSE-APACHE-2.0", "LICENSE_APACHE-2.0", "LICENSE-APACHE.txt", "LICENSE-APACHE.md"]]
        else:
            candidates = [["LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE", "LICENSE-MIT", "license.md", "LICENSE_1_0.txt", "COPYING"]]
        for names in candidates:
            try:
                filename, content, url = find_license(session, repo, revision, names)
            except FileNotFoundError:
                if name in {"react-remove-scroll-bar", "uri-js-replace"}:
                    # These npm gitHead revisions do not expose a license file.
                    # Preserve the publisher's current official LICENSE verbatim;
                    # URL and content hash make the provenance distinction clear.
                    filename, content, url = find_license(session, repo, "master", names)
                    destination = target / filename
                    destination.write_bytes(content)
                    relative = destination.relative_to(DOCS).as_posix()
                    files.append(relative)
                    sources.append({"file": relative, "url": url, "sha256": sha256(destination),
                                    "note": "Published npm gitHead did not expose LICENSE; official upstream master LICENSE preserved verbatim."})
                    continue
                if license_id == "MPL-2.0":
                    url = "https://www.mozilla.org/media/MPL/2.0/index.txt"
                elif license_id == "BSL-1.0":
                    url = "https://www.boost.org/LICENSE_1_0.txt"
                else:
                    raise
                response = session.get(url)
                response.raise_for_status()
                filename, content = "LICENSE.txt", response.content
            destination = target / filename
            destination.write_bytes(content)
            relative = destination.relative_to(DOCS).as_posix()
            files.append(relative)
            sources.append({"file": relative, "url": url, "sha256": sha256(destination)})
    return {"ecosystem": ecosystem, "name": name, "version": version,
            "repository": repo, "source_revision": revision, "license_files": files,
            "license_sources": sources}


def preserve_mpl_sources(records, local_metadata):
    output = DOCS / "third-party-sources"
    output.mkdir(parents=True, exist_ok=True)
    patches = []
    lock = tomllib.loads((ROOT / "apps/desktop/src-tauri/Cargo.lock").read_text(encoding="utf-8"))
    cargo_checksums = {(p["name"], p["version"]): p.get("checksum") for p in lock["package"]}
    npm_archives = {}
    for record in records:
        if record.get("license") != "MPL-2.0" or not (record.get("installed") or record.get("source_available")):
            continue
        ecosystem, name, version = record["ecosystem"], record["name"], record["version"]
        meta, folder = local_metadata[(ecosystem, name, version)]
        repo = repository(meta.get("repository"))
        if ecosystem == "cargo":
            archive = next(ROOT.glob(f".tools/cargo/registry/cache/*/{name}-{version}.crate"))
            digest = sha256(archive)
            if digest != cargo_checksums[(name, version)]:
                raise ValueError(f"Cargo archive checksum mismatch: {name} {version}")
            # Confirm no source modifications in the exact installed crate.
            with tarfile.open(archive, "r:gz") as source:
                for member in source.getmembers():
                    if not member.isfile():
                        continue
                    relative = Path(*Path(member.name).parts[1:])
                    installed = (folder / relative).resolve()
                    if not installed.is_relative_to(folder.resolve()):
                        raise ValueError("Unsafe source archive path")
                    if not installed.is_file() or installed.read_bytes() != source.extractfile(member).read():
                        raise ValueError(f"Installed crate was modified: {name}/{relative}")
            destination = output / archive.name
            shutil.copyfile(archive, destination)
            revision = json.loads((folder / ".cargo_vcs_info.json").read_text())["git"]["sha1"]
            url = f"https://static.crates.io/crates/{name}/{name}-{version}.crate"
        else:
            # The bindings and native binary come from the same published source release.
            key = (repo, version)
            if key not in npm_archives:
                published = npm_info("lightningcss", version)
                revision = published.get("gitHead") or f"v{version}"
                url = f"https://codeload.github.com/{repo.removeprefix('https://github.com/')}/tar.gz/{revision}"
                destination = output / f"lightningcss-{version}.tar.gz"
                if not destination.exists():
                    with client() as session:
                        response = session.get(url)
                        response.raise_for_status()
                        destination.write_bytes(response.content)
                # Ensure this is a source tarball, not an HTML error response.
                with tarfile.open(destination, "r:gz") as archive:
                    if not any(member.name.endswith("/Cargo.toml") for member in archive.getmembers()):
                        raise ValueError("Lightning CSS archive does not contain the upstream source")
                npm_archives[key] = (revision, url, destination)
            revision, url, destination = npm_archives[key]
        patches.append({"ecosystem": ecosystem, "name": name, "version": version,
                        "repository": repo, "source_revision": revision, "source_url": url,
                        "source_archive": destination.relative_to(DOCS).as_posix(),
                        "source_archive_sha256": sha256(destination), "modified": False,
                        "source_notice": "Upstream component used without PaperVault source modifications; original version source archive included."})
    return patches


def write_source_notice():
    patches = json.loads(SUPPLEMENTS.read_text(encoding="utf-8"))
    for patch in patches:
        if patch["name"] not in {"react-remove-scroll-bar", "uri-js-replace"}:
            continue
        name = patch["name"]
        original = ROOT / "apps/desktop/node_modules" / name / "package.json"
        metadata = json.loads(original.read_text(encoding="utf-8"))
        destination = DOCS / "third-party-licenses" / ("npm-" + name) / "PACKAGE-LICENSE-DECLARATION.json"
        shutil.copyfile(original, destination)
        relative = destination.relative_to(DOCS).as_posix()
        patch["license_files"] = sorted(set(patch["license_files"] + [relative]))
        patch["license_sources"] = [entry for entry in patch["license_sources"] if entry["file"] != relative]
        patch["license_sources"].append({"file": relative,
            "url": f"https://registry.npmjs.org/{name}/{patch['version']}",
            "sha256": sha256(destination), "note": "Installed official package.json copied verbatim; publication metadata at registry URL."})
        patch["published_license"] = metadata["license"]
        patch["declared_author"] = metadata.get("author")
        patch["license_source_revision"] = "official default branch; exact text identified by recorded SHA-256"
        if name == "uri-js-replace":
            patch["upstream_current_license_text"] = "MIT-0"
            patch["license_provenance_note"] = (
                "Version 1.0.1 package.json declares MIT. Its published gitHead has no LICENSE file. "
                "The official current LICENSE is titled MIT No Attribution (MIT-0), copyright 2025 andreinwald. "
                "Both declarations are preserved; the published license field has not been changed or conflated with MIT-0.")
        else:
            patch["license_provenance_note"] = (
                "Version 2.3.8 declares MIT and names Anton Korzunov. The published gitHead exposes no LICENSE; "
                "the author's official current MIT LICENSE, copyright 2025, is preserved verbatim with URL and digest.")
    SUPPLEMENTS.write_text(json.dumps(patches, ensure_ascii=False, indent=2), encoding="utf-8")
    mpl = [patch for patch in patches if "source_archive" in patch]
    lines = ["# MPL 组件源码与第三方许可来源", "",
             "PaperVault 未对下列组件的上游源码作修改。精确版本源码随安装包文档保存在 `third-party-sources/`；"
             "公开下载地址同时列于下表。源码沿用各自 MPL-2.0 许可，项目自身许可证不替代这些条款。", "",
             "Rust `.crate` 归档直接复制自本机官方 Cargo registry 缓存；SHA-256 与 Cargo.lock 校验和逐项一致，"
             "并已逐文件核对安装源码与归档内容相同。Lightning CSS 使用 npm 发布版本所记录的官方仓库修订；"
             "保存的是完整上游源码归档，未修改归档内容。", "",
             "| 组件 | 版本 | 随附源码 | 官方源码获取地址 |", "| --- | --- | --- | --- |"]
    for patch in mpl:
        lines.append(f"| {patch['name']} | {patch['version']} | [{Path(patch['source_archive']).name}]({patch['source_archive']}) "
                     f"| [官方版本源码]({patch['source_url']}) |")
    lines.extend(["", "所有源码归档的 SHA-256、版本修订号、许可证文本路径和来源 URL 均保存在 "
                  "`web-rust-dependencies.json` 与 `license-supplements.json`。未安装的其他平台 npm 可选包没有额外下载。", "",
                  "## 发布声明与官方当前许可证的差异", "",
                  "- `react-remove-scroll-bar@2.3.8` 的发布包声明 MIT、作者 Anton Korzunov；发布 gitHead 未提供 LICENSE。"
                  "本包同时附上原始 package.json 和官方当前仓库的 MIT 全文（2025 年版权声明），来源 URL 与文本哈希已记录。",
                  "- `uri-js-replace@1.0.1` 的原始 package.json 声明 MIT；发布 gitHead 未提供 LICENSE。官方当前全文标题为 "
                  "**MIT No Attribution（MIT-0）**、版权声明为 2025 andreinwald。两份原始声明均随附保存，"
                  "清单中的已发布 `license: MIT` 没有被改写，也没有把当前 MIT-0 文本冒充为该历史发布包的 MIT 原文。", ""])
    (DOCS / "MPL-SOURCE-NOTICE.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    records = json.loads(CATALOG.read_text(encoding="utf-8"))
    local_metadata = {}
    npm_lock = json.loads((ROOT / "apps/desktop/package-lock.json").read_text(encoding="utf-8"))
    for relative, value in npm_lock["packages"].items():
        folder = ROOT / "apps/desktop" / relative
        if relative and (folder / "package.json").is_file():
            meta = json.loads((folder / "package.json").read_text(encoding="utf-8"))
            local_metadata[("npm", meta["name"], value["version"])] = (meta, folder)
    for folder in ROOT.glob(".tools/cargo/registry/src/*/*"):
        if (folder / "Cargo.toml").is_file():
            meta = tomllib.loads((folder / "Cargo.toml").read_text(encoding="utf-8"))["package"]
            local_metadata[("cargo", meta["name"], meta["version"])] = (meta, folder)
    missing = [r for r in records if (r.get("installed") or r.get("source_available")) and not r["license_files"]]
    patches = json.loads(SUPPLEMENTS.read_text(encoding="utf-8")) if SUPPLEMENTS.exists() else []
    failures = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(supplement, r, local_metadata): r for r in missing}
        for future in as_completed(futures):
            record = futures[future]
            try:
                patches.append(future.result())
                print("NOTICE", record["name"], record["version"], flush=True)
            except Exception as exc:
                failures.append(f"{record['name']} {record['version']}: {exc}")
                print("ERROR", failures[-1], flush=True)
    SUPPLEMENTS.write_text(json.dumps(patches, ensure_ascii=False, indent=2), encoding="utf-8")
    patches.extend(preserve_mpl_sources(records, local_metadata))
    merged = {}
    for patch in patches:
        key = (patch["ecosystem"], patch["name"], patch["version"])
        merged.setdefault(key, {}).update(patch)
    SUPPLEMENTS.write_text(json.dumps(list(merged.values()), ensure_ascii=False, indent=2), encoding="utf-8")
    write_source_notice()
    from collect_web_rust_licenses import main as collect
    collect()
    print("Failures:", failures, flush=True)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
