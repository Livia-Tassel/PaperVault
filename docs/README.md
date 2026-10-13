# 文档导航

新用户可以先读[项目主页](../README.md)，再按目标选择下方文档。

## 使用与构建

| 文档 | 内容 |
| --- | --- |
| [用户指南](USER_GUIDE.md) | 导入、阅读、笔记、图表、搜索与备份 |
| [Windows 构建](WINDOWS.md) | 构建环境、NSIS 打包、安装验证与排错 |
| [发布与下载](RELEASES.md) | 安装包去向、校验与当前发布状态 |
| [已知问题](KNOWN_ISSUES.md) | 解析边界、验证限制与后续方向 |
| [演示说明](DEMO.md) | 演示内容、字幕、素材署名及本机复现 |
| [版本变更](../CHANGELOG.md) | 各版本的主要变化 |

## 开发与接口

| 文档 | 内容 |
| --- | --- |
| [开发指南](development/README.md) | 桌面与浏览器调试、测试命令、API 类型生成 |
| [架构](development/ARCHITECTURE.md) | 组件边界、持久化、搜索、阅读与笔记 |
| [技术决策](development/DECISIONS.md) | 引擎、进程隔离、迁移与渲染选择 |
| [本地 API](API.md) | 回环服务、鉴权与业务接口 |
| [阅读与笔记 API](READING_API.md) | 阅读状态、标注、冲突与导出 |
| [数据格式](DATA_FORMAT.md) | 库目录、数据库、自动结果与人工修改 |
| [0.2 升级](UPGRADE_0_2.md) | 数据迁移和阅读工作台验收 |
| [贡献指南](../CONTRIBUTING.md) | 问题反馈、修改与验证要求 |
| [脚本索引](../scripts/README.md) | 构建、验收、样本、性能与演示工具 |

## 验证与来源

- [验证索引](verification/README.md)与[总测试报告](verification/TEST_REPORT.md)：按版本和执行层查看结果。
- [原 7 篇真实论文报告](REAL_PAPER_TESTS.md)与[扩展 20 篇报告](EXPANDED_PAPER_TESTS.md)：逐篇质量与未解决问题。
- [测试样本](../tests/corpus/README.md)：来源、许可与下载复现。
- [第三方声明](THIRD_PARTY_NOTICES.md)与[MPL 源码说明](MPL-SOURCE-NOTICE.md)：依赖许可和随包源码。
- [历史档案](archive/README.md)：原始项目需求与开发进度。

`verification/` 保留紧凑证据，`third-party-licenses/` 和 `third-party-sources/` 保留随包许可与源码归档。本机生成的安装器、模型、完整解析输出和演示视频不随 Git 克隆下载。
