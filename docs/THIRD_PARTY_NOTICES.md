# 第三方组件与模型

PaperVault新增源码保留所有权利；这不改变第三方组件的许可。发行包须附带相应许可证和版权声明。

0.2阅读工作台沿用已锁定的第三方依赖和模型版本，没有引入新的第三方组件。新冻结包包含本项目0.2业务代码；Windows安装验收继续逐文件验证846个许可证文件和7个源码归档。迁移fixture仅含原创测试内容，其中academic.pdf继续适用CC0-1.0，数据库和手工测试元数据按仓库LICENSE保留权利。

| 组件 | 许可/说明 |
|---|---|
| Tauri | MIT / Apache-2.0，完整Rust依赖以Cargo.lock为准 |
| React、Vite、Tailwind、Radix UI、FastAPI | 各自MIT许可，保留依赖提供的文本 |
| PDF.js | Apache-2.0 |
| Docling / Docling Parse | MIT；模型许可独立 |
| pypdfium2 | Apache-2.0 / BSD-3-Clause |
| PDFium及其依赖 | BSD风格及各第三方许可；必须携带PDFium附带的完整许可目录 |
| SQLite | Public domain |
| 内置CPython 3.12运行时 | PSF许可证及Python发行包附带声明，原文保存在CPython-runtime目录 |
| SQLAlchemy / Alembic | MIT |
| PyInstaller | GPL许可附打包应用分发例外；保留其声明 |
| Heron布局模型 | Apache-2.0，实际revision记录在模型manifest |
| Docling TableFormer模型 | 仓库声明Apache-2.0及CDLA-Permissive-2.0，随模型保存原声明 |
| 原创测试PDF | CC0-1.0，来源见生成脚本与fixture许可证 |
| Docling Technical Report v5 | CC BY4.0，作者Christoph Auer等，arXiv:2408.09869v5；测试下载不代表用户数据上传 |

权威来源：[Docling](https://github.com/docling-project/docling)、[PDFium许可证](https://github.com/pypdfium2-team/pypdfium2#licensing)、[PyInstaller许可证](https://pyinstaller.org/en/stable/license.html)、[Heron模型卡](https://huggingface.co/docling-project/docling-layout-heron)、[TableFormer模型卡](https://huggingface.co/docling-project/docling-models)。

构建时运行 `scripts/collect_licenses.py` 与 `scripts/collect_web_rust_licenses.py` 保存已安装Python、npm、Cargo版本清单与包内许可证文本。清单中的其他平台optional依赖可能未安装，也不随本次Windows二进制分发；来源可用性逐项记录。遗漏于包内的声明按官方仓库补全，出处随补充记录保留。

MPL组件的精确版本源码、未修改说明，以及历史发布元信息与当前官方许可证的差异，见 [MPL源码与补充声明](MPL-SOURCE-NOTICE.md)。本机128个已安装npm包和287个可用Cargo包均已记录许可证文本来源；补充文件哈希见 `license-supplements.json`。
