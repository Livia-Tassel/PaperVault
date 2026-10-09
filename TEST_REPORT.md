# PaperVault 测试报告

## 0.2 当前结果（2026-10-09，最终安装包验收通过）

0.2 新增连续阅读工作台、书签/高亮/区域笔记和修改保护。下表区分源码、真实浏览器、冻结后端与实际安装验证。包含最新标注渲染优化和完整随包文档的最终安装器已在本机通过两套原生流程；先前候选单独保留。

| 范围 | 已核实结果 | 证据与边界 |
|---|---|---|
| 全部后端 | **117 passed，0 skipped**，55.62s；ruff通过 | 含5项真实离线CPU Docling；`artifacts/reading-backend-tests.json`、`backend-release-v02-junit.xml` |
| 前端源码 | 完整47项单元通过；TypeScript/生产构建通过 | 最初45项之后新增2项标注索引测试；不把单元通过视作实际安装验收 |
| PDF阅读器 | 优化后6项浏览器用例通过，38.8s | 4项挂载真实PDF.js组件、1项完整真实库/API读写、1项81页极端PDF；详见下文 |
| 工作台/笔记/修改保护 | 工作台5、笔记2、阅读冲突1、导出/书签保护2项通过 | 真实UI和API；延迟与503为显式失败注入，没有伪造成功保存 |
| 原有业务 | 7项通过、0跳过；同目标重复定位另1项通过 | `PAPERVAULT_E2E_REQUIRE_PARSE=1`；图库201项测试采用明确合成记录 |
| 视觉与键盘 | 44张真实数据截图，另2张键盘复验 | 浅/深色、1440×1000与1280×800；0个JS错误和坏图；DPR2另有PDF几何测试 |
| 标注渲染负载 | 优化后1000条/3000矩形滚动p95 16.8ms | CDP主线程工作占比由70.84%降至13.42%；合成负载、同机测量，非解析准确率或低端机保证 |
| 冻结后端新工作流 | 真实重新解析与备份恢复通过 | 5条人工二次修改记录及阅读状态全部字段不变，FTS始终5/5，源PDF哈希不变 |
| 已安装0.2候选 | A789候选的旧库升级、阅读/笔记/定位及API导出已通过 | 已归档为历史候选；**不含后续渲染性能优化，不能当作最终包证明** |
| 最终优化安装包 | **真实安装与两套原生验收通过** | SHA8b701f4e…fbf761；实际界面入口Bi9K65xx、应用与后台0.2.0，11文档/846许可/7归档哈希一致 |
| 原生另存为取消 | **实际Windows对话框取消通过** | owned PID 29300、窗口类#32770、标题“另存为”；0成功提示、0文件、笔记全部字段不变 |
| 至少5小时 | 已达门槛：21,218秒 | 父goal工具于11:31:54 UTC读取；同时完成功能、最终安装验收与文档 |
| 环境限制 | 干净Windows VM、宿主系统DPI变更、托管CI未验证 | 维持原边界，不宣称通过 |

最终逐项审计见 `docs/verification/0.2.0/upgrade-audit.json`；验收快照与发布清单位于同目录。早期尚有pending的原稿 `docs/verification/upgrade-v02-audit-draft.json` 保留为过程记录，不代表最终状态。

### 0.2 后端、迁移与真实重解析

完整命令：`PAPERVAULT_TEST_MODELS=D:\project\PaperVault\.cache\models HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/Scripts/python.exe -m pytest tests -v --basetemp=.test-data/backend-release-v02-11 --junitxml=artifacts/backend-release-v02-junit.xml --tb=short -o faulthandler_timeout=120`。在允许本机回环的Windows执行环境运行，117通过、0失败/错误/跳过；pytest为55.62s，进程总时长57.953s。5项真实解析依次使用academic、two-column、mixed-assets、scanned和embedded-jpeg样本，耗时38.688/3.157/2.476/1.557/1.611s。只使用既有本地模型，没有联网下载。`ruff check backend tests scripts`通过。

0002迁移新增独立阅读状态、可恢复删除的笔记及库UUID，先以SQLite Backup API保存升级前快照。完整测试覆盖旧0001库/旧备份恢复升级、DDL失败回滚和重试、同版本并发写仅一方提交、索引异常不留下半次编辑、位置/长度/有限数校验、论文移除后的笔记搜索隔离，以及同UUID不同路径恢复副本拒绝迟到旧库写入。阅读滚动保存不重建论文索引或覆盖人工元数据。原受限沙箱临时目录错误与TestClient停滞、后续真实宿主执行结果均保留在报告，没有把环境失败当通过。

