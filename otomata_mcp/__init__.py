"""otomata-mcp — socle commun des serveurs MCP Otomata (intra-entreprise, scope injecté).

Modules : content (doctrines en base → tools), run (start/stop), rbac, auth, logging.
Tout-en-tools. Le multi-entreprise (× Z) reste dans l'orchestrateur.
"""
from .bootstrap import build_server
from .content import ContentDoc, ContentStore, InMemoryContentStore, SCHEMA_SQL, validate
from .identity import Identity, current_identity, current_sub, set_resolver
from .instructions import SERVER_INSTRUCTIONS
from .logging import AccessLogger
from .rbac import GROUP_ADMIN, MEMBER, ORG_ADMIN, InMemoryRoleStore, Rbac, RoleStore
from .scope import CallableScope, ConstantScope, Scope, ScopeResolver

__all__ = [
    "build_server",
    "SERVER_INSTRUCTIONS",
    "ContentDoc",
    "ContentStore",
    "InMemoryContentStore",
    "SCHEMA_SQL",
    "validate",
    "Identity",
    "current_identity",
    "current_sub",
    "set_resolver",
    "AccessLogger",
    "MEMBER",
    "GROUP_ADMIN",
    "ORG_ADMIN",
    "InMemoryRoleStore",
    "Rbac",
    "RoleStore",
    "Scope",
    "ScopeResolver",
    "ConstantScope",
    "CallableScope",
]
