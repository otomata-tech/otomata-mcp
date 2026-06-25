"""Feedback — un signal d'usage VOLONTAIRE remonté par l'agent (boucle d'apprentissage).

`feedback(signal, kind, target, text?)` :
  - `signal='gap'`           : un besoin NON couvert (outil/doctrine/donnée manquant)
    → l'agent devient un capteur de demande non satisfaite, plutôt que d'abandonner en silence.
  - `signal='tool_feedback'` : un outil se comporte mal ou excellemment.

Run-aware (stampé du `run_id` actif) et identifié (sub/email). Le `sink` injecté écrit
la row ; il peut être SYNC ou ASYNC. Modèle aligné oto (`usage_signals`).
"""
from __future__ import annotations

import inspect
from typing import Awaitable, Callable, Optional, Protocol, Union

from fastmcp import Context

from ._util import maybe_await
from .identity import current_identity
from .rbac.gate import Rbac
from .rbac.roles import ORG_ADMIN
from .run import stack as run_stack

SIGNALS = ("tool_feedback", "gap")

FeedbackSink = Callable[[dict], Union[None, Awaitable[None]]]


class FeedbackStore(Protocol):
    """Côté lecture de la boucle : sert le digest des signaux remontés (admin)."""

    def recent(self, server: str, limit: int) -> list[dict]: ...

FEEDBACK_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS tool_feedback (
    id          BIGSERIAL PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    server      TEXT NOT NULL,
    signal      TEXT NOT NULL,          -- 'tool_feedback' | 'gap'
    kind        TEXT,                   -- tool_feedback: bug|misleading_doc|wrong_result|praise|other
                                        -- gap: missing_tool|missing_doctrine|missing_data|other
    target      TEXT NOT NULL,          -- tool_feedback: nom de l'outil ; gap: ce que tu voulais faire
    text        TEXT,
    sub         TEXT,
    email       TEXT,
    run_id      TEXT
);
CREATE INDEX IF NOT EXISTS tool_feedback_signal_idx ON tool_feedback (signal, created_at DESC);
"""


def register_feedback_tools(
    mcp,
    sink: FeedbackSink,
    *,
    server: str,
    store: Optional[FeedbackStore] = None,
    rbac: Optional[Rbac] = None,
    admin_role: str = ORG_ADMIN,
) -> None:
    async def feedback(signal: str, kind: str, target: str,
                       text: Optional[str] = None, ctx: Context = None) -> dict:
        """Remonte un signal d'usage — la boucle d'apprentissage du produit. Préfère
        remonter un signal plutôt que d'abandonner en silence.

        - `signal='gap'` : un besoin NON couvert (outil/doctrine/donnée manquant).
          `kind` ∈ missing_tool|missing_doctrine|missing_data|other ; `target` = ce que tu voulais faire.
        - `signal='tool_feedback'` : un outil se comporte mal ou excellemment.
          `kind` ∈ bug|misleading_doc|wrong_result|praise|other ; `target` = nom de l'outil.
        """
        if signal not in SIGNALS:
            raise ValueError(f"signal invalide : {signal!r} (attendu {'/'.join(SIGNALS)})")
        ident = current_identity()
        run_id = None
        if ctx is not None:
            try:
                run_id = await run_stack.active_run_id(ctx)
            except Exception:
                pass
        row = {
            "server": server, "signal": signal, "kind": kind, "target": target,
            "text": text or None,
            "sub": ident.sub if ident else None,
            "email": ident.email if ident else None,
            "run_id": run_id,
        }
        res = sink(row)
        if inspect.isawaitable(res):
            await res
        return {"ok": True, "signal": signal, "target": target}

    mcp.tool(name="feedback")(feedback)

    if store is not None:
        async def list_feedback(limit: int = 50) -> list[dict]:
            """Digest des signaux d'usage remontés (gap / tool_feedback). Réservé admin :
            c'est la lecture de la boucle de capitalisation côté gestionnaire du serveur."""
            if rbac is not None:
                await rbac.require_async(admin_role)
            return await maybe_await(store.recent(server, max(1, min(limit, 500))))

        mcp.tool(name="list_feedback")(list_feedback)
