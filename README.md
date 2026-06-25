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
  rbac/           # RÔLES : org_admin → group_admin → member, scopé (gate des écritures) · schema (DDL)
  acl/            # GRANTS par utilisateur : tool:<name> | doctrine:<name> | admin — middleware (gate + masquage) + tools (grant/revoke/list_grants)
  feedback.py     # boucle d'apprentissage : feedback(gap|tool_feedback) en écriture + list_feedback (digest admin)
  logging.py      # middleware run-aware (schéma otomata-calllog + run_id)
  adapters/pg.py        # ADAPTATEUR Postgres asyncpg : tous les stores + sinks + init_schema (extra [pg])
  adapters/postgrest.py # ADAPTATEUR PostgREST/Supabase (httpx) : mêmes stores via l'API REST (extra [postgrest], cible OGIC)
  bootstrap.py    # build_server(...) compose tout
```

**RBAC vs ACL** — complémentaires : le **RBAC** (rôle hiérarchique) gate les *privilèges*
(écrire une doctrine = org_admin) ; l'**ACL** (grants par utilisateur) gate l'*accès aux
tools* (`tool:<name>`) et masque de la liste ce qui n'est pas accordé. Le rôle amorce un jeu
de grants ; l'accès réel = l'ensemble exact des grants. Activer l'ACL : passer `grant_store`
(+ `acl_public_tools`) à `build_server`.

## Ce que le consommateur fournit (injecté)

- un **`ContentStore`** (OGIC : PostgREST/Supabase ; oto/madeleine : asyncpg) — `SCHEMA_SQL` fourni ;
- un **`RoleStore`** (rôles scopés) ;
- un **`ScopeResolver`** (`ConstantScope("ogic")` en Z=1, `CallableScope(current_org)` en Z=N) ;
- un **sink de logs** (table `tool_calls`, cf. `otomata-calllog`) ;
- *(optionnel)* un **`MemoryStore`** pour la mémoire partagée (`MEMORY_SCHEMA_SQL` fourni) ;
- *(optionnel)* un **`feedback_sink`** + un **`FeedbackStore`** (digest admin `list_feedback`) — `FEEDBACK_SCHEMA_SQL` fourni ;
- *(optionnel)* un **`GrantStore`** pour l'ACL (`ACL_SCHEMA_SQL` fourni) ;
- l'**auth** (verifier JWT du provider) — le socle lit l'identité via un resolver injecté. **Un provider self-hosté
  (ex. OAuth 2.1 embarqué de 321agents) se passe simplement en `auth=` ; le socle reste agnostique.**

> **Postgres clé en main** — `adapters/pg.py` fournit `PgContentStore` / `PgMemoryStore` /
> `PgRoleStore` / `PgGrantStore` / `PgFeedbackStore` + `make_pg_log_sink` / `make_pg_feedback_sink`,
> et `init_schema(pool)` qui applique tout le schéma. Plus aucun store à réécrire :
> ```python
> from otomata_mcp.adapters.pg import create_pool, init_schema, PgContentStore, PgMemoryStore, \
>     PgRoleStore, PgGrantStore, PgFeedbackStore, make_pg_log_sink, make_pg_feedback_sink
> pool = await create_pool(DSN); await init_schema(pool)
> mcp = build_server("mon-mcp", content_store=PgContentStore(pool), role_store=PgRoleStore(pool),
>                    scope_resolver=ConstantScope("acme"), sink=make_pg_log_sink(pool),
>                    memory_store=PgMemoryStore(pool), grant_store=PgGrantStore(pool),
>                    feedback_sink=make_pg_feedback_sink(pool), feedback_store=PgFeedbackStore(pool),
>                    acl_public_tools=["readme_agent"])
> ```
> Variante **PostgREST/Supabase** (même contrat, persistance via l'API REST — cible OGIC) :
> `from otomata_mcp.adapters.postgrest import PostgrestClient, PostgrestContentStore, …` avec
> `client = PostgrestClient(base_url, apikey=…)`. Le schéma reste les `*_SCHEMA_SQL` du socle
> appliqués à la base sous-jacente (PostgREST n'exécute pas de DDL).

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
pytest          # tests du socle (le test Postgres est skippé sans DSN)
python example_demo.py

# Test d'intégration Postgres (adaptateur asyncpg + ACL + RBAC bout en bout) :
docker run -d --name pg -e POSTGRES_PASSWORD=pg -e POSTGRES_DB=socle -p 55433:5432 postgres:16-alpine
OTOMATA_MCP_TEST_PG="postgresql://postgres:pg@127.0.0.1:55433/socle" pytest tests/test_pg_adapter.py
```

## Distribution

Publié sur **PyPI** (`pip install otomata-mcp`), modèle `otomata-calllog`. Le contenu est du
plumbing MCP générique — aucun secret ni donnée client.
