"""Adaptateur Postgres (asyncpg) prêt à l'emploi pour tous les stores du socle.

Le consommateur n'a plus à réimplémenter `ContentStore` / `MemoryStore` / `RoleStore` /
`GrantStore` / `FeedbackStore` ni les sinks : il fournit un pool asyncpg et branche ces
classes dans `build_server(...)`. Multi-tenant par `tenant_id` (le scope du socle).

Toutes les méthodes sont ASYNC — la couche tools du socle les attend (maybe_await).
Installe l'extra : `pip install otomata-mcp[pg]`."""
from __future__ import annotations

import json
from dataclasses import replace
from typing import Optional

import asyncpg

from ..acl.schema import SCHEMA_SQL as _ACL_SQL
from ..content.model import ContentDoc
from ..content.schema import SCHEMA_SQL as _CONTENT_SQL
from ..feedback import FEEDBACK_SCHEMA_SQL as _FEEDBACK_SQL
from ..logging import CALLLOG_SCHEMA_SQL as _CALLLOG_SQL
from ..memory.model import MemoryEntry
from ..memory.schema import SCHEMA_SQL as _MEMORY_SQL
from ..rbac.schema import SCHEMA_SQL as _ROLE_SQL
from ..scope import Scope

ALL_SCHEMA_SQL = "\n".join(
    [_CONTENT_SQL, _MEMORY_SQL, _ROLE_SQL, _ACL_SQL, _FEEDBACK_SQL, _CALLLOG_SQL]
)


async def create_pool(dsn: str, **kwargs) -> asyncpg.Pool:
    """Crée un pool asyncpg avec un codec JSONB transparent (dict ↔ jsonb)."""
    async def _init(conn):
        await conn.set_type_codec(
            "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
        )

    return await asyncpg.create_pool(dsn, init=_init, **kwargs)


async def init_schema(pool: asyncpg.Pool) -> None:
    """Applique tout le schéma du socle (idempotent)."""
    async with pool.acquire() as c:
        await c.execute(ALL_SCHEMA_SQL)


# ── Content (doctrines) ───────────────────────────────────────────────────────


def _doc(r) -> ContentDoc:
    return ContentDoc(
        scope=r["tenant_id"], kind=r["kind"], slug=r["slug"], body=r["body"],
        version=r["version"], title=r["title"], description=r["description"],
        frontmatter=r["frontmatter"] or {},
    )


class PgContentStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def latest(self, scope: Scope, kind: str, slug: str) -> Optional[ContentDoc]:
        r = await self.pool.fetchrow(
            "SELECT * FROM content_docs WHERE tenant_id=$1 AND kind=$2 AND slug=$3",
            scope, kind, slug,
        )
        return _doc(r) if r else None

    async def list(self, scope: Scope, kind: Optional[str] = None) -> list[ContentDoc]:
        if kind is None:
            rows = await self.pool.fetch(
                "SELECT * FROM content_docs WHERE tenant_id=$1 ORDER BY kind, slug", scope
            )
        else:
            rows = await self.pool.fetch(
                "SELECT * FROM content_docs WHERE tenant_id=$1 AND kind=$2 ORDER BY slug", scope, kind
            )
        return [_doc(r) for r in rows]

    async def put(self, doc: ContentDoc, *, set_by: Optional[str] = None) -> ContentDoc:
        async with self.pool.acquire() as c:
            async with c.transaction():
                cur = await c.fetchval(
                    "SELECT version FROM content_docs WHERE tenant_id=$1 AND kind=$2 AND slug=$3",
                    doc.scope, doc.kind, doc.slug,
                )
                v = (cur or 0) + 1
                await c.execute(
                    """INSERT INTO content_docs
                       (tenant_id,kind,slug,title,description,body,frontmatter,version,set_by,updated_at)
                       VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,NOW())
                       ON CONFLICT (tenant_id,kind,slug) DO UPDATE SET
                         title=EXCLUDED.title, description=EXCLUDED.description, body=EXCLUDED.body,
                         frontmatter=EXCLUDED.frontmatter, version=EXCLUDED.version,
                         set_by=EXCLUDED.set_by, updated_at=NOW()""",
                    doc.scope, doc.kind, doc.slug, doc.title, doc.description, doc.body,
                    doc.frontmatter, v, set_by,
                )
                await c.execute(
                    """INSERT INTO content_revisions
                       (tenant_id,kind,slug,version,title,description,body,frontmatter,set_by)
                       VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)""",
                    doc.scope, doc.kind, doc.slug, v, doc.title, doc.description, doc.body,
                    doc.frontmatter, set_by,
                )
        return replace(doc, version=v)

    async def history(self, scope: Scope, kind: str, slug: str) -> list[ContentDoc]:
        rows = await self.pool.fetch(
            "SELECT * FROM content_revisions WHERE tenant_id=$1 AND kind=$2 AND slug=$3 ORDER BY version",
            scope, kind, slug,
        )
        return [_doc(r) for r in rows]


# ── Memory (mémoire partagée) ─────────────────────────────────────────────────


def _entry(r) -> MemoryEntry:
    return MemoryEntry(
        scope=r["tenant_id"], key=r["key"], content=r["content"],
        version=r["version"], author=r["author"], updated_at=r["created_at"],
    )


class PgMemoryStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def latest(self, scope: Scope, key: str) -> Optional[MemoryEntry]:
        r = await self.pool.fetchrow(
            "SELECT * FROM shared_memory WHERE tenant_id=$1 AND key=$2 ORDER BY version DESC LIMIT 1",
            scope, key,
        )
        return _entry(r) if r else None

    async def list(self, scope: Scope) -> list[MemoryEntry]:
        rows = await self.pool.fetch(
            """SELECT DISTINCT ON (key) * FROM shared_memory WHERE tenant_id=$1
               ORDER BY key, version DESC""",
            scope,
        )
        return [_entry(r) for r in rows]

    async def put(self, scope: Scope, key: str, content: str, *, author: Optional[str] = None) -> MemoryEntry:
        async with self.pool.acquire() as c:
            async with c.transaction():
                cur = await c.fetchval(
                    "SELECT MAX(version) FROM shared_memory WHERE tenant_id=$1 AND key=$2", scope, key
                )
                v = (cur or 0) + 1
                r = await c.fetchrow(
                    """INSERT INTO shared_memory (tenant_id,key,version,content,author)
                       VALUES($1,$2,$3,$4,$5) RETURNING *""",
                    scope, key, v, content, author,
                )
        return _entry(r)

    async def history(self, scope: Scope, key: str) -> list[MemoryEntry]:
        rows = await self.pool.fetch(
            "SELECT * FROM shared_memory WHERE tenant_id=$1 AND key=$2 ORDER BY version", scope, key
        )
        return [_entry(r) for r in rows]


# ── RBAC (rôles) ──────────────────────────────────────────────────────────────


class PgRoleStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def role(self, scope: Scope, sub: Optional[str]) -> Optional[str]:
        if sub is None:
            return None
        return await self.pool.fetchval(
            "SELECT role FROM member_roles WHERE tenant_id=$1 AND sub=$2", scope, sub
        )

    async def set_role(self, scope: Scope, sub: str, role: str) -> None:
        await self.pool.execute(
            """INSERT INTO member_roles (tenant_id,sub,role,updated_at) VALUES($1,$2,$3,NOW())
               ON CONFLICT (tenant_id,sub) DO UPDATE SET role=EXCLUDED.role, updated_at=NOW()""",
            scope, sub, role,
        )


# ── ACL (grants) ──────────────────────────────────────────────────────────────


class PgGrantStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def grants(self, scope: Scope, sub: str) -> set[str]:
        rows = await self.pool.fetch(
            "SELECT resource FROM grants WHERE tenant_id=$1 AND sub=$2", scope, sub
        )
        return {r["resource"] for r in rows}

    async def all_grants(self, scope: Scope) -> list[tuple[str, str]]:
        rows = await self.pool.fetch(
            "SELECT sub, resource FROM grants WHERE tenant_id=$1 ORDER BY sub, resource", scope
        )
        return [(r["sub"], r["resource"]) for r in rows]

    async def grant(self, scope: Scope, sub: str, resource: str) -> None:
        await self.pool.execute(
            """INSERT INTO grants (tenant_id,sub,resource) VALUES($1,$2,$3)
               ON CONFLICT DO NOTHING""",
            scope, sub, resource,
        )

    async def revoke(self, scope: Scope, sub: str, resource: str) -> None:
        await self.pool.execute(
            "DELETE FROM grants WHERE tenant_id=$1 AND sub=$2 AND resource=$3", scope, sub, resource
        )


# ── Feedback (capitalisation) ─────────────────────────────────────────────────


class PgFeedbackStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def recent(self, server: str, limit: int) -> list[dict]:
        rows = await self.pool.fetch(
            """SELECT created_at, signal, kind, target, text, sub, email, run_id
               FROM tool_feedback WHERE server=$1 ORDER BY created_at DESC LIMIT $2""",
            server, limit,
        )
        return [
            {
                "at": r["created_at"].isoformat(), "signal": r["signal"], "kind": r["kind"],
                "target": r["target"], "text": r["text"], "sub": r["sub"],
                "email": r["email"], "run_id": r["run_id"],
            }
            for r in rows
        ]


# ── Sinks (feedback + journal d'appels) ───────────────────────────────────────


def make_pg_feedback_sink(pool: asyncpg.Pool):
    """Sink async pour le tool `feedback` → table tool_feedback."""
    async def sink(row: dict) -> None:
        await pool.execute(
            """INSERT INTO tool_feedback (server,signal,kind,target,text,sub,email,run_id)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8)""",
            row.get("server"), row.get("signal"), row.get("kind"), row.get("target"),
            row.get("text"), row.get("sub"), row.get("email"), row.get("run_id"),
        )

    return sink


def make_pg_log_sink(pool: asyncpg.Pool):
    """Sink async pour le middleware AccessLogger → table tool_calls."""
    async def sink(row: dict) -> None:
        await pool.execute(
            """INSERT INTO tool_calls (server,tool,args,sub,email,run_id,ok,error,duration_ms)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)""",
            row.get("server"), row.get("tool"), row.get("args"), row.get("sub"),
            row.get("email"), row.get("run_id"), row.get("ok"), row.get("error"),
            row.get("duration_ms"),
        )

    return sink
