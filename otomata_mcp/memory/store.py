"""Contrat de persistance de la mémoire partagée (scopée, versionnée).

Le consommateur l'implémente (asyncpg / PostgREST) ; `InMemoryMemoryStore` fourni
pour tests/démo. Aligné sur le modèle des doctrines (`content/store.py`)."""
from __future__ import annotations

from typing import Optional, Protocol

from ..scope import Scope
from .model import MemoryEntry


class MemoryStore(Protocol):
    def latest(self, scope: Scope, key: str) -> Optional[MemoryEntry]: ...
    def list(self, scope: Scope) -> list[MemoryEntry]: ...
    def put(self, scope: Scope, key: str, content: str, *, author: Optional[str] = None) -> MemoryEntry: ...
    def history(self, scope: Scope, key: str) -> list[MemoryEntry]: ...


class InMemoryMemoryStore:
    def __init__(self) -> None:
        # {(scope, key): [versions]}
        self._m: dict[tuple, list[MemoryEntry]] = {}

    def latest(self, scope, key):
        versions = self._m.get((scope, key))
        return versions[-1] if versions else None

    def list(self, scope):
        out = [versions[-1] for (s, _k), versions in self._m.items() if s == scope]
        return sorted(out, key=lambda e: e.key)

    def put(self, scope, key, content, *, author=None):
        versions = self._m.setdefault((scope, key), [])
        entry = MemoryEntry(
            scope=scope,
            key=key,
            content=content,
            version=(versions[-1].version + 1) if versions else 1,
            author=author,
        )
        versions.append(entry)
        return entry

    def history(self, scope, key):
        return list(self._m.get((scope, key), []))
