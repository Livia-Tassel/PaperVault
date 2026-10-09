# 论文库格式 v1

论文库由SQLite元数据与文件资源组成，应整体备份，不要在程序运行时仅复制一个.db文件。

```
database/papervault.db       # Alembic版本、元数据、任务、FTS5
papers/<uuid>/original.pdf  # 托管原件；导入来源不修改
papers/<uuid>/metadata.json # 便于独立查看的快照；DB为事实来源
papers/<uuid>/revisions/<run_id>/
    docling.json            # 原始解析器输出
    structure.json          # 标准化文档、资源与来源位置
    fulltext.md
    manifest.json           # 文件SHA-256
    resources/...
papers/<uuid>/manual/<revision_id>/
exports/
backups/
.staging/                   # 未发布结果，不参与搜索和浏览
```

Paper、Resource、ParseRun、Job使用UUID；论文按完整文件SHA-256去重。Figure编号来自原文Caption，缺失时留空，不能作为内部ID。

SourceLocation使用0基`page_index`和未旋转PDF user-space的`bbox=[x0,y0,x1,y1]`。保留MediaBox、CropBox、UserUnit、页面旋转及原始Docling provenance。bbox为null时只允许页码定位。多段资源有多个locations。

自动值放在auto_json；人工修改放在overrides_json。键不存在表示使用自动值，键存在且值为null表示用户主动清空。人工表格/裁剪生成独立文件，重解析不得写入此覆盖层。

Table保留rows、cells及header_rows；cells记录行列、row_span/col_span、表头和原始引擎字段。CSV使用UTF-8 BOM与标准引号；科学计数法保持原始文本，公式样式的文本加前导单引号以防电子表格应用执行。HTML保留合并结构并转义文本，PNG保留PDF视觉布局。

论文导出ZIP含原件、有效metadata、结构JSON、Markdown和资源。资源metadata中记录来源论文、位置、Caption、引擎与提取时间；导出文件可以独立于应用读取。

完整备份ZIP含数据库快照、论文目录和哈希清单。恢复验证路径、清单、外键、数据库完整性及资源引用后才切换。恶意路径、损坏清单和非空恢复目录将被拒绝。
