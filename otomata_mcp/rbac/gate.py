"""Gating de tools par rôle. Lève si insuffisant (FastMCP en fait une erreur de tool)."""
from __future__ import annotations

from typing import Optional

from ..identity import current_sub
from ..scope import ScopeResolver
from .roles import at_least
from .store import RoleStore


class Rbac:
    def __init__(self, store: RoleStore, scope_resolver: ScopeResolver) -> None:
        self.store = store
        self.scope_resolver = scope_resolver

    def effective_role(self) -> Optional[str]:
        return self.store.role(self.scope_resolver.resolve(), current_sub())

    def require(self, required: str) -> None:
        role = self.effective_role()
        if not at_least(role, required):
            raise PermissionError(
                f"rôle insuffisant : requis '{required}', obtenu '{role or 'aucun'}'"
            )
