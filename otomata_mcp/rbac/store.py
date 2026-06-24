"""Contrat de persistance des rôles (scopé). Le consommateur l'implémente.

Mono-tenant : lit un rôle dans le JWT (ex. un champ `*_role` → org_admin/member), Z=1.
Multi-tenant : lit le rôle en base, filtré par scope.
"""
from __future__ import annotations

from typing import Optional, Protocol

from ..scope import Scope


class RoleStore(Protocol):
    def role(self, scope: Scope, sub: Optional[str]) -> Optional[str]: ...


class InMemoryRoleStore:
    def __init__(self, roles: Optional[dict] = None) -> None:
        # {(scope, sub): role}
        self._roles = dict(roles or {})

    def set(self, scope: Scope, sub: str, role: str) -> None:
        self._roles[(scope, sub)] = role

    def role(self, scope: Scope, sub: Optional[str]) -> Optional[str]:
        return self._roles.get((scope, sub))
