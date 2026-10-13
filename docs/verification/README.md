# 验证记录

[总测试报告](TEST_REPORT.md)区分源码测试、浏览器测试、冻结后端与实际安装验收。记录中的版本、来源哈希和执行范围各自独立，不将一次本机成功推算为所有系统或所有 PDF 都通过。

## 按版本查看

| 版本 | 主要证据 |
| --- | --- |
| 0.2.2 | [交付清单](0.2.2/release-manifest.json)、[安装文件校验](0.2.2/install-layout.json)、[构建日志](0.2.2/build-installer-final.log)、[安装后流程](0.2.2/installed-desktop/report.json)、[阅读笔记](0.2.2/installed-reading/report.json) |
| 0.2.1 | [版本说明](0.2.1/README.md)、[交付清单](0.2.1/release-manifest.json)、[真实论文安装验收](0.2.1/real-papers/installed-native/report.json) |
| 0.2.0 | [版本说明](0.2.0/README.md)、[交付清单](0.2.0/release-manifest.json)、[升级审计](0.2.0/upgrade-audit.json) |
| 0.1.x | [早期交付清单](release-manifest.json)、[卸载保留](uninstall-retention.json)、[界面回归](ui-redesign-regression.json) |

## 按主题查看

- 真实论文：[原 7 篇说明](real-corpus/README.md)、[扩展 20 篇质量汇总](expanded-corpus/quality-summary.json)；人工结论见[原 7 篇报告](../REAL_PAPER_TESTS.md)和[扩展报告](../EXPANDED_PAPER_TESTS.md)。
- 0.2.2 专项：[冻结后台流程](0.2.2/expanded-corpus/frozen-report.json)、[附录编号](0.2.2/expanded-corpus/caption-number-validation.json)、[原生窗口](0.2.2/expanded-corpus/native/report.json)。
- 性能：[搜索](search-benchmark.json)、[图库](gallery-benchmark.json)、[阅读器](0.2.0/reader-performance/report.json)、[标注规模](0.2.0/annotation-benchmark/report.json)。
- 演示：[当前素材署名](demo-v2/SOURCES.md)、[字幕](demo-v2/PaperVault-demo-v2-zh.srt)、[编码检查](demo-v2/main-render-report.json)、[视觉核对](demo-v2/visual-review.json)。

## 本机结果与 GitHub CI

历史安装记录来自含开发工具的 Windows 主机；干净 Windows VM、代码签名及跨平台安装包没有通过记录。GitHub 上的最新执行状态以 [Windows Actions](https://github.com/Livia-Tassel/PaperVault/actions/workflows/windows.yml) 为准，下载与构建状态见[发布说明](../RELEASES.md)。

原始 JSON、日志、截图与来源文件可能参与交付哈希校验，整理仓库时保留其字节与路径。文档中的 `D:\project\PaperVault\...`、`artifacts/` 和 `.test-data/` 是记录产生时的本机路径；安装器、模型及完整解析输出不在源码仓库中。
