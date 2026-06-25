"""Petits utilitaires transverses du socle."""
from __future__ import annotations

import inspect
from typing import Any


async def maybe_await(value: Any) -> Any:
    """Renvoie `value`, en l'attendant si c'est un awaitable.

    Permet aux stores du socle d'être implémentés en SYNC (InMemory) ou en ASYNC
    (adaptateurs asyncpg) sans dupliquer la couche tools."""
    if inspect.isawaitable(value):
        return await value
    return value
