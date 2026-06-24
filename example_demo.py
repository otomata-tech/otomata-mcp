"""Démo du socle otomata-mcp : doctrines EN TOOLS (loggées) + RBAC + validation + run.

Prouve les 4 points du plan :
  1. le contenu est servi par des TOOLS (doctrine_list/open) → tout est loggé ;
  2. l'écriture (doctrine_set) est gated org_admin (un member est refusé) ;
  3. l'écriture avec un nom de personne est refusée (validation « zéro nom ») ;
  4. les appels sont corrélés au run actif (run_id).
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
    InMemoryRoleStore,
    build_server,
    set_resolver,
)
from otomata_mcp.rbac.roles import MEMBER, ORG_ADMIN

LOG: list[dict] = []
_WHO = {"sub": None, "email": None}
set_resolver(lambda: Identity(_WHO["sub"], _WHO["email"]) if _WHO["sub"] else None)


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
    blocklist=["Antonini", "Bolelli", "Delgado", "Thomas"],
)


async def main():
    async with Client(mcp) as client:
        # bob (member) : ouvre un run, lit
        as_("bob")
        started = await client.call_tool("run_start", {"label": "consult", "doctrine": "strategie"})
        run_id = started.data["run_id"]
        await client.call_tool("readme_agent", {})
        await client.call_tool("list_instructions", {})
        await client.call_tool("get_instruction", {"kind": "knowledge", "slug": "strategie"})
        # bob tente d'écrire → refus RBAC
        try:
            await client.call_tool("set_instruction", {"kind": "knowledge", "slug": "x", "body": "..."})
            print("✗ BUG : écriture par un member acceptée")
        except Exception as e:
            print("✓ refus RBAC (member) :", str(e).splitlines()[-1][:90])
        await client.call_tool("run_finish", {"run_id": run_id, "outcome": "done"})

        # alice (org_admin) : écrit OK
        as_("alice")
        await client.call_tool("set_instruction", {"kind": "rule", "slug": "seuils",
                                                   "body": "Prix unitaire, pas prix au m²."})
        # alice tente un contenu avec un nom → refus validation
        try:
            await client.call_tool("set_instruction", {"kind": "rule", "slug": "bad",
                                                       "body": '« On crève sinon » — Antonini'})
            print("✗ BUG : verbatim nominatif accepté")
        except Exception as e:
            print("✓ refus validation (nom) :", str(e).splitlines()[-1][:90])

    print("\n=== JOURNAL D'ACCÈS (tout est un tool → tout est tracé) ===")
    for r in LOG:
        print(f"  {r['tool']:13} sub={(r['sub'] or '-'):6} run={(r['run_id'] or '-'):>34} ok={r['ok']}")

    opened = [r for r in LOG if r["tool"] == "doctrine_open"]
    assert opened, "doctrine_open absent du journal"
    assert opened[0]["run_id"], "run_id non corrélé sur doctrine_open"
    assert any(r["tool"] == "doctrine_set" and r["ok"] for r in LOG), "aucune écriture réussie"
    assert sum(1 for r in LOG if r["tool"] == "doctrine_set" and not r["ok"]) == 2, "refus attendus manquants"
    print("\n✓ doctrines en TOOLS + loggées + corrélées run_id ; RBAC + validation OK")


asyncio.run(main())
