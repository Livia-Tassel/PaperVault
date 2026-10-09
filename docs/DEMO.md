# 带中文字幕的操作演示

成片为 MP4，1920 × 1080、30 fps、H.264，无配音。中文字幕直接烧录在画面底部的独立区域，同时提供可编辑的 SRT 字幕。

- [演示视频](../artifacts/demo/final/PaperVault-demo-zh.mp4)
- [中文字幕](../artifacts/demo/final/PaperVault-demo-zh.srt)
- [预览图](../artifacts/demo/final/poster.jpg) · [抽帧总览](../artifacts/demo/final/contact-sheet.jpg)
- [编码与验证报告](../artifacts/demo/final/render-report.json)

最终时长 **1分53.23秒**，文件大小 **3,641,470字节（约3.47 MiB）**。全片解码、30 fps、1080p、字幕区域和快速播放布局检查通过；另逐段查看抽帧，确认实际页面变化、图表原文、导出成功通知和中文笔记搜索均与字幕相符。

MP4 SHA-256：`7a1d27ad957e65f00349aeba54d87883740fb17cbb5dbaff2a651d3d6137f088`。编码报告和独立的 `visual-review.json` 分别记录自动检查与人工画面复核。

## 演示内容

使用实际安装的 PaperVault 0.2.2，从独立空论文库导入真实 SimCSE PDF，运行本地解析，然后展示：

1. 论文库与原始 PDF 阅读、文字查找。
2. Figure G.1 预览、图注与第 17 页原文定位。
3. Table A.1 结构化表格、原始截图、CSV 导出与第 13 页原文定位。
4. 页书签、中文阅读笔记、全文搜索与从搜索结果返回笔记。

解析等待经过剪辑，片中明确显示“本地解析完成；等待过程已剪辑”。CSV 通过真实系统保存对话框保存，并验证实际文件和应用成功通知。CDP 仅记录应用的 WebView 内容，不包含系统保存对话框、窗口边框或系统鼠标；相应字幕明确写明“导出 CSV；系统保存对话框已略去”。静止画面按真实等待时间保留，未将低更新频率的页面压缩成加速操作。

演示使用真实解析输出，不代表所有图表内容都准确。表格包含原图对照，CSV 不保留合并单元格；完整质量边界见 [真实论文测试报告](EXPANDED_PAPER_TESTS.md)。

## 论文来源

Tianyu Gao、Xingcheng Yao、Danqi Chen，*SimCSE: Simple Contrastive Learning of Sentence Embeddings*，EMNLP 2021，pp. 6894–6910。来自 [ACL Anthology 官方论文页](https://aclanthology.org/2021.emnlp-main.552/)，按 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 使用。片尾保留作者、会议、来源与许可证署名。

17 页原始 PDF 的 SHA-256：`b6bb8b5d1356095a02aae8e5e41265fde03f8f02101972e338bad0b7715f12fc`。下载地址、许可证依据与文件哈希保存在 [来源清单](../tests/corpus/expanded/sources-ml.json) 的 `ml-simcse-emnlp2021` 条目中。

## 复现

在仓库根目录执行。前提是 `.test-data/installed/PaperVault/papervault.exe` 已安装为 0.2.2，本地模型 `.cache/models` 就绪，来源清单对应的 PDF 已下载，Node.js 24、项目 Python 环境和 Edge WebDriver 可用。编码使用 `.tools/video-python/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe`，该工具独立存放，不修改应用运行依赖。

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe scripts/record_demo.py --probe
.venv/Scripts/python.exe scripts/record_demo.py
.venv/Scripts/python.exe scripts/render_demo.py --timeline 'artifacts/demo/capture-实际录制时间/timeline.json'
```

`--probe` 真实切换设置与论文库，并比较不同时间点的页面像素，验证录制会随应用变化。普通录制完成后打印实际 `timeline.json` 路径，将该路径传给渲染脚本。渲染默认拒绝覆盖现有成片；确认需要重做时添加 `--overwrite`。原生录制由 [record_demo.py](../scripts/record_demo.py) 调用 [capture_webview.mjs](../scripts/capture_webview.mjs)，字幕、剪辑与成片验证由 [render_demo.py](../scripts/render_demo.py) 完成。

录制目录保留原始视频、JPEG 帧、时间索引、操作证据与剪辑时间轴；成片目录保留 MP4、SRT、ASS、预览图、抽帧总览及验证报告。验证包括完整视频解码、尺寸、帧率、时长、颜色范围、字幕区域和 MP4 快速播放布局。动态录制探针已检查实际设置页面与论文库画面存在变化。

演示库、PDF 副本和导出文件位于 `.test-data/demo/`，视频与帧位于 `artifacts/demo/`，均为 Git 忽略目录。没有操作用户日常使用的论文库。早期 GDI 录制虽然能编码，但人工检查发现应用画面冻结，已拒绝交付，保留于 `artifacts/demo/rejected-gdi/`；该目录内容不是成片。
