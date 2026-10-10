# 带中文字幕的操作演示

## 当前修订版：从导入到找回图表

[播放修订版](../artifacts/demo-v2/final/PaperVault-demo-v2-zh.mp4) · [SRT字幕](../artifacts/demo-v2/final/PaperVault-demo-v2-zh.srt) · [素材署名](../artifacts/demo-v2/final/SOURCES.md)

长 **1分33.2秒**，真1920×1080应用画面、30fps、H.264，无音轨。主片不缩放、不补边，取消旧版120px字幕栏；中文字幕放在画面内，底图取当前帧的局部画面进行真实模糊，再加半透明暗色与圆角。复制图片的字幕移到顶部，避开实际操作按钮。片头继续使用黑底居中逐字动画。

本次开场改为：

> 读过的论文，可以成为你的知识库吗？
> 当然可以！
> 组会汇报、写论文，想用读过的图表，却忘了论文名？
> PaperVault，帮你把它找回来。

16秒片头后立即导入新的 *Docling Technical Report v5*，展示实际本地解析任务与完成状态。使用上一轮8篇演示库的独立备份副本，新增这篇9页PDF后共有9篇108页、31个图片和79个表格资源；原8篇库及用户论文库没有被本轮修改。本次实际导入至任务界面完成约52秒，46.156秒等待被剪去并明确标注。

约第39秒进入核心用法：只凭GLUE关键词找回BART与BERT中的表格，打开结果并定位原文；随后用BERT找图片，实际复制BERT Figure 1并显示剪贴板成功通知，再回原文核对。全库文字检索放在后段，列表/标签整理从本片移除。检索是关键词检索，不声称语义问答；新论文图表识别的既有质量限制仍保留。

完整解码、字幕时间与画面尺寸检查通过，人工核对了新片头、真实任务、跨论文表格结果、复制成功及字幕位置。MP4为3,091,268字节，SHA-256 `f752c615799d22314ccb7c14bccecdab94d251e102665518a5bb276640e6425d`。

复现工具为 `scripts/record_demo_v2.py`、`scripts/render_demo_v2.py --timeline <录制时间轴>` 与 `scripts/add_demo_intro_v2.py --demo <主片MP4> --subtitles <主片SRT> --output-directory <新目录>`。录制和渲染均使用新目录，旧版保留。原始实录与完整证据位于 `artifacts/demo-v2/`，紧凑验证记录在 `docs/verification/demo-v2/`。

## 多论文库与联合搜索版

[播放新版视频](../artifacts/demo-library/final/PaperVault-library-demo-zh.mp4) · [SRT字幕](../artifacts/demo-library/final/PaperVault-library-demo-zh.srt) · [素材署名](../artifacts/demo-library/final/SOURCES.md)

新版长 **2分17.43秒**，1920×1080、30fps、H.264，无音轨。前13.2秒是黑底居中打字机文字，逐个字符出现；第一句1.8秒打完、停留至3.6秒，最后保留0.3秒纯黑后进入实机画面。字幕已经烧录，单独SRT用于编辑，不需重复加载。

片头文案：

1. 读过的论文，能成为你的知识资产吗？
2. PaperVault，把论文变成可检索的本地知识库。
3. 正文、图表，跨论文一起找。
4. 找到线索，一键回到原文。

主片使用同一新建演示库内的8篇公开论文：BERT、Sentence-BERT、BART、SciBERT、SimCSE、mT5、ChineseBERT和MacBERT，共99页。全部通过已安装0.2.2真实离线解析，8个worker退出0，产生26个图片和76个表格资源。画面明确说明已预先解析；没有伪造数据库记录或触碰用户论文库。

实际演示列表/卡片、三篇批量标签与筛选、全库BERT关键词查询、论文/表格/正文分组，以及从MacBERT第5页表格和BART第2页文本命中分别回到原文。两个来源保留在阅读标签页中切换；图片库BERT筛选涉及3篇论文，表格库GLUE筛选涉及2篇论文。BERT查询的返回结果覆盖5篇论文信息、3篇图片、5篇表格和8篇正文来源；每组25条是当前返回上限，不能当作全库总命中数。这是关键词检索，不声称语义问答或跨论文自动总结。

编码、全片解码、字幕平移及人工抽帧核对通过。最终文件5,165,413字节，SHA-256：`618465fa20b561ba0940bbce62557121774d019dc8d643d75ebef0df1a53aa84`。新的真实解析不改变既有准确性报告的结论，复杂图表仍需对照原文。

复现：先运行 `scripts/prepare_library_demo.py`（默认拒绝覆盖已准备的输出，可用`--help`查看新目录参数），再运行 `scripts/record_library_demo.py --preparation artifacts/demo-library/preparation.json`，把打印出的时间轴传给 `scripts/render_demo.py --timeline ...`。最后执行：

```powershell
.venv/Scripts/python.exe scripts/add_demo_intro.py --demo artifacts/demo-library/main/PaperVault-demo-zh.mp4 --subtitles artifacts/demo-library/main/PaperVault-demo-zh.srt --output-directory artifacts/demo-library/final
```

各生成步骤拒绝覆盖已有成品，应选择新的目录。原始输入、实录、检索证据和帧在 `artifacts/demo-library/`，紧凑验收记录在 `docs/verification/demo-library/`。下面保留此前单篇流程版本。

## 单篇导入与阅读版

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
