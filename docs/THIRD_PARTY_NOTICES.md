# 第三方组件与模型

PaperVault新增源码保留所有权利；这不改变第三方组件的许可。发行包须附带相应许可证和版权声明。

| 组件 | 许可/说明 |
|---|---|
| Tauri | MIT / Apache-2.0，完整Rust依赖以Cargo.lock为准 |
| React、Vite、Tailwind、Radix UI、FastAPI | 各自MIT许可，保留依赖提供的文本 |
| PDF.js | Apache-2.0 |
| Docling / Docling Parse | MIT；模型许可独立 |
| pypdfium2 | Apache-2.0 / BSD-3-Clause |
| PDFium及其依赖 | BSD风格及各第三方许可；必须携带PDFium附带的完整许可目录 |
| SQLite | Public domain |
| SQLAlchemy / Alembic | MIT |
| PyInstaller | GPL许可附打包应用分发例外；保留其声明 |
| Heron布局模型 | Apache-2.0，实际revision记录在模型manifest |
| Docling TableFormer模型 | 仓库声明Apache-2.0及CDLA-Permissive-2.0，随模型保存原声明 |
| 原创测试PDF | CC0-1.0，来源见生成脚本与fixture许可证 |
| Docling Technical Report v5 | CC BY4.0，作者Christoph Auer等，arXiv:2408.09869v5；测试下载不代表用户数据上传 |

权威来源：[Docling](https://github.com/docling-project/docling)、[PDFium许可证](https://github.com/pypdfium2-team/pypdfium2#licensing)、[PyInstaller许可证](https://pyinstaller.org/en/stable/license.html)、[Heron模型卡](https://huggingface.co/docling-project/docling-layout-heron)、[TableFormer模型卡](https://huggingface.co/docling-project/docling-models)。

构建时运行 `scripts/collect_licenses.py` 保存已安装Python版本清单与包内许可证文本；npm和Rust锁文件记录实际前端和桌面依赖。最终分发以实际包含的组件为准，缺失许可文本必须在发行前补齐。
