export interface paths {
    "/api/v1/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_api_v1_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/openapi.json": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Openapi */
        get: operations["openapi_api_v1_openapi_json_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/library": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Library Info */
        get: operations["library_info_api_v1_library_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/library/open": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Library Open */
        post: operations["library_open_api_v1_library_open_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/papers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Papers */
        get: operations["papers_api_v1_papers_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/papers/import-paths": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Import Paths */
        post: operations["import_paths_api_v1_papers_import_paths_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/papers/import": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Import Upload */
        post: operations["import_upload_api_v1_papers_import_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/papers/{paper_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Paper */
        get: operations["paper_api_v1_papers__paper_id__get"];
        put?: never;
        post?: never;
        /** Paper Delete */
        delete: operations["paper_delete_api_v1_papers__paper_id__delete"];
        options?: never;
        head?: never;
        /** Paper Edit */
        patch: operations["paper_edit_api_v1_papers__paper_id__patch"];
        trace?: never;
    };
    "/api/v1/papers/{paper_id}/reparse": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reparse */
        post: operations["reparse_api_v1_papers__paper_id__reparse_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/papers/{paper_id}/pdf": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Pdf */
        get: operations["pdf_api_v1_papers__paper_id__pdf_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/papers/{paper_id}/reading-state": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Reading State */
        get: operations["reading_state_api_v1_papers__paper_id__reading_state_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Reading State */
        patch: operations["update_reading_state_api_v1_papers__paper_id__reading_state_patch"];
        trace?: never;
    };
    "/api/v1/annotations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Annotations */
        get: operations["annotations_api_v1_annotations_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/papers/{paper_id}/annotations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Annotation */
        post: operations["create_annotation_api_v1_papers__paper_id__annotations_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/annotations/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Annotation Export */
        post: operations["annotation_export_api_v1_annotations_export_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/annotations/{annotation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Annotation */
        get: operations["annotation_api_v1_annotations__annotation_id__get"];
        put?: never;
        post?: never;
        /** Delete Annotation */
        delete: operations["delete_annotation_api_v1_annotations__annotation_id__delete"];
        options?: never;
        head?: never;
        /** Update Annotation */
        patch: operations["update_annotation_api_v1_annotations__annotation_id__patch"];
        trace?: never;
    };
    "/api/v1/annotations/{annotation_id}/restore": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Restore Annotation */
        post: operations["restore_annotation_api_v1_annotations__annotation_id__restore_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/papers/{paper_id}/text": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Text */
        get: operations["text_api_v1_papers__paper_id__text_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/resources": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Resources */
        get: operations["resources_api_v1_resources_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/resources/{resource_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Resource */
        get: operations["resource_api_v1_resources__resource_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Edit Resource */
        patch: operations["edit_resource_api_v1_resources__resource_id__patch"];
        trace?: never;
    };
    "/api/v1/resources/{resource_id}/files/{format_name}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Resource File */
        get: operations["resource_file_api_v1_resources__resource_id__files__format_name__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/resources/{resource_id}/crop": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Crop Resource */
        post: operations["crop_resource_api_v1_resources__resource_id__crop_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/papers/{paper_id}/resources": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Manual Resource */
        post: operations["manual_resource_api_v1_papers__paper_id__resources_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/exports": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Export */
        post: operations["export_api_v1_exports_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Search All */
        get: operations["search_all_api_v1_search_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/jobs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Jobs */
        get: operations["jobs_api_v1_jobs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/jobs/{job_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Cancel Job */
        post: operations["cancel_job_api_v1_jobs__job_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/jobs/{job_id}/retry": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Retry Job */
        post: operations["retry_job_api_v1_jobs__job_id__retry_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/models": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Models */
        get: operations["models_api_v1_models_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/models/download": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Download Models */
        post: operations["download_models_api_v1_models_download_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/models/import": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Import Models */
        post: operations["import_models_api_v1_models_import_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/folders": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Folders */
        get: operations["folders_api_v1_folders_get"];
        put?: never;
        /** Add Folder */
        post: operations["add_folder_api_v1_folders_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/folders/{folder_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Delete Folder */
        delete: operations["delete_folder_api_v1_folders__folder_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/backups": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Backup */
        post: operations["backup_api_v1_backups_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/backups/restore": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Restore */
        post: operations["restore_api_v1_backups_restore_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/settings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Settings */
        get: operations["settings_api_v1_settings_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Edit Settings */
        patch: operations["edit_settings_api_v1_settings_patch"];
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** Annotation */
        Annotation: {
            /**
             * Title
             * @default
             */
            title?: string;
            /**
             * Quote
             * @default
             */
            quote?: string;
            /**
             * Body
             * @default
             */
            body?: string;
            /**
             * Color
             * @default amber
             * @enum {string}
             */
            color?: "amber" | "green" | "blue" | "pink" | "purple";
            /** Tags */
            tags?: string[];
            /** Locations */
            locations?: components["schemas"]["AnnotationLocation"][];
            /** Id */
            id: string;
            /** Paper Id */
            paper_id: string;
            /** Paper Title */
            paper_title: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "bookmark" | "highlight" | "note";
            /** Version */
            version: number;
            /** Deleted */
            deleted: boolean;
            /** Created At */
            created_at: string;
            /** Updated At */
            updated_at: string;
        } & {
            [key: string]: unknown;
        };
        /** AnnotationCreate */
        AnnotationCreate: {
            /**
             * Title
             * @default
             */
            title?: string;
            /**
             * Quote
             * @default
             */
            quote?: string;
            /**
             * Body
             * @default
             */
            body?: string;
            /**
             * Color
             * @default amber
             * @enum {string}
             */
            color?: "amber" | "green" | "blue" | "pink" | "purple";
            /** Tags */
            tags?: string[];
            /** Locations */
            locations?: components["schemas"]["AnnotationLocation"][];
            /**
             * Kind
             * @enum {string}
             */
            kind: "bookmark" | "highlight" | "note";
        };
        /** AnnotationExportRequest */
        AnnotationExportRequest: {
            /** Ids */
            ids?: string[];
            /** Paper Id */
            paper_id?: string | null;
            /**
             * Format
             * @default markdown
             * @enum {string}
             */
            format?: "markdown" | "json";
        };
        /** AnnotationList */
        AnnotationList: {
            /** Items */
            items: components["schemas"]["Annotation"][];
            /** Total */
            total: number;
        };
        /** AnnotationLocation */
        AnnotationLocation: {
            /** Page Index */
            page_index: number;
            /** Bbox */
            bbox?: [
                number,
                number,
                number,
                number
            ] | null;
        };
        /** AnnotationPatch */
        AnnotationPatch: {
            /**
             * Title
             * @default
             */
            title?: string;
            /**
             * Quote
             * @default
             */
            quote?: string;
            /**
             * Body
             * @default
             */
            body?: string;
            /**
             * Color
             * @default amber
             * @enum {string}
             */
            color?: "amber" | "green" | "blue" | "pink" | "purple";
            /** Tags */
            tags?: string[];
            /** Locations */
            locations?: components["schemas"]["AnnotationLocation"][];
            /** Expected Version */
            expected_version: number;
        };
        /** BackupRequest */
        BackupRequest: {
            /** Destination */
            destination?: string | null;
        };
        /** Body_import_upload_api_v1_papers_import_post */
        Body_import_upload_api_v1_papers_import_post: {
            /** Files */
            files: string[];
        };
        /** CropRequest */
        CropRequest: {
            location: components["schemas"]["SourceLocation"];
            /**
             * Dpi
             * @default 300
             * @enum {integer}
             */
            dpi?: 150 | 300 | 600;
            /**
             * Kind
             * @default figure
             * @enum {string}
             */
            kind?: "figure" | "table";
            /**
             * Name
             * @default
             */
            name?: string;
            /**
             * Caption
             * @default
             */
            caption?: string;
        };
        /** ExpectedVersion */
        ExpectedVersion: {
            /** Expected Version */
            expected_version: number;
        };
        /** ExportRequest */
        ExportRequest: {
            /** Paper Ids */
            paper_ids?: string[];
            /** Resource Ids */
            resource_ids?: string[];
            /**
             * Format
             * @default zip
             * @enum {string}
             */
            format?: "zip" | "png" | "csv" | "html";
            /**
             * Dpi
             * @default 300
             * @enum {integer}
             */
            dpi?: 150 | 300 | 600;
        };
        /** FolderRequest */
        FolderRequest: {
            /** Name */
            name: string;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** ImportPaths */
        ImportPaths: {
            /** Paths */
            paths: string[];
            /**
             * Recursive
             * @default true
             */
            recursive?: boolean;
        };
        /** LibraryInfo */
        LibraryInfo: {
            /** Id */
            id?: string | null;
            /** Path */
            path: string | null;
            /** Paper Count */
            paper_count: number;
            /** Figure Count */
            figure_count: number;
            /** Table Count */
            table_count: number;
        };
        /** LibraryOpen */
        LibraryOpen: {
            /** Path */
            path: string;
            /**
             * Create
             * @default true
             */
            create?: boolean;
        };
        /** Paper */
        Paper: {
            /** Id */
            id: string;
            /** Filename */
            filename: string;
            /** Title */
            title?: string | null;
            /** Authors */
            authors?: string[];
            /** Status */
            status: string;
            /**
             * Figure Count
             * @default 0
             */
            figure_count?: number;
            /**
             * Table Count
             * @default 0
             */
            table_count?: number;
            /**
             * Reading Status
             * @default unread
             * @enum {string}
             */
            reading_status?: "unread" | "reading" | "read";
            /** Last Opened */
            last_opened?: string | null;
            /**
             * Annotation Count
             * @default 0
             */
            annotation_count?: number;
        } & {
            [key: string]: unknown;
        };
        /** PaperPatch */
        PaperPatch: {
            /** Title */
            title?: string | null;
            /** Authors */
            authors?: string[] | null;
            /** Abstract */
            abstract?: string | null;
            /** Year */
            year?: number | null;
            /** Venue */
            venue?: string | null;
            /** Doi */
            doi?: string | null;
            /** Arxiv Id */
            arxiv_id?: string | null;
            /** Keywords */
            keywords?: string[] | null;
            /** Tags */
            tags?: string[] | null;
            /** Folders */
            folders?: string[] | null;
            /** Favorite */
            favorite?: boolean | null;
            /** Notes */
            notes?: string | null;
            /** Sections */
            sections?: {
                [key: string]: unknown;
            }[] | null;
            /** References */
            references?: string[] | null;
        };
        /** PathRequest */
        PathRequest: {
            /** Path */
            path: string;
        };
        /** ReadingPatch */
        ReadingPatch: {
            /** Expected Version */
            expected_version: number;
            /** Page Index */
            page_index?: number;
            /** Anchor */
            anchor?: [
                number,
                number
            ] | null;
            /** Scale */
            scale?: number;
            /**
             * Rotation
             * @enum {integer}
             */
            rotation?: 0 | 90 | 180 | 270;
            /**
             * Fit Mode
             * @enum {string}
             */
            fit_mode?: "custom" | "width" | "page";
            /**
             * Status
             * @enum {string}
             */
            status?: "unread" | "reading" | "read";
            /**
             * Touch
             * @default false
             */
            touch?: boolean;
        };
        /** ReadingState */
        ReadingState: {
            /** Paper Id */
            paper_id: string;
            /** Version */
            version: number;
            /** Page Index */
            page_index: number;
            /** Anchor */
            anchor: [
                number,
                number
            ] | null;
            /** Scale */
            scale: number;
            /** Rotation */
            rotation: number;
            /**
             * Fit Mode
             * @enum {string}
             */
            fit_mode: "custom" | "width" | "page";
            /**
             * Status
             * @enum {string}
             */
            status: "unread" | "reading" | "read";
            /** Last Opened */
            last_opened: string | null;
            /** Updated At */
            updated_at: string | null;
        };
        /** Resource */
        Resource: {
            /** Id */
            id: string;
            /** Paper Id */
            paper_id: string;
            /** Paper Title */
            paper_title: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "figure" | "table";
            /** Locations */
            locations?: components["schemas"]["SourceLocation"][];
            /** Files */
            files?: {
                [key: string]: string;
            };
            table?: components["schemas"]["TableData"] | null;
        } & {
            [key: string]: unknown;
        };
        /** ResourcePatch */
        ResourcePatch: {
            /** Name */
            name?: string | null;
            /** Number */
            number?: string | null;
            /** Caption */
            caption?: string | null;
            /** Tags */
            tags?: string[] | null;
            /** Notes */
            notes?: string | null;
            table?: components["schemas"]["TableData"] | null;
            /** Needs Review */
            needs_review?: boolean | null;
        };
        /** RestoreRequest */
        RestoreRequest: {
            /** Path */
            path: string;
            /** Destination */
            destination: string;
        };
        /** SourceLocation */
        SourceLocation: {
            /** Page Index */
            page_index: number;
            /** Bbox */
            bbox?: [
                number,
                number,
                number,
                number
            ] | null;
        } & {
            [key: string]: unknown;
        };
        /** TableData */
        TableData: {
            /** Rows */
            rows: string[][];
            /** Cells */
            cells?: {
                [key: string]: unknown;
            }[];
            /**
             * Header Rows
             * @default 1
             */
            header_rows?: number;
        } & {
            [key: string]: unknown;
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
            /** Input */
            input?: unknown;
            /** Context */
            ctx?: Record<string, never>;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    health_api_v1_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    openapi_api_v1_openapi_json_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    library_info_api_v1_library_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LibraryInfo"];
                };
            };
        };
    };
    library_open_api_v1_library_open_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LibraryOpen"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LibraryInfo"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    papers_api_v1_papers_get: {
        parameters: {
            query?: {
                q?: string;
                tag?: string | null;
                folder?: string | null;
                favorite?: boolean | null;
                year?: number | null;
                sort?: string;
                offset?: number;
                limit?: number;
                reading_status?: string | null;
                opened?: boolean | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    import_paths_api_v1_papers_import_paths_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ImportPaths"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    import_upload_api_v1_papers_import_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_import_upload_api_v1_papers_import_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    paper_api_v1_papers__paper_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                paper_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Paper"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    paper_delete_api_v1_papers__paper_id__delete: {
        parameters: {
            query?: {
                delete_files?: boolean;
            };
            header?: never;
            path: {
                paper_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    paper_edit_api_v1_papers__paper_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                paper_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PaperPatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Paper"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reparse_api_v1_papers__paper_id__reparse_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                paper_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    pdf_api_v1_papers__paper_id__pdf_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                paper_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reading_state_api_v1_papers__paper_id__reading_state_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                paper_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadingState"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_reading_state_api_v1_papers__paper_id__reading_state_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                paper_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReadingPatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadingState"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    annotations_api_v1_annotations_get: {
        parameters: {
            query?: {
                q?: string;
                paper_id?: string | null;
                kind?: string | null;
                tag?: string | null;
                offset?: number;
                limit?: number;
                deleted?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnnotationList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_annotation_api_v1_papers__paper_id__annotations_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                paper_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AnnotationCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Annotation"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    annotation_export_api_v1_annotations_export_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AnnotationExportRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    annotation_api_v1_annotations__annotation_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                annotation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Annotation"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_annotation_api_v1_annotations__annotation_id__delete: {
        parameters: {
            query: {
                expected_version: number;
            };
            header?: never;
            path: {
                annotation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Annotation"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_annotation_api_v1_annotations__annotation_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                annotation_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AnnotationPatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Annotation"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    restore_annotation_api_v1_annotations__annotation_id__restore_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                annotation_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExpectedVersion"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Annotation"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    text_api_v1_papers__paper_id__text_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                paper_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    resources_api_v1_resources_get: {
        parameters: {
            query?: {
                kind?: string | null;
                paper_id?: string | null;
                q?: string;
                tag?: string | null;
                year?: number | null;
                offset?: number;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    resource_api_v1_resources__resource_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                resource_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Resource"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    edit_resource_api_v1_resources__resource_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                resource_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResourcePatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Resource"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    resource_file_api_v1_resources__resource_id__files__format_name__get: {
        parameters: {
            query?: {
                dpi?: number | null;
            };
            header?: never;
            path: {
                resource_id: string;
                format_name: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    crop_resource_api_v1_resources__resource_id__crop_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                resource_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CropRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Resource"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    manual_resource_api_v1_papers__paper_id__resources_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                paper_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CropRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Resource"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    export_api_v1_exports_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExportRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    search_all_api_v1_search_get: {
        parameters: {
            query?: {
                q?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    jobs_api_v1_jobs_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    cancel_job_api_v1_jobs__job_id__cancel_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                job_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    retry_job_api_v1_jobs__job_id__retry_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                job_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    models_api_v1_models_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    download_models_api_v1_models_download_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    import_models_api_v1_models_import_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PathRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    folders_api_v1_folders_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    add_folder_api_v1_folders_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FolderRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_folder_api_v1_folders__folder_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                folder_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    backup_api_v1_backups_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BackupRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    restore_api_v1_backups_restore_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RestoreRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    settings_api_v1_settings_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    edit_settings_api_v1_settings_patch: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    [key: string]: unknown;
                };
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
