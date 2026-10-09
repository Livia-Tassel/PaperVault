# 新增20篇真实论文测试

2026-10-09。新增下载并测试 **20篇完整论文、243页**，加上上一轮7篇71页，累计 **27篇不同论文、314页**。本轮覆盖ACL、JMLR、PLOS、JOSS和JORS的公开出版PDF，没有把自建fixture或重复解析算成新增论文。

20篇均通过导入、真实CPU解析、持久化和导出流程，但内容识别仍有明确缺陷。6篇深入核对、14篇图表清单核对；不能用流程通过率代替提取准确率。本轮原始质量基线来自**已安装0.2.1**，后续0.2.2仅修复附录图表编号，另行验证，不覆盖旧输出。

本地可直接打开 [原文与实际导出目录](../artifacts/real-corpus-expanded/review.html)。每个资源附原页、300DPI PNG、CSV/HTML；原文图表清单包含未提取的对象。原始PDF位于 `.test-data/external/expanded-corpus/`。来源、许可证、下载地址及SHA-256在 [来源清单](../tests/corpus/expanded/) 中，论文和渲染图不提交Git。

## 样本与实际输出

原文“图/表”按有编号的完整逻辑对象计数，多子图仍计一个Figure；自动数是原始资源条目，包含碎片、出版标志、合法无编号对象及误识别。两列不能直接相除得到准确率。

