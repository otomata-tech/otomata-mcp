"""Identité de l'appelant.

En prod, elle vient du JWT FastMCP (`get_access_token`). Le socle l'expose via un
**resolver injectable** pour rester découplé du provider : la couche auth pousse le
resolver, le reste du socle lit `current_identity()`. (Tests/démo : resolver trivial.)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class Identity:
    sub: Optional[str]
    email: Optional[str] = None


_resolver: Optional[Callable[[], Optional[Identity]]] = None


def set_resolver(fn: Optional[Callable[[], Optional[Identity]]]) -> None:
    """Installe le resolver d'identité (auth en prod, holder en test)."""
    global _resolver
    _resolver = fn


def _jwt_identity() -> Optional[Identity]:
    """Resolver par défaut : lit le JWT FastMCP courant."""
    try:
        from fastmcp.server.dependencies import get_access_token

        token = get_access_token()
    except Exception:
        return None
    if token is None or not getattr(token, "claims", None):
        return None
    return Identity(token.claims.get("sub"), token.claims.get("email"))


def current_identity() -> Optional[Identity]:
    return (_resolver or _jwt_identity)()


def current_sub() -> Optional[str]:
    ident = current_identity()
    return ident.sub if ident else None
