# PaperVault

面向科研人员的本地论文与图表资源库。导入PDF后，使用本机CPU上的Docling识别正文、章节、Figure和Table，生成可搜索、可编辑、可导出的知识资产。

## 当前交付状态

PaperVault 0.2.2 包含阅读工作台：多论文标签页、阅读位置恢复、页内查找、书签、高亮和可定位笔记。全库笔记支持搜索、筛选、删除恢复及 Markdown/JSON 导出。界面使用紧凑的中性灰工作区，支持收起侧栏、可调信息栏与亮暗主题。

本机产物：[Windows安装包](apps/desktop/src-tauri/target/x86_64-pc-windows-msvc/release/bundle/nsis/PaperVault_0.2.2_x64-setup.exe)。已在本机实际安装并通过真实PDF、阅读笔记与旧库迁移验收（511.54 MiB）；结果与哈希以 [测试报告](TEST_REPORT.md) 和 [交付清单](docs/verification/0.2.2/release-manifest.json) 为准。首次使用可在设置中导入本项目已有的 `.cache/models` 模型目录，或选择下载模型。开发工具只供构建使用，安装版内置Python后端。

最新新增20篇真实论文、243页，累计27篇314页。新增样本保留226个实际图表导出，6篇深入核对、14篇图表清单核对；0.2.2修复SimCSE附录编号，并通过新冻结后台与实际安装窗口复测。漏图、复杂表格、裁剪、科学符号及两处标题问题仍存在，见[新增20篇测试报告](docs/EXPANDED_PAPER_TESTS.md)和[原7篇报告](docs/REAL_PAPER_TESTS.md)。流程通过不表示内容全部准确。

安装器未签名；干净Windows VM尚未验证。复杂PDF识别限制及再次出现且根因未定位的原生诊断均如实记录在 [TEST_REPORT.md](TEST_REPORT.md)，开发记录见 [PROGRESS.md](PROGRESS.md)。

[多论文库与联合搜索演示](artifacts/demo-library/final/PaperVault-library-demo-zh.mp4)（2分17秒，黑底打字机片头、1080p中文字幕）；另有[单篇导入流程](artifacts/demo/final/PaperVault-demo-zh.mp4)。[字幕、素材来源与复现说明](docs/DEMO.md)。

## 开发运行（Windows）

需要Python3.12、Node.js24、Rust MSVC工具链、Visual Studio C++ Build Tools及Windows SDK。最终安装版不需要这些开发工具。

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.lock
.venv\Scripts\python.exe -m pip install --no-deps -e .
cd apps\desktop
npm ci
cd ..\..
powershell -ExecutionPolicy Bypass -File scripts\dev-desktop.ps1
```

已验证的依赖以Python与npm/Cargo锁文件为准。CPU PyTorch构建使用官方CPU索引。需要补齐Windows编译环境时运行 `scripts/bootstrap-windows.ps1`；脚本只负责明确列出的构建工具。

浏览器调试可分别运行 `scripts/dev-backend.ps1` 和 `npm run dev --prefix apps/desktop`。浏览器模式的开发令牌只用于本机调试；桌面版每次启动会生成独立令牌。

## 第一次使用

1. 选择本地空文件夹创建论文库，或选择已有PaperVault库。
2. 在设置中下载解析模型，或导入已校验的离线模型目录。下载只获取模型，不上传论文。
3. 点击“导入论文”、导入文件夹，或将PDF拖入窗口。原文件会复制到库中，相同内容自动去重。
4. 在解析任务页查看实际处理阶段，完成后浏览论文详情、图片库和表格库。

模型准备好后，核心解析、阅读、搜索、编辑和导出均可离线使用。首版主要处理数字原生PDF；扫描件及复杂版面可能需要人工校对。

## 常用操作

- **图片：**图片库中查看Caption，导出150/300/600 DPI PNG；“查看原文”定位并高亮对应PDF区域。可重新框选裁剪。
- **表格：**预览原图或结构化单元格，修改内容/行列/表头，再导出CSV、HTML或PNG。CSV不能保留合并单元格，HTML和原图用于保留结构与视觉证据。
- **搜索：**全局搜索支持论文信息、正文、图表Caption、表格内容、标签、备注和可定位笔记，支持中文和英文混合关键词。
- **阅读：**最近阅读继续上次位置，多论文标签页支持返回/前进；`Ctrl+F` 在 PDF 中查找。选中文字可高亮或记笔记，工具栏可添加页书签或框选区域笔记。
- **笔记：**在论文旁编辑摘录、正文、颜色与标签，或在全库笔记中搜索和定位。笔记独立保存，重新解析不覆盖，也不写回原始 PDF。未保存修改在离开或关闭前提供保存、放弃和继续编辑。
- **管理：**使用标签、收藏夹、收藏和备注组织论文；列表与图库支持多选及批量导出。
- **备份：**设置中生成完整备份；恢复到新的空目录，原库保留。卸载程序不应删除论文库。

数据保存在用户选择的论文库目录。UUID用于目录和资源标识；原件位于 `papers/<paper_id>/original.pdf`。文件格式见 [数据格式说明](docs/DATA_FORMAT.md)。

## 测试与Windows打包

```powershell
.venv\Scripts\python.exe -m pytest tests -m "not real_parser" -q
npm test --prefix apps/desktop
npm run build --prefix apps/desktop
.venv\Scripts\python.exe scripts\acceptance.py --models .cache\models
powershell -ExecutionPolicy Bypass -File scripts\package-windows.ps1
```

打包会生成Python onedir运行时与NSIS安装包。安装验证必须使用真实发布文件，不能以浏览器测试代替。详细步骤见 [Windows构建说明](docs/WINDOWS.md)。

## 文档

- [用户指南](docs/USER_GUIDE.md)
- [架构](ARCHITECTURE.md) / [技术决策](DECISIONS.md)
- [本地API](docs/API.md) / [数据格式](docs/DATA_FORMAT.md)
- [阅读与笔记接口](docs/READING_API.md) / [0.2 升级验收](docs/UPGRADE_0_2.md)
- [第三方许可](docs/THIRD_PARTY_NOTICES.md)
- [已知问题与后续开发](docs/KNOWN_ISSUES.md)
