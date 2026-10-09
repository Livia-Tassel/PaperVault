# PaperVault 测试报告

## 当前结果（2026-10-09）

| 项目 | 状态 | 证据 |
|---|---|---|
| 存储、搜索、导出、备份单元与API集成 | 已通过测试 | pytest tests/unit tests/integration：28 passed，1.80s |
| 源文件保护与哈希去重 | 已通过测试 | 相同文件实体唯一，源与托管副本SHA-256一致 |
| 人工修正与重解析 | 已通过测试 | 唯一位置匹配复用资源，歧义保留待关联人工资源 |
| 中文单字/双字/混合搜索 | 已通过测试 | FTS5短语与原文高亮用例 |
| Python源代码Sidecar | 已通过测试 | ready、认证health、匿名拒绝、stdin EOF退出 |
| Docling真实PDF解析 | 开发与验证中 | 不以存储单元测试输入替代解析结果 |
| React/Tauri真实UI | 开发与验证中 | 待构建和桌面E2E |
| Windows安装包 | 尚未验证 | 工具链安装完成，打包进行中 |
| 干净Windows VM | 受环境限制未验证 | 不等同本机开发/打包运行 |

## 测试条件
Windows 11 x64；Python3.12.8；Node24.15；SQLite3.45.3含FTS5。后续准确性、资源性能和安装结果在实测后补充。

## 已解决问题
FastAPI跨线程关闭FileLock导致重启无法重新打开库：锁改为thread_local=False，加入重启集成用例并通过。

## 已知限制
Starlette当前TestClient提示httpx迁移弃用警告，不影响本轮测试结果。真实桌面/模型/安装结果完成前，不标记整体交付通过。