新增 `scripts/reading-acceptance.py` 单独启动冻结0.2.0后端与真实Docling子进程，使用独立测试库和端口26001，不借用共享8765。执行命令为 `.venv/Scripts/python.exe scripts/reading-acceptance.py --backend apps/desktop/src-tauri/binaries/papervault-backend-x86_64-pc-windows-msvc.exe --models .cache/models --pdf tests/fixtures/academic.pdf --report artifacts/reading-reparse-frozen-v02.json`。冻结后端SHA-256为 `40f03cbfe81ad7ab701680627cf9e777dc5903f7d0c377537985babbf0ac8b8a`。

该验收首次真实解析19.996s、重新解析14.391s、总计38.176s，确认产生不同job和自动revision。通过API创建单段高亮、跨页高亮、页书签、区域笔记与论文笔记，再分别人工修改到version 2。文本矩形来自真实PDF文本索引，区域笔记引用实际提取图框。重新解析前后以及真实ZIP备份恢复后，5条记录的**全部字段、版本、位置和时间戳**严格相等，阅读状态全部字段也相等，笔记FTS每阶段命中5/5。JSON导出逐记录核查，Markdown三次内容哈希相同；原PDF与各阶段API读取副本SHA-256均为 `a77a692de65dfc76c9c0252dfde57e5c742e470db0d9639d495e5f7893e75386`。数据、导出路径、引擎、job、revision和备份哈希详见该报告。没有SyntheticParsedDocument或直接构造数据库行替代实际解析。

本轮完整后端日志保留11条上游弃用警告；未输出access violation/fatal诊断。此前原生偶发记录仍保留，不能据本次成功推断原因已经解决。

### 0.2 浏览器与原生证据分别覆盖什么

`reader-upgrade.spec.ts`的5项中，4项在测试页面挂载真实生产PdfViewer并提供真实fixture PDF字节，测试字形/选择/查找、坐标、适配和快捷键；这4项不声称运行了完整库或解析任务。第5项使用完整界面和真实本地API，创建跨页高亮与区域笔记，保存页码/锚点/125%缩放/90度旋转，刷新后回读并比较位置。另1项 `reader-performance.spec.ts` 使用81页真实生成PDF，测试极端渲染和跨页选择。memo优化后两文件合跑命令：`npx playwright test e2e/reader-performance.spec.ts e2e/reader-upgrade.spec.ts --workers=1 --reporter=list --output=../../artifacts/reader-memo-regression`，6 passed，38.8s。优化后标注索引/选区/几何定向3文件12单元也通过，这12项是完整47项中的子集，不另加总。

24组字形测量覆盖DPR1/2、4种原生旋转及50%/100%/200%缩放，保留CropBox/UserUnit。阅读恢复误差按实际PDF锚点核查。浏览器deviceScaleFactor仿真与Windows系统显示缩放是两种不同验证，本轮没有更改宿主系统DPI。

工作台5项实际UI/API测试覆盖标签去重、键盘历史、会话/筛选恢复、图库第二页/滚动/焦点、迟到论文响应隔离，以及元数据/目录/资源保存守卫。笔记2项测试覆盖创建、标签/颜色、真实409冲突、搜索、浏览器JSON下载、返回原文、删除恢复和预填区域笔记关闭保护。阅读冲突专项验证“保存当前位置”保留完整本地视图、“采用已保存记录”实际移动PDF。导出/书签2项验证导出前先处理脏表格并使用已保存单元格，以及先保存书签编辑再删除、撤销后仍保留新内容。失败注入只延迟真实GET或让一次保存返回503，不注入成功响应。

原有7条回归在 `PAPERVAULT_E2E_REQUIRE_PARSE=1` 下通过，覆盖真实导入、Docling资源、裁剪、表格导出、目录/参考文献、元数据草稿、完整备份恢复及DPR2几何；精确命令和用例耗时见 `artifacts/legacy-regression-v02/report.json`。图库第201项检查采用共享真实裁剪PNG的合成资源元数据，不能算解析准确性样本。

专用原生关闭验收使用实际Tauri调试程序和WM_CLOSE，分别确认继续编辑不关窗口、保存后关闭并重启回读、放弃不覆盖已保存内容，以及退出后侧边服务端口关闭。证据 `artifacts/native-close-guard/report.json`。已安装A789候选另验证真实旧冻结后端生成的0001库迁移、PDF/metadata原哈希保持、页码书签、同ID恢复副本切换清空旧编辑/撤销对象、旧scope延迟请求409、笔记创建编辑搜索删除恢复和干净退出；其中JSON/Markdown通过安装版后台API导出，不冒称系统另存为对话框已测。

已解决的实际失败包括：回调混入只读字段导致422、选区多余coordinate字段、仅缩放冲突误用远端页码、采用远端但未移动阅读器、textarea改变label查询、恢复副本残留旧撤销对象、同一目录目标再次点击不定位，以及未保存表格直接导出旧值。旧失败截图与被替代候选留作诊断，不将它们混作最终成功证据。

