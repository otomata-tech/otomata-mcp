"""Enforcement de l'ACL en UN seul point : un middleware qui gate les appels de tools
ET masque de la liste les tools non accordés, par utilisateur.

`public_tools` = tools accessibles à tout appelant authentifié (sans grant) — typiquement
la porte d'entrée (`readme_agent`, `whoami`…). Un détenteur du grant `admin` voit/appelle
tout. Sans identité résolue (stdio local), aucun enforcement (dev)."""
from __future__ import annotations

from typing import Sequence

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware

from .._util import maybe_await
from ..identity import current_sub
from ..scope import ScopeResolver
from .store import ADMIN, GrantStore, tool_resource


class AclMiddleware(Middleware):
    def __init__(
        self,
        grant_store: GrantStore,
        scope_resolver: ScopeResolver,
        *,
        public_tools: Sequence[str] = (),
    ) -> None:
        self.grant_store = grant_store
        self.scope_resolver = scope_resolver
        self.public_tools = set(public_tools)

    async def _grants(self, sub: str) -> set[str]:
        return await maybe_await(self.grant_store.grants(self.scope_resolver.resolve(), sub))

    async def on_call_tool(self, context, call_next):
        name = context.message.name
        sub = current_sub()
        if sub is not None and name not in self.public_tools:
            grants = await self._grants(sub)
            if ADMIN not in grants and tool_resource(name) not in grants:
                raise ToolError(f"accès refusé : le tool '{name}' ne t'est pas accordé.")
        return await call_next(context)

    async def on_list_tools(self, context, call_next):
        tools = await call_next(context)
        sub = current_sub()
        if sub is None:
            return tools
        grants = await self._grants(sub)
        if ADMIN in grants:
            return tools
        return [t for t in tools if t.name in self.public_tools or tool_resource(t.name) in grants]
