# PaperVault 开发进度

## 当前任务
2026-10-09：核心功能与P1实现完成，正在验证冻结后台、真实Tauri窗口与NSIS安装包。源码完整验收已分别使用原创PDF和公开9页学术论文通过。

## 阶段清单
- [ ] 1 基础工程、桌面与后端通信、Sidecar烟测
- [x] 2 Docling真实结构化解析与模型管理
- [x] 3 Figure提取、原始JPEG保留与人工裁剪
- [x] 4 Table导出、合并表头与编辑
- [x] 5 论文库、批量导入、去重、标签收藏
- [x] 6 PDF.js定位与高亮
- [x] 7 全局Figure/Table图库
- [x] 8 中英全文搜索与增量更新
- [x] 9 任务恢复、备份恢复与可靠性
- [ ] 10 Windows安装交付
- [ ] 11 P1补齐、回归与性能测量
- [ ] 12 体验完善、用户文档和最终报告

## 分工
主代理：存储、API、任务、测试、集成与交付记录。
解析代理：Docling、PDFium、模型管理、合法PDF样本。
界面代理：React完整用户流程与PDF.js。
桌面代理：Tauri运行时、构建工具、打包与Windows流水线。

## 已知问题/验证
2026-10-09：64项非模型回归通过；另新增非UTF-8宿主下中文Sidecar路径测试通过。解析组30项测试通过，其中5项使用真实Docling离线CPU。React8项测试及3条真实浏览器E2E通过。

修复：FastAPI工作线程取得的论文库锁必须使用非线程局部FileLock，保证生命周期线程退出时正确释放。

Rust/MSVC/SDK已安装；Tauri release主程序已编译。Docling模型384MB已校验并固定SHA。真实source sidecar全流程通过；冻结后台正补齐实际运行发现的包数据，安装包尚未最终验收。

已修复：stdin控制管道下Windows multiprocessing启动停滞（改显式worker子进程）；日志句柄阻塞Windows目录发布；多段PNG仅导出首段；导出结构JSON/manifest旧引用；自选备份.zip误当目录；删除与备份竞争；非UTF-8冻结解释器控制通道乱码。

性能：1000篇/5000资源的明确合成负载，分组搜索P95=106.550ms，30项图库分页P95=22.694ms。原创2页真实PDF导入+解析+发布20.121秒，后台及worker峰值RSS约1.16GiB。机器与方法详见测试报告。

测试运行注意：受限Windows沙箱阻止asyncio创建本地socketpair，API测试需要允许本机回环连接；不是应用离线依赖。
