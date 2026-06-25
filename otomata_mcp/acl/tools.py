"""Gestion de l'ACL EN TOOLS (loggée) : grant / revoke / list_grants. Réservé admin
(grant `admin`). Permet à un admin de piloter les droits depuis l'agent, sans console."""
from __future__ import annotations

from typing import Optional

from .._util import maybe_await
from ..identity import current_sub
from ..scope import ScopeResolver
from .store import ADMIN, GrantStore


def register_acl_tools(mcp, store: GrantStore, scope_resolver: ScopeResolver) -> None:
    def _scope():
        return scope_resolver.resolve()

    async def _require_admin() -> None:
        grants = await maybe_await(store.grants(_scope(), current_sub()))
        if ADMIN not in grants:
            raise PermissionError("réservé à un administrateur (grant 'admin').")

    async def list_grants(sub: Optional[str] = None) -> list[dict]:
        """Liste les grants : d'un utilisateur si `sub` fourni, sinon de tout le tenant. Admin."""
        await _require_admin()
        if sub is not None:
            return [{"sub": sub, "resource": r} for r in sorted(await maybe_await(store.grants(_scope(), sub)))]
        return [{"sub": s, "resource": r} for s, r in await maybe_await(store.all_grants(_scope()))]

    async def grant(sub: str, resource: str) -> dict:
        """Accorde un droit (`tool:<name>` | `doctrine:<name>` | `admin`) à un utilisateur. Admin."""
        await _require_admin()
        await maybe_await(store.grant(_scope(), sub, resource))
        return {"ok": True, "sub": sub, "resource": resource}

    async def revoke(sub: str, resource: str) -> dict:
        """Retire un droit à un utilisateur. Admin."""
        await _require_admin()
        await maybe_await(store.revoke(_scope(), sub, resource))
        return {"ok": True, "sub": sub, "resource": resource}

    mcp.tool(name="list_grants")(list_grants)
    mcp.tool(name="grant")(grant)
    mcp.tool(name="revoke")(revoke)
