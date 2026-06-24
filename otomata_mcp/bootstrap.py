"""Compose un serveur MCP du socle : FastMCP + RBAC + instructions-en-tools + runs + logging.

Le consommateur fournit les adaptateurs (stores), le resolver de scope, le sink de logs et
le `readme` (doctrine de base). Tout-en-tools : pas de resource, pas de prompt.
"""
from __future__ import annotations

from typing import Callable, Optional, Sequence, Union

from fastmcp import FastMCP

from .content.store import ContentStore
from .content.tools import register_content_tools
from .feedback import FeedbackSink, register_feedback_tools
from .instructions import SERVER_INSTRUCTIONS
from .logging import AccessLogger
from .rbac.gate import Rbac
from .rbac.store import RoleStore
from .run.tools import register_run_tools
from .scope import ScopeResolver

Readme = Union[str, Callable[[], str]]


def build_server(
    name: str,
    *,
    content_store: ContentStore,
    role_store: RoleStore,
    scope_resolver: ScopeResolver,
    sink: Callable[[dict], None],
    readme: Optional[Readme] = None,
    instructions: Optional[str] = None,
    blocklist: Sequence[str] = (),
    feedback_sink: Optional[FeedbackSink] = None,
    auth=None,
) -> FastMCP:
    # La porte d'entrée : instructions métier (optionnelles) + la convention du socle.
    full_instructions = "\n\n".join(filter(None, [instructions, SERVER_INSTRUCTIONS]))
    mcp = FastMCP(name, instructions=full_instructions, auth=auth)
    rbac = Rbac(role_store, scope_resolver)
    mcp.add_middleware(AccessLogger(sink, server=name))
    register_content_tools(mcp, content_store, scope_resolver, rbac, readme=readme, blocklist=blocklist)
    register_run_tools(mcp)
    if feedback_sink is not None:
        register_feedback_tools(mcp, feedback_sink, server=name)
    return mcp
