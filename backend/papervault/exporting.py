from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

from .files import safe_path, uid


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
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            resources = {resource_id: library.resource(resource_id) for resource_id in resource_ids}
            for paper_id in dict.fromkeys(paper_ids):
                paper = library.paper(paper_id)
                prefix = f"papers/{paper_id}"
                archive.write(library.pdf(paper_id), f"{prefix}/original.pdf")
                archive.writestr(f"{prefix}/metadata.json", json.dumps(paper, ensure_ascii=False, indent=2))
                paper_resources = library.resources(paper_id=paper_id, limit=100000)["items"]
                resources.update({r["id"]: r for r in paper_resources})
                if paper.get("active_revision"):
                    revision = safe_path(library.root, f"papers/{paper_id}/revisions/{paper['active_revision']}")
                    for name in ("structure.json", "docling.json", "manifest.json"):
                        if (revision / name).exists():
                            archive.write(revision / name, f"{prefix}/{name}")
                    text = (revision / "fulltext.md").read_text(encoding="utf-8") if (revision / "fulltext.md").exists() else ""
                    # Rewrite parser-specific image links to the exported effective assets.
                    by_caption = {r.get("caption", ""): r for r in paper_resources if r["files"].get("png")}
                    for r in paper_resources:
                        original = r["files"].get("png", "")
                        basename = Path(original).name
                        relative = f"resources/{r['id']}/image.png"
                        text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)',
                                      lambda m, b=basename, p=relative: f"![{m[1]}]({p})" if Path(m[2]).name == b else m[0], text)
                    # An explicit asset inventory is always portable, including manual resources.
                    text += "\n\n## PaperVault resources\n"
                    for r in by_caption.values():
                        text += f"\n![{r.get('caption','') .replace(']', '')}](resources/{r['id']}/image.png)\n"
                    archive.writestr(f"{prefix}/fulltext.md", text)
            for resource in resources.values():
                prefix = f"papers/{resource['paper_id']}/resources/{resource['id']}"
                exported = {**resource, "files": {}}
                formats = list(resource["files"]) if format_name == "zip" or paper_ids else [format_name]
                for extension in formats:
                    if extension not in ("png", "thumbnail", "csv", "html"):
                        continue
                    path = library.resource_file(resource["id"], extension, dpi if extension == "png" and len(resource["locations"]) == 1 else None)
                    filename = {"png": "image.png", "thumbnail": "thumbnail" + path.suffix,
                                "csv": "table.csv", "html": "table.html"}[extension]
                    archive.write(path, f"{prefix}/{filename}")
                    exported["files"][extension] = filename
                archive.writestr(f"{prefix}/metadata.json", json.dumps(exported, ensure_ascii=False, indent=2))
        return target
