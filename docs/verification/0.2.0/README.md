# PaperVault 0.2.0 本机交付证据

- [最终验收汇总](upgrade-v02-final.json)：功能范围、测试层次、时长与环境边界。
- [逐项独立审计](upgrade-audit.json)：对应升级方案的九项门槛。
- [安装器清单](release-manifest.json)与[安装文件校验](install-layout.json)：固定源码版本、安装器/应用/后台SHA-256及随包文档校验。
- [真实安装后PDF流程](installed-desktop/report.json)与[阅读笔记流程](installed-reading/report.json)：真实Windows窗口、内置后台、迁移、定位、系统另存为取消与退出清理。
- [后端117项](reading-backend-tests.json)、[前端47项与浏览器回归](frontend-release-v02.json)、[原业务回归](legacy-regression-v02/report.json)。
- [真实冻结后端重解析与备份恢复](reading-reparse-frozen-v02.json)：人工记录、原件和导出内容保持。
- [1000条合成批注前后对照](annotation-benchmark/report.json)：同目录before/after保留原始数据，不作为解析准确率。
- [真实安装窗口截图](reader.png)；使用原创合成PDF，未使用私人文献。
- [父任务时长原始工具快照](goal-final-v02.json)：21218秒，超过5小时门槛。

这些是同一台含开发工具的Windows主机记录。干净VM、实际修改宿主DPI、托管CI及本版卸载保留没有声明为通过；旧版本证据位于上层目录，未被本次结果覆盖。可复现命令和各次失败修复记录见仓库TEST_REPORT.md与scripts。
