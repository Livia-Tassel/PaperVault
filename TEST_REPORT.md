# PaperVault 测试报告

## 当前结果（2026-10-09）

| 项目 | 状态 | 证据 |
|---|---|---|
| 非模型后端/文件/几何/模型管理回归 | 已通过测试 | 64 passed / 5 deselected，5.34s；后续中文Sidecar协议回归单独通过 |
| 源文件保护与哈希去重 | 已通过测试 | 相同文件实体唯一，源与托管副本SHA-256一致 |
| 人工修正与重解析 | 已通过测试 | 唯一位置匹配复用资源，歧义保留待关联人工资源 |
| 中文单字/双字/混合搜索 | 已通过测试 | FTS5短语与原文高亮用例 |
| Python源代码Sidecar | 已通过测试 | ready、认证health、匿名拒绝、stdin EOF退出 |
| Docling真实离线CPU解析 | 已通过测试 | parser组30项通过，含5个真实解析样本 |
| React界面与PDF.js | 已通过测试 | 8个unit、3个真实浏览器E2E、生产build通过 |
| 冻结Python后台完整业务链 | 已通过测试 | 实际EXE完成真实解析、图表导出、编辑、搜索、备份恢复、重启；最终编码修复重冻中 |
| Tauri原生窗口 / NSIS安装 | 验证中 | 已构建release EXE，最终包验证进行中 |
| 干净Windows VM | 受环境限制未验证 | 不等同本机开发/打包运行 |

## 测试条件
Windows 11 x64 10.0.26300；Intel64 Family6 Model186 Stepping2，16逻辑核心，16,890,716,160字节内存（约15.73GiB）；Python3.12.8；Node24.15；SQLite3.45.3含FTS5；CPU PyTorch2.7.1、Docling Slim2.135.0。

## 真实端到端
`scripts/acceptance.py` 通过真实本地HTTP和独立worker执行：创建库→导入→Docling→图表PNG/CSV/HTML→Caption检索→源PDF坐标→人工Caption/表格/裁剪→ZIP导出→备份恢复至新目录→关闭后重新启动→确认文件、修改和索引。没有mock解析或硬编码输出。

| 样本 | 后台启动 | 导入+解析+发布 | 后台及worker峰值RSS | 结果 |
|---|---:|---:|---:|---|
| 原创2页academic.pdf，源代码 | 1.494s | 20.121s | 1,243,947,008B | 1 Figure、1 Table，全流程通过 |
| 公开9页Docling Technical Report v5，源代码 | 1.266s | 34.009s | 1,995,804,672B | 5图片区域、3表格区域，全流程通过 |
| 原创2页，冻结EXE（补齐公式数据后） | 1.162s | 15.936s | 1,252,556,800B | 全流程通过；后续最终包结果另列 |

这些是新进程启动测量，未清空操作系统文件缓存；测量期间存在并行构建，不能视为干净机器冷启动性能保证。源码证据位于artifacts/acceptance-source.json与acceptance-public-paper.json。

公开样本：https://arxiv.org/pdf/2408.09869v5，CC BY4.0，SHA-256 `82dd470712ce8389f19f20eb9330475e2166a281f8c7990a9f1d0763d73b4d22`。仅下载公开测试论文，没有上传用户文件。

## 解析准确性边界
原创标注样本academic.pdf：预期1 Figure/1 Table，实测各1，无额外检测；Figure bbox IoU=0.702553，Table IoU=0.975783；Caption文字匹配，16个表格单元格全部一致。仅代表该小样本，不推导通用论文准确率。

其他真实回归覆盖双栏、多级合并表头（rowspan/colspan）、嵌入位图、原始JPEG字节保留、纯扫描页诚实降级、矢量图、四向旋转、非零CropBox、UserUnit=2、中文/空格及超过260字符的库路径。唯一JPEG对应样本IoU=0.993515，提取JPEG与原字节相同。

## 检索与分页性能
明确合成负载：1000篇论文元数据、5000个资源、1000个正文块；不计作真实PDF解析验收。索引构建5.272s，50次分组查询P50=82.845ms/P95=106.550ms，图库30条分页P50=17.329ms/P95=22.694ms，进程RSS64,208,896B。方法见scripts/benchmark.py，原始结果artifacts/search-benchmark.json。

## 已解决问题
FastAPI跨线程关闭FileLock导致重启无法重新打开库：锁改为thread_local=False，加入重启集成用例并通过。

此外修复：Windows stdin读线程下multiprocessing启动停滞；显式worker日志未关闭阻止目录发布；解析器多段路径类型与API契约不一致；旧UUID导出结构/manifest失效；多页PNG高DPI导出丢页；自选备份ZIP被当目录；并发删除可能破坏备份；缺失文件备份应失败；冻结程序缺少latex2mathml静态数据；非UTF-8宿主下中文控制通道。

## 已知限制
Starlette TestClient的httpx迁移提示和Docling内部弃用warning不影响本轮结果。干净Windows VM尚未验证；本机源码、冻结后台、原生窗口和安装包各自记录，不能互相代替。
