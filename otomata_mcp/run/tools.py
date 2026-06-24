"""Tools run_start / run_finish (model-controlled)."""
from __future__ import annotations

from typing import Optional

from fastmcp import Context

from . import stack


def register_run_tools(mcp) -> None:
    async def run_start(label: str, doctrine: Optional[str] = None, ctx: Context = None) -> dict:
        """Ouvre un run (encadre une procédure). `doctrine` = slug si on exécute une doctrine nommée."""
        return await stack.run_start(ctx, label, doctrine)

    async def run_finish(run_id: str, outcome: str, note: Optional[str] = None, ctx: Context = None) -> dict:
        """Ferme un run. outcome ∈ done|abandoned|failed|blocked."""
        return await stack.run_finish(ctx, run_id, outcome, note)

    mcp.tool(name="run_start")(run_start)
    mcp.tool(name="run_finish")(run_finish)
