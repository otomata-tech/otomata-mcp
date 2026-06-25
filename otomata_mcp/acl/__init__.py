"""ACL du socle : grants par utilisateur (`tool:*` / `doctrine:*` / `admin`), scopés.

Enforcement par middleware (gate des appels + masquage de la liste), gestion en tools."""
from .middleware import AclMiddleware
from .schema import SCHEMA_SQL as ACL_SCHEMA_SQL
from .store import (
    ADMIN,
    GrantStore,
    InMemoryGrantStore,
    doctrine_resource,
    is_admin,
    tool_resource,
)
from .tools import register_acl_tools

__all__ = [
    "AclMiddleware",
    "ACL_SCHEMA_SQL",
    "ADMIN",
    "GrantStore",
    "InMemoryGrantStore",
    "doctrine_resource",
    "is_admin",
    "tool_resource",
    "register_acl_tools",
]
