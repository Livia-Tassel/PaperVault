# 开发指南

当前完整桌面构建流程面向 Windows x64。工具准备和安装包构建从 [README](../../README.md#windows-自行打包)开始；以下命令均在仓库根目录执行。

## 桌面调试

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev-desktop.ps1
```

Tauri 启动 Vite 和 Python Sidecar，每次启动生成独立访问令牌。模型权重单独保存在本地，首次使用通过设置下载或导入。

## 浏览器调试

在两个 PowerShell 窗口分别启动后端与前端：

```powershell
# 窗口 1：后端，默认端口 8765
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev-backend.ps1
```

```powershell
# 窗口 2：Vite，默认端口 1420
npm run dev --prefix apps/desktop
```

打开 `http://127.0.0.1:1420`。浏览器模式使用本机开发令牌 `dev-token`，开发配置位于 `.test-data/dev-config/`；开发服务仅供本机调试。

## 常规检查

```powershell
# 文档链接：标准库即可运行，不需要安装项目依赖
python scripts/check-doc-links.py

# 后端静态检查与无需真实模型的测试
.venv\Scripts\python.exe -m ruff check backend tests scripts
.venv\Scripts\python.exe -m pytest tests -m "not real_parser" -q

# 前端类型、单元测试与生产构建
npm run typecheck --prefix apps/desktop
npm test --prefix apps/desktop
npm run build --prefix apps/desktop
```

### 真实解析与端到端

真实模型测试要求解析依赖和校验完成的模型目录。运行完整后端测试前设置：

```powershell
$env:PAPERVAULT_TEST_MODELS = (Resolve-Path .cache\models).Path
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
.venv\Scripts\python.exe -m pytest tests -q
```

Playwright 测试的后端、库与模型前置条件见[配置](../../apps/desktop/playwright.config.mjs)及对应 `e2e/` 用例。前端目录中执行 `npx playwright install chromium` 后，可用 `npm run test:e2e --prefix apps/desktop` 运行；不同并行验收使用各自的报告目录。

冻结后台、完整安装及阅读笔记验收分别使用[脚本索引](../../scripts/README.md)中的工具。Windows 打包细节见[构建指南](../WINDOWS.md)，历史结果见[验证索引](../verification/README.md)。

## API 类型生成

启动浏览器调试后端后执行：

```powershell
npm run api:generate --prefix apps/desktop
```

该命令从真实后端 OpenAPI 生成 `apps/desktop/src/api.generated.ts`。使用其他端口或令牌时，设置 `PAPERVAULT_API_URL` 与 `PAPERVAULT_API_TOKEN`。

## 目录与生成文件

产品界面在 `apps/desktop/src/`，桌面进程管理在 `apps/desktop/src-tauri/src/`，后端业务与迁移在 `backend/papervault/`。组件职责见[架构](ARCHITECTURE.md)，历史选择见[技术决策](DECISIONS.md)。

现有构建和验收脚本从自身位置解析仓库根目录，因此 `scripts/` 保持固定路径。依赖、冻结后端、安装包、模型、临时库和完整测试输出均位于 Git 忽略目录。已归档的验证文件保留原始版本、运行环境与字节哈希。
