# 脚本索引

在仓库根目录执行脚本。Windows 工具使用 PowerShell；Python 工具使用项目 `.venv`，具体参数可用 `--help` 查看。生成目录默认由 `.gitignore` 排除。

## 开发与构建

| 脚本 | 用途 |
| --- | --- |
| [bootstrap-windows.ps1](bootstrap-windows.ps1) | Python / npm 依赖；`-InstallToolchain` 补齐 Rust / C++ 构建工具 |
| [dev-desktop.ps1](dev-desktop.ps1) / [dev-backend.ps1](dev-backend.ps1) | 桌面调试 / 独立后端调试 |
| [build-backend.ps1](build-backend.ps1) / [backend.spec](backend.spec) | PyInstaller onedir、依赖收集与冻结后台验证 |
| [package-windows.ps1](package-windows.ps1) | Tauri 与 NSIS 安装包；详细命令见[构建指南](../docs/WINDOWS.md) |
| [check-doc-links.py](check-doc-links.py) | 无第三方依赖的仓库 Markdown 本地链接检查 |

## 打包与安装验收

| 脚本 | 用途 |
| --- | --- |
| [package-smoke.py](package-smoke.py) | 后端启动、鉴权、库初始化与标准输入关闭后的退出 |
| [acceptance.py](acceptance.py) / [reading-acceptance.py](reading-acceptance.py) | 真实解析与导出 / 阅读笔记重解析和恢复 |
| [bootstrap-webdriver.ps1](bootstrap-webdriver.ps1) / [native_client.py](native_client.py) | WebView2 驱动与原生窗口测试工具 |
| [package-install-smoke.ps1](package-install-smoke.ps1) / [package-uninstall-smoke.ps1](package-uninstall-smoke.ps1) | NSIS 实际安装 / 卸载与重装 |
| [package-desktop-smoke.py](package-desktop-smoke.py) / [package-reading-smoke.py](package-reading-smoke.py) | 实际桌面业务 / 阅读笔记与旧库迁移 |
| [release-manifest.py](release-manifest.py) / [collect_verification.py](collect_verification.py) | 安装器和源码、随包文件与归档证据的哈希绑定 |

## 真实论文与质量复核

- [download_real_corpus.py](download_real_corpus.py)：按来源清单下载；许可和样本范围见[样本说明](../tests/corpus/README.md)。
- [test_real_corpus.py](test_real_corpus.py)、[native-real-corpus.py](native-real-corpus.py)：冻结后台和实际安装窗口的真实样本验收。
- [report_real_corpus.py](report_real_corpus.py)、[render_expanded_review.py](render_expanded_review.py)：生成原文与导出对照页面。
- [summarize_expanded_corpus.py](summarize_expanded_corpus.py)、[summarize_expanded_quality.py](summarize_expanded_quality.py)、[validate_caption_numbers.py](validate_caption_numbers.py)：汇总流程、人工质量与编号检查。

## 性能、界面与演示

- [benchmark.py](benchmark.py)、[benchmark-gallery.py](benchmark-gallery.py)、[benchmark-annotations.mjs](benchmark-annotations.mjs)：搜索、图库与合成标注性能。
- [ui-review.mjs](ui-review.mjs)、[dev-guard-smoke.py](dev-guard-smoke.py)：界面布局和原生未保存保护。
- [prepare_library_demo.py](prepare_library_demo.py)、[record_demo_v2.py](record_demo_v2.py)、[capture_webview.mjs](capture_webview.mjs)：准备独立演示库、实际录制 WebView。
- [render_demo_v2.py](render_demo_v2.py)、[add_demo_intro_v2.py](add_demo_intro_v2.py)：剪辑、字幕和片头；完整经过见[演示说明](../docs/DEMO.md)。

现有脚本相互引用固定路径，因此保留在 `scripts/`；各次临时输出、完整视频与验收库不提交 Git。历史结果从[验证索引](../docs/verification/README.md)进入。