### 0.2 视觉与标注性能

44张真实数据截图覆盖两种主题与1440×1000/1280×800，紧凑中性灰布局未新增宣传卡片；随后对reader/workspace方向键焦点、Home/End、手动激活和tabpanel关系补2张截图复验。特殊字符笔记以文本呈现，没有脚本节点。记录位于 `artifacts/ui-review-v02/review.json` 与 `artifacts/ui-review-v02-keyboard/review.json`；这些视觉运行允许真实阅读状态自动保存，禁止修改论文、资源与笔记正文。

极端PDF测试使用81页/800%/DPR2。每页限制16,777,216像素和8192最长边，实测同时存在位图总峰值33,544,800像素，RGBA估算134,179,200字节（约128MiB）。**完整浏览器进程树**抽样工作集峰值1,261,379,584字节（约1.17GiB），不能把画布预算说成浏览器内存上限。跨8页选择保留80个矩形。报告 `artifacts/reader-performance/report.json`。

1000条笔记性能实验明确为合成负载：1份真实academic.pdf、800条高亮和200条区域笔记、每条3个矩形；无真实用户论文或解析准确率声明。生产dist从磁盘加载，API请求转发至独立真实后端，保持共享库不变。优化前后报告分别在 `artifacts/annotation-benchmark/before/report.json` 与 `after/report.json`。

| 指标 | 优化前 | 优化后 |
|---|---:|---:|
| 1000条标注持续滚动主线程工作占比 | 70.84% | 13.42% |
| 0条标注同机基线主线程工作占比 | 7.96% | 3.71% |
| 优化后1000条滚动帧间隔p95 | — | 16.8ms |
| 优化后持续滚动最大长任务 | — | 0ms |

占比定义为CDP `TaskDuration / 该阶段墙钟时长`，**不是整机CPU利用率**。优化前虽然约60fps，主线程负载仍明显偏高，因此没有以帧率通过掩盖问题。改动为按页索引、稳定输入、PDF页/标注层memo、近视口挂载标注，以及阅读保存队列仅在错误/状态/dirty变化时通知父界面。优化后生产入口为 `index-Bi9K65xx.js`，SHA-256 `96c3541eea34dabb90e1655d5dd08da9ef76fa336df3ae433e92c48ee0c77f0b`；本机预先声明的延迟门槛通过，无JS/API错误。这些数值不保证低端机表现，性能数值来自生产构建浏览器测量；最终安装版另验证加载同一入口与新工作流，未把浏览器压力指标冒称安装版重新测量值。

### 0.2 最终Windows交付

最终安装器 `PaperVault_0.2.0_x64-setup.exe` 为536,385,237字节（511.54 MiB），SHA-256 `8b701f4e91dbdf25e551098feab219fb6989cd65d4c9ee60d4c3e741c9fbf761`。源版本 `131c0a0ae69fc27a930bfb8f82b05ffd1b255941` 包含性能代码与随包文档/资源映射。实际安装应用SHA为 `4c703df07bfef6ad11c170f2bcf4a6593f430f97d8f12ae18344d385deaeb661`，后台SHA保持40f03cbf…；WebView实际加载 `index-Bi9K65xx.js`。

基础原生验收完成真实CPU解析1图1表、PDF区域定位、目录/参考修改、自动元数据刷新与草稿保护；关闭后应用PID29092退出且已鉴权后台39393端口关闭。阅读专项8阶段全部通过：真实0001旧库迁移、同目录项两次重新定位、页码/书签保存、同ID不同路径副本切换、迟到旧scope请求409、笔记创建编辑搜索删除恢复与实际JSON/Markdown API导出、真正的Windows保存窗口取消、窗口和后台清理。取消用例确认0成功提示、0文件、笔记全部字段不变。

安装后逐个核对11项显式随包文档/声明/清单、846个许可证文件与7个源码归档。保留A789与942F两个先前候选，最终报告不是其passed字段的复制。manifest记录构建时还有脚本/证据待提交，产品源码和资源对应上述固定commit。

最后原生测试曾出现两项harness问题：只认品牌就点击导航，早于实际库恢复；以及功能通过后TemporaryDirectory删除仍在刷盘的WebView缓存导致WinError32。脚本改为等待精确库路径和工作区，保留唯一fixture/profile；写成功报告前验证所属应用进程与后台退出。原失败分别归档 `artifacts/install-initialization-race`、`artifacts/install-profile-cleanup-race`，最终完整复验exit0。没有关闭产品保护或忽略仍在运行的应用来通过测试。

