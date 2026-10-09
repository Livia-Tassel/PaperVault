# Windows 构建与排错

## 环境
Windows x64、Python3.12、Node.js24、Rust x86_64-pc-windows-msvc、微软C++ Build Tools及Windows SDK。项目内开发依赖不要求安装版用户自行安装。

`scripts/bootstrap-windows.ps1` 提供工具准备。Rust可位于项目 `.tools`，构建脚本会查找MSVC安装。

## 打包
运行 `scripts/package-windows.ps1`。它先以 `scripts/backend.spec` 生成Python onedir文件夹，再由Tauri构建React与Windows程序并生成当前用户NSIS安装包。仅当前冻结后端与源码哈希一致时可用 `-SkipBackend`，不要将旧0.1.x后端与0.2界面混装。不要拍平 `_internal` 目录，否则Torch、Python DLL及包数据无法加载。

模型在首次使用时下载或从离线目录导入，安装后已有论文阅读与库管理不依赖在线模型服务。Model manifest记录下载revision与每个文件的SHA-256。

## 实测层次
1. Python源代码后台：`scripts/package-smoke.py --source --backend .venv/Scripts/python.exe`。
2. 冻结后台：同一脚本传入打包后的后台EXE。
3. 真实桌面：`scripts/package-desktop-smoke.py` 使用WebView2驱动真实Tauri窗口。
4. 完整解析：`scripts/acceptance.py --backend <冻结后台exe> --models <模型目录>`。
5. NSIS安装及干净Windows机器验证另记报告。

## 常见问题
- **启动时后台未就绪：**检查后台日志、安装目录中的EXE/_internal相对位置、Python DLL和被遗漏的原生库。
- **模型无法下载：**界面可重试，或从另一台电脑导入完整模型目录；不要仅复制权重文件而遗漏配置/清单。
- **库被占用：**关闭正在使用同一库的另一个PaperVault实例。不要强行删除数据库或锁文件。
- **开发API测试挂起：**受限Windows执行环境可能阻止asyncio本地socketpair，测试需要允许本机回环连接。
- **未签名提示：**本项目当前未配置签名证书；核实本地构建来源和哈希后再决定安装，勿关闭系统安全软件。
- **中文路径：**启动与构建脚本使用路径参数和UTF-8；若第三方工具报路径问题，保留日志作为回归用例。

应用数据与安装目录分离。升级或卸载应保留论文库；数据库升级前应创建完整备份。

## 0.2 升级验收

`tests/fixtures/legacy-library-0001.zip` 是用真实旧冻结后端生成的原创测试库，不含模型或私有文献。对应JSON记录UUID、文件SHA与schema0001。安装验收可传 `-LegacyFixture` 运行旧库迁移和新阅读/笔记工作流，避免依赖开发机残留的旧版本EXE。

真实原生测试使用固定WebView2 `userDataFolder` 验证重启会话；默认WebDriver临时profile不能用于证明产品丢失会话。受控输入须发送实际键盘事件，直接改DOM value或对disabled候选项调用click不能代表用户编辑成功。

系统另存为窗口属于独立原生控件。跨进程读取文件名编辑框应发送 `WM_GETTEXT` 并设置超时；`GetWindowTextW`不能读取另一应用的Edit内容，返回空值不代表保存窗口异常。依据：[微软GetWindowTextW说明](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getwindowtextw)。测试必须只定位当前PaperVault进程拥有的窗口，取消后核查文件、提示和笔记内容。

并行Playwright使用各自的 `--output` 目录和list报告器，防止互相删除trace。Vite忽略测试报告和Rust目标目录，避免生成HTML报告时重载正在验收的窗口。
