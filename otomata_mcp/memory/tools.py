"""Mémoire partagée servie EN TOOLS (donc loggée) : memory_list / memory_read / memory_write.

Versionnée (un write = une nouvelle version), scopée par tenant. La lecture est ouverte
à tout appelant authentifié ; l'écriture est gated au rôle `write_role` (défaut : member).
La connaissance vivante de l'équipe vit ici — la doctrine (`content/`) reste, elle, courte et stable."""
from __future__ import annotations

from .._util import maybe_await
from ..identity import current_sub
from ..rbac.gate import Rbac
from ..rbac.roles import MEMBER
from ..scope import ScopeResolver
from .store import MemoryStore


def register_memory_tools(
    mcp,
    store: MemoryStore,
    scope_resolver: ScopeResolver,
    rbac: Rbac,
    *,
    write_role: str = MEMBER,
) -> None:
    def _scope():
        return scope_resolver.resolve()

    async def memory_list() -> list[dict]:
        """Liste les clés de la mémoire partagée (dernière version, auteur, date)."""
        entries = await maybe_await(store.list(_scope()))
        return [
            {
                "key": e.key,
                "version": e.version,
                "author": e.author,
                "updated_at": e.updated_at.isoformat() if e.updated_at else None,
            }
            for e in entries
        ]

    async def memory_read(key: str) -> dict:
        """Renvoie la dernière version d'une clé de mémoire."""
        e = await maybe_await(store.latest(_scope(), key))
        if e is None:
            raise ValueError(f"clé de mémoire inconnue : {key!r}")
        return {"key": e.key, "version": e.version, "content": e.content, "author": e.author}

    async def memory_write(key: str, content: str) -> dict:
        """Écrit une nouvelle version d'une clé (append-only, versionné). Avant d'écrire,
        relis `memory_read(key)` pour repartir de la dernière version et écris autoportant."""
        if not key.strip() or not content.strip():
            raise ValueError("`key` et `content` ne peuvent pas être vides.")
        await rbac.require_async(write_role)
        e = await maybe_await(store.put(_scope(), key.strip(), content, author=current_sub()))
        return {"key": e.key, "version": e.version}

    mcp.tool(name="memory_list")(memory_list)
    mcp.tool(name="memory_read")(memory_read)
    mcp.tool(name="memory_write")(memory_write)