父goal于2026-10-09 11:31:54 UTC的工具快照：`createdAt=1791524296`（05:38:16 UTC）、`timeUsedSeconds=21218`，即5小时53分38秒，超过18,000秒要求。原始工具结果保存在 `docs/verification/0.2.0/goal-final-v02.json`；实际开发、修复、性能对照与安装验收均有相应记录。

干净Windows VM、实际调整宿主系统DPI、另一台机器与托管CI仍未验证；安装器未签名。0.1.x卸载保留实验属于历史证据，不自动算作0.2已经复跑。历史原生异常诊断说明继续保留在下方与 `native-exception-investigation.json`。

## 0.1.0 阶段结果（历史记录，非0.2最终结论）

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

## 0.1.0 Windows交付
安装包 `PaperVault_0.1.0_x64-setup.exe`：536,330,353字节（511.48MiB），SHA-256 `B2466D9F245F4DE016EE3FC578FB736F107BE7B53808053FE30382573626C6F3`。

最终安装后的真实Tauri程序自动启动包内后台，验证未认证访问401、中文目录、各主导航、真实CPU解析1Figure/1Table、PDF.js高亮、章节/参考编辑，以及解析完成后自动字段刷新与未保存备注保护。846个许可证文件和7个源代码归档逐个安装哈希通过。实际执行卸载及重装，独立库的原PDF、托管PDF、metadata.json、数据库SHA保持，SQLite完整性通过。程序现重新安装于项目测试目录，可双击运行。

证据：artifacts/installed-desktop/report.json、install-layout.json、uninstall-retention.json；最终可审查快照保存在docs/verification。安装器未签名。本机含开发工具，因此不把这些结果宣称为干净VM验收；实际宿主系统DPI变更、另一台机器、托管CI仍未验证。

一次组合测试曾打印两条Windows原生access violation诊断，但进程exit0且70项全部通过。保持faulthandler开启后的35项分组、70项完整详细输出、70项原默认捕获模式三次受控复验均未再出现该诊断。CPython的Windows vectored handler会打印后继续交由其他处理器，故不能仅凭这行文字判断进程终止；目前缺少故障DLL/地址及C栈，原因未定位，也不认定为无害CPU探测。应用按单PDF独立worker运行，源码/冻结/原生队列流程验证均通过。保留此历史偶发记录与artifacts/native-exception-investigation.json，未通过禁用诊断或改写结果掩盖问题。


## 0.1.1 UI回归（2026-10-09）

本次修改界面和桌面版本，Python业务与冻结后端未改。16项前端单元测试通过，TypeScript检查与Vite生产构建通过。第一次在受限沙箱运行Vitest曾因临时SSR文件ENOENT加载失败，在正常Windows执行环境复验16项全部通过；该失败未当作通过记录。

`scripts/ui-review.mjs`对已有真实测试PDF及其持久化资源执行只读浏览，生成26张截图（`artifacts/ui-review`）：覆盖浅/深色、1440×1000和1280×800、论文列表、PDF/目录、图片/表格库、表格详情、搜索结果、任务、设置，以及侧栏折叠后刷新。严格断言折叠宽度56px并验证展开/主题持久化。截图已目视检查；0个JS错误、请求失败、坏图或主内容横向溢出。图库中的几何标注和人工裁剪均是测试数据，不冒充真实论文集合。证据快照：`docs/verification/ui-review-review.json`。

本次7条Playwright业务用例最终全部通过（首轮6 passed、1 failed；备份textbox精确名称因同Field按钮文案而不匹配，调整为名称前缀后仅重跑该条，1 passed）。测试未mock API，覆盖真实导入、裁剪定位、PNG/CSV/HTML导出、表格人工修改、标签收藏夹、备份恢复、目录编辑、元数据刷新和DPR2几何。跨200项资源分页专项使用明确合成测试库，不计为真实论文解析准确性验收。命令、每次结果和环境见docs/verification/ui-redesign-regression.json。

0.1.1 Windows安装包536,327,787字节（511.48MiB），SHA-256 `E2C608C6341E0F3A92DB6494EFDAE3E86F0529D01F2D8B9F53283F18C0A38AC0`。复用已验证且源码无变化的冻结Python后端，重建Tauri 0.1.1并重新嵌入前端。项目测试目录内实际升级安装后，通过真实WebView2验证原生版本号0.1.1、内置后端鉴权、CPU解析1Figure/1Table、PDF区域高亮、解析后字段刷新/未保存备注保护、目录和参考文献修改持久化。846个许可文件与7个源码归档在安装目录逐个SHA校验通过；实际截图见`artifacts/installed-desktop`。

本次安装测试在同一台含开发工具的Windows主机执行，未宣称干净VM或托管CI通过。安装器未签名。0.1.0的卸载/重装保留证据继续保留，本次0.1.1未重复执行；release-manifest通过独立字段标识先前版本证据，避免混同本次测试范围。
