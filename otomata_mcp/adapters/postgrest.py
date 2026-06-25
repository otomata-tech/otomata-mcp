"""Adaptateur PostgREST / Supabase (httpx) prêt à l'emploi pour tous les stores du socle.

Même contrat que l'adaptateur asyncpg, mais la persistance passe par l'API REST PostgREST
(ex. OGIC sur Supabase) au lieu d'une connexion SQL directe. Le schéma (DDL) reste celui du
socle, appliqué à la base sous-jacente (les `*_SCHEMA_SQL` du socle) — PostgREST n'exécute
pas de DDL, il expose les tables.

Multi-tenant par `tenant_id` (le scope). Toutes les méthodes sont ASYNC.
Installe l'extra : `pip install otomata-mcp[postgrest]` (httpx)."""
from __future__ import annotations

import datetime as _dt
from dataclasses import replace
from typing import Optional

import httpx

from ..content.model import ContentDoc
from ..memory.model import MemoryEntry
from ..scope import Scope


class PostgrestClient:
    """Petit wrapper REST PostgREST/Supabase. `apikey` pose les en-têtes Supabase
    (apikey + Bearer) ; sinon passer `headers` (ex. un JWT) directement."""

    def __init__(self, base_url: str, *, apikey: Optional[str] = None,
                 headers: Optional[dict] = None, timeout: float = 20.0) -> None:
        h = dict(headers or {})
        if apikey:
            h.setdefault("apikey", apikey)
            h.setdefault("Authorization", f"Bearer {apikey}")
        self._c = httpx.AsyncClient(base_url=base_url.rstrip("/"), headers=h, timeout=timeout)

    async def select(self, table: str, params: dict) -> list[dict]:
        r = await self._c.get(f"/{table}", params=params)
        r.raise_for_status()
        return r.json()

    async def insert(self, table: str, row: dict, *, upsert: bool = False, returning: bool = True):
        prefer = ["resolution=merge-duplicates"] if upsert else []
        prefer.append("return=representation" if returning else "return=minimal")
        r = await self._c.post(f"/{table}", json=row, headers={"Prefer": ",".join(prefer)})
        r.raise_for_status()
        return r.json() if returning else None

    async def delete(self, table: str, params: dict) -> None:
        r = await self._c.request("DELETE", f"/{table}", params=params)
        r.raise_for_status()

    async def aclose(self) -> None:
        await self._c.aclose()


def _eq(value) -> str:
    return f"eq.{value}"


def _dtparse(value):
    if value is None or isinstance(value, _dt.datetime):
        return value
    return _dt.datetime.fromisoformat(value)


# ── Content (doctrines) ───────────────────────────────────────────────────────


def _doc(r) -> ContentDoc:
    return ContentDoc(
        scope=r["tenant_id"], kind=r["kind"], slug=r["slug"], body=r["body"],
        version=r["version"], title=r.get("title", ""), description=r.get("description", ""),
        frontmatter=r.get("frontmatter") or {},
    )


class PostgrestContentStore:
    def __init__(self, client: PostgrestClient) -> None:
        self.c = client

    async def latest(self, scope: Scope, kind: str, slug: str) -> Optional[ContentDoc]:
        rows = await self.c.select("content_docs", {
            "tenant_id": _eq(scope), "kind": _eq(kind), "slug": _eq(slug), "limit": 1})
        return _doc(rows[0]) if rows else None

    async def list(self, scope: Scope, kind: Optional[str] = None) -> list[ContentDoc]:
        params = {"tenant_id": _eq(scope), "order": "kind.asc,slug.asc"}
        if kind is not None:
            params["kind"] = _eq(kind)
        return [_doc(r) for r in await self.c.select("content_docs", params)]

    async def put(self, doc: ContentDoc, *, set_by: Optional[str] = None) -> ContentDoc:
        cur = await self.c.select("content_docs", {
            "tenant_id": _eq(doc.scope), "kind": _eq(doc.kind), "slug": _eq(doc.slug),
            "select": "version", "limit": 1})
        v = (cur[0]["version"] if cur else 0) + 1
        body = {"tenant_id": doc.scope, "kind": doc.kind, "slug": doc.slug, "title": doc.title,
                "description": doc.description, "body": doc.body, "frontmatter": doc.frontmatter,
                "version": v, "set_by": set_by}
        await self.c.insert("content_docs", body, upsert=True, returning=False)
        await self.c.insert("content_revisions", {
            "tenant_id": doc.scope, "kind": doc.kind, "slug": doc.slug, "version": v,
            "title": doc.title, "description": doc.description, "body": doc.body,
            "frontmatter": doc.frontmatter, "set_by": set_by}, returning=False)
        return replace(doc, version=v)

    async def history(self, scope: Scope, kind: str, slug: str) -> list[ContentDoc]:
        rows = await self.c.select("content_revisions", {
            "tenant_id": _eq(scope), "kind": _eq(kind), "slug": _eq(slug), "order": "version.asc"})
        return [_doc(r) for r in rows]


# ── Memory (mémoire partagée) ─────────────────────────────────────────────────


