"""Compose un serveur MCP du socle : FastMCP + RBAC + doctrines-en-tools + runs + logging.

Le consommateur fournit les adaptateurs (stores), le resolver de scope et le sink de logs.
Tout-en-tools : pas de resource, pas de prompt.
"""
from __future__ import annotations

from typing import Callable, Sequence

from fastmcp import FastMCP

from .content.tools import register_content_tools
from .logging import AccessLogger
from .rbac.gate import Rbac
from .rbac.store import RoleStore
from .run.tools import register_run_tools
from .scope import ScopeResolver
from .content.store import ContentStore


def build_server(
    name: str,
    *,
    content_store: ContentStore,
    role_store: RoleStore,
    scope_resolver: ScopeResolver,
    sink: Callable[[dict], None],
    blocklist: Sequence[str] = (),
    prefix: str = "doctrine",
    auth=None,
) -> FastMCP:
    mcp = FastMCP(name, auth=auth) if auth is not None else FastMCP(name)
    rbac = Rbac(role_store, scope_resolver)
    mcp.add_middleware(AccessLogger(sink, server=name))
    register_content_tools(mcp, content_store, scope_resolver, rbac, prefix=prefix, blocklist=blocklist)
    register_run_tools(mcp)
    return mcp
