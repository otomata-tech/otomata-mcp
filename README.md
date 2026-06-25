# otomata-mcp

Socle commun des serveurs MCP Otomata (Python / FastMCP). **Tout-en-tools** (pas de
resource ni de prompt → tout accès est loggé), **scopé par entreprise**.

Le socle modélise l'**intra-entreprise** (1 org = X groupes, Y users). Le **multi-entreprise
(× Z)** — résolution de l'org courante, `platform_admin`, marketplace de doctrines — reste dans
l'**orchestrateur** (oto / madeleine), qui injecte un **scope** (`tenant_id`) à chaque appel. Le
socle ne requête jamais sans scope → pas de fuite cross-org.

## Modules

```
otomata_mcp/
  scope.py        # Scope + ScopeResolver (ConstantScope = Z1, CallableScope = ZN)
  identity.py     # current_identity() via resolver injecté (JWT en prod)
  content/        # instructions en base, servies EN TOOLS (readme_agent / list_instructions / get_instruction / set_instruction)
                  #   model · store (Protocol + InMemory) · validate (zéro nom) · schema (DDL) · tools
  memory/         # mémoire partagée versionnée, EN TOOLS (memory_list / memory_read / memory_write)
                  #   model · store (Protocol + InMemory) · schema (DDL) · tools ; write gated (write_role, défaut member)
  run/            # start/stop : pile de runs en session state, corrélée run_id
  rbac/           # org_admin → group_admin → member, scopé (gate des tools)
  feedback.py     # boucle d'apprentissage : feedback(gap|tool_feedback) en écriture + list_feedback (digest admin)
  logging.py      # middleware run-aware (réutilise le schéma otomata-calllog + run_id)
  bootstrap.py    # build_server(...) compose tout
```

## Ce que le consommateur fournit (injecté)

- un **`ContentStore`** (OGIC : PostgREST/Supabase ; oto/madeleine : asyncpg) — `SCHEMA_SQL` fourni ;
- un **`RoleStore`** (rôles scopés) ;
- un **`ScopeResolver`** (`ConstantScope("ogic")` en Z=1, `CallableScope(current_org)` en Z=N) ;
- un **sink de logs** (table `tool_calls`, cf. `otomata-calllog`) ;
- *(optionnel)* un **`MemoryStore`** pour la mémoire partagée (`MEMORY_SCHEMA_SQL` fourni) ;
- *(optionnel)* un **`feedback_sink`** + un **`FeedbackStore`** (digest admin `list_feedback`) — `FEEDBACK_SCHEMA_SQL` fourni ;
- l'**auth** (verifier JWT du provider) — le socle lit l'identité via un resolver injecté. **Un provider self-hosté
  (ex. OAuth 2.1 embarqué de 321agents) se passe simplement en `auth=` ; le socle reste agnostique.**

## Exemple

```python
from otomata_mcp import build_server, InMemoryContentStore, InMemoryRoleStore, ConstantScope
mcp = build_server("mon-mcp", content_store=..., role_store=..., scope_resolver=ConstantScope("acme"),
                   sink=my_sink, blocklist=["NomInterdit"])
```

`example_demo.py` montre tout (doctrines + mémoire en tools loggées + corrélées run_id, RBAC, validation, digest admin).

## Dev

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest          # tests du socle
python example_demo.py
```

## Distribution

Publié sur **PyPI** (`pip install otomata-mcp`), modèle `otomata-calllog`. Le contenu est du
plumbing MCP générique — aucun secret ni donnée client.
