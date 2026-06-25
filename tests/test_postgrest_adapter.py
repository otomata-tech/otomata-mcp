"""Intégration : build_server sur un vrai PostgREST (adaptateur httpx) + ACL + RBAC.

Skippé si OTOMATA_MCP_TEST_POSTGREST (URL de base PostgREST) n'est pas fourni. Même
scénario que le test asyncpg, mais la persistance passe par l'API REST (cible OGIC/Supabase)."""
import asyncio
import logging
import os

import pytest
from fastmcp import Client

from otomata_mcp import ConstantScope, Identity, build_server, set_resolver
from otomata_mcp.adapters.postgrest import (
    PostgrestClient,
    PostgrestContentStore,
    PostgrestFeedbackStore,
    PostgrestGrantStore,
    PostgrestMemoryStore,
    PostgrestRoleStore,
    make_postgrest_feedback_sink,
    make_postgrest_log_sink,
)
from otomata_mcp.rbac.roles import ORG_ADMIN

logging.getLogger("FastMCP").setLevel(logging.CRITICAL)

BASE = os.environ.get("OTOMATA_MCP_TEST_POSTGREST")
SCOPE = "acme"
SERVER = "prest"


async def _cleanup(client: PostgrestClient) -> None:
    for table in ("content_docs", "content_revisions", "shared_memory", "member_roles", "grants"):
        await client.delete(table, {"tenant_id": f"eq.{SCOPE}"})
    for table in ("tool_feedback", "tool_calls"):
        await client.delete(table, {"server": f"eq.{SERVER}"})


async def _scenario():
    client = PostgrestClient(BASE)
    await _cleanup(client)

    content, memory = PostgrestContentStore(client), PostgrestMemoryStore(client)
    roles, grants = PostgrestRoleStore(client), PostgrestGrantStore(client)
    feedback = PostgrestFeedbackStore(client)

    await roles.set_role(SCOPE, "alice", ORG_ADMIN)
    await roles.set_role(SCOPE, "bob", "member")
    await grants.grant(SCOPE, "alice", "admin")
    for r in ("tool:memory_read", "tool:memory_write", "tool:feedback"):
        await grants.grant(SCOPE, "bob", r)

    who = {"sub": None}
    set_resolver(lambda: Identity(who["sub"]) if who["sub"] else None)

    mcp = build_server(
        SERVER,
        content_store=content,
        role_store=roles,
        scope_resolver=ConstantScope(SCOPE),
        sink=make_postgrest_log_sink(client),
        feedback_sink=make_postgrest_feedback_sink(client),
        feedback_store=feedback,
        memory_store=memory,
        grant_store=grants,
        acl_public_tools=["readme_agent"],
    )

    out = {}
    async with Client(mcp) as cl:
        who["sub"] = "bob"
        out["bob_tools"] = sorted(t.name for t in await cl.list_tools())
        await cl.call_tool("memory_write", {"key": "onboarding", "content": "v1"})
        w2 = await cl.call_tool("memory_write", {"key": "onboarding", "content": "v2"})
        out["mem_version"] = w2.data["version"]
        out["mem_read"] = (await cl.call_tool("memory_read", {"key": "onboarding"})).data["content"]
        await cl.call_tool("feedback", {"signal": "gap", "kind": "missing_tool", "target": "export PDF"})
        out["bob_listfeedback_denied"] = False
        try:
            await cl.call_tool("list_feedback", {})
        except Exception:
            out["bob_listfeedback_denied"] = True

        who["sub"] = "alice"
        await cl.call_tool("set_instruction", {"kind": "rule", "slug": "seuils", "body": "Prix unitaire."})
        out["doc"] = (await cl.call_tool("get_instruction", {"kind": "rule", "slug": "seuils"})).data["body"]
        await cl.call_tool("grant", {"sub": "costas", "resource": "tool:memory_read"})
        out["all_grants"] = (await cl.call_tool("list_grants", {})).data
        out["digest"] = (await cl.call_tool("list_feedback", {})).data
        await asyncio.sleep(0.4)  # laisse le sink de logs (fire-and-forget) flusher

    out["calllog"] = await client.select("tool_calls", {"server": f"eq.{SERVER}", "select": "id"})
    await client.aclose()
    return out


@pytest.mark.skipif(not BASE, reason="OTOMATA_MCP_TEST_POSTGREST (URL PostgREST) non fourni")
def test_postgrest_adapter():
    out = asyncio.run(_scenario())

    assert "memory_write" in out["bob_tools"] and "readme_agent" in out["bob_tools"]
    for hidden in ("list_feedback", "grant", "revoke", "list_grants", "set_instruction"):
        assert hidden not in out["bob_tools"], f"{hidden} ne devrait pas être visible par bob"
    assert out["bob_listfeedback_denied"], "bob a pu lire le digest (ACL cassée)"

    assert out["mem_version"] == 2 and out["mem_read"] == "v2", "mémoire PostgREST non versionnée"
    assert out["doc"] == "Prix unitaire.", "doctrine PostgREST non persistée"
    assert any(g["sub"] == "costas" for g in out["all_grants"]), "grant non persisté"
    assert out["digest"] and out["digest"][0]["signal"] == "gap", "feedback non relu (digest)"
    assert len(out["calllog"]) >= 5, f"journal d'appels trop court ({len(out['calllog'])})"
