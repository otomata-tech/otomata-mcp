"""Scope (tenant) : le socle exige un scope à CHAQUE opération.

L'orchestrateur résout l'entreprise courante et l'injecte ; un consommateur mono-tenant (Z=1)
utilise un scope constant. Le socle ne requête JAMAIS sans scope → pas de fuite cross-org.
"""
from __future__ import annotations

from typing import Callable, Optional, Protocol

from .identity import current_sub

Scope = str  # tenant_id


class ScopeResolver(Protocol):
    def resolve(self) -> Scope: ...


class ConstantScope:
    """Z=1 : un seul tenant (consommateur mono-entreprise)."""

    def __init__(self, scope: Scope) -> None:
        self._scope = scope

    def resolve(self) -> Scope:
        return self._scope


class CallableScope:
    """Z=N : délègue à une fonction de l'orchestrateur (ex. current_org(sub))."""

    def __init__(self, fn: Callable[[Optional[str]], Optional[Scope]]) -> None:
        self._fn = fn

    def resolve(self) -> Scope:
        scope = self._fn(current_sub())
        if not scope:
            raise PermissionError("scope (entreprise) non résolu pour l'appelant")
        return str(scope)
