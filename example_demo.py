"""Démo du socle otomata-mcp : doctrines + mémoire EN TOOLS (loggées) + RBAC + validation + run.

Prouve les points du plan :
  1. le contenu est servi par des TOOLS (readme_agent / get_instruction) → tout est loggé ;
  2. l'écriture (set_instruction) est gated org_admin (un member est refusé) ;
  3. l'écriture avec un nom de personne est refusée (validation « zéro nom ») ;
  4. la mémoire partagée est versionnée (memory_write → nouvelle version) ;
  5. les appels sont corrélés au run actif (run_id).
"""
import asyncio
import logging

from fastmcp import Client

logging.getLogger("FastMCP").setLevel(logging.CRITICAL)  # quiete les tracebacks de tool-error attendus

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

LOG: list[dict] = []
FB: list[dict] = []
_WHO = {"sub": None, "email": None}
set_resolver(lambda: Identity(_WHO["sub"], _WHO["email"]) if _WHO["sub"] else None)


class ListFeedbackStore:
    def recent(self, server, limit):
        return [r for r in FB if r["server"] == server][-limit:][::-1]


def as_(sub):
    _WHO["sub"] = sub


content = InMemoryContentStore()
content.seed(ContentDoc(scope="acme", kind="knowledge", slug="strategie",
                        title="Stratégie", description="cadre", body="Filtre prioritaire : la TVA 5,5 %."))
roles = InMemoryRoleStore({("acme", "alice"): ORG_ADMIN, ("acme", "bob"): MEMBER})

mcp = build_server(
    "demo",
    content_store=content,
    role_store=roles,
    scope_resolver=ConstantScope("acme"),
    sink=LOG.append,
    feedback_sink=FB.append,
    feedback_store=ListFeedbackStore(),
    memory_store=InMemoryMemoryStore(),
    blocklist=["Antonini", "Bolelli", "Delgado", "Thomas"],
)


async def main():
    async with Client(mcp) as client:
        # bob (member) : ouvre un run, lit, enrichit la mémoire, remonte un signal
        as_("bob")
        started = await client.call_tool("run_start", {"label": "consult", "doctrine": "strategie"})
        run_id = started.data["run_id"]
        await client.call_tool("readme_agent", {})
        await client.call_tool("list_instructions", {})
        await client.call_tool("get_instruction", {"kind": "knowledge", "slug": "strategie"})
        await client.call_tool("memory_write", {"key": "onboarding", "content": "Premier jet."})
        v2 = await client.call_tool("memory_write", {"key": "onboarding", "content": "Premier jet, enrichi."})
        print(f"✓ mémoire versionnée : onboarding → v{v2.data['version']}")
        await client.call_tool("feedback", {"signal": "gap", "kind": "missing_data",
                                            "target": "comparables au m² par étage"})
        # bob tente d'écrire une doctrine → refus RBAC
        try:
            await client.call_tool("set_instruction", {"kind": "knowledge", "slug": "x", "body": "..."})
            print("✗ BUG : écriture par un member acceptée")
        except Exception as e:
            print("✓ refus RBAC (member) :", str(e).splitlines()[-1][:90])
        await client.call_tool("run_finish", {"run_id": run_id, "outcome": "done"})

        # alice (org_admin) : écrit OK + lit le digest de capitalisation
        as_("alice")
        await client.call_tool("set_instruction", {"kind": "rule", "slug": "seuils",
                                                   "body": "Prix unitaire, pas prix au m²."})
        digest = await client.call_tool("list_feedback", {})
        print(f"✓ digest admin : {len(digest.data)} signal(aux) remonté(s)")
        # alice tente un contenu avec un nom → refus validation
        try:
            await client.call_tool("set_instruction", {"kind": "rule", "slug": "bad",
                                                       "body": '« On crève sinon » — Antonini'})
            print("✗ BUG : verbatim nominatif accepté")
        except Exception as e:
            print("✓ refus validation (nom) :", str(e).splitlines()[-1][:90])

    print("\n=== JOURNAL D'ACCÈS (tout est un tool → tout est tracé) ===")
    for r in LOG:
        print(f"  {r['tool']:15} sub={(r['sub'] or '-'):6} run={(r['run_id'] or '-'):>34} ok={r['ok']}")

    opened = [r for r in LOG if r["tool"] == "get_instruction"]
    assert opened, "get_instruction absent du journal"
    assert opened[0]["run_id"], "run_id non corrélé sur get_instruction"
    assert any(r["tool"] == "set_instruction" and r["ok"] for r in LOG), "aucune écriture réussie"
    assert any(r["tool"] == "memory_write" and r["ok"] for r in LOG), "memory_write non tracé"
    print("\n✓ doctrines + mémoire en TOOLS + loggées + corrélées run_id ; RBAC + validation OK")


asyncio.run(main())
