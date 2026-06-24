"""Validation à l'écriture d'une doctrine.

Garde-fou central de l'incident OGIC : **zéro nom de personne/client**. Ici, deux
mécanismes complémentaires :
  - `blocklist` : termes interdits (noms connus) — déterministe, fourni par le consommateur.
  - `forbid_attribution` : heuristique sur les citations attribuées (« … » — Nom / (Nom)).

Retourne la liste des erreurs (vide = OK). La détection fine (NER) pourra enrichir plus tard.
"""
from __future__ import annotations

import re
from typing import Optional, Sequence

# Citation attribuée : guillemets fermants suivis d'un tiret cadratin + un Nom capitalisé.
_ATTRIBUTION = re.compile(r"[»\"”]\s*[—–-]\s*[A-ZÀ-Ÿ][\wÀ-ÿ'’.-]+")


def validate(
    body: str,
    *,
    blocklist: Sequence[str] = (),
    forbid_attribution: bool = False,
    require_frontmatter: bool = False,
    frontmatter: Optional[dict] = None,
) -> list[str]:
    errors: list[str] = []

    if require_frontmatter:
        fm = frontmatter or {}
        for key in ("name", "description"):
            if not fm.get(key):
                errors.append(f"frontmatter.{key} manquant")

    low = body.lower()
    for term in blocklist:
        if term and term.lower() in low:
            errors.append(f"terme interdit (nom de personne/client) : {term!r}")

    if forbid_attribution and _ATTRIBUTION.search(body):
        errors.append("citation attribuée nominativement détectée (verbatim interdit)")

    return errors
