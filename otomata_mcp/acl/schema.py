"""DDL de l'ACL (grants par utilisateur, scopé). À appliquer par le consommateur."""

SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS grants (
    tenant_id   TEXT NOT NULL,
    sub         TEXT NOT NULL,
    resource    TEXT NOT NULL,   -- 'tool:<name>' | 'doctrine:<name>' | 'admin'
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, sub, resource)
);
CREATE INDEX IF NOT EXISTS grants_scope_sub ON grants (tenant_id, sub);
"""
