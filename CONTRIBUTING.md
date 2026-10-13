# 参与改进

可以通过问题反馈、文档修正、测试复现和代码修改帮助改进 PaperVault。源码与第三方素材的许可分别见 [LICENSE](LICENSE) 和[第三方声明](docs/THIRD_PARTY_NOTICES.md)。

## 提交问题

先阅读[已知问题](docs/KNOWN_ISSUES.md)，再搜索已有 [Issues](https://github.com/Livia-Tassel/PaperVault/issues)。反馈时请提供：

- PaperVault 版本、Windows 版本，以及使用安装版还是源码运行。
- 可以重复执行的操作步骤、预期结果和实际结果。
- 相关错误日志与截图；涉及解析时，提供可公开分享的最小 PDF 样本及来源。

日志和截图可能包含论文内容、库目录或访问令牌，提交前请移除私人信息。无法公开原文时，可以描述排版特征或使用原创测试 PDF。

## 准备开发环境

[README 的 Windows 步骤](README.md#windows-自行打包)包含工具准备、依赖安装和打包命令。日常开发、浏览器调试与 API 类型生成见[开发指南](docs/development/README.md)。

## 修改与验证

从 `main` 创建自己的分支，每个 PR 聚焦一个问题。在 PR 中说明问题、修改后的行为、实际执行的验证，以及仍受环境限制的部分。

| 修改范围 | 建议检查 |
| --- | --- |
| Markdown 与目录链接 | `python scripts/check-doc-links.py` |
| Python 后端 | Ruff、对应 pytest 用例；数据库变更补迁移与恢复验证 |
| React / TypeScript | 类型检查、对应单元测试与生产构建；交互修改按需运行 Playwright |
| Windows 打包与 Sidecar | 冻结后台验证、NSIS 构建及实际安装验收 |

完整命令在[开发指南](docs/development/README.md)。文档修改无需重跑所有解析或安装测试；源码测试、浏览器测试和实际安装验证请分别记录。

## 仓库约定

- `apps/desktop/` 和 `backend/papervault/` 保存产品代码；现有脚本使用固定根目录，相互调用路径见[脚本索引](scripts/README.md)。
- 用户指南和 API 文档在 `docs/`；架构与开发说明在 `docs/development/`；原始需求和历史进度在 `docs/archive/`。
- 测试证据在 `docs/verification/`，按版本和主题归档。已记录的日志、JSON、截图及来源文件可能参与 SHA-256 校验，修正说明应新增记录，保留旧证据。
- `target/`、`build/`、`artifacts/`、`.cache/`、`.test-data/` 和 `node_modules/` 是本机生成目录，不提交安装包、模型权重或用户论文库。
- 新增 PDF fixture 应附来源与许可；真实论文下载依据 `tests/corpus/` 的来源清单。
- 更新依赖时同步相应锁文件和许可记录，不将机器上的未锁定依赖当作可复现环境。

对用户可见的行为变更请更新 [CHANGELOG.md](CHANGELOG.md)，操作步骤变化请同步[用户指南](docs/USER_GUIDE.md)。
