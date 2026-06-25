"""Test du socle : doctrines-tools loggées + corrélées run_id, RBAC, validation « zéro nom »,
mémoire partagée versionnée, et digest de capitalisation (list_feedback) gated admin."""
import asyncio
import logging

from fastmcp import Client

from otomata_mcp import (
    ConstantScope,
    ContentDoc,
    Identity,
    InMemoryContentStore,
    InMemoryMemoryStore,
    InMemoryRoleStore,
    build_server,
    set_resolver,
)
from otomata_mcp.rbac.roles import MEMBER, ORG_ADMIN

logging.getLogger("FastMCP").setLevel(logging.CRITICAL)


class _ListFeedbackStore:
    """Côté lecture du feedback adossé à la même liste que le sink (tests)."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def recent(self, server: str, limit: int) -> list[dict]:
        return [r for r in self._rows if r["server"] == server][-limit:][::-1]


def _build():
    log: list[dict] = []
    fb: list[dict] = []
    who = {"sub": None}
    set_resolver(lambda: Identity(who["sub"]) if who["sub"] else None)

    content = InMemoryContentStore()
    content.seed(ContentDoc(scope="acme", kind="knowledge", slug="strategie",
                            title="Stratégie", body="Filtre prioritaire : la TVA 5,5 %."))
    roles = InMemoryRoleStore({("acme", "alice"): ORG_ADMIN, ("acme", "bob"): MEMBER})
    mcp = build_server("test", content_store=content, role_store=roles,
                       scope_resolver=ConstantScope("acme"), sink=log.append,
                       feedback_sink=fb.append, feedback_store=_ListFeedbackStore(fb),
                       memory_store=InMemoryMemoryStore(), blocklist=["Antonini"])
    return mcp, log, who, fb


async def _scenario():
    mcp, log, who, fb = _build()
    async with Client(mcp) as client:
        who["sub"] = "bob"
        started = await client.call_tool("run_start", {"label": "consult"})
        run_id = started.data["run_id"]
        readme = await client.call_tool("readme_agent", {})
        assert readme.data["instructions"], "readme_agent doit renvoyer l'index"
        await client.call_tool("get_instruction", {"kind": "knowledge", "slug": "strategie"})
        await client.call_tool("feedback", {"signal": "gap", "kind": "missing_data",
                                            "target": "comparables au m² par étage"})

        # Mémoire partagée : bob (member) écrit deux versions, puis relit.
        await client.call_tool("memory_write", {"key": "onboarding", "content": "v1"})
        w2 = await client.call_tool("memory_write", {"key": "onboarding", "content": "v2"})
        assert w2.data["version"] == 2, "la mémoire doit versionner"
        mem = await client.call_tool("memory_read", {"key": "onboarding"})
        assert mem.data["content"] == "v2", "memory_read doit renvoyer la dernière version"
        keys = await client.call_tool("memory_list", {})
        assert any(k["key"] == "onboarding" for k in keys.data), "memory_list doit lister la clé"

        # bob (member) ne doit PAS voir le digest admin.
        bob_digest_refused = False
        try:
            await client.call_tool("list_feedback", {})
        except Exception:
            bob_digest_refused = True

        bob_set_refused = False
        try:
            await client.call_tool("set_instruction", {"kind": "knowledge", "slug": "x", "body": "y"})
        except Exception:
            bob_set_refused = True
        await client.call_tool("run_finish", {"run_id": run_id, "outcome": "done"})

        who["sub"] = "alice"
        await client.call_tool("set_instruction", {"kind": "rule", "slug": "seuils", "body": "Prix unitaire."})
        digest = await client.call_tool("list_feedback", {})
        name_refused = False
        try:
            await client.call_tool("set_instruction", {"kind": "rule", "slug": "bad", "body": "« x » — Antonini"})
        except Exception:
            name_refused = True
    return log, run_id, bob_set_refused, bob_digest_refused, name_refused, fb, digest.data


def test_socle():
    log, run_id, bob_set_refused, bob_digest_refused, name_refused, fb, digest = asyncio.run(_scenario())

    opened = [r for r in log if r["tool"] == "get_instruction"]
    assert opened, "get_instruction absent du journal"
    assert opened[0]["run_id"] == run_id, "run_id non corrélé sur get_instruction"

    assert bob_set_refused, "un member a pu écrire une instruction (RBAC cassé)"
    assert any(r["tool"] == "set_instruction" and r["ok"] for r in log), "aucune écriture org_admin réussie"
    assert name_refused, "un verbatim nominatif a été accepté (validation cassée)"

    assert len(fb) == 1 and fb[0]["signal"] == "gap", "feedback non capté"
    assert fb[0]["run_id"] == run_id, "feedback non corrélé au run"

    # Mémoire : les writes passent par le journal (tout est un tool → tout est tracé).
    assert any(r["tool"] == "memory_write" and r["ok"] for r in log), "memory_write non tracé"

    # Digest de capitalisation : gated admin.
    assert bob_digest_refused, "un member a pu lire le digest (gate admin cassée)"
    assert digest and digest[0]["signal"] == "gap", "list_feedback (admin) doit renvoyer les signaux"
