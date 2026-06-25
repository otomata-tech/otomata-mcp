"""ACL — l'accès d'un utilisateur = exactement l'ensemble des *grants* qu'il détient.

Complémentaire du RBAC (rôles hiérarchiques) : là où RBAC répond « ton rôle est-il
≥ requis ? », l'ACL répond « détiens-tu *ce* droit précis ? ». Une ressource est une
chaîne : `tool:<name>` (appeler un tool), `doctrine:<name>` (voir une doctrine), `admin`
(tout gérer — implique tout). Le rôle ne sert qu'à amorcer un jeu de grants initial.

Scopé par tenant. Le consommateur implémente le `GrantStore` (InMemory fourni ;
adaptateur asyncpg dans `adapters/pg.py`)."""
from __future__ import annotations

from typing import Protocol

from ..scope import Scope

ADMIN = "admin"


def tool_resource(name: str) -> str:
    return f"tool:{name}"


def doctrine_resource(name: str) -> str:
    return f"doctrine:{name}"


def is_admin(grants: set[str]) -> bool:
    return ADMIN in grants


class GrantStore(Protocol):
    def grants(self, scope: Scope, sub: str) -> set[str]: ...
    def all_grants(self, scope: Scope) -> list[tuple[str, str]]: ...  # (sub, resource)
    def grant(self, scope: Scope, sub: str, resource: str) -> None: ...
    def revoke(self, scope: Scope, sub: str, resource: str) -> None: ...


class InMemoryGrantStore:
    def __init__(self, seed: dict | None = None) -> None:
        # {(scope, sub): {resource}}
        self._g: dict[tuple, set] = {}
        for (s, sub), resources in (seed or {}).items():
            self._g[(s, sub)] = set(resources)

    def grants(self, scope, sub):
        return set(self._g.get((scope, sub), set()))

    def all_grants(self, scope):
        return sorted(
            (sub, res)
            for (s, sub), resources in self._g.items()
            if s == scope
            for res in resources
        )

    def grant(self, scope, sub, resource):
        self._g.setdefault((scope, sub), set()).add(resource)

    def revoke(self, scope, sub, resource):
        self._g.get((scope, sub), set()).discard(resource)
