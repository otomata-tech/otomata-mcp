"""DDL de la mémoire partagée (à appliquer par le consommateur, comme content.SCHEMA_SQL).

Row-scopé par `tenant_id` → multi-entreprise dans une DB partagée. Append-only
versionné : PK = (tenant_id, key, version) ; la dernière version par clé = le `MAX(version)`."""

SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS shared_memory (
    tenant_id   TEXT NOT NULL,
    key         TEXT NOT NULL,
    version     INTEGER NOT NULL,
    content     TEXT NOT NULL,
    author      TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, key, version)
);
CREATE INDEX IF NOT EXISTS shared_memory_scope_key ON shared_memory (tenant_id, key, version DESC);
"""
