# Local API v1

Base: `/api/v1`. All requests require `Authorization: Bearer <session-token>`. List responses use `{items, total}`. IDs are UUID strings. Locations use zero-based `page_index` and unrotated PDF-space `bbox:[x0,y0,x1,y1]` (nullable).

- GET `/library`; POST `/library/open` `{path,create:true}`.
- GET `/papers` with q/tag/folder/favorite/year/reading_status/opened/sort/offset/limit; sort includes last_opened. GET/PATCH/DELETE `/papers/{id}`. DELETE query `delete_files=false`. PATCH accepts metadata, tags, folders, favorite, notes.
- POST `/papers/import` multipart `files`; POST `/papers/import-paths` `{paths,recursive:true}`. Return `{items,duplicates,errors}`.
- POST `/papers/{id}/reparse`; GET `/papers/{id}/pdf`; GET `/papers/{id}/text`.
- GET `/resources` with kind/paper_id/q/tag/year/offset/limit; GET/PATCH `/resources/{id}`.
- GET `/resources/{id}/files/{png|thumbnail|csv|html}`; optional dpi=150|300|600 for png.
- POST `/resources/{id}/crop` `{location,dpi}`; POST `/papers/{id}/resources` `{kind,name,caption,location,dpi}`.
- POST `/exports` `{paper_ids:[],resource_ids:[],format:'zip'|'png'|'csv'|'html',dpi:300}` returns downloadable binary.
- GET `/search?q=` => `{papers,figures,tables,content,notes}`. Results include `snippet:[{text,matched}]`, ids and location.
- GET `/jobs` => `{items,total}`; POST `/jobs/{id}/cancel` or `/retry`.
- GET `/models`; POST `/models/download`; POST `/models/import` `{path}`.
- GET/POST `/folders`; DELETE `/folders/{id}`. Folder `{id,name}`.
- POST `/backups` `{destination?}` => `{path}`; POST `/backups/restore` `{path,destination}`.
- GET/PATCH `/settings`; GET `/health`.

Paper fields: id,title(nullable),filename,authors[],abstract,year,venue,doi,arxiv_id,keywords[],tags[],folders[],favorite,notes,status,figure_count,table_count,sections[],references[],warnings[],created_at.
Resource: id,paper_id,paper_title,kind,number,name,caption,locations[],tags[],notes,table:{rows:[][],cells:[],header_rows:int}|null,files:{png,...},warnings[],needs_review.
Job: id,paper_id,paper_title,status,phase,pages_done,pages_total,resources_count,error,created_at.

Import failures are explicit per-file `errors:[{path,error}]`, duplicates are existing Paper entries; source files are never changed. Errors use standard FastAPI `{detail:message}` with actionable Chinese messages.

0.2 adds GET/PATCH `/papers/{id}/reading-state`, GET `/annotations`, POST `/papers/{id}/annotations`, GET/PATCH/DELETE `/annotations/{id}`, POST `/annotations/{id}/restore`, and POST `/annotations/export`. Reading/annotation updates use `expected_version`; conflicts return409 and the current record where applicable. See [Reading API](READING_API.md) for complete schemas and range constraints.

Library information includes a persistent `id`. The UI scopes library writes with `X-PaperVault-Library: encodeURIComponent(id + ':' + path)`. Library changes and writes are serialized; a request for the previously active library is rejected before execution. The Bearer token remains mandatory and must not be persisted in UI preferences.
