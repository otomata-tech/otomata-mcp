"""Test du socle : doctrines-tools loggées + corrélées run_id, RBAC, validation « zéro nom »."""
import asyncio
import logging

from fastmcp import Client

from otomata_mcp import (
    ConstantScope,
    ContentDoc,
    Identity,
    InMemoryContentStore,
    InMemoryRoleStore,
    build_server,
    set_resolver,
)
from otomata_mcp.rbac.roles import MEMBER, ORG_ADMIN

logging.getLogger("FastMCP").setLevel(logging.CRITICAL)


def _build():
    log: list[dict] = []
    who = {"sub": None}
    set_resolver(lambda: Identity(who["sub"]) if who["sub"] else None)

    content = InMemoryContentStore()
    content.seed(ContentDoc(scope="acme", kind="knowledge", slug="strategie",
                            title="Stratégie", body="Filtre prioritaire : la TVA 5,5 %."))
    roles = InMemoryRoleStore({("acme", "alice"): ORG_ADMIN, ("acme", "bob"): MEMBER})
    mcp = build_server("test", content_store=content, role_store=roles,
                       scope_resolver=ConstantScope("acme"), sink=log.append,
                       blocklist=["Antonini"])
    return mcp, log, who


async def _scenario():
    mcp, log, who = _build()
    async with Client(mcp) as client:
        who["sub"] = "bob"
        started = await client.call_tool("run_start", {"label": "consult"})
        run_id = started.data["run_id"]
        readme = await client.call_tool("readme_agent", {})
        assert readme.data["instructions"], "readme_agent doit renvoyer l'index"
        await client.call_tool("get_instruction", {"kind": "knowledge", "slug": "strategie"})
        bob_set_refused = False
        try:
            await client.call_tool("set_instruction", {"kind": "knowledge", "slug": "x", "body": "y"})
        except Exception:
            bob_set_refused = True
        await client.call_tool("run_finish", {"run_id": run_id, "outcome": "done"})

        who["sub"] = "alice"
        await client.call_tool("set_instruction", {"kind": "rule", "slug": "seuils", "body": "Prix unitaire."})
        name_refused = False
        try:
            await client.call_tool("set_instruction", {"kind": "rule", "slug": "bad", "body": "« x » — Antonini"})
        except Exception:
            name_refused = True
    return log, run_id, bob_set_refused, name_refused


def test_socle():
    log, run_id, bob_set_refused, name_refused = asyncio.run(_scenario())

    opened = [r for r in log if r["tool"] == "get_instruction"]
    assert opened, "get_instruction absent du journal"
    assert opened[0]["run_id"] == run_id, "run_id non corrélé sur get_instruction"

    assert bob_set_refused, "un member a pu écrire (RBAC cassé)"
    assert name_refused, "un verbatim nominatif a été accepté (validation cassée)"
    assert any(r["tool"] == "set_instruction" and r["ok"] for r in log), "aucune écriture org_admin réussie"
