# 阅读与笔记 API（0.2）

所有接口沿用 `/api/v1` 与 Bearer 会话认证。位置使用零基 `page_index`、未旋转 PDF user-space 坐标（保留 CropBox 原点和 UserUnit 语义），不得传 CSS 像素。图片、书签、笔记都不修改 PDF。

修改论文库的 POST/PATCH/DELETE 请求可携带 `X-PaperVault-Library: encodeURIComponent(library.id + ':' + library.path)`。新客户端必须在操作创建时捕获此值；阅读写队列使用挂载时的库值，不能在真正发送时换成当前库值。百分号编码允许中文路径安全进入HTTP头。服务端用异步锁把验证和处理请求放在同一临界区；库切换和备份恢复也使用该锁。库已切换时返回409 `{detail:"论文库已切换，旧操作未执行",code:"library_switched"}`，没有 current，不能当成条目版本冲突自动重试。`/library/open`只加锁不验证旧scope；`/models/*`和全局`/settings`不验证scope。无此header的旧客户端仍可用；GET不加全局锁，客户端应取消切库前的旧读取。

## 阅读状态

`GET /papers/{id}/reading-state` 返回 `{paper_id,version,page_index,anchor,scale,rotation,fit_mode,status,last_opened,updated_at}`。无记录时默认 `version:0,page_index:0,anchor:null,scale:1,rotation:0,fit_mode:"custom",status:"unread",last_opened:null,updated_at:null`。

`PATCH /papers/{id}/reading-state` 必须传 `expected_version`；其余均为可选变更字段：`page_index,anchor:[PDFx,PDFy]|null,scale,rotation,fit_mode,status,touch`。旋转为额外旋转 `0|90|180|270`；scale 为有限数 `0.05..8`；fit_mode 为 `custom|width|page`；status 为 `unread|reading|read`。`touch:true` 用服务器时间更新 last_opened。改变页码且不传 anchor 时清除旧 anchor。请求串行发送并在导航/关闭前等候已发出的保存；冲突不能静默覆盖。

返回完整最新状态。成功修改后 version 加一；空变更不增加版本。`409` 返回 `{detail:"记录已被更新，请重新读取后重试",current:<最新记录>}`；论文移除/不存在返回404。读取或保存阅读状态不会重建 FTS、改动论文人工字段或追加人工修改历史。

论文列表增加 `reading_status,last_opened,annotation_count`；接受 `reading_status=unread|reading|read`、`opened=true|false` 与 `sort=last_opened`。最近阅读入口使用 `opened=true&sort=last_opened`，仅列 last_opened 非空的论文；即使用户后来改回未读也保留在此列表。仅保存缩放或状态而没有touch，不算实际打开。`GET /library` 新增持久化 UUID `id`；会话隔离键使用 `id + path`，备份恢复保留 id。

## 书签、高亮与笔记

记录结构：`{id,paper_id,paper_title,kind,title,quote,body,color,tags,locations,version,deleted,created_at,updated_at}`。kind 为 `bookmark|highlight|note`，color 为 `amber|green|blue|pink|purple`（默认amber），默认 version 为1。

- `GET /annotations?q=&paper_id=&kind=&tag=&offset=0&limit=30` → `{items,total}`；默认只返回未删除记录和未移除论文，按 `updated_at DESC,id` 排序；`deleted=true` 可查看笔记回收列表（已删除内容不保留全文索引，暂不支持与非空q组合）。
- `GET /annotations/{id}` 返回单条未删除笔记；删除或已移除论文下的笔记返回404。
- `POST /papers/{id}/annotations`：传 `kind`，其余内容字段可选；服务器分配 id。
- `PATCH /annotations/{id}`：必须 `expected_version`，支持 title/quote/body/color/tags/locations；kind 与 paper_id 创建后不变。
- `DELETE /annotations/{id}?expected_version=N`：软删除并增加版本，返回完整 deleted:true 记录，供撤销使用。
- `POST /annotations/{id}/restore`：`{expected_version:N}`，撤销软删除并增加版本，返回完整记录。

location 为 `{page_index,bbox:[x0,y0,x1,y1]|null}`，允许多个位置（跨行/跨页高亮应传多个小矩形，不用大包围框填满整段）。note 可不带位置，表示论文级笔记；bookmark 恰好一个位置，bbox可空；highlight 至少一个位置且每个位置必须有bbox。位置须在原始 PDF 真实页数和该页有效 CropBox 范围内。数值误差不超过0.01 PDF point时可夹紧至边界，明显越界拒绝。

上限：title 500字、quote 20,000字、body 100,000字、tags 50项（各1..80字）、locations 512项、q 1000字、limit 1..200。标签去重并去掉两端空白；空标签拒绝。非有限数字、空/反向矩形和越界页码拒绝。修改与全文索引同事务；重新解析不修改笔记记录。

全局 `GET /search` 新增 `notes` 分组，命中包含 `kind:"notes",id,paper_id,title,location,locations,annotation_kind,snippet`，用于打开具体笔记并定位原文。摘录 quote 与用户 body 保持独立字段。

## 导出与备份

`POST /annotations/export`：`{ids:[],paper_id?:string,format:"markdown"|"json"}`，返回文件流。非空 ids 导出这些未删除记录；空 ids 加 paper_id 导出该论文；两者都无则导出全库未删除记录（UI须明确选择全库）。上限10,000项。输出保留论文标题、论文ID、原PDF哈希、笔记ID、类型、摘录、正文、标签、颜色、每个位置及时间。独立Markdown用文字列明页码/坐标并说明不包含原PDF；整篇论文ZIP内的notes.md使用有效的相对 `original.pdf#page=N` 链接。

整篇论文 ZIP 同时包含该论文 `annotations.json`、`notes.md` 和 reading-state 信息；完整库备份自动包含新增数据库表。旧版0001库升级仅新增表，原有 Paper.notes / Resource.notes 保持原样，不推断其位置、不改成自动结果。
