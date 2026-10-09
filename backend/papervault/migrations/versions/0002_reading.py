"""Add independent reading state and user annotations without changing parser data."""
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE TABLE library_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    op.get_bind().execute(sa.text("INSERT INTO library_meta(key,value) VALUES('id',:value)"), {"value": str(uuid4())})
    op.execute("""CREATE TABLE reading_states (
      paper_id TEXT PRIMARY KEY REFERENCES papers(id) ON DELETE CASCADE,
      page_index INTEGER NOT NULL DEFAULT 0 CHECK(page_index>=0), anchor_json TEXT NOT NULL DEFAULT 'null',
      scale REAL NOT NULL DEFAULT 1 CHECK(scale>=0.05 AND scale<=8),
      rotation INTEGER NOT NULL DEFAULT 0 CHECK(rotation IN(0,90,180,270)),
      fit_mode TEXT NOT NULL DEFAULT 'custom' CHECK(fit_mode IN('custom','width','page')),
      status TEXT NOT NULL DEFAULT 'unread' CHECK(status IN('unread','reading','read')),
      version INTEGER NOT NULL CHECK(version>=1), last_opened TEXT, updated_at TEXT NOT NULL)""")
    op.execute("CREATE INDEX reading_recent ON reading_states(last_opened DESC,paper_id)")
    op.execute("""CREATE TABLE annotations (
      id TEXT PRIMARY KEY, paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
      kind TEXT NOT NULL CHECK(kind IN('bookmark','highlight','note')),
      title TEXT NOT NULL DEFAULT '', quote TEXT NOT NULL DEFAULT '', body TEXT NOT NULL DEFAULT '',
      color TEXT NOT NULL DEFAULT 'amber' CHECK(color IN('amber','green','blue','pink','purple')),
      tags_json TEXT NOT NULL DEFAULT '[]', locations_json TEXT NOT NULL DEFAULT '[]',
      version INTEGER NOT NULL DEFAULT 1 CHECK(version>=1), deleted INTEGER NOT NULL DEFAULT 0 CHECK(deleted IN(0,1)),
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    op.execute("CREATE INDEX annotations_paper ON annotations(paper_id,deleted,updated_at DESC,id)")
    op.execute("CREATE INDEX annotations_recent ON annotations(deleted,updated_at DESC,id)")


def downgrade():
    raise RuntimeError("Destructive downgrades are unsupported; restore a library backup instead.")
