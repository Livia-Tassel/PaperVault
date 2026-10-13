# Windows 构建与排错

## 环境
Windows x64、Python **3.12 x64**、Node.js **24**、Rust `x86_64-pc-windows-msvc`、微软 C++ Build Tools 及 Windows SDK。项目内开发依赖不要求安装版用户自行安装。

先安装 Git、Python 3.12 和 Node.js 24，并确保命令在 PATH 中可用。完整桌面后端使用 Windows 的 Python 解释器与原生依赖，现有打包脚本不能直接在 macOS / Linux 上生成 Windows 安装器。

## 从源码构建

在 Windows PowerShell 中执行：

```powershell
git clone --depth 1 --single-branch https://github.com/Livia-Tassel/PaperVault.git
cd PaperVault
python --version
node --version

# 准备虚拟环境、锁定依赖和构建工具
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap-windows.ps1 -InstallToolchain

# 冻结后端、验证后端、构建前端 / Tauri，并生成 NSIS 安装器
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\package-windows.ps1
```

若已配置 Rust / MSVC / SDK，省略 `-InstallToolchain`。Rust 也可位于项目 `.tools`，构建脚本会查找 MSVC 安装。工具安装请求重启时，先完成重启，再回到仓库目录继续。

同时安装多个 Python 版本时，可先执行 `py -3.12 -m venv .venv`，保证脚本使用 `.venv\Scripts\python.exe` 中的 3.12 解释器。项目不接受 Python 3.13 或 3.14；Python 和 npm 依赖分别由 `requirements.lock` 与 `apps/desktop/package-lock.json` 固定。

成功产物（当前版本 0.2.2）：

```text
apps/desktop/src-tauri/target/x86_64-pc-windows-msvc/release/bundle/nsis/PaperVault_0.2.2_x64-setup.exe
```

可以查看文件并计算哈希：

```powershell
Get-Item .\apps\desktop\src-tauri\target\x86_64-pc-windows-msvc\release\bundle\nsis\PaperVault_0.2.2_x64-setup.exe
Get-FileHash -Algorithm SHA256 .\apps\desktop\src-tauri\target\x86_64-pc-windows-msvc\release\bundle\nsis\PaperVault_0.2.2_x64-setup.exe
```

该目录被 Git 忽略，克隆仓库不会下载安装器。公开下载与 Actions 产物的区别见[发布说明](RELEASES.md)。

## 打包
运行 `scripts/package-windows.ps1`。它先以 `scripts/backend.spec` 生成Python onedir文件夹，再由Tauri构建React与Windows程序并生成当前用户NSIS安装包。仅当前冻结后端与源码哈希一致时可用 `-SkipBackend`，不要将旧0.1.x后端与0.2界面混装。不要拍平 `_internal` 目录，否则Torch、Python DLL及包数据无法加载。

默认打包离线 WebView2 安装器。希望改为安装时下载 WebView2 时，运行 `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\package-windows.ps1 -OnlineWebViewInstaller`。

模型在首次使用时下载或从离线目录导入，安装后已有论文阅读与库管理不依赖在线模型服务。Model manifest记录下载revision与每个文件的SHA-256。

## 实测层次
1. Python源代码后台：`scripts/package-smoke.py --source --backend .venv/Scripts/python.exe`。
2. 冻结后台：同一脚本传入打包后的后台EXE。
3. 真实桌面：`scripts/package-desktop-smoke.py` 使用WebView2驱动真实Tauri窗口。
4. 完整解析：`scripts/acceptance.py --backend <冻结后台exe> --models <模型目录>`。
5. NSIS安装及干净Windows机器验证另记报告。

## 常见问题
- **冻结后台退出超时：**`package-smoke.py` 会关闭标准输入并等待后台退出。出现 `subprocess.TimeoutExpired` 时，打包在后端验证阶段停止，还没有生成 NSIS 安装器；保留退出阶段的日志再排查。首次 GitHub CI 发生过此问题，见[发布说明](RELEASES.md)，不应跳过验证来宣称构建成功。
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
