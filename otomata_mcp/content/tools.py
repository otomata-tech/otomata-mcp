"""Sert les doctrines EN TOOLS (donc loggées). Remplace les resources MCP.

Peu de tools, quel que soit le nombre de docs : list / open / set / get_doctrine.
"""
from __future__ import annotations

from typing import Optional, Sequence

from ..identity import current_sub
from ..rbac.gate import Rbac
from ..rbac.roles import ORG_ADMIN
from ..scope import ScopeResolver
from .model import ContentDoc
from .store import ContentStore
from .validate import validate


def register_content_tools(
    mcp,
    store: ContentStore,
    scope_resolver: ScopeResolver,
    rbac: Rbac,
    *,
    prefix: str = "doctrine",
    blocklist: Sequence[str] = (),
    forbid_attribution: bool = True,
) -> None:
    def _scope():
        return scope_resolver.resolve()

    async def _list(kind: Optional[str] = None) -> list[dict]:
        """Liste les doctrines disponibles (sans le corps)."""
        return [
            {
                "kind": d.kind,
                "slug": d.slug,
                "title": d.title,
                "description": d.description,
                "version": d.version,
            }
            for d in store.list(_scope(), kind)
        ]

    async def _open(kind: str, slug: str) -> dict:
        """Sert le corps d'une doctrine."""
        d = store.latest(_scope(), kind, slug)
        if d is None:
            raise ValueError(f"doctrine introuvable : {kind}/{slug}")
        return {"kind": d.kind, "slug": d.slug, "title": d.title, "version": d.version, "body": d.body}

    async def _set(kind: str, slug: str, body: str, title: str = "", description: str = "") -> dict:
        """Crée/édite une doctrine (réservé org_admin). Refuse tout nom de personne/client."""
        rbac.require(ORG_ADMIN)
        errors = validate(body, blocklist=blocklist, forbid_attribution=forbid_attribution)
        if errors:
            raise ValueError("écriture refusée : " + " ; ".join(errors))
        doc = ContentDoc(scope=_scope(), kind=kind, slug=slug, body=body, title=title, description=description)
        saved = store.put(doc, set_by=current_sub())
        return {"kind": saved.kind, "slug": saved.slug, "version": saved.version}

    async def _get_doctrine() -> dict:
        """Bundle de démarrage : l'index des doctrines (sans corps) pour le scope courant."""
        docs = store.list(_scope(), None)
        return {
            "scope": _scope(),
            "index": [
                {"kind": d.kind, "slug": d.slug, "title": d.title, "description": d.description, "version": d.version}
                for d in docs
            ],
        }

    mcp.tool(name=f"{prefix}_list")(_list)
    mcp.tool(name=f"{prefix}_open")(_open)
    mcp.tool(name=f"{prefix}_set")(_set)
    mcp.tool(name="get_doctrine")(_get_doctrine)
