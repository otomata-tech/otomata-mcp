"""Middleware de journalisation des appels de tools, corrélé au run actif.

Ce middleware stampe le `run_id` du run actif sur chaque appel. Il réutilise le MÊME schéma/sink que calllog (`server, sub, email, tool,
args, ok, error, duration_ms` + `run_id`). Comme tout est un tool, TOUT accès est loggé.

Le sink peut être SYNC (ex. sqlite) ou ASYNC (ex. PostgREST httpx) : une coroutine est
programmée en fire-and-forget avec une référence forte (anti-GC asyncio).
"""
from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any, Awaitable, Callable, Optional, Union

from fastmcp.server.middleware import Middleware

from .identity import current_identity
from .run import stack as run_stack

MAX_ARG_CHARS = 300

Sink = Callable[[dict], Union[None, Awaitable[None]]]

_PENDING: set = set()


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
    def __init__(self, sink: Sink, server: str) -> None:
        self.sink = sink
        self.server = server

    def _emit(self, row: dict) -> None:
        """Best-effort : ne casse jamais l'appel de tool. Sink sync ou async."""
        try:
            res = self.sink(row)
        except Exception:
            return
        if inspect.isawaitable(res):
            task = asyncio.ensure_future(res)
            _PENDING.add(task)
            task.add_done_callback(_PENDING.discard)

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
            self._emit(row)
            raise
        row.update(ok=True, error=None, duration_ms=int((time.monotonic() - t0) * 1000))
        self._emit(row)
        return result
