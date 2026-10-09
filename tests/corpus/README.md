# 真实论文回归样本

三份 `sources-*.json` 记录官方来源、版本、开放许可、作者、页数与PDF SHA-256。当前7篇共71页，包含原Docling报告与新增6篇真实论文。PDF保存在忽略的 `.test-data/external/`，不混入自建的 `tests/fixtures`。

```powershell
.venv\Scripts\python.exe scripts\download_real_corpus.py
.venv\Scripts\python.exe scripts\download_real_corpus.py --verify-only
$CorpusRelease = Get-Content docs/verification/0.2.1/release-manifest.json -Raw | ConvertFrom-Json
.venv\Scripts\python.exe scripts\test_real_corpus.py --manifest 'tests/corpus/sources-*.json' --expect-version $CorpusRelease.version --expect-sha256 $CorpusRelease.backend_sha256 --dpi 300 --exercise-copy --report artifacts/corpus-rerun/report.json
```

测试runner的旧默认值固定0.2.0后台SHA，避免静默替换原始71页基线。上面命令通过发布清单显式选择新安装版；使用其他后台路径时还须传 `--backend`。总是使用新的 `--report` 路径，不覆盖旧结果。`--existing-report`仅重验已解析内容及独立副本，不会悄悄重跑模型。新运行会产生新UUID，需要重新核对输出，不能直接套用旧人工质量判定。`scripts/report_real_corpus.py`仅组合已经审核的原始基线与对应质量文件。

`ground-truth-*.json` 为逐页看原文后独立记录的图表参照，不由解析结果反推。每个有编号的完整Figure/Table为一个逻辑对象，多子图计一个Figure，PRISMA跨页Table 1计一个Table。截图内部的嵌套论文图表、出版logo与另附补充材料分别标记，不伪装成额外科研对象。

人工检查分开记录区域完整性、图注关联、表格结构与预定单元格。原文PNG完整不代表CSV/HTML正确，抽查单元格通过也不代表整张表正确。全部原页、54资源导出、复核JSON和可筛选的原文/导出对照页位于 `artifacts/real-corpus/`。最终结论见 `docs/REAL_PAPER_TESTS.md`。

论文及其中原文内容保留出版方/作者的各自开放许可；引用与派生页面渲染的来源归属见各manifest。2012年PLOS原文只明确CC BY，未把不明的许可证版本推断为4.0。下载器核验既有文件、不覆盖哈希不符的PDF，不上传论文。