| 论文（官方来源） | 页 | 原文图/表 | 自动图/表 | 耗时/秒 | 人工范围 |
|---|---:|---:|---:|---:|---|
| [BART](https://aclanthology.org/2020.acl-main.703/) | 10 | 3/9 | 5/8 | 80.4 | 深入 |
| [SciBERT](https://aclanthology.org/D19-1371/) | 6 | 0/2 | 0/2 | 23.4 | 清单 |
| [BasicTools](https://joss.theoj.org/papers/10.21105/joss.05142) | 4 | 2/0 | 9/0 | 14.7 | 清单 |
| [DifferentialEquations.jl](https://openresearchsoftware.metajnl.com/articles/10.5334/jors.151) | 10 | 1/0 | 3/0 | 18.3 | 清单 |
| [PyBaMM](https://openresearchsoftware.metajnl.com/articles/10.5334/jors.309) | 8 | 3/0 | 7/0 | 16.8 | 清单 |
| [SimCSE](https://aclanthology.org/2021.emnlp-main.552/) | 17 | 5/16 | 5/16 | 78.3 | 清单 |
| [LongT5](https://aclanthology.org/2022.findings-naacl.55/) | 13 | 4/8 | 5/8 | 72.3 | 深入 |
| [mT5](https://aclanthology.org/2021.naacl-main.41/) | 16 | 4/14 | 4/14 | 167.3 | 清单 |
| [Non-attracting Regions of Local Minima](https://www.jmlr.org/papers/v22/19-586.html) | 34 | 4/0 | 8/3 | 46.1 | 清单 |
| [Temporal Resolution of an Ecological Network](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0081694) | 9 | 4/2 | 10/2 | 29.3 | 深入 |
| [Ignoring Imperfect Detection](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0099571) | 14 | 6/4 | 9/4 | 35.1 | 清单 |
| [scikit-fem](https://joss.theoj.org/papers/10.21105/joss.02369) | 4 | 1/0 | 1/0 | 34.9 | 清单 |
| [Antibiotic Transport in Resistant Bacteria](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0038624) | 9 | 5/1 | 19/1 | 20.9 | 清单 |
| [ChineseBERT](https://aclanthology.org/2021.acl-long.161/) | 11 | 5/9 | 4/9 | 43.0 | 深入 |
| [Fractional diffusion wave equation](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0295525) | 28 | 9/13 | 12/14 | 56.4 | 深入 |
| [Fuzzy fractional cancer tumor model](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0303891) | 14 | 4/1 | 7/1 | 26.5 | 清单 |
| [MacBERT](https://aclanthology.org/2020.findings-emnlp.58/) | 12 | 2/11 | 1/12 | 49.9 | 清单 |
| [CellFIT](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0099116) | 15 | 7/1 | 10/1 | 26.9 | 深入 |
| [STROBE Statement](https://journals.plos.org/plosmedicine/article?id=10.1371/journal.pmed.0040296) | 5 | 0/1 | 7/1 | 18.3 | 清单 |
| [DAMASK Python library](https://joss.theoj.org/papers/10.21105/joss.07164) | 4 | 0/0 | 4/0 | 13.7 | 清单 |
| **合计** | **243** | **69/92** | **130/96** | — | **6深入/14清单** |

耗时是同机导入至解析结果发布的墙钟时间，非纯模型推理或独立性能基准。一次只处理一篇；本机同时有其他开发工作，未控制系统负载。环境为Windows 11 x64、16逻辑CPU、16,890,716,160字节内存、Docling 2.135.0和CPU PyTorch；具体依赖与模型锁定记录沿用项目锁文件。五批后台/worker内存采样及机器信息保留在各batch报告，不将首篇耗时等同冷启动性能。

## 实际检查了什么

- 20个原PDF均重新核验来源清单SHA-256；使用独立测试库，未触碰用户论文库。
- 安装版后台通过真实Docling子进程处理全部243页；模型已在本地，设置离线环境变量，不进行模型下载。保留原始Docling JSON、统一结构、Markdown、警告和worker日志。
- 226个资源逐个检查位置边界、300DPI PNG解码、表格CSV/HTML、Caption搜索和基线文件未变；五批主进程正常退出、端口关闭。第二批还在独立副本执行人工编辑、备份、恢复和重启回读。
- 通过Windows进程句柄实际读取20个worker的退出码，全部为0。观察器用自有退出码0和7的子进程校验，未把未知状态当作0。没有在这20个worker日志中发现原生异常诊断。
- 先按原PDF建立独立图表清单及60个语义单元格参照，再核对解析结果。资源文件可打开、编号有匹配或进程退出0，均不自动判为内容正确。

原始安装版后台SHA-256：`567bc425d9df91f4813dfacdf64a8a8e5548381becc5950627830862439dd43a`；模型清单SHA-256：`0667a164e1d7633187c24ba81302ca86bb50dff449f49c420e0217a6fd03fd45`。

## 人工核对结果与尚未修复的问题

6篇深入核对共86页、74个有编号的逻辑对象。72个能找到对应资源，2个完全遗漏：BART Table 9、ChineseBERT Figure 3。按各组记录的主体完整性标准，65个跨片段内容完整、63个在单一资源内完整；“完整”不代表裁剪干净、表格结构正确或图注准确。无保留的正确图注关联为65个。多子图的内部标签/解释属于主体检查范围。

60个预选单元格逐项核对JSON、CSV和展开后的HTML网格：**50个精确一致、6个错误、4个语义行列缺失**。后4个在JSON中沿用`ambiguous_missing`状态名，但人工已确认是原表内容遗漏。样本不是随机抽样，不推算全表或通用准确率；数学符号、表头与分组问题另列。

14篇清单核对共157页、87个逻辑对象；仅核对对象对应、类型、编号和图注关联，并记录有限抽查发现。它们不计入完整裁剪或单元格正确性的分母，未审字段保留null。主要缺陷如下：

| 原文位置 | 实际问题 | 影响/状态 |
|---|---|---|
| BART Figure 1、Figure 3、Table 9 | 多子图拆开，内部标签/说明遗漏，部分子图错配Caption；Table 9未形成资源 | 图文对应和完整性失败，未修复 |
| LongT5 Tables 2、7、8 | 合并表头丢失、分组标题混入数据行；另有纯白Figure | 抽查数字正确仍不能使用原结构结论，未修复 |
| ChineseBERT Figures 1–4 | Figure 1/2合入大块页面裁剪；Figure 3漏提取、另输出空白图；Figure 4图注混入其他图中文字 | 分离、漏检及图注污染，未修复 |
| Fractional wave Figure 4、Table 2、PDF页18 | 四子图只裁出(c)；表头缺失；Equation 41误识别为Table | 裁剪/结构/分类失败，未修复 |
| Ecological network Figure 2、Table 2、Figure 4 | 图拆成5块，仅末块有正确Caption；表的A/B部分遗漏；坐标轴边缘轻微裁切 | 数据缺失和图注不完整，未修复 |
| CellFIT Table 1、Figure 6 | 旋转90°表格的PNG完整，但结构化数据转置、方法名碎裂；蓝色端点轻微裁切 | CSV/HTML不能当作正确原表，未修复 |
| CellFIT、fractional wave科学符号 | 可见±/∞等与原PDF可提取文字不一致；分数和指数结构丢失 | 独立PDFium读取也出现部分错误；保留原图，不猜测替换科研数值 |
| LongT5、STROBE首页标题 | LongT5误选较高的作者文字框；STROBE信任PDF元数据`untitled` | 两个应用标题选择缺陷已记录，0.2.2未修复；可人工编辑 |

额外资源分别记录为33个已确认出版标志、2个空白区域、1个误识别公式、3个合法无编号符号表，以及16个未深入分类的额外资源。JMLR的3张符号说明表确实存在于原文，不记为虚构表格。匹配到的子图碎片归属于原逻辑对象，不重复计为额外正确Figure。

两处标题问题来自逐篇标题对照。17篇标题逐字一致，另1篇仅弯引号/直引号不同；这不是作者、年份或其他元数据的完整准确率声明。逐篇证据见 `metadata-observations.json`。

## 中文内容与来源限制

ChineseBERT和MacBERT是包含中文内容的英文论文，不是全中文论文。额外通过真实已安装后台执行6个查询，覆盖中文单字、连续短语和含`[M]`的片段，6次均命中正确论文和PDF页；独立PDFium读取确认原文确有这些字串，查询前后内容快照不变。证据为 `chinese-search.json`。

若干纯中文出版PDF下载遇到403、429或反机器人页面，未绕过限制；未能独立确认许可的CLUE候选未纳入20篇。访问尝试与替代选择见 `tests/corpus/expanded/diverse-access-attempts.json`。本轮不能宣称覆盖全中文长文、扫描/OCR论文或所有出版版式。较早PLOS原文只明确CC BY的，保留这一原始许可描述，不擅自写成CC BY 4.0。

## 0.2.2附录编号修复

SimCSE的8张附录表和Figure G.1都有正确Caption，却因应用编号规则不接受`A.1`等格式而显示空编号。0.2.2修复该规则，支持字母附录、S1、罗马数字等；不从文件名、页码或无Caption资源猜编号。对不支持的`1.2a`、`A.1.2a`和`V-Net`也不能回退截取成1、A.1或V。

旧规则先复现13个失败；补齐边界后编号26项与元数据6项定向检查通过。对原226个资源重放只产生9处目标编号变化，其余Caption、类型、坐标和结构不变。最终完整后端测试 **146 passed、0 skipped**，42.29秒，11条上游弃用警告；本次日志没有原生异常诊断。没有将这些合成fixture用例算成外部论文。

生产源码冻结于`44c568eccca416c9a4103a07a1fae3d315b53b9d`，最终冻结后台SHA-256为`b5e1ece230ab2ec1183057ab1f0050e6899947632897724febb117eeaa51755f`。这个新后台已重新执行SimCSE的真实模型解析：17页、21资源全部流程检查通过，9个附录编号逐一正确；原来缺Caption的Figure F.1仍保持未知编号。证据来自新解析，单独保留，不把源码字符串重放当作模型复测。

最终安装器与实际桌面验收结果见 [0.2.2交付清单](verification/0.2.2/release-manifest.json) 和 [总测试报告](../TEST_REPORT.md)。本轮没有改变模型、表格识别、裁剪算法或前端业务代码；上述识别/标题缺陷仍存在。

## 可复现记录

紧凑证据归档于 `docs/verification/expanded-corpus/`，包括五批原始报告、输入清单快照、三份人工复核、质量汇总、worker退出码、中文查询、标题观察及最终146项后端日志/JUnit。原始226个资源和243页渲染保留在 `artifacts/real-corpus-expanded/`。

```powershell
.venv\Scripts\python.exe scripts\download_real_corpus.py --manifest 'tests/corpus/expanded/sources-*.json' --verify-only
.venv\Scripts\python.exe scripts\summarize_expanded_corpus.py --require-complete
.venv\Scripts\python.exe scripts\summarize_expanded_quality.py
.venv\Scripts\python.exe scripts\render_expanded_review.py
```

上述汇总命令读取保留的0.2.1基线，不运行新模型。重新解析须按 [样本说明](../tests/corpus/README.md) 显式指定当前后台版本/SHA，并使用新的报告路径；新的UUID与模型输出必须重新审核，不沿用旧对象判定。报告页面已在真实浏览器检查20篇目录、226图像条目、569个本地文件链接，以及6/14范围筛选与问题筛选；该检查不冒充桌面软件测试。

上一轮120项源码组合曾打印Windows access violation诊断，根因仍未定位。本次20个实际worker退出0及146项测试未见诊断，只说明本轮观察结果，不证明旧问题已经解决。干净Windows VM、托管CI、改变宿主DPI和新的卸载保留实验均不属于本次完成范围；安装器仍未签名。
