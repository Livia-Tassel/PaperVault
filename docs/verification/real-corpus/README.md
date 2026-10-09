# 真实论文基线与人工核对

这组证据对应7篇真实论文、71页、已安装0.2.0后台（SHA40f03cbf…）。软件修复后的0.2.1产物在相邻版本目录，不能把两个版本的结果混成同一次运行。

- [质量汇总](quality-summary.json)：38个编号图表、60个预选单元格，以及错误/辅助图片的计数边界。
- [流程与文件检查](installed-backend-report.json)：7篇和54资源的实际API、导出、位置、备份与重启结果。
- [Docling报告逐项核对](quality-control.json)、[ML三篇](quality-ml.json)、[科学三篇](quality-science.json)：原文参照、实际资源ID、错误位置和检查范围。
- [文字层诊断](source-text-layer-diagnosis.json)：独立读取原PDF仍存在符号差异，未猜测改写单位。
- [原生窗口](native/report.json)：实际BERT和显微论文阅读、图表定位、笔记与重启。
- [原生异常调查](native-diagnostic-review.json)：组合测试再次出现诊断，定向复验未复现，根因仍未定位；保留日志和XML。
- [快照清单](snapshot-manifest.json)：原文件与归档文件的字节哈希。

源PDF和全部页面/导出PNG保留在本机`.test-data`与`artifacts/real-corpus`，不提交第三方PDF。独立标注、下载来源与许可见`tests/corpus`。完整中文结论见`docs/REAL_PAPER_TESTS.md`；不能把流程passed或选定单元格成功读成整篇内容准确。
