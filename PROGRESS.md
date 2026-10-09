# PaperVault 开发进度

## 当前任务
2026-10-09：P0/P1主要功能与Windows本机交付验收完成。最终安装包511.48MiB，已实际安装、卸载验证数据保留、重装并复验。源码与冻结后台完整验收分别使用原创PDF和公开9页学术论文通过。

## 阶段清单
- [x] 1 基础工程、桌面与后端通信、Sidecar烟测
- [x] 2 Docling真实结构化解析与模型管理
- [x] 3 Figure提取、原始JPEG保留与人工裁剪
- [x] 4 Table导出、合并表头与编辑
- [x] 5 论文库、批量导入、去重、标签收藏
- [x] 6 PDF.js定位与高亮
- [x] 7 全局Figure/Table图库
- [x] 8 中英全文搜索与增量更新
- [x] 9 任务恢复、备份恢复与可靠性
- [x] 10 Windows安装交付（本机验证；干净VM未验证）
- [x] 11 P1补齐、回归与性能测量
- [x] 12 体验完善、用户文档和最终报告

## 分工
主代理：存储、API、任务、测试、集成与交付记录。
解析代理：Docling、PDFium、模型管理、合法PDF样本。
界面代理：React完整用户流程与PDF.js。
桌面代理：Tauri运行时、构建工具、打包与Windows流水线。

## 已知问题/验证
最终70项后端回归通过（其中5项使用真实Docling离线CPU），16项前端单元测试通过。原业务流程、目录编辑/分页、元数据刷新和DPR2几何的真实UI专项均通过。

修复：FastAPI工作线程取得的论文库锁必须使用非线程局部FileLock，保证生命周期线程退出时正确释放。

Rust/MSVC/SDK已安装；Tauri release及冻结后台已实际运行。Docling模型384MB已校验并固定SHA。最终安装包与安装后全流程验收通过。

已修复：stdin控制管道下Windows multiprocessing启动停滞（改显式worker子进程）；日志句柄阻塞Windows目录发布；多段PNG仅导出首段；导出结构JSON/manifest旧引用；自选备份.zip误当目录；删除与备份竞争；非UTF-8冻结解释器控制通道乱码。

性能：1000篇/5000资源的明确合成负载，分组搜索P95=106.550ms，30项图库分页P95=22.694ms。原创2页真实PDF导入+解析+发布20.121秒，后台及worker峰值RSS约1.16GiB。机器与方法详见测试报告。

补充验证：DPR2几何16个UI场景最大误差0.009375 CSSpx；Excel16.0实际只读打开CSV通过；三篇真实队列取消/失败隔离/重试通过。最终更新安装、卸载及重装保留数据验证通过。

最终结果：70项后端测试（含5项真实离线Docling）通过；16项前端单元通过；实际浏览器与安装后Tauri流程均通过，包括解析时未编辑字段刷新/未保存备注保护。846个许可证文件、7个MPL源码归档在安装目录逐个SHA验证。卸载及重装后的原件、托管PDF、metadata、DB哈希与SQLite完整性保持。

## 交付与后续
- 安装包：apps/desktop/src-tauri/target/x86_64-pc-windows-msvc/release/bundle/nsis/PaperVault_0.1.0_x64-setup.exe。
- 已安装可执行：.test-data/installed/PaperVault/papervault.exe；测试开发服务1420/8765/8766均已关闭。
- 离线模型：.cache/models；原始验收证据artifacts，最终快照docs/verification。
- 尚未验证：无开发工具的干净Windows VM、实际调整Windows系统DPI、托管Windows CI执行。CI配置已提供，未上传仓库或假称CI运行成功。
- 历史偶发：一次组合测试打印原生access violation诊断但exit0，三次受控复验未重现；原因未定位，记录见TEST_REPORT，不屏蔽诊断。
- P2后续：高级OCR、AI语义检索、跨平台安装包等；不参与本次P0/P1交付声明。

测试运行注意：受限Windows沙箱阻止asyncio创建本地socketpair，API测试需要允许本机回环连接；不是应用离线依赖。
