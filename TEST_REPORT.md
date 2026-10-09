# PaperVault 测试报告

## 当前结果（2026-10-09）

| 项目 | 状态 | 证据 |
|---|---|---|
| 全部后端回归（含5项真实解析） | 已通过测试 | 最终70 passed；受控复验70 passed/32.01s；历史原生诊断见下方说明 |
| 源文件保护与哈希去重 | 已通过测试 | 相同文件实体唯一，源与托管副本SHA-256一致 |
| 人工修正与重解析 | 已通过测试 | 唯一位置匹配复用资源，歧义保留待关联人工资源 |
| 中文单字/双字/混合搜索 | 已通过测试 | FTS5短语与原文高亮用例 |
| Python源代码Sidecar | 已通过测试 | ready、认证health、匿名拒绝、stdin EOF退出 |
| Docling真实离线CPU解析 | 已通过测试 | parser组30项通过，含5个真实解析样本 |
| React界面与PDF.js | 已通过测试 | 最终16个unit；3条原始真实E2E、目录/分页、元数据刷新及DPR2专项通过 |
| 冻结Python后台完整业务链 | 已通过测试 | 最终UTF-8版本实际EXE完成真实解析、图表导出、编辑、搜索、备份恢复、重启 |
| Tauri原生窗口 / 初次NSIS安装 | 已通过测试 | 实际安装的exe自动启动sidecar、真实解析1图1表、PDF.js区域高亮 |
| 最终UI更新安装 / 卸载数据保留 | 已通过测试 | 最新UI真实安装；卸载与重装后库/PDF/metadata/DB哈希及SQLite完整性保持 |
| 干净Windows VM | 受环境限制未验证 | 不等同本机开发/打包运行 |

## 测试条件
Windows 11 x64 10.0.26300；Intel64 Family6 Model186 Stepping2，16逻辑核心，16,890,716,160字节内存（约15.73GiB）；Python3.12.8；Node24.15；SQLite3.45.3含FTS5；CPU PyTorch2.7.1、Docling Slim2.135.0。

## 真实端到端
`scripts/acceptance.py` 通过真实本地HTTP和独立worker执行：创建库→导入→Docling→图表PNG/CSV/HTML→Caption检索→源PDF坐标→人工Caption/表格/裁剪→ZIP导出→备份恢复至新目录→关闭后重新启动→确认文件、修改和索引。没有mock解析或硬编码输出。

| 样本 | 后台启动 | 导入+解析+发布 | 后台及worker峰值RSS | 结果 |
|---|---:|---:|---:|---|
| 原创2页academic.pdf，源代码 | 1.494s | 20.121s | 1,243,947,008B | 1 Figure、1 Table，全流程通过 |
| 公开9页Docling Technical Report v5，源代码 | 1.266s | 34.009s | 1,995,804,672B | 5图片区域、3表格区域，全流程通过 |
| 原创2页，最终冻结EXE | 1.574s | 14.392s | 1,255,157,760B | 全流程通过 |

这些是新进程启动测量，未清空操作系统文件缓存；测量期间存在并行构建，不能视为干净机器冷启动性能保证。源码证据位于artifacts/acceptance-source.json与acceptance-public-paper.json。

真实队列验收还执行了三篇批量导入（0.105666s，未计解析）：运行中的论文取消且不发布资源，损坏PDF失败后其他论文仍完成，取消任务重试后实际生成图表。证据artifacts/queue-acceptance.json。

本机Excel16.0已只读打开冻结后台导出的4×4 CSV；列头Method正确，`-1.2e-3`读为数值`-0.0012`，源CSV的SHA-256前后不变。证据artifacts/excel-csv.json。

公开样本：https://arxiv.org/pdf/2408.09869v5，CC BY4.0，SHA-256 `82dd470712ce8389f19f20eb9330475e2166a281f8c7990a9f1d0763d73b4d22`。仅下载公开测试论文，没有上传用户文件。

## 解析准确性边界
原创标注样本academic.pdf：预期1 Figure/1 Table，实测各1，无额外检测；Figure bbox IoU=0.702553，Table IoU=0.975783；Caption文字匹配，16个表格单元格全部一致。仅代表该小样本，不推导通用论文准确率。

其他真实回归覆盖双栏、多级合并表头（rowspan/colspan）、嵌入位图、原始JPEG字节保留、纯扫描页诚实降级、矢量图、四向旋转、非零CropBox、UserUnit=2、中文/空格及超过260字符的库路径。唯一JPEG对应样本IoU=0.993515，提取JPEG与原字节相同。

## 检索与分页性能
明确合成负载：1000篇论文元数据、5000个资源、1000个正文块；不计作真实PDF解析验收。索引构建5.272s，50次分组查询P50=82.845ms/P95=106.550ms，图库30条分页P50=17.329ms/P95=22.694ms，进程RSS64,208,896B。方法见scripts/benchmark.py，原始结果artifacts/search-benchmark.json。

图库浏览器压力测量：1000条明确合成Figure记录共享真实PDF裁剪PNG，每页24项。Edge154 headless、1440×1000、Vite开发模式，首屏310.2ms且8/8可见图片通过decode()；3×6秒共1080个rAF帧间隔P50=16.7ms/P95=16.8ms，页内DOM图片最多24，滚动后24/24解码成功，JS/HTTP错误为0。该结果不是1000张图同屏，也不是安装版启动指标。证据artifacts/gallery-benchmark.json。

