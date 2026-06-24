"""Contrat de persistance des doctrines (scopé). Le consommateur l'implémente
(ex. PostgREST/Supabase, ou asyncpg). InMemory fourni pour tests/démo.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Optional, Protocol

from ..scope import Scope
from .model import ContentDoc


class ContentStore(Protocol):
    def latest(self, scope: Scope, kind: str, slug: str) -> Optional[ContentDoc]: ...
    def list(self, scope: Scope, kind: Optional[str] = None) -> list[ContentDoc]: ...
    def put(self, doc: ContentDoc, *, set_by: Optional[str] = None) -> ContentDoc: ...
    def history(self, scope: Scope, kind: str, slug: str) -> list[ContentDoc]: ...


class InMemoryContentStore:
    def __init__(self) -> None:
        self._docs: dict[tuple, list[ContentDoc]] = {}

    def latest(self, scope, kind, slug):
        versions = self._docs.get((scope, kind, slug))
        return versions[-1] if versions else None

    def list(self, scope, kind=None):
        out = [
            versions[-1]
            for (s, k, _slug), versions in self._docs.items()
            if s == scope and (kind is None or k == kind)
        ]
        return sorted(out, key=lambda d: (d.kind, d.slug))

    def put(self, doc, *, set_by=None):
        key = (doc.scope, doc.kind, doc.slug)
        versions = self._docs.setdefault(key, [])
        new_version = (versions[-1].version + 1) if versions else 1
        saved = replace(doc, version=new_version)
        versions.append(saved)
        return saved

    def history(self, scope, kind, slug):
        return list(self._docs.get((scope, kind, slug), []))

    def seed(self, doc: ContentDoc) -> None:
        """Insère un doc tel quel (tests/démo, sans bump de version)."""
        self._docs.setdefault((doc.scope, doc.kind, doc.slug), []).append(doc)
