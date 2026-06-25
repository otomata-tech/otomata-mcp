"""Intégration : build_server sur un vrai Postgres (adaptateur asyncpg) + ACL + RBAC.

Skippé si OTOMATA_MCP_TEST_PG (DSN) n'est pas fourni. Prouve bout en bout :
  - les stores Pg (content/memory/role/grant/feedback) + sinks fonctionnent ;
  - l'ACL gate les appels et masque les tools non accordés, par utilisateur ;
  - le RBAC (rôle org_admin via PgRoleStore) gate l'écriture de doctrine ;
  - mémoire et doctrine versionnées ; feedback persisté et relu (digest admin)."""
import asyncio
import logging
import os

import pytest
from fastmcp import Client

from otomata_mcp import (
    ConstantScope,
    Identity,
    build_server,
    set_resolver,
)
from otomata_mcp.adapters.pg import (
    PgContentStore,
    PgFeedbackStore,
    PgGrantStore,
    PgMemoryStore,
    PgRoleStore,
    create_pool,
    init_schema,
    make_pg_feedback_sink,
    make_pg_log_sink,
)
from otomata_mcp.rbac.roles import ORG_ADMIN

logging.getLogger("FastMCP").setLevel(logging.CRITICAL)

DSN = os.environ.get("OTOMATA_MCP_TEST_PG")
SCOPE = "acme"
_TABLES = ["content_docs", "content_revisions", "shared_memory", "member_roles",
           "grants", "tool_feedback", "tool_calls"]


async def _scenario():
    pool = await create_pool(DSN)
    await init_schema(pool)
    async with pool.acquire() as c:
        await c.execute("TRUNCATE " + ", ".join(_TABLES))

    content = PgContentStore(pool)
    memory = PgMemoryStore(pool)
    roles = PgRoleStore(pool)
    grants = PgGrantStore(pool)
    feedback = PgFeedbackStore(pool)

    # Seed: rôle de base (RBAC) + grants (ACL) coexistent.
    # alice = org_admin + grant admin ; bob = member granted memory + feedback.
    await roles.set_role(SCOPE, "alice", ORG_ADMIN)
    await roles.set_role(SCOPE, "bob", "member")
    await grants.grant(SCOPE, "alice", "admin")
    for r in ("tool:memory_read", "tool:memory_write", "tool:feedback"):
        await grants.grant(SCOPE, "bob", r)

    who = {"sub": None}
    set_resolver(lambda: Identity(who["sub"]) if who["sub"] else None)

    mcp = build_server(
        "pgtest",
        content_store=content,
        role_store=roles,
        scope_resolver=ConstantScope(SCOPE),
        sink=make_pg_log_sink(pool),
        feedback_sink=make_pg_feedback_sink(pool),
        feedback_store=feedback,
        memory_store=memory,
        grant_store=grants,
        acl_public_tools=["readme_agent"],
    )

    out = {}
    async with Client(mcp) as client:
        # ── bob (member) ──
        who["sub"] = "bob"
        bob_tools = sorted(t.name for t in await client.list_tools())
        out["bob_tools"] = bob_tools

        w1 = await client.call_tool("memory_write", {"key": "onboarding", "content": "v1"})
        w2 = await client.call_tool("memory_write", {"key": "onboarding", "content": "v2"})
        out["mem_version"] = w2.data["version"]
        out["mem_read"] = (await client.call_tool("memory_read", {"key": "onboarding"})).data["content"]
        await client.call_tool("feedback", {"signal": "gap", "kind": "missing_tool", "target": "export PDF"})

        out["bob_listfeedback_denied"] = False
        try:
            await client.call_tool("list_feedback", {})
        except Exception:
            out["bob_listfeedback_denied"] = True
        out["bob_grant_denied"] = False
        try:
            await client.call_tool("grant", {"sub": "bob", "resource": "admin"})
        except Exception:
            out["bob_grant_denied"] = True

        # ── alice (org_admin + admin) ──
        who["sub"] = "alice"
        await client.call_tool("set_instruction", {"kind": "rule", "slug": "seuils", "body": "Prix unitaire."})
        out["doc"] = (await client.call_tool("get_instruction", {"kind": "rule", "slug": "seuils"})).data["body"]
        await client.call_tool("grant", {"sub": "costas", "resource": "tool:memory_read"})
        out["all_grants"] = (await client.call_tool("list_grants", {})).data
        digest = await client.call_tool("list_feedback", {})
        out["digest"] = digest.data

        await asyncio.sleep(0.3)  # laisse le sink de logs (fire-and-forget) flusher

    async with pool.acquire() as c:
        out["calllog_count"] = await c.fetchval("SELECT COUNT(*) FROM tool_calls WHERE server='pgtest'")
    await pool.close()
    return out


@pytest.mark.skipif(not DSN, reason="OTOMATA_MCP_TEST_PG (DSN Postgres) non fourni")
def test_pg_adapter():
    out = asyncio.run(_scenario())

    # ACL : la liste de bob exclut les tools admin-only, expose les siens + le public.
    assert "memory_write" in out["bob_tools"] and "readme_agent" in out["bob_tools"]
    for hidden in ("list_feedback", "grant", "revoke", "list_grants", "set_instruction"):
        assert hidden not in out["bob_tools"], f"{hidden} ne devrait pas être visible par bob"
    assert out["bob_listfeedback_denied"], "bob a pu lire le digest (ACL cassée)"
    assert out["bob_grant_denied"], "bob a pu accorder un grant (ACL cassée)"

    # Persistance Pg : mémoire versionnée, doctrine écrite, feedback relu.
    assert out["mem_version"] == 2 and out["mem_read"] == "v2", "mémoire Pg non versionnée"
    assert out["doc"] == "Prix unitaire.", "doctrine Pg non persistée"
    assert any(g["sub"] == "costas" for g in out["all_grants"]), "grant non persisté"
    assert out["digest"] and out["digest"][0]["signal"] == "gap", "feedback non relu (digest)"

    # Tout est un tool → tout est tracé (journal Pg).
    assert out["calllog_count"] >= 5, f"journal d'appels trop court ({out['calllog_count']})"
