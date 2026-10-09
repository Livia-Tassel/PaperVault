# Windows 构建与排错

## 环境
Windows x64、Python3.12、Node.js24、Rust x86_64-pc-windows-msvc、微软C++ Build Tools及Windows SDK。项目内开发依赖不要求安装版用户自行安装。

`scripts/bootstrap-windows.ps1` 提供工具准备。Rust可位于项目 `.tools`，构建脚本会查找MSVC安装。

## 打包
运行 `scripts/package-windows.ps1`。它先构建React，再以 `scripts/backend.spec` 生成Python onedir文件夹，并使用Tauri NSIS配置生成当前用户安装包。不要拍平 `_internal` 目录，否则Torch、Python DLL及包数据无法加载。

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
