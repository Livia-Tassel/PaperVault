"""Initial durable library schema."""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    statements = [
        """CREATE TABLE papers (id TEXT PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE,
        filename TEXT NOT NULL, auto_json TEXT NOT NULL DEFAULT '{}',
        overrides_json TEXT NOT NULL DEFAULT '{}', status TEXT NOT NULL DEFAULT 'queued',
        active_revision TEXT, created_at TEXT NOT NULL, removed INTEGER NOT NULL DEFAULT 0)""",
        """CREATE TABLE resources (id TEXT PRIMARY KEY, paper_id TEXT NOT NULL REFERENCES papers(id)
        ON DELETE CASCADE, kind TEXT NOT NULL CHECK(kind IN ('figure','table')), auto_json TEXT NOT NULL,
        overrides_json TEXT NOT NULL DEFAULT '{}', revision TEXT, active INTEGER NOT NULL DEFAULT 1,
        manual INTEGER NOT NULL DEFAULT 0, needs_review INTEGER NOT NULL DEFAULT 0)""",
        "CREATE INDEX resources_paper ON resources(paper_id,active,kind)",
        """CREATE TABLE blocks (id TEXT PRIMARY KEY, paper_id TEXT NOT NULL REFERENCES papers(id)
        ON DELETE CASCADE, label TEXT NOT NULL, text TEXT NOT NULL, location_json TEXT, revision TEXT)""",
        """CREATE TABLE parse_runs (id TEXT PRIMARY KEY, paper_id TEXT NOT NULL REFERENCES papers(id)
        ON DELETE CASCADE, engine_json TEXT NOT NULL, manifest_json TEXT NOT NULL, created_at TEXT NOT NULL)""",
        """CREATE TABLE jobs (id TEXT PRIMARY KEY, paper_id TEXT NOT NULL REFERENCES papers(id)
        ON DELETE CASCADE, status TEXT NOT NULL, phase TEXT NOT NULL, progress_json TEXT NOT NULL DEFAULT '{}',
        error TEXT, attempt_token TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
        "CREATE INDEX jobs_queue ON jobs(status,created_at)",
        """CREATE UNIQUE INDEX jobs_one_active ON jobs(paper_id)
        WHERE status IN ('queued','running','publishing','cancel_requested')""",
        "CREATE TABLE folders (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE)",
        """CREATE TABLE paper_folders (paper_id TEXT REFERENCES papers(id) ON DELETE CASCADE,
        folder_id TEXT REFERENCES folders(id) ON DELETE CASCADE, PRIMARY KEY(paper_id,folder_id))""",
        """CREATE TABLE manual_revisions (id TEXT PRIMARY KEY, entity_id TEXT NOT NULL,
        entity_kind TEXT NOT NULL, changes_json TEXT NOT NULL, created_at TEXT NOT NULL)""",
        """CREATE VIRTUAL TABLE search_entries USING fts5(entity_id UNINDEXED, kind UNINDEXED,
        paper_id UNINDEXED, title UNINDEXED, raw_text UNINDEXED, location_json UNINDEXED,
        tokens, tokenize='unicode61 remove_diacritics 2')""",
    ]
    for statement in statements:
        op.execute(statement)


def downgrade():
    raise RuntimeError("Destructive downgrades are unsupported; restore a library backup instead.")
