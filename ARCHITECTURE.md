# PaperVault 架构

## 状态
开始实施，功能与实测状态以 PROGRESS.md、TEST_REPORT.md 为准。

## 边界
React/TypeScript 提供中文桌面界面；Tauri 2 管理原生交互与 Python Sidecar；FastAPI 只监听回环地址，按每次启动的令牌鉴权。后台解析在独立进程中执行，SQLite 是元数据与索引的唯一事实来源。

## 持久化
原件复制到 `papers/<uuid>/original.pdf`，源文件不修改。自动解析结果放在不可变 revisions 目录，人工覆盖单独记录。发布采用同卷临时目录、文件校验、目录重命名、数据库最后提交的协议。SQLite 与文件系统不具备联合事务，启动恢复处理未引用结果。SQLite 使用 WAL、FULL 同步、外键及单库进程锁。

## 搜索与定位
FTS5 使用应用层中英预分词。原文和高亮片段独立处理。资源位置保存未旋转 PDF user-space 坐标与原始 provenance，PDF.js 使用 viewport 正逆变换定位，PDFium负责渲染。

## 技术选择
Docling 完成真实版面与表格识别，PDFium替代PyMuPDF避免引入其AGPL/商业许可选择。SQLAlchemy/Alembic负责迁移，直接 sqlite3 事务适配层负责FTS与备份API。PyInstaller onedir 保留原生依赖目录；模型独立管理，正常解析禁止隐式网络下载。

## 扩展
Parser接口隔离引擎；AI Provider只预留协议，核心使用不需要API Key。P2不计入首版验收。
