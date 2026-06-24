"""Hiérarchie de rôles INTRA-entreprise.

Le cross-Z (`platform_admin`, super-admin de toutes les orgs) est HORS socle : c'est
l'orchestrateur (oto/madeleine) qui le porte.
"""
from __future__ import annotations

from typing import Optional

MEMBER = "member"
GROUP_ADMIN = "group_admin"
ORG_ADMIN = "org_admin"

_ORDER = {MEMBER: 1, GROUP_ADMIN: 2, ORG_ADMIN: 3}


def rank(role: Optional[str]) -> int:
    return _ORDER.get(role or "", 0)


def at_least(role: Optional[str], required: str) -> bool:
    return rank(role) >= rank(required)
