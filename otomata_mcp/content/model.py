from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ContentDoc:
    """Un document de doctrine versionné. `kind` est libre (knowledge|rule|skill…),
    défini par le consommateur. Le `body` est du texte (markdown ou autre)."""

    scope: str
    kind: str
    slug: str
    body: str
    version: int = 1
    title: str = ""
    description: str = ""
    frontmatter: dict = field(default_factory=dict)
