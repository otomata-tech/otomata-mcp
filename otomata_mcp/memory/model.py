from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class MemoryEntry:
    """Une entrée de mémoire partagée, versionnée et scopée par tenant.

    Un write sur une `key` crée une nouvelle version (append-only) ; un read
    renvoie la dernière. Le `content` est du texte autoportant (compréhensible
    hors contexte de chat)."""

    scope: str
    key: str
    content: str
    version: int = 1
    author: Optional[str] = None  # sub de l'auteur du write
    updated_at: Optional[_dt.datetime] = None
