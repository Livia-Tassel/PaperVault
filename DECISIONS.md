# 技术决策

- 2026-10-09：采用用户批准的Tauri/React/FastAPI/Docling/SQLite架构。根据真实包注册表、Windows轮子与解析烟测锁定版本，调研所得版本不能代替安装验证。
- PDFium用于渲染及裁剪，保留其二进制第三方许可。数字原生PDF为首版重点，OCR限制明确显示。
- 默认一个解析子进程。解析子进程不写数据库，父进程校验并发布结果。
- 搜索汉字按字分词，拉丁词保留，使用FTS5短语查询；用户输入不作为FTS语法执行。
- 新代码保留所有权利。第三方代码、模型、测试论文各自保留原许可证。仅做本地交付，不自动发布远程仓库。
- 真实Sidecar验收中，Windows multiprocessing spawn与带stdin控制管道的启动组合出现worker初始化停滞；独立解析与dev模式正常。任务改用显式同一EXE的`--worker`子进程及JSONL进度，stdin为DEVNULL，保留独立进程取消/超时/崩溃隔离。该方案也减少冻结环境对multiprocessing序列化引导的依赖。
