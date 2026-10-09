from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path

from .files import safe_path, sha256, uid
from .annotation_export import annotation_markdown


def export_assets(library, paper_ids, resource_ids, format_name="zip", dpi=300):
    if format_name not in ("zip", "png", "csv", "html"):
        raise ValueError("不支持的导出格式")
    if not paper_ids and not resource_ids:
        raise ValueError("请选择要导出的论文或资源")
    if len(paper_ids) + len(resource_ids) > 10000:
        raise ValueError("单次导出数量超过上限")
    with library.mutex:
        if not paper_ids and len(resource_ids) == 1 and format_name != "zip":
            return library.resource_file(resource_ids[0], format_name, dpi if format_name == "png" else None)
        target = library.root / "exports" / f"papervault-{uid()}.zip"
        checksums = {}
        exported_resources = {}
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            def add_file(source: Path, name: str):
                archive.write(source, name)
                checksums[name] = sha256(source)

            def add_json(value, name):
                add_text(json.dumps(value, ensure_ascii=False, indent=2), name)

            def add_text(value, name):
                raw = value.encode("utf-8")
                archive.writestr(name, raw)
                checksums[name] = hashlib.sha256(raw).hexdigest()

            resources = {resource_id: library.resource(resource_id) for resource_id in resource_ids}
            for paper_id in dict.fromkeys(paper_ids):
                resources.update({r["id"]: r for r in library.resources(paper_id=paper_id, limit=100000)["items"]})
            for resource in resources.values():
                prefix = f"papers/{resource['paper_id']}/resources/{resource['id']}"
                exported = {**resource, "files": {}}
                formats = list(resource["files"]) if format_name == "zip" or paper_ids else [format_name]
                for extension in formats:
                    if extension not in ("png", "thumbnail", "csv", "html", "original") and not re.fullmatch(r"segment_\d+", extension):
                        continue
                    path = library.resource_file(resource["id"], extension, dpi if extension == "png" else None)
                    filename = {"png": "image.png", "thumbnail": "thumbnail" + path.suffix,
                                "csv": "table.csv", "html": "table.html", "original": "original" + path.suffix}.get(
                                    extension, extension + path.suffix)
                    add_file(path, f"{prefix}/{filename}")
                    exported["files"][extension] = filename
                add_json(exported, f"{prefix}/metadata.json")
                exported_resources[resource["id"]] = {**exported, "files": {
                    key: f"resources/{resource['id']}/{value}" for key, value in exported["files"].items()}}
            for paper_id in dict.fromkeys(paper_ids):
                paper = library.paper(paper_id)
                prefix = f"papers/{paper_id}"
                add_file(library.pdf(paper_id), f"{prefix}/original.pdf")
                add_json(paper, f"{prefix}/metadata.json")
                annotation_result = library.annotations(paper_id=paper_id, limit=10000)
                if annotation_result["total"] > 10000:
                    raise ValueError("论文笔记超过10000条，请分批导出")
                add_json(annotation_result["items"], f"{prefix}/annotations.json")
                add_text(annotation_markdown(annotation_result["items"], linked_pdf=True), f"{prefix}/notes.md")
                add_json(library.reading_state(paper_id), f"{prefix}/reading-state.json")
                paper_resources = [r for r in resources.values() if r["paper_id"] == paper_id]
                effective_resources = [exported_resources[r["id"]] for r in paper_resources]
                text, structure = "", {"metadata": paper, "blocks": [], "resources": effective_resources}
                if paper.get("active_revision"):
                    revision = safe_path(library.root, f"papers/{paper_id}/revisions/{paper['active_revision']}")
                    if (revision / "docling.json").exists():
                        add_file(revision / "docling.json", f"{prefix}/docling.json")
                    if (revision / "structure.json").exists():
                        structure = json.loads((revision / "structure.json").read_text(encoding="utf-8"))
                    if (revision / "fulltext.md").exists():
                        text = (revision / "fulltext.md").read_text(encoding="utf-8")
                    file_map = {}
                    with library.db.read() as con:
                        for resource in paper_resources:
                            row = con.execute("SELECT auto_json FROM resources WHERE id=?", (resource["id"],)).fetchone()
                            original = json.loads(row[0]).get("files", {}).get("png")
                            if original:
                                try:
                                    source_relative = safe_path(library.root, original).relative_to(revision).as_posix()
                                    file_map[source_relative] = f"resources/{resource['id']}/image.png"
                                except ValueError:
                                    pass
                    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)',
                                  lambda m: f"![{m[1]}]({file_map.get(m[2], m[2])})", text)
                structure.update(metadata=paper, resources=effective_resources, paper_id=paper_id,
                                 export_format="papervault-export-v1", original_pdf="original.pdf")
                add_json(structure, f"{prefix}/structure.json")
                text += "\n\n## PaperVault resources\n"
                for resource in effective_resources:
                    if resource["files"].get("png"):
                        caption = (resource.get("caption") or "").replace("]", "")
                        text += f"\n![{caption}]({resource['files']['png']})\n"
                add_text(text, f"{prefix}/fulltext.md")
            archive.writestr("manifest.json", json.dumps({"format": "papervault-export-v1", "files": checksums},
                                                         ensure_ascii=False, indent=2))
        return target
