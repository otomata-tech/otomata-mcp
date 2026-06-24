"""DDL des doctrines en base (à appliquer par le consommateur, comme calllog.SCHEMA_SQL).

Row-scopé par `tenant_id` → multi-entreprise dans une DB partagée. `content_docs` =
version courante ; `content_revisions` = historique append-only (revert/audit).
"""

SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS content_docs (
    tenant_id   TEXT NOT NULL,
    kind        TEXT NOT NULL,
    slug        TEXT NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    body        TEXT NOT NULL,
    frontmatter JSONB NOT NULL DEFAULT '{}'::jsonb,
    version     INTEGER NOT NULL,
    set_by      TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, kind, slug)
);
CREATE TABLE IF NOT EXISTS content_revisions (
    tenant_id   TEXT NOT NULL,
    kind        TEXT NOT NULL,
    slug        TEXT NOT NULL,
    version     INTEGER NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    body        TEXT NOT NULL,
    frontmatter JSONB NOT NULL DEFAULT '{}'::jsonb,
    set_by      TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, kind, slug, version)
);
CREATE INDEX IF NOT EXISTS content_docs_scope_kind ON content_docs (tenant_id, kind);
"""
