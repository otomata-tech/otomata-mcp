"""DDL des rôles RBAC (scopé). À appliquer par le consommateur multi-tenant.

Mono-tenant : le rôle peut venir du JWT (RoleStore lisant un claim) → table inutile."""

SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS member_roles (
    tenant_id   TEXT NOT NULL,
    sub         TEXT NOT NULL,
    role        TEXT NOT NULL,   -- 'member' | 'group_admin' | 'org_admin'
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, sub)
);
"""
