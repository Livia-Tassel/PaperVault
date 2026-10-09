# PaperVault 0.2.1

生产源码：`3d9988bd1e9d69cc78c7abe4bcb4b08d24d46fa2`。此版修复出版PDF的内部输出标识误当论文标题，依赖、模型和数据库schema未变。

- [安装包与源码绑定](release-manifest.json)、[安装文件校验](install-layout.json)。
- [实际安装后的原业务](installed-desktop/report.json)、[迁移与阅读笔记](installed-reading/report.json)。
- [新冻结后台真实两篇](real-papers/frozen-backend-report.json)、[标题修复前后对照](real-papers/title-fix-comparison.json)。
- [实际安装窗口真实两篇](real-papers/installed-native/report.json)、[正确标题截图](real-paper-reader.png)。

新后台SHA567bc425…；安装器SHA12b4e697…，536,387,791字节。旧0.2.0的七篇基线和人工质量检查在`../real-corpus`，模型结构/符号限制仍存在，详见`docs/REAL_PAPER_TESTS.md`。未签名、干净VM/托管CI/本次卸载保留仍未验证。
