"""Gating de tools par rôle. Lève si insuffisant (FastMCP en fait une erreur de tool)."""
from __future__ import annotations

from typing import Optional

from .._util import maybe_await
from ..identity import current_sub
from ..scope import ScopeResolver
from .roles import at_least
from .store import RoleStore


class Rbac:
    def __init__(self, store: RoleStore, scope_resolver: ScopeResolver) -> None:
        self.store = store
        self.scope_resolver = scope_resolver

    def effective_role(self) -> Optional[str]:
        """Rôle effectif — pour un RoleStore SYNC (InMemory / claims JWT)."""
        return self.store.role(self.scope_resolver.resolve(), current_sub())

    async def effective_role_async(self) -> Optional[str]:
        """Rôle effectif, tolérant un RoleStore ASYNC (adaptateur asyncpg)."""
        return await maybe_await(self.store.role(self.scope_resolver.resolve(), current_sub()))

    async def require_async(self, required: str) -> None:
        """Exige au moins `required` ; tolère un store sync ou async. Appelé depuis la couche tools."""
        role = await self.effective_role_async()
        if not at_least(role, required):
            raise PermissionError(
                f"rôle insuffisant : requis '{required}', obtenu '{role or 'aucun'}'"
            )

    def require(self, required: str) -> None:
        """Variante synchrone (RoleStore sync uniquement). Conservée pour compat."""
        role = self.effective_role()
        if not at_least(role, required):
            raise PermissionError(
                f"rôle insuffisant : requis '{required}', obtenu '{role or 'aucun'}'"
            )
