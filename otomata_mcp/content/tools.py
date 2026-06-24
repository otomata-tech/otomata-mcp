"""Sert les instructions (doctrines) EN TOOLS (donc loggées) — pas de resources.

Vocabulaire « instruction » (aligné oto). Tools fixes, quel que soit le nombre de docs :
- `readme_agent()`      : point d'entrée — doctrine de base + index des instructions.
- `list_instructions()` : l'index (sans corps).
- `get_instruction()`   : le corps d'une instruction.
- `set_instruction()`   : écriture versionnée (org_admin, validée « zéro nom »).
"""
from __future__ import annotations

from typing import Callable, Optional, Sequence, Union

from ..identity import current_sub
from ..rbac.gate import Rbac
from ..rbac.roles import ORG_ADMIN
from ..scope import ScopeResolver
from .model import ContentDoc
from .store import ContentStore
from .validate import validate

Readme = Union[str, Callable[[], str]]


def register_content_tools(
    mcp,
    store: ContentStore,
    scope_resolver: ScopeResolver,
    rbac: Rbac,
    *,
    readme: Optional[Readme] = None,
    blocklist: Sequence[str] = (),
    forbid_attribution: bool = True,
) -> None:
    def _scope():
        return scope_resolver.resolve()

    def _index() -> list[dict]:
        return [
            {"kind": d.kind, "slug": d.slug, "title": d.title,
             "description": d.description, "version": d.version}
            for d in store.list(_scope(), None)
        ]

    async def readme_agent() -> dict:
        """À LIRE EN PREMIER. Renvoie la doctrine de base (contrat + conventions) ET
        l'index des instructions disponibles (à charger ensuite via get_instruction)."""
        base = readme() if callable(readme) else readme
        return {"scope": _scope(), "readme": base or "", "instructions": _index()}

    async def list_instructions(kind: Optional[str] = None) -> list[dict]:
        """L'index des instructions disponibles (sans le corps), filtrable par kind."""
        return [
            {"kind": d.kind, "slug": d.slug, "title": d.title,
             "description": d.description, "version": d.version}
            for d in store.list(_scope(), kind)
        ]

    async def get_instruction(kind: str, slug: str) -> dict:
        """Sert le corps d'une instruction (knowledge/rule/…)."""
        d = store.latest(_scope(), kind, slug)
        if d is None:
            raise ValueError(f"instruction introuvable : {kind}/{slug}")
        return {"kind": d.kind, "slug": d.slug, "title": d.title, "version": d.version, "body": d.body}

    async def set_instruction(kind: str, slug: str, body: str, title: str = "", description: str = "") -> dict:
        """Crée/édite une instruction (réservé org_admin). Refuse tout nom de personne/client."""
        rbac.require(ORG_ADMIN)
        errors = validate(body, blocklist=blocklist, forbid_attribution=forbid_attribution)
        if errors:
            raise ValueError("écriture refusée : " + " ; ".join(errors))
        doc = ContentDoc(scope=_scope(), kind=kind, slug=slug, body=body, title=title, description=description)
        saved = store.put(doc, set_by=current_sub())
        return {"kind": saved.kind, "slug": saved.slug, "version": saved.version}

    mcp.tool(name="readme_agent")(readme_agent)
    mcp.tool(name="list_instructions")(list_instructions)
    mcp.tool(name="get_instruction")(get_instruction)
    mcp.tool(name="set_instruction")(set_instruction)
