"""Cadre start/stop : pile de runs dans l'état de session FastMCP (zéro table).

Le run actif est corrélé aux appels de tools par le logger
(`run_id`). Imbrication supportée (pile). Outcomes : done|abandoned|failed|blocked.
"""
from __future__ import annotations

import uuid
from typing import Optional

_KEY = "otomata_mcp_runs"
_OUTCOMES = ("done", "abandoned", "failed", "blocked")


async def _stack(ctx) -> list:
    return list(await ctx.get_state(_KEY) or [])


async def run_start(ctx, label: str, doctrine: Optional[str] = None) -> dict:
    run_id = uuid.uuid4().hex
    stack = await _stack(ctx)
    stack.append({"run_id": run_id, "label": label, "doctrine": doctrine})
    await ctx.set_state(_KEY, stack)
    return {"run_id": run_id, "label": label, "doctrine": doctrine}


async def active_run_id(ctx) -> Optional[str]:
    stack = await _stack(ctx)
    return stack[-1]["run_id"] if stack else None


async def run_finish(ctx, run_id: str, outcome: str, note: Optional[str] = None) -> dict:
    if outcome not in _OUTCOMES:
        raise ValueError(f"outcome invalide : {outcome!r} (attendu {'/'.join(_OUTCOMES)})")
    stack = await _stack(ctx)
    for i in range(len(stack) - 1, -1, -1):  # robuste à l'imbrication
        if stack[i]["run_id"] == run_id:
            stack.pop(i)
            await ctx.set_state(_KEY, stack)
            return {"ok": True, "run_id": run_id, "outcome": outcome, "was_open": True}
    return {"ok": True, "run_id": run_id, "outcome": outcome, "was_open": False}
