"""otomata-mcp — socle commun des serveurs MCP Otomata (intra-entreprise, scope injecté).

Modules : content (doctrines en base → tools), memory (mémoire partagée versionnée),
run (start/stop), rbac, feedback (boucle d'apprentissage), logging. Tout-en-tools.
Le multi-entreprise (× Z) reste dans l'orchestrateur.
"""
from .bootstrap import build_server
from .content import ContentDoc, ContentStore, InMemoryContentStore, SCHEMA_SQL, validate
from .feedback import (
    FEEDBACK_SCHEMA_SQL,
    SIGNALS,
    FeedbackStore,
    register_feedback_tools,
)
from .identity import Identity, current_identity, current_sub, set_resolver
from .instructions import SERVER_INSTRUCTIONS
from .logging import AccessLogger
from .memory import (
    InMemoryMemoryStore,
    MEMORY_SCHEMA_SQL,
    MemoryEntry,
    MemoryStore,
    register_memory_tools,
)
from .rbac import GROUP_ADMIN, MEMBER, ORG_ADMIN, InMemoryRoleStore, Rbac, RoleStore
from .scope import CallableScope, ConstantScope, Scope, ScopeResolver

__all__ = [
    "build_server",
    "SERVER_INSTRUCTIONS",
    "register_feedback_tools",
    "FEEDBACK_SCHEMA_SQL",
    "FeedbackStore",
    "SIGNALS",
    "ContentDoc",
    "ContentStore",
    "InMemoryContentStore",
    "SCHEMA_SQL",
    "validate",
    "MemoryEntry",
    "MemoryStore",
    "InMemoryMemoryStore",
    "register_memory_tools",
    "MEMORY_SCHEMA_SQL",
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
