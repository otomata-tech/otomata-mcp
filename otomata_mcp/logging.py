"""Middleware de journalisation des appels de tools, corrélé au run actif.

Réf oto `server.py:199-225` : c'est ce middleware (et non `otomata-calllog` brut) qui
stampe `run_id`. Il réutilise le MÊME schéma/sink que calllog (`server, sub, email, tool,
args, ok, error, duration_ms` + `run_id`). Comme tout est un tool, TOUT accès est loggé.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Optional

from fastmcp.server.middleware import Middleware

from .identity import current_identity
from .run import stack as run_stack

MAX_ARG_CHARS = 300


def _truncated_args(arguments: Optional[dict]) -> Optional[dict]:
    if not arguments:
        return None
    out: dict[str, Any] = {}
    for k, v in arguments.items():
        if not (v is None or isinstance(v, (int, float, bool))):
            v = str(v)
            if len(v) > MAX_ARG_CHARS:
                v = v[:MAX_ARG_CHARS] + "…"
        out[k] = v
    return out


class AccessLogger(Middleware):
    def __init__(self, sink: Callable[[dict], None], server: str) -> None:
        self.sink = sink
        self.server = server

    async def on_call_tool(self, context, call_next):
        ident = current_identity()
        fctx = getattr(context, "fastmcp_context", None)
        run_id = None
        if fctx is not None:
            try:
                run_id = await run_stack.active_run_id(fctx)
            except Exception:
                pass
        row = {
            "server": self.server,
            "tool": context.message.name,
            "args": _truncated_args(getattr(context.message, "arguments", None)),
            "sub": ident.sub if ident else None,
            "email": ident.email if ident else None,
            "run_id": run_id,
        }
        t0 = time.monotonic()
        try:
            result = await call_next(context)
        except Exception as e:
            row.update(ok=False, error=str(e)[:MAX_ARG_CHARS], duration_ms=int((time.monotonic() - t0) * 1000))
            self.sink(row)
            raise
        row.update(ok=True, error=None, duration_ms=int((time.monotonic() - t0) * 1000))
        self.sink(row)
        return result