def _entry(r) -> MemoryEntry:
    return MemoryEntry(
        scope=r["tenant_id"], key=r["key"], content=r["content"], version=r["version"],
        author=r.get("author"), updated_at=_dtparse(r.get("created_at")))


class PostgrestMemoryStore:
    def __init__(self, client: PostgrestClient) -> None:
        self.c = client

    async def latest(self, scope: Scope, key: str) -> Optional[MemoryEntry]:
        rows = await self.c.select("shared_memory", {
            "tenant_id": _eq(scope), "key": _eq(key), "order": "version.desc", "limit": 1})
        return _entry(rows[0]) if rows else None

    async def list(self, scope: Scope) -> list[MemoryEntry]:
        # PostgREST n'a pas de DISTINCT ON simple : on trie et on dédoublonne côté client.
        rows = await self.c.select("shared_memory", {
            "tenant_id": _eq(scope), "order": "key.asc,version.desc"})
        out, seen = [], set()
        for r in rows:
            if r["key"] not in seen:
                seen.add(r["key"])
                out.append(_entry(r))
        return out

    async def put(self, scope: Scope, key: str, content: str, *, author: Optional[str] = None) -> MemoryEntry:
        cur = await self.c.select("shared_memory", {
            "tenant_id": _eq(scope), "key": _eq(key), "select": "version",
            "order": "version.desc", "limit": 1})
        v = (cur[0]["version"] if cur else 0) + 1
        rows = await self.c.insert("shared_memory", {
            "tenant_id": scope, "key": key, "version": v, "content": content, "author": author})
        return _entry(rows[0])

    async def history(self, scope: Scope, key: str) -> list[MemoryEntry]:
        rows = await self.c.select("shared_memory", {
            "tenant_id": _eq(scope), "key": _eq(key), "order": "version.asc"})
        return [_entry(r) for r in rows]


# ── RBAC (rôles) ──────────────────────────────────────────────────────────────


class PostgrestRoleStore:
    def __init__(self, client: PostgrestClient) -> None:
        self.c = client

    async def role(self, scope: Scope, sub: Optional[str]) -> Optional[str]:
        if sub is None:
            return None
        rows = await self.c.select("member_roles", {
            "tenant_id": _eq(scope), "sub": _eq(sub), "select": "role", "limit": 1})
        return rows[0]["role"] if rows else None

    async def set_role(self, scope: Scope, sub: str, role: str) -> None:
        await self.c.insert("member_roles", {"tenant_id": scope, "sub": sub, "role": role},
                            upsert=True, returning=False)


# ── ACL (grants) ──────────────────────────────────────────────────────────────


class PostgrestGrantStore:
    def __init__(self, client: PostgrestClient) -> None:
        self.c = client

    async def grants(self, scope: Scope, sub: str) -> set[str]:
        rows = await self.c.select("grants", {
            "tenant_id": _eq(scope), "sub": _eq(sub), "select": "resource"})
        return {r["resource"] for r in rows}

    async def all_grants(self, scope: Scope) -> list[tuple[str, str]]:
        rows = await self.c.select("grants", {
            "tenant_id": _eq(scope), "select": "sub,resource", "order": "sub.asc,resource.asc"})
        return [(r["sub"], r["resource"]) for r in rows]

    async def grant(self, scope: Scope, sub: str, resource: str) -> None:
        await self.c.insert("grants", {"tenant_id": scope, "sub": sub, "resource": resource},
                            upsert=True, returning=False)

    async def revoke(self, scope: Scope, sub: str, resource: str) -> None:
        await self.c.delete("grants", {
            "tenant_id": _eq(scope), "sub": _eq(sub), "resource": _eq(resource)})


# ── Feedback (capitalisation) ─────────────────────────────────────────────────


class PostgrestFeedbackStore:
    def __init__(self, client: PostgrestClient) -> None:
        self.c = client

    async def recent(self, server: str, limit: int) -> list[dict]:
        rows = await self.c.select("tool_feedback", {
            "server": _eq(server), "order": "created_at.desc", "limit": limit,
            "select": "created_at,signal,kind,target,text,sub,email,run_id"})
        return [
            {"at": r["created_at"], "signal": r["signal"], "kind": r["kind"], "target": r["target"],
             "text": r["text"], "sub": r["sub"], "email": r["email"], "run_id": r["run_id"]}
            for r in rows
        ]


# ── Sinks (feedback + journal d'appels) ───────────────────────────────────────


def make_postgrest_feedback_sink(client: PostgrestClient):
    async def sink(row: dict) -> None:
        await client.insert("tool_feedback", {
            "server": row.get("server"), "signal": row.get("signal"), "kind": row.get("kind"),
            "target": row.get("target"), "text": row.get("text"), "sub": row.get("sub"),
            "email": row.get("email"), "run_id": row.get("run_id")}, returning=False)

    return sink


def make_postgrest_log_sink(client: PostgrestClient):
    async def sink(row: dict) -> None:
        await client.insert("tool_calls", {
            "server": row.get("server"), "tool": row.get("tool"), "args": row.get("args"),
            "sub": row.get("sub"), "email": row.get("email"), "run_id": row.get("run_id"),
            "ok": row.get("ok"), "error": row.get("error"),
            "duration_ms": row.get("duration_ms")}, returning=False)

    return sink