## 浏览器PDF几何
真实geometry.pdf、PDF.js及资源API，模拟deviceScaleFactor=2，16个UI案例覆盖4种原生旋转、55%/100%/205%缩放及额外旋转按钮；高亮相对独立CropBox/UserUnit公式最大误差0.009375 CSSpx（门槛2px）。另12个真实PDF.js 50%/100%/200%矩阵往返误差为0。未修改或验证宿主Windows系统缩放设置，不能把浏览器DPR仿真当系统DPI测试。证据artifacts/pdf-geometry-browser.json。

目录/参考文献专项使用真实API保存并重载，确认仅PATCH sections/references、保留已有bbox、添加页码导航到真实第二页。详情图库专项创建201条明确测试资源并确认第201条可分页访问，避免静默截断。证据artifacts/outline-ui-acceptance.json与Playwright输出。

元数据刷新专项通过真实API更新服务器有效字段，验证5秒轮询后未编辑标题/作者刷新、未保存备注保留、收藏回读不丢草稿，保存请求只包含notes。此专项不冒称重新运行Docling；安装后原生窗口另验证解析期间打开表单的更新。证据artifacts/metadata-refresh-ui.json。

## 已解决问题
FastAPI跨线程关闭FileLock导致重启无法重新打开库：锁改为thread_local=False，加入重启集成用例并通过。

此外修复：Windows stdin读线程下multiprocessing启动停滞；显式worker日志未关闭阻止目录发布；解析器多段路径类型与API契约不一致；旧UUID导出结构/manifest失效；多页PNG高DPI导出丢页；自选备份ZIP被当目录；并发删除可能破坏备份；缺失文件备份应失败；冻结程序缺少latex2mathml静态数据；非UTF-8宿主下中文控制通道。

## 已知限制
Starlette TestClient的httpx迁移提示和Docling内部弃用warning不影响本轮结果。干净Windows VM尚未验证；本机源码、冻结后台、原生窗口和安装包各自记录，不能互相代替。

## 最终Windows交付
安装包 `PaperVault_0.1.0_x64-setup.exe`：536,330,353字节（511.48MiB），SHA-256 `B2466D9F245F4DE016EE3FC578FB736F107BE7B53808053FE30382573626C6F3`。

最终安装后的真实Tauri程序自动启动包内后台，验证未认证访问401、中文目录、各主导航、真实CPU解析1Figure/1Table、PDF.js高亮、章节/参考编辑，以及解析完成后自动字段刷新与未保存备注保护。846个许可证文件和7个源代码归档逐个安装哈希通过。实际执行卸载及重装，独立库的原PDF、托管PDF、metadata.json、数据库SHA保持，SQLite完整性通过。程序现重新安装于项目测试目录，可双击运行。

证据：artifacts/installed-desktop/report.json、install-layout.json、uninstall-retention.json；最终可审查快照保存在docs/verification。安装器未签名。本机含开发工具，因此不把这些结果宣称为干净VM验收；实际宿主系统DPI变更、另一台机器、托管CI仍未验证。

一次组合测试曾打印两条Windows原生access violation诊断，但进程exit0且70项全部通过。保持faulthandler开启后的35项分组、70项完整详细输出、70项原默认捕获模式三次受控复验均未再出现该诊断。CPython的Windows vectored handler会打印后继续交由其他处理器，故不能仅凭这行文字判断进程终止；目前缺少故障DLL/地址及C栈，原因未定位，也不认定为无害CPU探测。应用按单PDF独立worker运行，源码/冻结/原生队列流程验证均通过。保留此历史偶发记录与artifacts/native-exception-investigation.json，未通过禁用诊断或改写结果掩盖问题。


## 0.1.1 UI回归（2026-10-09）

本次修改界面和桌面版本，Python业务与冻结后端未改。16项前端单元测试通过，TypeScript检查与Vite生产构建通过。第一次在受限沙箱运行Vitest曾因临时SSR文件ENOENT加载失败，在正常Windows执行环境复验16项全部通过；该失败未当作通过记录。

`scripts/ui-review.mjs`对已有真实测试PDF及其持久化资源执行只读浏览，生成26张截图（`artifacts/ui-review`）：覆盖浅/深色、1440×1000和1280×800、论文列表、PDF/目录、图片/表格库、表格详情、搜索结果、任务、设置，以及侧栏折叠后刷新。严格断言折叠宽度56px并验证展开/主题持久化。截图已目视检查；0个JS错误、请求失败、坏图或主内容横向溢出。图库中的几何标注和人工裁剪均是测试数据，不冒充真实论文集合。证据快照：`docs/verification/ui-review-review.json`。

本次7条Playwright业务用例最终全部通过（首轮6 passed、1 failed；备份textbox精确名称因同Field按钮文案而不匹配，调整为名称前缀后仅重跑该条，1 passed）。测试未mock API，覆盖真实导入、裁剪定位、PNG/CSV/HTML导出、表格人工修改、标签收藏夹、备份恢复、目录编辑、元数据刷新和DPR2几何。跨200项资源分页专项使用明确合成测试库，不计为真实论文解析准确性验收。命令、每次结果和环境见docs/verification/ui-redesign-regression.json。
