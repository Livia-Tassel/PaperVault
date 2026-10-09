# 真实论文回归样本

来源清单记录官方来源、版本、开放许可、作者、页数与PDF SHA-256。根目录三份 `sources-*.json` 是原7篇71页；`expanded/`三份来源清单新增20篇243页。累计27篇不同论文、314页。PDF保存在忽略的 `.test-data/external/`，不混入自建的 `tests/fixtures`；下载器默认递归读取所有来源清单，可用 `--manifest` 缩小范围。

```powershell
.venv\Scripts\python.exe scripts\download_real_corpus.py
.venv\Scripts\python.exe scripts\download_real_corpus.py --verify-only
$CorpusRelease = Get-Content docs/verification/0.2.2/release-manifest.json -Raw | ConvertFrom-Json
.venv\Scripts\python.exe scripts\test_real_corpus.py --manifest 'tests/corpus/expanded/sources-*.json' --expect-version $CorpusRelease.version --expect-sha256 $CorpusRelease.backend_sha256 --dpi 300 --exercise-copy --report artifacts/corpus-new-run/report.json
```

测试runner的旧默认值固定0.2.0后台SHA，避免静默替换原始71页基线。上面命令通过发布清单显式选择新安装版；使用其他后台路径时还须传 `--backend`。总是使用新的 `--report` 路径，不覆盖旧结果。`--existing-report`仅重验已解析内容及独立副本，不会悄悄重跑模型。新运行会产生新UUID，需要重新核对输出，不能直接套用旧人工质量判定。`scripts/report_real_corpus.py`仅组合已经审核的原7篇基线；新增20篇的基线明确固定0.2.1，0.2.2 SimCSE编号修复验证单独保存。

原20篇保留为五批独立测试库。输入快照在 `artifacts/real-corpus-expanded/input-batches/`，原始报告在同目录的 `batches/`；完整证据保存后可运行以下汇总，命令本身不重新解析PDF：

```powershell
.venv\Scripts\python.exe scripts\summarize_expanded_corpus.py --require-complete
.venv\Scripts\python.exe scripts\summarize_expanded_quality.py
.venv\Scripts\python.exe scripts\render_expanded_review.py
```

`worker_observer.py`在自有worker仍存活时取得Windows句柄，记录实际退出码；未知或未观察到的进程不会被当作退出0。20篇本轮均捕获正常退出，不据此推断内容准确或以前的原生诊断已解决。

`ground-truth-*.json` 为逐页看原文后独立记录的图表参照，不由解析结果反推。每个有编号的完整Figure/Table为一个逻辑对象，多子图计一个Figure，PRISMA跨页Table 1计一个Table。截图内部的嵌套论文图表、出版logo与另附补充材料分别标记，不伪装成额外科研对象。

人工检查分开记录区域完整性、图注关联、表格结构与预定单元格。原文PNG完整不代表CSV/HTML正确，抽查单元格通过也不代表整张表正确。原7篇的全部原页、54资源导出、复核JSON和对照页位于 `artifacts/real-corpus/`，结论见 [原7篇报告](../../docs/REAL_PAPER_TESTS.md)。

新增20篇保留243原页和226资源导出，6篇深审、14篇只核图表清单；后者的裁剪/单元格未审字段保留null，不计作通过。深审6篇预先选定60单元格，不以选定样本推算全表准确率。包含中文的英文论文不冒称全中文论文。来源替换/未选候选/访问失败保留在 `expanded/diverse-access-attempts.json`。逐篇结果见 [新增20篇报告](../../docs/EXPANDED_PAPER_TESTS.md)。

论文及其中原文内容保留出版方/作者的各自开放许可；引用与派生页面渲染的来源归属见各manifest。2012年PLOS原文只明确CC BY，未把不明的许可证版本推断为4.0。下载器核验既有文件、不覆盖哈希不符的PDF，不上传论文。
